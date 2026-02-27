import gc
import utime
import request
import audio
import G711
from machine import ExtInt,Pin
from usr.libs import current_app
from usr.libs.threading import Thread, Lock
from usr.libs.logging import getLogger
from usr.configure import settings


logger = getLogger(__name__)


RECORD_TIME_MS = 200


class AudioManager(object):

    def __init__(self,):
        self.pcm = None
        self.g711 = None
        self.aud = audio.Audio(0)  # 初始化音频播放通道
        # self.aud.set_pa(29)
        # self.aud.set_open_pa_delay(10)
        self.aud.setVolume(settings.get("audio_volume"))  # 设置音量
        self.rec = audio.Record(0)
        self.rec.ovkws_set_callback(self.kws_cb)
        self.__kws_thread = None
        self.__kws_stop_flag = False
        # 音量按键
        self.vol_plus = ExtInt(ExtInt.GPIO31, ExtInt.IRQ_FALLING, ExtInt.PULL_PU, self.__set_audio_volume, 50)
        self.vol_sub = ExtInt(ExtInt.GPIO20, ExtInt.IRQ_FALLING, ExtInt.PULL_PU, self.__set_audio_volume, 50)
        self.vol_plus.enable()
        self.vol_sub.enable()
        # 音乐播放
        self.__stop_flag = False
        self.t = None
        self.lock = Lock()
        self.chunk=b""
        self.music_flag = False

    def init(self):
        logger.info("init {} extension".format(type(self).__name__))

    def play_music(self, url):
        # https://uat-ai-media.iotomp.com/hls/music/maibaoge.mp3
        # https://uat-ai-media.iotomp.com/hls/music/liangzhilaohu.mp3
        # url = "https://uat-ai-media.iotomp.com/hls/music/liangzhilaohu.mp3"
        url1="https://euai-media.acceleronix.io/hls/music/ThroughThickandThin.mp3"
        url2="https://euai-media.acceleronix.io/hls/music/jp04.mp3"
        self.__stop_flag = False
        self.chunk=b""
        def inner(url):
            self.music_flag = True
            logger.debug("play audio data start")
            if url == url1 or url ==url2:
                resp = request.get(url,stream=True)
                print("play")
                chunk_size = 1024
                while True:
                    self.chunk = resp.raw.read(chunk_size)
                    if not self.chunk or self.__stop_flag:
                        resp.close()
                        self.music_flag = False
                        break
                    self.aud.playStream(3, self.chunk)   
                    utime.sleep_ms(5)
            else:
                resp = request.get(url,stream=True)
                print("play other music")
                for data in resp.content:
                    if self.__stop_flag:
                        resp.close()
                        self.music_flag = False
                        break
                    self.aud.playStream(3, data.encode())
                    utime.sleep_ms(5)
            self.aud.stopPlayStream()
            logger.debug("play audio data stop")
        self.t = Thread(target=inner, args=(url, ))
        if not self.music_flag:
            print("flag is true")   
            self.t.start()

    def stop_music(self):
        self.__stop_flag = True
    
    def is_playing(self):
        return (self.t is not None and self.t.is_running())

    def init_g711(self):
        with self.lock:
            self.pcm = audio.Audio.PCM(0, audio.Audio.PCM.MONO, 8000, audio.Audio.PCM.WRITEREAD, audio.Audio.PCM.BLOCK, 25)
            self.g711 = G711(self.pcm)
    
    def deinit_g711(self):
        with self.lock:
            if self.g711 is not None:
                del self.g711
                self.g711 = None
            if self.pcm is not None:
                self.pcm.close()
                del self.pcm
                self.pcm = None
            gc.collect()

    def g711_read(self):
        with self.lock:
            return self.g711.read(0, 5)
    
    def g711_write(self, data):
        with self.lock:
            return self.g711.write(data, 0)

    def stop_kws(self):
        logger.debug("stop kws...")
        self.rec.ovkws_stop()
        self.rec.stream_stop()

    def start_kws(self):
        logger.debug("start kws...")
        value = settings.get("WAKEUP_KEYWORD")
        logger.debug("wakeup keywords: {}".format(value))
        self.rec.stream_start(2, 16000, 0)
        self.rec.ovkws_start(value, 0.7)
    
    def kws_cb(self, state):
        logger.info("on_keyword_spotting: {}".format(state))
        if state[0] == 1 and state[1] == 0:
            # 唤醒词触发
            current_app.ai_manager.on_wakeup_key_click(args=None)
        else:
            pass

    def __set_audio_volume(self, args):
        v = self.aud.getVolume() + (1 if args[0] == 31 else -1)
        v = 10 if v > 10 else 1 if v < 1 else v
        self.set_volume(v)

    def set_volume(self, level):
        logger.debug("set audio volume: {}".format(level))
        self.aud.setVolume(level)
        print("当前音量: %d" % level)
        settings.set("audio_volume", level).save()
