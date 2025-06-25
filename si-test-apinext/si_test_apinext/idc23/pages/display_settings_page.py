import logging
import os
import time

from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.global_steps import GlobalSteps

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class DisplaySettingsAppPage(BasePage):

    PACKAGE_NAME = "com.bmwgroup.apinext.displaysettings"
    DISPLAY_SETTINGS_APP_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".MainActivity"

    INSTRUMENT_CLUSTER_SUBMENU_ID = Element(By.XPATH, "//*[@text='Instrument cluster']")
    DISPLAY_SUBMENU_TITLE_ID = Element(By.ID, DISPLAY_SETTINGS_APP_RESOURCE_ID_PREFIX + "statusbar_title")
    HEAD_UP_DISPLAY_SUBMENU_ID = Element(By.XPATH, "//*[@text='Head-up display']")

    KOMBI_SECOND_SPEED_ID = Element(By.ID, DISPLAY_SETTINGS_APP_RESOURCE_ID_PREFIX + "kombidisplay_secondspeed_cbx")
    KOMBI_SECOND_SPEED_TOGGLE_ID = Element(By.ID, DISPLAY_SETTINGS_APP_RESOURCE_ID_PREFIX + "item_toggle_container")

    @classmethod
    @utils.gather_info_on_fail
    def enter_ic_submenu(cls):
        """
        Try to enter Instrument Cluster submenu is option available
        """
        ic_button = cls.driver.find_elements(*cls.INSTRUMENT_CLUSTER_SUBMENU_ID)
        if ic_button:
            ic_submenu_title = GlobalSteps.click_button_and_expect_elem(
                cls.wb, ic_button[0], cls.DISPLAY_SUBMENU_TITLE_ID, sleep_time=2
            )
            logger.debug(f"The Instrument cluster submenu text is {ic_submenu_title.text}")
            assert ic_submenu_title.text == "DISPLAYS", "Not able to select and enter the Instrument Cluster submenu"
        else:
            logger.debug("Didn't find Instrument Cluster submenu option")

    @classmethod
    @utils.gather_info_on_fail
    def get_second_speed_status(cls):
        """
        Get second speed setting status

        :return: tuple with (availability of setting, status of setting)
        availability - True if setting available, False is setting not available
        status - "selected" if setting activated, "not selected" if not activated, None if status not available
        :rtype: tuple(bool, string)
        """

        screenshot_name = "second_speed_status_screenshot.png"
        screenshot_path = os.path.join(cls.results_dir, screenshot_name)
        cls.enter_ic_submenu()
        time.sleep(1)
        # Try to swipe 3 times to find second speed setting
        for x in range(3):
            second_speed_element = cls.driver.find_elements(*cls.KOMBI_SECOND_SPEED_ID)
            if second_speed_element:
                assert len(second_speed_element) == 1, "Unexpectedly found more than one second speed element"
                second_speed_toggle = second_speed_element[0].find_element(*cls.KOMBI_SECOND_SPEED_TOGGLE_ID)
                cls.apinext_target.take_screenshot(screenshot_path)
                selected_status = "selected" if second_speed_toggle[0].get_attribute("selected") else "not selected"
                logger.debug(f"Got second speed status: {selected_status}")
                return second_speed_element, selected_status
            cls.driver.swipe(733, 680, 733, 220)
        cls.apinext_target.take_screenshot(screenshot_path)
        return False, None

    @classmethod
    @utils.gather_info_on_fail
    def set_ic_second_speed(cls, sec_speed="disable"):
        """
        Try to enable/disable the converted speed option for IC

        :param sec_speed: action for converted speed setting, defaults to "disable"
        :type sec_speed: str, optional
        :raises AssertionError: if not given a valid option: ["enable", "disable"]
        """
        valid_values = ["enable", "disable"]
        if sec_speed not in valid_values:
            raise AssertionError(f"Given value '{sec_speed}' is not valid, valid values are: '{str(valid_values)}'")

        # Start Display Settings App
        cls.start_activity(validate_activity=False)
        (sec_speed_element, sec_speed_selected) = cls.get_second_speed_status()

        if sec_speed_element:
            if (sec_speed_selected == "selected" and sec_speed == "enable") or (
                sec_speed_selected == "not selected" and sec_speed == "disable"
            ):
                return
            else:
                sec_speed_element.click()
        else:
            logger.debug("Not able to find 'Converted speed' option on Displays APP")
