import logging
import os
import re
import time
from unittest import TestCase, skip

import si_test_apinext.util.driver_utils as utils
from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import OcrMode
from si_test_apinext.idc23 import IC_HMI_REF_IMG_PATH
from si_test_apinext.idc23.pages.display_settings_page import DisplaySettingsAppPage as DisplaySet
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.units_settings_page import UnitsSettingsAppPage as Units
from si_test_apinext.testing.test_base import TestBase
from si_test_apinext.util.screenshot_utils import (
    check_screendump,
    compare_snapshot,
    extract_text,
    take_ic_screenshot_and_extract,
)

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

temp_box = (1420, 660, 1610, 720)
speed_box = [(840, 200, 1170, 450), (770, 210, 1170, 430)]
max_speed_range_box = [(380, 77, 525, 120), (440, 30, 640, 100)]
speed_unit_box = [(890, 390, 1020, 430)]

temp_value_regex = re.compile(".*([\+|-].*\d+).*[C|c]")  # noqa: W605
speed_value_regex = re.compile(".*(?:mph|km/h)")  # noqa: W605
max_speed_value_regex = re.compile("\d+.*(?:mph|km/h)")  # noqa: W605

IC_text_test_data = [
    ("Temp", temp_box, temp_value_regex),  # noqa: W605
    ("Speed", speed_unit_box + speed_box, speed_value_regex),  # noqa: W605
    ("Max Speed", max_speed_range_box, max_speed_value_regex),  # noqa: W605
]

fuel_bar_box = (70, 680, 300, 720)  # Fuel Bar
fuel_icon_box = (0, 670, 45, 710)  # Fuel Icon
temp_bar_box = (1635, 675, 1920, 720)  # Temp bar

IC_screenshot_test_data = [
    ("Fuel bar", fuel_bar_box, "IC_HMI_FuelBar.png", "fuel_bar.png"),
    ("Fuel icon", fuel_icon_box, "IC_HMI_FuelIcon.png", "fuel_icon.png"),
    ("Temp bar", temp_bar_box, "IC_HMI_TempBar.png", "temp_bar.png"),
]

fuel_level_vcar_msg = "IK.RangeWarningFuelLevel"

video_name = "ic_hmi_tests"
speed_can_message = "IK.V_VEH_COG"


