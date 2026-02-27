from usr.libs import Application
from usr.components import (
    led_manager,
    net_manager,
    power_manager,
    audio_manager,
    qth_client,
    ai_manager,
)
from usr.configure import settings
from usr.libs.logging import getLogger


logger = getLogger(__name__)


class SetUp(object):

    def init(self):
        logger.info("init {} extension".format(type(self).__name__))
        # self.set_apn()
        self.sync_datetime()
    
    def set_apn(self):
        import dataCall
        result = dataCall.getPDPContext(1)
        if result != -1 and result[1] == "orange.m2m.spec":
            logger.info("read apn: {}".format(repr(result[1])))
            return
        result = dataCall.setPDPContext(1, 0, "orange.m2m.spec", "", "", 0)
        logger.info("apn set to: {}, result: {}".format(repr("orange.m2m.spec"), result))

    def sync_datetime(self):
        # 同步时间
        import ntptime, utime
        result = ntptime.settime(timezone=utime.getTimeZone())
        logger.info("ntp set time result: {}".format(result))


def create_application(name="ChatGPT", version=settings.get_version()):
    app = Application(name, version=version)

    app.register("led_manager", led_manager)
    app.register("power_manager", power_manager)
    app.register("net_manager", net_manager)
    app.register("setup", SetUp())
    app.register("audio_manager", audio_manager)
    app.register("qth_client", qth_client)
    app.register("ai_manager", ai_manager)

    return app


if __name__ == "__main__":
    app = create_application()
    app.run()
