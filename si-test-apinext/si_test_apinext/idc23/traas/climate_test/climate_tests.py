# Copyright (C) 2022. BMW Car IT. All rights reserved.
import logging
import os
import time

import si_test_apinext.util.driver_utils as utils
from si_test_apinext.idc23 import CLIMATE_REF_IMG_PATH
from si_test_apinext.idc23.pages.climate_page import ClimatePage as Climate
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.testing.test_base import TestBase
from si_test_apinext.util.global_steps import GlobalSteps
from si_test_apinext.util.mtee_utils import MteeUtils
from si_test_apinext.util.screenshot_utils import (
    capture_screenshot,
    check_screendump,
    compare_captured_image_with_multiple_snapshots,
)

logger = logging.getLogger(__name__)

AUTO_ON_DATA = [("auto_button_on", True)]
AUTO_BLOWER_DATA = ["VERY LOW", "LOW", "MEDIUM", "HIGH", "VERY HIGH"]
AUTO_OFF_DATA = [("auto_button_off", False)]
MINUS_LAYOUT_DATA = [Climate.TEMP_MINUS_BUTTON, Climate.OVERLAY_TIME_MINUS_BUTTON]
PLUS_LAYOUT_DATA = [Climate.TEMP_PLUS_BUTTON, Climate.OVERLAY_TIME_PLUS_BUTTON]
MODE_TEXT_DATA = [Climate.OVERLAY_MODE_TEXT, Climate.MODE_TEXT]
TEMP_VALUE_DATA = [Climate.TEMP_VALUE, Climate.OVERLAY_TEMP_VALUE]
AIR_FLOW_DATA = [
    ("air_flow_recirculate", Climate.AIR_RECIRCULATION_MODE),
    ("air_flow_auto", Climate.AUTO_AIR_RECIRCULATION_MODE),
    ("air_flow_fresh", Climate.FRESH_AIR_MODE),
]
AC_DATA = [
    ("ac_button_on", True),
    ("ac_button_off", False),
]
SYNC_DATA = [
    ("sync_button_off", False),
    ("sync_button_on", True),
]
TEMP_CHECK = [
    (
        "left",
        0,
        {
            "LOW": (Climate.TEMP_MINUS_BUTTON, Climate.OVERLAY_TIME_MINUS_BUTTON),
            "HIGH": (Climate.TEMP_PLUS_BUTTON, Climate.OVERLAY_TIME_PLUS_BUTTON),
        },
    ),
    (
        "right",
        1,
        {
            "LOW": (Climate.TEMP_MINUS_BUTTON, Climate.OVERLAY_TIME_MINUS_BUTTON),
            "HIGH": (Climate.TEMP_PLUS_BUTTON, Climate.OVERLAY_TIME_PLUS_BUTTON),
        },
    ),
]

TEXT_CLIMATE_OFF = "CLIMATE OFF".split()
WAIT_POPUP_TO_DISAPPEAR = 8
# For Fahrenheit from max to min goes 24 degrees
# For Celsius goes 12 degrees. So with this values works for both units
MAX_TEMP_CLICK = 25


