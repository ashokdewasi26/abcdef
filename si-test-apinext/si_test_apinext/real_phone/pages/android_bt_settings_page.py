import time

from si_test_apinext.common.pages.base_page import BasePage


class AndroidBTSettings(BasePage):
    PACKAGE_NAME = "android.settings.BLUETOOTH_SETTINGS"
    ANDROID_SETTINGS_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ""

    @classmethod
    def start_action(cls):
        """Call start action on the target

        This is different from BasePage.start_activity because:

        -n Specify the component name with package name prefix to create an explicit intent
        -a Specify the intent action
        see: https://developer.android.com/tools/adb#IntentSpec
        """
        cls.apinext_target.execute_adb_command(["shell", f"am start -a {cls.PACKAGE_NAME}"])
        time.sleep(1)
