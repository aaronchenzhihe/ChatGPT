from machine import Pin
from usr.libs.led import Led
from usr.libs.logging import getLogger
import utime

logger = getLogger(__name__)


class LedManager(object):

    def __init__(self) -> None:
        # 初始化 led; write(1) 灭； write(0) 亮
        self.wifi_red_led = Led(33)  #WIFI 指示灯1亮0灭
        self.wifi_green_led = Led(32)  # WIFI 指示灯1亮0灭
        self.power_red_led = Led(39)
        self.power_green_led = Led(38)  # 电量指示灯
        self.lte_red_led = Led(10) #1亮0灭
        self.lte_green_led = Led(11)  # LTE 网络指示灯
        self.wifi_green_led.on()
        self.wifi_red_led.on()
        self.lte_red_led.on()
        self.led_power_pin = Pin(Pin.GPIO30, Pin.OUT, Pin.PULL_DISABLE, 0)
    
    def init(self):
        logger.info("init {} extension".format(type(self).__name__))
        self.enable_led()
    
    def enable_led(self):
        return self.led_power_pin.write(1)

    def disable_led(self):
        return self.led_power_pin.write(0)

    def disable_all(self):
        self.wifi_red_led.on()
        self.wifi_green_led.on()  # WIFI 指示灯
        # self.power_red_led.off()
        # self.power_green_led.off()  # 电量指示灯
        self.lte_red_led.on()
        self.lte_green_led.off()  # LTE 网络指示灯
        self.disable_led()
