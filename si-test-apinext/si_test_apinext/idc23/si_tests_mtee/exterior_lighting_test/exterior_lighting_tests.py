# Copyright (C) 2022. BMW Car IT. All rights reserved.
import glob
import logging
import os
import time
from unittest import skipIf

import si_test_apinext.util.driver_utils as utils
from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.idc23 import EXTERIOR_LIGHT_REF_IMG_PATH, HMI_BUTTONS_REF_IMG_PATH
from si_test_apinext.idc23.pages.exterior_lighting_page import ExteriorLightPage as Elp
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.settings_app_page import SettingsAppPage as Settings
from si_test_apinext.testing.test_base import TestBase
from si_test_apinext.util.hmi_helper import HMIhelper
from si_test_apinext.util.screenshot_utils import capture_screenshot, match_template
from si_test_apinext.util.mtee_utils import MteeUtils

logger = logging.getLogger(__name__)
target = TargetShare().target


class TestExteriorLights:
    hmi_buttons_ref_img_path = HMI_BUTTONS_REF_IMG_PATH
    exterior_light_ref_img_path = EXTERIOR_LIGHT_REF_IMG_PATH

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.mtee_util = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        cls.hmihelper = HMIhelper(cls.test, cls.hmi_buttons_ref_img_path)
        Settings.language_change(language_name="English (UK)")
        cls.home_light_coords_option, cls.swipe_to_end_option = (
            (Elp.home_light_coords_pu2403, Elp.swipe_to_end_pu2403)
            if cls.test.branch_name == "pu2403"
            else (Elp.home_light_coords, Elp.swipe_to_end)
        )
        utils.start_recording(cls.test)
        Launcher.go_to_home()
        Elp.start_activity(validate_activity=False)
        utils.ensure_no_alert_popup(cls.test.results_dir, cls.test.driver, cls.test.apinext_target)
        additional_button = cls.test.wb.until(
            ec.visibility_of_element_located(Elp.ADDITIONAL_SETTINGS),
            message=f"Unable to find {Elp.ADDITIONAL_SETTINGS.selector} element on All Apps search",
        )
        additional_button.click()

    @classmethod
    def teardown_class(cls):
        Launcher.go_to_home()
        utils.stop_recording(cls.test, "TestExteriorLights")
        cls.test.quit_driver()

    @utils.gather_info_on_fail
    def setup(self):
        utils.ensure_no_alert_popup(self.test.results_dir, self.test.driver, self.test.apinext_target)

    @utils.gather_info_on_fail
    def test_01_toggle_one_touch_indicator(self):
        """
        Toggle selected radio button of one touch indicator option

        Steps:
        1. Go to Exterior lighting app.
        2. Select Additional settings sub menu.
        3. Find current value of one touch indicator option.
        4. Click on one touch indicator option.
        5. Select a different option from the radio buttons.
        6. Validate the previous value and current value is different.

        Traceability: ABPI-178256
        """
        capture_screenshot(test=self.test, test_name="test_01_toggle_one_touch_indicator_start")
        onetouch_option = self.test.driver.find_element(*Elp.ONE_TOUCH_INDICATOR)
        current_value = self.test.driver.find_element(*Elp.TOUCH_INDICATOR).get_attribute("text")
        self.hmihelper.click_and_capture(onetouch_option, "test_01_toggle_one_touch_indicator_click")
        buttons = self.test.driver.find_elements(*Elp.TOUCH_INDICATOR)
        for button in buttons:
            if button.get_attribute("text") != current_value:
                self.hmihelper.click_and_capture(button, "test_01_toggle_one_touch_indicator_end")
                break
        new_value = self.test.driver.find_element(*Elp.TOUCH_INDICATOR).get_attribute("text")
        popup = self.test.driver.find_elements(*Elp.POPUP_ID)
        if popup:
            self.test.apinext_target.send_tap_event(*Elp.tap_out)
        assert current_value != new_value, f"unable to switch one touch indicator value from {current_value}"

    @utils.gather_info_on_fail
    def test_03_toggle_rear_daytime_driving_lights(self):
        """
        Toggle status of Rear daytime driving lights option

        Steps:
        1. Go to Exterior lighting app.
        2. Select Additional settings sub menu.
        3. Capture snapshot & find current button status of Rear daytime driving lights option using match template.
        4. Click on Rear daytime driving lights option.
        5. Capture snapshot & validate the button status of Rear daytime driving lights is toggled.

        Traceability: ABPI-178256
        """
        capture_screenshot(test=self.test, test_name="test_03_Toggle_Rear_daytime_driving_lights_start")
        rear_option = self.test.driver.find_element(*Elp.REAR_LIGHTS)
        button = rear_option.find_element(*Elp.TOGGLE_BUTTON)
        # Finding current button status
        status = self.hmihelper.find_current_button_status(
            button, "test_03_SubMenu_Additional_Settings_initial", image_pattern="button_*.png"
        )
        logger.debug(f"Button status of test_01_initial {status}")
        self.hmihelper.click_and_validate_button_status(
            button, status, "test_03_Toggle_Rear_daytime_driving_final_state"
        )

    @utils.gather_info_on_fail
    def test_04_toggle_welcome_and_goodbye(self):
        """
        Toggle status of welcome and goodbye option

        Steps:
        1. Go to Exterior lighting app.
        2. Select Additional settings sub menu.
        3. Capture snapshot & find current button status of welcome and goodbye option using match template.
        4. Click on welcome and goodbye option.
        5. Capture snapshot & validate the button status of welcome and goodbye is toggled.

        Traceability: ABPI-178256
        """
        self.test.driver.swipe(*self.swipe_to_end_option, duration=1000)
        capture_screenshot(test=self.test, test_name="test_04_toggle_welcome_and_goodbye_start")
        welcome_option = self.test.driver.find_element(*Elp.WELCOME_LIGHT)
        button = welcome_option.find_element(*Elp.TOGGLE_BUTTON)
        # Finding current button status
        status = self.hmihelper.find_current_button_status(
            button, "test_04_SubMenu_Additional_Settings_initial", image_pattern="button_*.png"
        )
        logger.debug(f"Button status of test_02_initial: {status}")
        self.hmihelper.click_and_validate_button_status(
            button, status, "test_04_toggle_welcome_and_goodbye_final_state"
        )

    @skipIf(target.has_capability(TEST_ENVIRONMENT.test_bench.farm), "Cannot toggle option on test farm workers.")
    @utils.gather_info_on_fail
    def test_05_change_home_lights(self):
        """
        Check Home lights option slider value can be set to min, 50% and max.

        Steps:
        1. Go to Exterior lighting app.
        2. Select Additional settings sub menu.
        3. Go to Home lights option.
        4. Set the slider to min, 50% and max.
        5. Capture snapshot for each position and validate slider is changed with reference image.

        Traceability: ABPI-178256
        """
        additional_button = self.test.driver.find_element(*Elp.ADDITIONAL_SETTINGS)
        additional_button.click()
        self.test.driver.swipe(*Elp.swipe_to_end, duration=1000)
        capture_screenshot(test=self.test, test_name="test_05_change_home_lights_start")
        homelight_option = self.test.driver.find_element(*Elp.FOLLOW_HOME_DURATION)
        elem_bounds = utils.get_elem_bounds_detail(homelight_option, crop_region=True)
        self.hmihelper.click_and_capture(homelight_option, "test_05_change_home_lights")

        for each_pos in self.home_light_coords_option.keys():
            for _ in range(self.home_light_coords_option[each_pos]["steps"]):
                self.test.apinext_target.send_tap_event(*self.home_light_coords_option[each_pos]["coords"])
                time.sleep(0.5)
            time.sleep(1)
            screenshot = capture_screenshot(test=self.test, test_name=f"test_05_home_light_{each_pos}")
            files_data = glob.glob(os.path.join(self.exterior_light_ref_img_path, f"{each_pos}*.png"))
            logger.debug(f"Reference images: {files_data}")
            comparison_results = []
            for file_path in files_data:
                result, error = match_template(
                    screenshot, file_path, elem_bounds, self.test.results_dir, acceptable_diff=3.0
                )
                comparison_results.append(result)
                if result:
                    break
            assert any(comparison_results), (
                f"Error on checking {each_pos} position. "
                f"Reference {files_data} templates cannot be found on actual image {screenshot}"
            )