class TestICHMI(TestCase):
    ic_hmi_ref_img_path = IC_HMI_REF_IMG_PATH

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.vcar_manager = TargetShare().vcar_manager
        Launcher.go_to_home()
        utils.start_recording(cls.test)

    @classmethod
    def teardown_class(cls):
        Launcher.go_to_home()
        utils.stop_recording(cls.test, video_name)
        cls.test.quit_driver()

    @classmethod
    def _set_validate_vcar_msg_float(cls, vcar_message, vcar_value, list_errors=[]):
        """
        Send a vcar message with a value to be set and validate the value is correctly set

        :param vcar_message: vcar message template
        :type vcar_message: str
        :param vcar_value: vcar value to be appended to vcar_message, and then validated
        :type vcar_value: float
        :param list_errors: list of str with error messages
        :type list_errors: list of str
        :return: list_errors
        :rtype: list of str
        """
        cls.vcar_manager.send(f"{vcar_message} = {vcar_value}")
        time.sleep(1)
        verify_result = cls.vcar_manager.send(f"{vcar_message}")
        if float(verify_result) != float(vcar_value):
            list_errors.append(
                f"Error on validating value of vcar command '{vcar_message} = {vcar_value}',"
                f" value received:'{verify_result}'"
            )
        return list_errors

    @classmethod
    def _set_fuel_level_state(cls, flag):
        """
        With This command We can set fuel icon mode
        Parameter fuel_icon_mode type int (1 or 0)
        "IK.RangeWarningFuelLevel=1" to enable fuel icon warning (yellow color icon)
        "IK.RangeWarningFuelLevel=0" to disable fuel icon warning (gray color icon)
        """
        cls._set_validate_vcar_msg_float(vcar_message=fuel_level_vcar_msg, vcar_value=flag)

    @utils.gather_info_on_fail
    def test_000_prepare_speed_parameters(self):  # noqa: N802
        """
        Prepare the speed parameters

        Set distance unit of measurement with Kilometers
        Enable the second speed option on IC display
        """
        DisplaySet.set_ic_second_speed("enable")
        Units.set_distance_unit("km")

    @utils.gather_info_on_fail
    def test_001_IC_availability(self):  # noqa: N802
        """
        Check if IC is available

        *Background information*

        In this test we expect that the IC is available by taking a screenshot and check its contents.

        *Steps*
        1. Take screenshot of IC
        2. Validate the following text elements from screenshot:
            - Temperature
            - Current speed (located on the middle of the screen)
            - Max speed on scale
        3. Validate following image elements from screenshot:
            - Fuel bar
            - Fuel icon
            - Temperature bar
        """
        # Set a random speed (different than 0)
        self._set_validate_vcar_msg_float(speed_can_message, 10000)
        self._set_fuel_level_state(0)
        screenshot_path = os.path.join(self.test.results_dir, "IC_HMI.png")
        take_ic_screenshot_and_extract(self.test.mtee_target, screenshot_path)
        for prop, box, regex_pattern in IC_text_test_data:
            logger.info("Checking text of: " + prop)
            result, error_msg = check_screendump(screenshot_path, regex_pattern, region=box)
            assert result, f"Error on checking {prop}. {error_msg}"

        for prop, box, cropped_image_name, reference_image_name in IC_screenshot_test_data:
            logger.info("Checking image: " + prop)
            cropped_image = os.path.join(self.test.results_dir, cropped_image_name)
            reference_image = os.path.join(self.ic_hmi_ref_img_path, reference_image_name)
            result, error = compare_snapshot(screenshot_path, reference_image, prop, fuzz_percent=99, region=box)
            if not result:
                raise AssertionError(
                    f"Error on checking {prop}. {cropped_image} not equal to reference {reference_image_name}, {error}"
                )

    @utils.gather_info_on_fail
    def test_002_speed(self):
        """
        Test Speed

        *Background information*

        In this test we expect that interact with IC, by changing default value for speed.

        *Steps*
        1. Send Speed CAN messages to target (IK.V_VEH_COG)
            a.  value = 100 means 1 mph
        2. Take screenshots of IC
        3. Validate the speed element from screenshot.
        """
        speed_values = [
            # [Vcar_speed, mph, kmh]
            [0, 0, "O"],
            [10, 10, 16],
            [20, 20, 32],
            [65, 64, 103],
            [100, 98, 157],
            [120, 117, 189],
            [150, 146, 235],
        ]

        list_errors = []
        # Save default/initial value
        default_value = float(self.vcar_manager.send(f"{speed_can_message}"))
        for speed_test in speed_values:
            list_errors = self._set_validate_vcar_msg_float(speed_can_message, speed_test[0] * 100, list_errors)
            screenshot_path = os.path.join(self.test.results_dir, f"IC_HMI_speed_{speed_test[1]}.png")
            take_ic_screenshot_and_extract(self.test.mtee_target, screenshot_path)
            regex = rf"(?:{speed_test[1]}|{speed_test[2]})"
            regex_pattern = re.compile(regex)
            result, error_msg = check_screendump(screenshot_path, regex_pattern, region=speed_box)
            if not result:
                list_errors.append(f"{screenshot_path}: Error checking vcar speed {speed_test[0]}, {error_msg}")
        # Set default/initial value
        list_errors = self._set_validate_vcar_msg_float(speed_can_message, default_value, list_errors)
        if any(list_errors):
            raise AssertionError(list_errors)

    @utils.gather_info_on_fail
    def test_003_temperature(self):
        """
        Test Temperature

        *Background information*

        In this test we expect to interact with IC, by changing default value for temperature.

        *Steps*

        1. Set Temperature_Ambient to 10
        2. Set Temperature_Ambient to -5.3
        3. Set Temperature_Ambient to -41

        *Expected Result*
        1. Value "+10 °C" of Temperature_Ambient displayed
        2. Value "-5 °C" of Temperature_Ambient displayed
        3. Value "-40 °C" of Temperature_Ambient displayed
        """
        temp_data = [
            (1100, "+10"),
            (947, "-5"),
            (590, "-40"),
        ]
        default_temp = self.vcar_manager.send("IK.RawDataSensorTempExPresent")
        failed_temps = []

        for temp_value, expected_ic_temp_value in temp_data:
            self.vcar_manager.send(f"IK.RawDataSensorTempExPresent={temp_value}")
            time.sleep(3)
            screenshot_path = os.path.join(self.test.results_dir, f"IC_HMI_temp_{expected_ic_temp_value}.png")
            take_ic_screenshot_and_extract(self.test.mtee_target, screenshot_path)
            text = extract_text(screenshot_path, region=temp_box, pagesegmode=OcrMode.SINGLE_LINE)
            re_result = temp_value_regex.findall(text)
            if re_result:
                re_text = re_result[0].replace(" ", "")
                if expected_ic_temp_value not in re_text:
                    failed_temps.append(
                        f"Unable to find the expected temperature: '{expected_ic_temp_value}', "
                        + f"on text from image: IC_HMI_temp_'{expected_ic_temp_value}'.png"
                    )
            else:
                failed_temps.append(f"Unable to match temperature from screenshot {screenshot_path}")
        try:
            if any(failed_temps):
                raise AssertionError(failed_temps)
        finally:
            # Teardown
            self.vcar_manager.send(f"IK.RawDataSensorTempExPresent={default_temp}")

    @utils.gather_info_on_fail
    def test_004_fuel_tank_level(self):
        """
        Test Tank Level

        *Background information*

        In this test we expect to interact with IC, by changing default value for tank level.

        *Steps*
        1. Send CAN Signal to 0h (Kraftstoff_Fuellstand_in_Ordnung)
        2. Send tank level 0%(000h) over CAN signal
        3. Send tank level 50%(640h) over CAN signal RelativeFuelLevelEstimate (427h)
        4. Send tank level 100%(C80) over CAN signal RelativeFuelLevelEstimate (427h)
        5. Execute a tank level sweep from 100% to 0% and from 0% to 100% over CAN signal
        6. Send CAN Signal to 1h (Kraftstoff_Fuellstand_gering)

        *Expected Result*
        1. Fuel Level do not change colour
        2. Tank level is 0%
        3. Tank level is 50%
        4. Tank level is 100%
        5. Execute a tank level sweep from 100% to 0% and from 0% to 100% over CAN signal
        6. Fuel Level should be colorized in yellow
        """

        self._set_fuel_level_state(0)
        default_level = self.vcar_manager.send("IK.RelativeFuelLevelEstimate")
        values = [0, 1600, 3200, 0, 3200]
        for val in values:
            self.vcar_manager.send(f"IK.RelativeFuelLevelEstimate={val}")
            time.sleep(2)
            screenshot_path = os.path.join(self.test.results_dir, f"IC_HMI_fuel_level_{val}.png")
            reference_image = os.path.join(self.ic_hmi_ref_img_path, f"fuel_level_{val}.png")
            take_ic_screenshot_and_extract(self.test.mtee_target, screenshot_path)
            result, _ = compare_snapshot(
                screenshot_path, reference_image, "crop_fuel_level", fuzz_percent=2, region=fuel_bar_box
            )
            self.assertTrue(
                result,
                f"Cropped fuel level image do not match reference image fuel_level_{val}.png",
            )

        self._set_fuel_level_state(1)
        time.sleep(2)
        screenshot_path = os.path.join(self.test.results_dir, "IC_HMI_fuel_warning.png")
        reference_image = os.path.join(self.ic_hmi_ref_img_path, "fuel_icon_warning.png")
        take_ic_screenshot_and_extract(self.test.mtee_target, screenshot_path)
        result, _ = compare_snapshot(
            screenshot_path, reference_image, "warning_fuel_icon", fuzz_percent=2, region=fuel_icon_box
        )
        self.assertTrue(
            result,
            "Cropped fuel icon image do not match reference image fuel_icon_warning.png",
        )

        # Teardown
        self._set_fuel_level_state(0)
        time.sleep(2)
        screenshot_path = os.path.join(self.test.results_dir, "default_fuel_icon_check.png")
        reference_image = os.path.join(self.ic_hmi_ref_img_path, "fuel_icon.png")
        take_ic_screenshot_and_extract(self.test.mtee_target, screenshot_path)
        result, _ = compare_snapshot(
            screenshot_path, reference_image, "default_fuel_icon_diff", fuzz_percent=2, region=fuel_icon_box
        )
        self.assertTrue(
            result,
            "Cropped fuel icon image do not match reference image fuel_icon.png",
        )

        self.vcar_manager.send(f"IK.RelativeFuelLevelEstimate={default_level}")
        time.sleep(2)

    @skip("Test not implemented")
    def test_005_range_ICE(self):  # noqa: N802
        """
        Test Range

        *Background information*

        In this test we expect to interact with IC, by changing default value for Range.

        *Steps*
        1. Send Range ICE CAN message to target (IK.DataRangeDisplayTotal // IK.DataRangeDisplayElectric) //Not working
        2. Send Fadeout  Range CAN message to target (IK.FadeoutRangeDisplayTotal // IK.FadeoutRangeDisplayElectric)
        3. Take screenshot of IC
        4. Validate the temp elements from screenshot.
        5. Send Range Warning Fuel Level to 1. (Kraftstoff_Fuellstand_gering)
        """

    @skip("Test not implemented")
    def test_006_odometer(self):
        """
        Test Odometer

        *Background information*

        Currently screenshot do not have info about Odometer.
        """

    @skip("Test not implemented")
    def test_007_time(self):
        """
        Test Time

        *Background information*

        Currently screenshot do not have info about Time.
        """
