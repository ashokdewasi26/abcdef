import logging
import time

# from mtee_apinext.enablers.support.android_generic_hid_mapping import AndroidGenericKeyCodes
from mtee_apinext.targets.android_generic import AndroidTarget

logger = logging.getLogger(__name__)

# temporary while https://cc-github.bmwgroup.net/apinext/mtee-apinext/pull/258 isn't on traas master executor version
KEYCODE_DPAD_UP = 19
KEYCODE_DPAD_DOWN = 20
KEYCODE_DPAD_LEFT = 21
KEYCODE_DPAD_RIGHT = 22
KEYCODE_DPAD_CENTER = 23
KEYCODE_ENTER = 66
KEYCODE_HOME = 3
KEYCODE_POWER = 26
KEYCODE_WAKEUP = 224
KEYCODE_MENU = 82


class RealPhoneTarget(AndroidTarget):
    """This class is meant to be used by any real hardware Android phone

    TODO Currently the methods implemented are specific to the only phone present on a test
     rack (Pixel 5 with a specific password)
    To re-use this class it might be required to overwrite some methods or not use them at all
    """

    def __init__(
        self,
        adb,
        android_home,
        atest,
        serial_number,
        tradefed_sh=None,
        _capture_adb_logcat=True,
        _clear_logcat_buffers=False,
    ):
        super(RealPhoneTarget, self).__init__(
            adb=adb,
            android_home=android_home,
            atest=atest,
            serial_number=serial_number,
            tradefed_sh=tradefed_sh,
            _capture_adb_logcat=_capture_adb_logcat,
            _clear_logcat_buffers=_clear_logcat_buffers,
        )

    def swipe_up(self):
        """Swipe up method

        Coordinates specific to pixel 5
        """
        self.execute_adb_command(["shell", "input", "touchscreen", "swipe", "930", "880", "930", "380"])

    def swipe_down(self):
        """Swipe down method

        Coordinates specific to pixel 5
        """
        self.execute_adb_command(["shell", "input", "touchscreen", "swipe", "930", "010", "930", "880"])

    def unlock_screen(self):
        """Unblock method

        Password specific to pixel 5
        """
        self.send_keycode(KEYCODE_WAKEUP)
        time.sleep(0.5)
        self.send_keycode(KEYCODE_POWER)
        time.sleep(0.5)
        self.send_keycode(KEYCODE_WAKEUP)
        time.sleep(0.5)
        self.send_keycode(KEYCODE_MENU)
        time.sleep(0.5)
        self.execute_adb_command(["shell", "input", "text", "123654"])
        self.send_keycode(KEYCODE_ENTER)
        time.sleep(0.5)

    def lock_screen(self):
        """Block screen by pressing power"""
        self.send_keycode(KEYCODE_POWER)
        time.sleep(0.5)

    def press_home(self):
        """Go home by pressing home"""
        self.send_keycode(KEYCODE_HOME)
        time.sleep(0.5)

    def alternative_turn_on_bt_w_reboot(self):
        """Alternative method to turn on bluetooth (includes reboot)"""
        self.execute_command(["settings", "put", "global", "bluetooth_on", "1"])
        self.restart_android(wait_for_boot_completion=True)

    def bring_up_activity(self, activity):
        """Call start activity-single-top on the target to bring it to the foreground"""
        self.execute_command(cmd=["am", "start", f"--activity-single-top {activity}"])
        time.sleep(0.5)
