import time

from mtee_apinext.enablers.support.android_generic_hid_mapping import AndroidGenericKeyCodes
from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage


class CarhubPage(BasePage):

    COMMON_NAME = "Carhub"
    PACKAGE_NAME = "com.bmwgroup.apinext.livevehicle"
    CARHUB_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".carhub.CarHubActivity"

    MAXIMUM_THRESHOLD_BOOT_TIME = 3000

    @classmethod
    def start_activity(cls, cmd=""):
        """Start the activity"""
        # CarHub is only detected in the dumpsy command when it's run in the All apps page
        cls.apinext_target.send_keycode(AndroidGenericKeyCodes.KEYCODE_BACK)
        time.sleep(1)
        cmd = cmd if cmd else f"am start -a android.intent.action.MAIN -n {cls.get_activity_name()}"
        return_stdout = cls.apinext_target.execute_command(cmd)
        return return_stdout

    @classmethod
    def get_command_cold_start(cls):
        """Return the command to cold start the activity"""
        return "am start -a android.intent.action.MAIN -W -S -n {}".format(cls.get_activity_name())

    @classmethod
    def get_command_warm_hot_start(cls):
        """Return the command to warm/hot start the activity"""
        return "am start -a android.intent.action.MAIN -W -n {}".format(cls.get_activity_name())
