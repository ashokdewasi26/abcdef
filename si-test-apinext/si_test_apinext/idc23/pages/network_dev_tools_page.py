import time

import si_test_apinext.util.driver_utils as utils
from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element
from si_test_apinext.idc23.pages.android_permissions_page import AndroidPermissionsPage


class NetworkDevToolsPage(BasePage):
    PACKAGE_NAME = "com.bmwgroup.apinext.networkdevtool"
    NETWORK_DEV_TOOL_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".ui.MainActivity"

    CONNECTION_INFO_TEXT = Element(By.ID, NETWORK_DEV_TOOL_ID_PREFIX + "connection_info_text")
    SIDE_NAVIGATION_VIEW = Element(By.ID, NETWORK_DEV_TOOL_ID_PREFIX + "side_navigation_view")

    WAVE = Element(By.XPATH, "//*[contains(@text, 'Wave')]")

    @classmethod
    def validate_wave_status_connected(cls):
        """Open networkdevtool app and check wave status

        :raises AssertionError: In case the wave shows disconnected status
        :return: True if wave shows "Connected" status
        :rtype: bool
        """
        cls.start_activity(validate_activity=False)
        time.sleep(1)
        AndroidPermissionsPage.click_allow_while_using_app()
        # Go to Wave submenu
        side_bar = cls.check_visibility_of_element(cls.SIDE_NAVIGATION_VIEW)
        wave_side_option = side_bar.find_element(*cls.WAVE)
        wave_side_option.click()
        wave_status = cls.check_visibility_of_element(cls.CONNECTION_INFO_TEXT)
        if wave_status.text == "Connected":
            utils.take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, "wave_CONNECTED")
            return True
        else:
            raise AssertionError("Wave not connected as expected")
