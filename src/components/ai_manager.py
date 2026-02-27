import gc
import utime
import base64
from misc import PowerKey, Power
from machine import ExtInt
from usr.libs import current_app
from usr.libs.lpm import auto_sleep
from usr.libs.threading import EventSet, Thread
from usr.libs.common import Button
from usr.libs.logging import getLogger
from .protocol import OpenAIRealTimeConnection


logger = getLogger(__name__)


SESSION_CREATED_EVENT = 1 << 0


class AIManager(object):

    def __init__(self):
        # misc 的 power key，注册空回调，以防止插拔 USB 导致意外关机
        self.power_key = PowerKey()
        self.power_key.powerKeyEventRegister(self.power_cb)

        # openAI Realtime
        self.protocol = OpenAIRealTimeConnection(event_cb=self.on_openai_event)

        self.chat_thread = None
        
        # power key 黑绿按键
        self.power_down = ExtInt(ExtInt.GPIO41, ExtInt.IRQ_FALLING, ExtInt.PULL_PU, self.power_down_handle, 2000)
        #wake up key 灰黑按键
        self.wakeup_key=ExtInt(ExtInt.GPIO19, ExtInt.IRQ_RISING, ExtInt.PULL_PD, self.on_wakeup_key_click, 50)

        self.event_set = EventSet()
        self.power_down.enable()
        self.wakeup_key.enable()
        # self.wakeup_key1.enable()
        
        self.conversation_item_id = None  # 记录对话的id
        self.interrupt_flag = False
        self.stop_chat_flag = False
    
    def init(self):
        logger.info("init {} extension".format(type(self).__name__))
        self.on_wakeup_key_click(args=None)
        
    def power_cb(self):
        pass
    
    
    
    def power_down_handle(self,args):
        logger.info("power down")
        self.stop_chat()
        Power.powerDown()

    def on_wakeup_key_click(self,args):
        self.start_chat()
        current_app.audio_manager.stop_music()
        self.__cancel_response()

    def __cancel_response(self):
        if self.conversation_item_id is not None:
            try:
                self.protocol.response_cancel()
                self.protocol.conversation_item_truncate(self.conversation_item_id)
            except:
                pass
            self.conversation_item_id = None
            self.interrupt_flag = True

    def start_chat(self):
        self.stop_chat_flag = False
        if self.chat_thread is None or not self.chat_thread.is_running():
            self.chat_thread = Thread(target=self.chat_process)
            self.chat_thread.start(stack_size=128)

    def stop_chat(self):
        self.stop_chat_flag = True
        if self.chat_thread and self.chat_thread.is_running():
            self.chat_thread.join()

    def chat_process(self):
        logger.debug("chat_process thread enter")
        try:
            auto_sleep(False)
            # current_app.led_manager.wifi_green_led.blink(50, 50)
            current_app.audio_manager.stop_kws()
            current_app.audio_manager.init_g711()
            with self.protocol:
                if not self.event_set.wait(SESSION_CREATED_EVENT, timeout=10, clear=True):
                    logger.debug("protocol connect failed, get no SESSION_CREATED_EVENT after 10 seconds.")
                    return
                logger.debug("protocol connect successed")
                while not self.stop_chat_flag:
                    if not self.protocol.is_state_ok():
                        print("protocol state error")
                        break
                    buf = current_app.audio_manager.g711_read()
                    current_app.ai_manager.protocol.input_audio_buffer_append(buf)
                    utime.sleep_ms(10)
        except Exception as e:
            logger.debug("chat process got {}".format(repr(e)))
        finally:
            logger.debug("chat process thread break out")
            current_app.audio_manager.deinit_g711()
            current_app.audio_manager.start_kws()
            # current_app.led_manager.wifi_green_led.blink(250, 250)
            auto_sleep(True)
        logger.debug("chat_process thread exit")

    def on_openai_event(self, event):
        try:
            if "type" in event:
                event_type = event["type"].replace(".", "_")
                getattr(self, "{}".format(event_type))(event)
            else:
                logger.warn("open ai event got no type keyword: {}".format(event))
        except Exception as e:
            logger.error("{} on_openai_event got: {}".format(type(self).__name__, repr(e)))

    def error(self, event):
        logger.error("error: \n{}".format(event))

    def session_created(self, event):
        logger.debug("session_created: \n{}".format(event))
        self.event_set.set(SESSION_CREATED_EVENT)
    
    def session_updated(self, event):
        logger.debug("session_updated: \n{}".format(event))
    
    def transcription_session_created(self, event):
        logger.debug("transcription_session_created: \n{}".format(event))

    def transcription_session_updated(self, event):
        logger.debug("transcription_session_updated: \n{}".format(event))

    def conversation_item_created(self, event):
        logger.debug("conversation_item_created: \n{}".format(event))
        self.conversation_item_id = event["item"]["id"]

    def conversation_item_retrieved(self, event):
        logger.debug("conversation_item_retrieved: \n{}".format(event))

    def conversation_item_input_audio_transcription_completed(self, event):
        logger.debug("conversation_item_input_audio_transcription_completed: \n{}".format(event))

    def conversation_item_input_audio_transcription_delta(self, event):
        logger.debug("conversation_item_input_audio_transcription_delta: \n{}".format(event))
    
    def conversation_item_input_audio_transcription_segment(self, event):
        logger.debug("conversation_item_input_audio_transcription_segment: \n{}".format(event))
    
    def conversation_item_input_audio_transcription_failed(self, event):
        logger.debug("conversation_item_input_audio_transcription_failed: \n{}".format(event))

    def conversation_item_truncated(self, event):
        logger.debug("ncoversation_item_truncated: \n{}".format(event))
        self.interrupt_flag = False
    
    def conversation_item_deleted(self, event):
        logger.debug("conversation_item_deleted: \n{}".format(event))
    
    def input_audio_buffer_committed(self, event):
        logger.debug("input_audio_buffer_committed: \n{}".format(event))
    
    def input_audio_buffer_cleared(self, event):
        logger.debug("input_audio_buffer_cleared: \n{}".format(event))
    
    def input_audio_buffer_speech_started(self, event):
        logger.debug("input_audio_buffer_speech_started: \n{}".format(event))
        current_app.led_manager.wifi_red_led.blink(50, 50)
        current_app.audio_manager.stop_music()
        current_app.led_manager.wifi_green_led.on()
        self.interrupt_flag = False

    def input_audio_buffer_speech_stopped(self, event):
        logger.debug("input_audio_buffer_speech_stopped: \n{}".format(event))
        current_app.led_manager.wifi_red_led.on()

    def input_audio_buffer_speech_committed(self, event):
        logger.debug("input_audio_buffer_speech_committed: \n{}".format(event))
    
    def input_audio_buffer_timeout_triggered(self, event):
        logger.debug("input_audio_buffer_timeout_triggered: \n{}".format(event))

    def response_created(self, event):
        logger.debug("response_created: \n{}".format(event))

    def response_done(self, event):
        logger.debug("response_done: \n{}".format(event))
        current_app.led_manager.wifi_green_led.on()
        gc.collect()

    def response_output_item_added(self, event):
        logger.debug("response_output_item_added: \n{}".format(event))
    
    def response_output_item_done(self, event):
        logger.debug("response_output_item_done: \n{}".format(event))

    def response_content_part_added(self, event):
        logger.debug("response_content_part_added: \n{}".format(event))

    def response_content_part_done(self, event):
        logger.debug("response_content_part_done: \n{}".format(event))

    def response_output_text_delta(self, event):
        logger.debug("response_output_text_delta: \n{}".format(event))

    def response_output_text_done(self, event):
        logger.debug("response_output_text_done: \n{}".format(event))

    def response_output_audio_transcript_delta(self, event):
        logger.debug("response_output_audio_transcript_delta: \n{}".format(event))

    def response_output_audio_transcript_done(self, event):
        logger.debug("response_output_audio_transcript_done: \n{}".format(event))

    def response_output_audio_delta(self, event):
        logger.debug("response_output_audio_delta: \n{}".format(event))

    def response_output_audio_done(self, event):
        logger.debug("response_output_audio_done: \n{}".format(event))
    
    def response_function_call_arguments_delta(self, event):
        logger.debug("response_function_call_arguments_delta: \n{}".format(event))
    
    def response_function_call_arguments_done(self, event):
        logger.debug("response_function_call_arguments_done: \n{}".format(event))
    
    def response_mcp_call_arguments_delta(self, event):
        logger.debug("response_mcp_call_arguments_delta: \n{}".format(event))
    
    def esponse_mcp_call_arguments_done(self, event):
        logger.debug("esponse_mcp_call_arguments_done: \n{}".format(event))

    def response_mcp_call_in_progress(self, event):
        logger.debug("response_mcp_call_in_progress: \n{}".format(event))
    
    def response_mcp_call_completed(self, event):
        logger.debug("response_mcp_call_completed: \n{}".format(event))
    
    def response_mcp_call_failed(self, event):
        logger.debug("response_mcp_call_failed: \n{}".format(event))
    
    def mcp_list_tools_in_progress(self, event):
        logger.debug("mcp_list_tools_in_progress: \n{}".format(event))
    
    def mcp_list_tools_completed(self, event):
        logger.debug("mcp_list_tools_completed: \n{}".format(event))
    
    def mcp_list_tools_failed(self, event):
        logger.debug("mcp_list_tools_failed: \n{}".format(event))
    
    def rate_limits_updated(self, event):
        logger.debug("rate_limits_updated: \n{}".format(event))

    def response_cancelled(self, event):
        logger.debug("response_cancelled: \n{}".format(event))

    def response_text_delta(self, event):
        logger.debug("response_text_delta: \n{}".format(event))

    def response_audio_transcript_delta(self, event):
        logger.debug("response_audio_transcript_delta: \n{}".format(event))
    
    def response_audio_transcript_done(self, event):
        logger.debug("response_audio_transcript_done: \n{}".format(event))
        current_app.led_manager.wifi_green_led.blink(250,250)
    
    def response_audio_delta(self, event):
        if self.interrupt_flag or current_app.audio_manager.is_playing():
            return
        data = base64.b64decode(event["delta"])
        current_app.audio_manager.g711_write(data)

    def response_audio_done(self, event):
        logger.debug("response_audio_done: \n{}".format(event))