class TestClimate:
    climate_ref_img_path = CLIMATE_REF_IMG_PATH

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.mtee_util = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        cls.mapping_ids()
        utils.start_recording(cls.test)
        time.sleep(3)
        Launcher.go_to_home()
        Climate.start_activity(validate_activity=False)

    @classmethod
    def teardown_class(cls):
        Launcher.go_to_home()
        utils.stop_recording(cls.test, "Climate_test")
        cls.test.quit_driver()

    @classmethod
    def mapping_ids(cls):
        if cls.test.branch_name == "pu2403":
            cls.CLIMATE_AUTO = Climate.CLIMATE_AUTO_ID
        else:
            cls.CLIMATE_AUTO = Climate.CLIMATE_AUTO_ID_ML

    def setUp(self) -> None:
        climate_off = self.test.driver.find_elements(*Climate.CLIMATE_OFF)
        if climate_off:
            on_off_button = self.test.driver.find_element(*Climate.CLIMATE_ON_OFF)
            on_off_button.click()
        time.sleep(1)
        self.get_status_and_switch(Climate.CLIMATE_AC, True)

    def send_multiple_tap(self, coordinates, count=1, delay=0.25):
        """
        Tap on the same coordinates multiple times
        Param coordinates: x,y pixels of the screen to tap.
        Param count: Number of times to tap on the coordinates.
        Param delay: Sleep time between consecutive taps
        """
        for _ in range(count):
            self.test.apinext_target.send_tap_event(*coordinates)
            time.sleep(delay)

    def multiple_click_on_elem(self, elem, count=1, delay=0.25):
        """
        Tap on the same coordinates multiple times
        Param elem: appium element.
        Param count: Number of times to tap on the coordinates.
        Param delay: Sleep time between consecutive taps
        """
        for _ in range(count):
            elem.click()
            time.sleep(delay)

    @classmethod
    def get_status_and_switch(cls, element, switch):
        """Get current status of Climate options
        param element: Android id of climate options
        param switch: To turn ON/OFF the option. True=ON, False=OFF

        return: True/False based on button status
        """
        option_element = cls.test.driver.find_element(*element)

        # After new UI changes auto blower doesn't have an element OPT_Active
        if element == cls.CLIMATE_AUTO:
            option_status = cls.test.driver.find_elements(*Climate.AUTO_BLOWER_TEXT)
        else:
            option_status = option_element.find_elements(*Climate.CLIMATE_OPT_ACTIVE)

        if option_status and not switch:
            option_element.click()  # Turn off the option
        elif not option_status and switch:
            option_element.click()  # Turn on the option
        time.sleep(2)

    @classmethod
    def search_mode_text_in_climate_bar(cls, mode_text):
        """Get modes on the climate bar and check is there is a specific one
        param mode_text: Mode Text to search on the climate bar

        return: True/False based on mode text found or not
        """
        # Should return left and right side modes
        for climate_mode_option in MODE_TEXT_DATA:
            climate_bar_modes = cls.test.driver.find_elements(*climate_mode_option)
            if climate_bar_modes:
                climate_bar_modes_text = []
                for mode in climate_bar_modes:
                    climate_bar_modes_text.append(mode.text)

        # this change will ignore all the acsii values present in the string.
        climate_bar_modes_text = [string.encode("ascii", "ignore").decode() for string in climate_bar_modes_text]
        logger.info(f"climate mode expected: {mode_text}, got: {climate_bar_modes_text}")
        if mode_text in climate_bar_modes_text:
            return True
        return False

    @utils.gather_info_on_fail
    def test_01_on_off_climate_app(self):
        """
        Turn ON/OFF climate app

        Steps:
        1. Go to climate app
        2. Tap on the climate app on/off button.
        3. Validate app is turned off with presence of "climateMainClimateOffTextView" id
        4. Tap on the climate app on/off button.
        5. Validate app is turned on if "climateMainClimateOffTextView" id is not available

        Traceability: ABPI-178255, ABPI-207315
        """
        on_off_button = self.test.driver.find_element(*Climate.CLIMATE_ON_OFF)
        climate_status = GlobalSteps.click_button_and_expect_elem(self.test.wb, on_off_button, Climate.CLIMATE_OFF)
        capture_screenshot(test=self.test, test_name="test_01_on_off_climate_app_off")
        # Storing the text in a variable because the .text is a method that queries appium on every call
        climate_text = climate_status.text
        assert all([word in climate_text for word in TEXT_CLIMATE_OFF]), f"Unexpected test: '{climate_text}'"
        GlobalSteps.click_button_and_not_expect_elem(self.test.wb, on_off_button, Climate.CLIMATE_OFF)
        capture_screenshot(test=self.test, test_name="test_01_on_off_climate_app_on")

    @utils.gather_info_on_fail
    def test_02_on_off_ac(self):
        """
        ON OFF A/C in climate app

        Steps:
        1. Go to climate app
        2. Toggle the climate A/C button.
        3. Validate option is turned on/off with image comparison

        Traceability: ABPI-178255, ABPI-207315
        """
        capture_screenshot(test=self.test, test_name="test_02_on_off_ac_start")
        for prop, status in AC_DATA:
            logger.info("switching to: " + prop)
            self.get_status_and_switch(Climate.CLIMATE_AC, status)
            screenshot_path = capture_screenshot(test=self.test, test_name=prop)
            elem = self.test.driver.find_element(*Climate.CLIMATE_AC)
            elem_bounds = utils.get_elem_bounds_detail(elem, crop_region=True)
            ref_image_path_pattern = os.path.join(self.climate_ref_img_path, f"*{prop}*.png")
            compare_captured_image_with_multiple_snapshots(
                screenshot_path, ref_image_path_pattern, prop, fuzz_percent=10, region=elem_bounds
            )
        assert self.search_mode_text_in_climate_bar(mode_text="A/C OFF"), "Failed to validate A/C OFF on climate bar"

    @utils.gather_info_on_fail
    def test_03_on_auto(self):
        """
        ON AUTO option in climate app

        Steps:
        1. Go to climate app
        2. Turn ON climate AUTO button.
        3. Validate option is turned on with image comparison
        4. Validate fan cannot be turned off if AUTO option is ON
        5. Validate fan speeds from min to max values

        Traceability: ABPI-178255, ABPI-207315
        """
        capture_screenshot(test=self.test, test_name="test_03_on_off_auto_start")
        self.get_status_and_switch(Climate.CLIMATE_SYNC_TEMP, False)
        for prop, status in AUTO_ON_DATA:
            logger.info("switching to: " + prop)
            self.get_status_and_switch(self.CLIMATE_AUTO, status)
            screenshot_path = capture_screenshot(test=self.test, test_name=prop)
            elem = self.test.driver.find_element(*self.CLIMATE_AUTO)
            elem_bounds = utils.get_elem_bounds_detail(elem, crop_region=True)
            ref_image_path_pattern = os.path.join(self.climate_ref_img_path, f"*{prop}*.png")
            compare_captured_image_with_multiple_snapshots(
                screenshot_path, ref_image_path_pattern, prop, fuzz_percent=10, region=elem_bounds
            )
        temp_minus_button = self.test.driver.find_element(*Climate.AUTO_BLOWER_MINUS)
        self.multiple_click_on_elem(elem=temp_minus_button, count=6, delay=0.15)
        screenshot_path = capture_screenshot(test=self.test, test_name="auto_blower_popup")
        test_result, message = check_screendump(
            screenshot_path, "Fan cannot be deactivated in automatic programme.", region=Climate.fan_popup
        )
        if not test_result:
            raise AssertionError(message)

        temp_plus_button = self.test.driver.find_element(*Climate.AUTO_BLOWER_PLUS)
        for i in range(len(AUTO_BLOWER_DATA)):
            capture_screenshot(test=self.test, test_name=f"auto_blower_{i}")
            auto_blower_text = self.test.driver.find_element(*Climate.AUTO_BLOWER_TEXT).text
            assert (
                AUTO_BLOWER_DATA[i] in auto_blower_text
            ), f"Expected text to be {AUTO_BLOWER_DATA[i]}, instead found: {auto_blower_text}"
            temp_plus_button.click()

    @utils.gather_info_on_fail
    def test_04_off_auto(self):
        """
        OFF AUTO option in climate app

        Steps:
        1. Go to climate app
        2. Turn OFF the climate AUTO button.
        3. Validate option is turned OFF with image comparison
        4. Validate fan speeds from min to max values

        Traceability: ABPI-178255, ABPI-207315
        """
        capture_screenshot(test=self.test, test_name="test_04_on_off_auto_start")
        self.get_status_and_switch(Climate.CLIMATE_SYNC_TEMP, False)
        for prop, status in AUTO_OFF_DATA:
            logger.info("switching to: " + prop)
            self.get_status_and_switch(self.CLIMATE_AUTO, status)
            screenshot_path = capture_screenshot(test=self.test, test_name=prop)
            elem = self.test.driver.find_element(*self.CLIMATE_AUTO)
            elem_bounds = utils.get_elem_bounds_detail(elem, crop_region=True)
            ref_image_path_pattern = os.path.join(self.climate_ref_img_path, f"*{prop}*.png")
            compare_captured_image_with_multiple_snapshots(
                screenshot_path, ref_image_path_pattern, prop, fuzz_percent=25, region=elem_bounds
            )
        assert self.search_mode_text_in_climate_bar(mode_text="AUTO OFF"), "Failed to validate AUTO OFF on climate bar"

        temp_minus_button = self.test.driver.find_element(*Climate.MANUAL_BLOWER_MINUS)
        self.multiple_click_on_elem(elem=temp_minus_button, count=6, delay=0.15)

        temp_plus_button = self.test.driver.find_element(*Climate.MANUAL_BLOWER_PLUS)
        for i in range(6):
            capture_screenshot(test=self.test, test_name=f"manual_blower_{i}")
            manual_blower_text = self.test.driver.find_element(*Climate.MANUAL_BLOWER_TEXT).text
            assert manual_blower_text == str(i), f"Expected text to be: {str(i)}, instead found: {manual_blower_text}"
            temp_plus_button.click()

    @utils.gather_info_on_fail
    def test_05_on_off_sync(self):
        """
        ON OFF sync option in climate app

        Steps:
        1. Go to climate app
        2. Toggle the climate SYNC button.
        3. Validate option is turned on/off with image comparison
        4. Validate temp on both sides are equal when sync is ON

        Traceability: ABPI-178255, ABPI-207315
        """
        capture_screenshot(test=self.test, test_name="test_05_on_off_sync_start")
        for prop, status in SYNC_DATA:
            logger.info("switching to: " + prop)
            for minus_temp in MINUS_LAYOUT_DATA:
                minus_temp_buttons = self.test.driver.find_elements(*minus_temp)
                if minus_temp_buttons:
                    minus_temp_buttons[0].click()
            for plus_temp in PLUS_LAYOUT_DATA:
                plus_temp_buttons = self.test.driver.find_elements(*plus_temp)
                if plus_temp_buttons:
                    plus_temp_buttons[0].click()
            self.get_status_and_switch(Climate.CLIMATE_SYNC_TEMP, status)
            screenshot_path = capture_screenshot(test=self.test, test_name=prop)
            elem = self.test.driver.find_element(*Climate.CLIMATE_SYNC_TEMP)
            elem_bounds = utils.get_elem_bounds_detail(elem, crop_region=True)
            ref_image_path_pattern = os.path.join(self.climate_ref_img_path, f"*{prop}*.png")
            compare_captured_image_with_multiple_snapshots(
                screenshot_path, ref_image_path_pattern, prop, fuzz_percent=5, region=elem_bounds
            )
        assert self.search_mode_text_in_climate_bar(mode_text="SYNC"), "Failed to validate SYNC on climate bar"

        # Get climate temperatures and validate they are the same
        temp_elements = self.test.driver.find_elements(*Climate.TEMP_VALUE)
        temp_values = []
        for temp in temp_elements:
            temp_values.append(temp.text)

        assert all(
            value == temp_values[0] for value in temp_values
        ), f"Failed to validate sync temperatures, they are different. Got: {temp_values}"

    @utils.gather_info_on_fail
    def test_06_toggle_airflow(self):
        """
        Toggle airflow option in climate app

        Steps:
        1. Go to climate app
        2. Toggle the climate airflow button.
        3. Validate option is changed with image comparison.

        Traceability: ABPI-178255, ABPI-207315
        """

        capture_screenshot(test=self.test, test_name="test_06_toggle_airflow_start")
        for prop, mode_tile in AIR_FLOW_DATA:
            airflow__button = self.test.driver.find_element(*Climate.CLIMATE_AIR_FLOW)
            elem = GlobalSteps.click_button_and_expect_elem(self.test.wb, airflow__button, mode_tile)
            elem.click()
            time.sleep(1)
            screenshot_path = capture_screenshot(test=self.test, test_name=f"test_06_toggle_airflow_{prop}")
            elem = self.test.driver.find_element(*Climate.CLIMATE_AIR_FLOW)
            elem_bounds = utils.get_elem_bounds_detail(elem, crop_region=True)
            ref_image_path_pattern = os.path.join(self.climate_ref_img_path, f"*{prop}*.png")
            compare_captured_image_with_multiple_snapshots(
                screenshot_path, ref_image_path_pattern, prop, fuzz_percent=25, region=elem_bounds
            )

    def test_07_check_min_max_temp(self):
        """
        Check the Min and Max temp in climate app

        Steps:
        1. Go to climate app
        2. Turn off SYNC option
        3. Decrease/Increase the temp in left side to min/max.
        4. Validate temp is min/max extracting the value from elem.
        5. Repeat step 3 and 4 for the right side

        Traceability: ABPI-178255, ABPI-207315
        """
        Climate.open_climate()
        capture_screenshot(test=self.test, test_name="test_07_check_min_max_temp_start")
        for side, region, reference_data in TEMP_CHECK:
            for expected_value, elem in reference_data.items():
                for clm_ele in elem:
                    buttons = self.test.driver.find_elements(*clm_ele)
                    if buttons:
                        self.multiple_click_on_elem(elem=buttons[region], count=MAX_TEMP_CLICK)
                        capture_screenshot(test=self.test, test_name=f"test_07_{expected_value}_{side}")

                # Get current temp and validate against expected, LOW or HIGH
                for ele_temp in TEMP_VALUE_DATA:
                    temp_elements = self.test.driver.find_elements(*ele_temp)
                    if temp_elements:
                        temp_value = temp_elements[region].text
                        assert (
                            expected_value == temp_value
                        ), f"Failed to validate  {side} temperature value. Expected {expected_value} got {temp_value}"
