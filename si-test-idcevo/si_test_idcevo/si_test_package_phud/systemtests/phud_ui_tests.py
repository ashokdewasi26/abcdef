# Copyright (C) 2024. BMW CTW PT. All rights reserved.
import logging
import os
import re
import time

from pathlib import Path

from mtee.testing.tools import (
    OcrMode,
    TimeoutCondition,
    TimeoutError,
    assert_equal,
    assert_false,
    assert_true,
    metadata,
)
from si_test_idcevo.si_test_helpers.android_helpers import (
    check_early_cluster_after_cold_reboot,
    ensure_launcher_page,
    get_ready_textbox_phud,
    get_text_from_phud_with_ocr,
    retrieve_speed_phud,
)
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.pages.idcevo.connectivity_page import ConnectivityPage as Connectivity
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target
from si_test_idcevo.si_test_helpers.screenshot_utils import (
    extract_text,
    match_template,
    take_phud_driver_screenshot,
)
from tee.target_common import VehicleCondition


logger = logging.getLogger(__name__)

SPEED_INPUT_VALUE = 54
# IcQMReadyOff::SubscribeDisplayedSpeed:displayed_speed:  54.6
# IcQMTripDataEES25::SubscribeDisplayedSpeed:displayed_speed:  54.6
# IcQMTripHistoryEES25::SubscribeDisplayedSpeed:displayed_speed analog:  54.6
# This will be rounded on the car to 55
EXPECTED_DISPLAYED_SPEED = 55

# 4- tuple defining the left, upper, right, and lower pixel
# coordinate. See :ref:`coordinate-system`. Ex.: (662, 119, 842, 216)
CROP_SPEED_MAIN_BOX = {
    "single_digit_speed": (700, 110, 800, 227),
    "double_digit_speed": (662, 119, 842, 216),
    "triple_digit_speed": (635, 119, 865, 216),
}
CROP_SPEED_SECONDARY_BOX = (688, 246, 757, 283)
CROP_BATTERY_CHARGE = (1298, 110, 1378, 165)
CROP_CID_SAFETY_LAYER_RIGHT_REGION = (2886, 291, 3254, 987)
SAFETY_LAYER_CID_FILE_REGEX = re.compile("screenshot-idcevo-.*-primary-safety.png")


class TestPHUD:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(root=True)
        cls.sp25 = True
        wait_for_application_target(cls.test.mtee_target)

    @classmethod
    def teardown_class(cls):
        cls.test.vcar_manager.execute_remote_method("set_speed", 0, cls.sp25)
        cls.test.teardown_base_class()

    def wait_for_screenshot_conversion(self, screenshot_input_file_name, screenshot_output_file_path, timeout=30):
        """Wait for screenshot inside /tmp to be converted from .argb format to .png and download it to different path

        :param screenshot_input_file_name (str): name or regex pattern of the screenshot inside /tmp directory
        :param screenshot_output_file_path (str): name of the file path where the screenshot will be downloaded
        :param timeout (int): maximum time to wait for the screenshot conversion and download, in seconds
        """
        timeout_condition = TimeoutCondition(timeout)
        while timeout_condition():
            result = self.test.mtee_target.execute_command(["ls", "-R", "/tmp"])
            if ".png" in result.stdout and ".argb" not in result.stdout:
                logger.info("Successfully converted safety-layer screenshots to .png format")
                for filename in result.stdout.splitlines():
                    if re.search(screenshot_input_file_name, filename):
                        self.test.mtee_target.download(f"/tmp/{filename}", screenshot_output_file_path)
                        break
                break
            time.sleep(1)

    def set_car_ready_to_drive_using_vcar(self):
        """Send vCar signals to make car ready to drive
        Driving state, in D gear, w/ normal display, at 0 km/h
        """
        self.test.vcar_manager.execute_remote_method("set_vehicle_lifecycle_state_sp25", VehicleCondition.FAHREN)
        self.test.vcar_manager.send("StatusDisplayDrivingFunctions.DisplayDrivePosition.StatusDisplayStageDrive=4")
        self.test.vcar_manager.send(
            "StatusDisplayDrivingFunctions.DisplayDrivePosition.StatusDisplayStageDriveExtension=1"
        )

    def test_001_phud_driver_main_speed_zero(self):
        """
        [SIT_Automated] PHUD driver main speed is being displayed

        Steps:
            - Take a screenshot of the PHUD driver section using ADB
            - Parse the section of the screenshot where the speed will be
            - Compare the parsed value with the expected value

        Expected outcome:
            - Screenshot is successfully taken
            - We can parse the speed and it is 0
        """
        for i in range(3):
            screenshot_path = Path(f"phud_driver_0_speed_{i}.png")
            speed = retrieve_speed_phud(self.test, screenshot_path, CROP_SPEED_MAIN_BOX["single_digit_speed"])
            if "0" in speed:
                break
            time.sleep(10)  # PHUD might not be available yet, holding back 10s
        assert_equal(speed, "0", f"Speed is not 0 or is not showing. Check {screenshot_path}")

    def test_002_phud_driver_change_speed(self):
        """
        [SIT_Automated] Change the speed using vCar to a know value and check if PHUD follows

            Steps:
            - Set a speed using vCar to a known value e.g 55 km/h
            - Parse the section of the screenshot were the speed is
            - Compare the parsed value with the expected

            Expected outcome:
                - Screenshot is successfully taken
                - Speed matches the expected value

        """
        logger.info(f"Changing speed with vCar for {SPEED_INPUT_VALUE}")

        self.set_car_ready_to_drive_using_vcar()

        # Check ascgit142.vcar/server/libraries/vehicle_speed_lib.py
        self.test.vcar_manager.execute_remote_method("set_speed", SPEED_INPUT_VALUE, self.sp25)
        time.sleep(1)  # small wait for speed change to take effect

        screenshot_path = Path(self.test.results_dir, f"phud_driver_speed_{EXPECTED_DISPLAYED_SPEED}.png")
        take_phud_driver_screenshot(self.test, screenshot_path)

        speed_text = extract_text(
            screenshot_path,
            region=CROP_SPEED_MAIN_BOX["double_digit_speed"],
            monochrome=True,
            pagesegmode=OcrMode.SINGLE_LINE,
        )
        assert_equal(
            speed_text,
            f"{EXPECTED_DISPLAYED_SPEED}",
            f"Speed is not the expected value {EXPECTED_DISPLAYED_SPEED} or is not showing. Check {screenshot_path}",
        )

    def test_003_speed_lock_popup(self):
        """
        [SIT_Automated] Open wireless/connectivity without speed lock

            Steps:
            - Set a speed using vCar to a known value e.g 55 km/h
            - Open wireless services / connectivity app
            - Check application is open without the speed lock layer

            Expected outcome:
                - Connectivity opens without speed lock
        """
        logger.info(f"Changing speed with vCar for {SPEED_INPUT_VALUE}")
        self.test.vcar_manager.execute_remote_method("set_speed", SPEED_INPUT_VALUE, self.sp25)
        time.sleep(1)  # small wait for speed change to take effect

        for i in range(3):
            ensure_launcher_page(self.test)
            logger.info(f"Attempting open wireless services / connectivity {i}/3")
            # Take CID and PHUD0 screenshots before launch app
            screenshot_path = Path(self.test.results_dir, f"phud_speed_before_app_launch_{i}.png")
            take_phud_driver_screenshot(self.test, screenshot_path)
            self.test.take_apinext_target_screenshot(self.test.results_dir, f"cid_before_app_launch_{i}.png")

            self.test.apinext_target.execute_command(Connectivity().get_command_warm_hot_start())
            time.sleep(3)  # Connectivity/wireless services takes sometime to open
            self.test.take_apinext_target_screenshot(self.test.results_dir, f"cid_connectivity_screen_{i}.png")
            screenshot_path = Path(self.test.results_dir, f"phud_speed_after_app_launch_{i}.png")
            take_phud_driver_screenshot(self.test, screenshot_path)

            dumpsys_cmd = "dumpsys activity activities | grep -E 'mCurrentFocus|mFocusedApp'"
            launched_activities_result = self.test.apinext_target.execute_command(dumpsys_cmd)
            logger.debug(launched_activities_result)
            if Connectivity().PACKAGE_NAME in launched_activities_result:
                break

        assert_true(
            "SpeedLockBlockingActivity" not in launched_activities_result, "Speedlock found after connectivity"
        )
        assert_true(Connectivity().PACKAGE_NAME in launched_activities_result, "Wireless services app was not open.")

    @metadata(
        testsuite=["BAT", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Instrument Cluster",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-12236",
        traceability={""},
    )
    def test_004_search_android_cluster_ready(self):
        """
        [SIT_Automated] Verify Android Cluster App started and working properly

        Steps:
            - Verify early cluster is up
            - Set necessary variables as per manual test ticket
            - Check if "ready" is present in PHUD screen
        """
        check_early_cluster_after_cold_reboot(self.test)
        self.set_car_ready_to_drive_using_vcar()
        self.test.vcar_manager.execute_remote_method("set_speed", 0, self.sp25)
        time.sleep(1)
        ready_textbox = get_ready_textbox_phud(self.test, "PHUD_ready_box.png")

        assert ready_textbox, "NO text was found, PHUD probably wasn't setup."
        assert (
            ready_textbox == "READY"
        ), f"Could not find the text 'READY' in PHUD as was expected, instead found: {ready_textbox}"

    @metadata(
        testsuite=["BAT", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Instrument Cluster",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-12231",
        traceability={""},
    )
    def test_005_verify_early_cluster_after_10sec(self):
        """[SIT_Automated] Verify Early-Cluster started and working properly after 10 sec after cold-boot

        Steps:
            - Power-on ECU and wait until early cluster display is up
            - Wait 10 seconds and check if early cluster display is still up
        """
        check_early_cluster_after_cold_reboot(self.test)

        # Setting speed as zero just to have a constant test basis
        self.test.vcar_manager.execute_remote_method("set_speed", 0, self.sp25)
        time.sleep(1)

        initial_speed = retrieve_speed_phud(
            self.test, "early_cluster_after_reboot.png", CROP_SPEED_MAIN_BOX["single_digit_speed"]
        )
        time.sleep(10)
        final_speed = retrieve_speed_phud(
            self.test, "early_cluster_after_10sec.png", CROP_SPEED_MAIN_BOX["single_digit_speed"]
        )

        assert_true(
            initial_speed == final_speed == "0",
            "Speed displayed in PHUD changed unexpectedly after 10 seconds",
        )

    @metadata(
        testsuite=["BAT", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Instrument Cluster",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-12240",
        traceability={""},
    )
    def test_006_verify_speed_kph_mph(self):
        """
        [SIT_Automated] Verify speed in main and secondary dials

        Steps:
            - Set speed to 0
            - Verify both main and secondary dials show '0'
            - Set speed to 63 (which will show in PHUD as 64)
            - Verify both main and secondary dials show '64' and '40', respectively

        Note:
            - Test assumes main dial is for km/h and secondary for mph
        """
        self.set_car_ready_to_drive_using_vcar()
        self.test.vcar_manager.execute_remote_method("set_speed", 0, self.sp25)
        time.sleep(1)
        kph_speed_0 = retrieve_speed_phud(
            self.test, "comparison_KPH_0_speed.png", CROP_SPEED_MAIN_BOX["single_digit_speed"]
        )
        mph_speed_0 = retrieve_speed_phud(self.test, "comparison_MPH_0_speed.png", CROP_SPEED_SECONDARY_BOX)

        assert_true(
            kph_speed_0 == mph_speed_0 == "0",
            "Speed in KPH and MPH expected to be at 0, but instead"
            f"was set to {kph_speed_0} KPH and {mph_speed_0} MPH. Please verify the screenshots.",
        )
        self.test.vcar_manager.execute_remote_method("set_speed", 63, self.sp25)
        time.sleep(1)
        kph_speed_64 = retrieve_speed_phud(
            self.test, "comparison_KPH_64_speed.png", CROP_SPEED_MAIN_BOX["double_digit_speed"]
        )
        mph_speed_40 = retrieve_speed_phud(self.test, "comparison_MPH_40_speed.png", CROP_SPEED_SECONDARY_BOX)

        errors = []
        if kph_speed_64 != "64":
            errors.append(f"Speed in KPH expected to be '64', but was set to {kph_speed_64}.")
        if mph_speed_40 != "40":
            errors.append(f"Speed in MPH expected to be '40', but was set to {mph_speed_40}.")

        assert_false(errors, "Errors found in speed verification.")

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Instrument Cluster",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-12240",
        traceability={},
    )
    def test_007_verify_display_state_of_charge(self):
        """
        [SIT_Automated] Verify PHUD battery percentage

        Steps:
            - Set State of Charge (SoC) to 75
            - Extract SoC percentage

        Expect Outcome:
            - Verify SoC is displaying expected percentage.
            - On Display, icon overlapping or anomaly should not be observed.
        """
        display_state_of_charge_value = 75
        self.test.vcar_manager.execute_remote_method("set_vehicle_lifecycle_state_sp25", VehicleCondition.FAHREN)
        self.test.vcar_manager.send(
            f"PowertrainDriveDisplay.displayStateOfEnergy.displayStateOfChargeHvs={display_state_of_charge_value}"
        )
        self.test.vcar_manager.send(
            "PowertrainDriveDisplay.displayStateOfEnergy.qualifier_Value_displayStateOfChargeHvs=0"
        )
        self.test.vcar_manager.send("PowertrainDriveDisplay.displayRange.warning.rangeWarningStateOfCharge=0")
        time.sleep(3)
        battery_text = get_text_from_phud_with_ocr(self.test, "PHUD_battery_percentage.png", CROP_BATTERY_CHARGE)
        assert_true(
            str(display_state_of_charge_value) == battery_text,
            f"Expected display battery percentage : {display_state_of_charge_value} "
            f"got display battery percentage {battery_text}.",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Instrument Cluster",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-12239",
        traceability={},
    )
    def test_008_verify_sqhmi_ready(self):
        """
        [SIT_Automated] Verify SQHMI started and working properly after Power ON

        ** We are not validating step 3 of the domain test ticket (Assisted Driving verification). Also we are not
        validating parking break light in PHUD, since the correspondent screenshot is empty **

        Steps:
            - Activate parking break light in CID
            - Execute safety layer screenshots with "screenshot-fake" command
            - Ensure screenshots conversion to .png format
            - Download CID screenshot file to results directory
            - Search for parking break light reference image inside CID screenshot

        Expected Outcome:
            - Parking break light found in CID screenshot
        """
        safety_layer_screenshot_cid = os.path.join(self.test.results_dir, "safety_layer_cid.png")
        parking_break_reference_cid = Path(os.sep) / "resources" / "parking_break_light_reference_image.png"

        self.test.vcar_manager.send(
            "RequestDisplayCheckControl.requestDispCc.activeCcMessageList.numberCheckControl=6407"
        )
        self.test.vcar_manager.send(
            "RequestDisplayCheckControl.requestDispCc.activeCcMessageList.telltaleFlashingFrequency=0"
        )
        self.test.vcar_manager.send("RequestDisplayCheckControl.requestDispCc.numberOfListsToTransfer=1")
        self.test.vcar_manager.send("RequestDisplayCheckControl.requestDispCc.numberCurrentList=1")
        time.sleep(3)

        self.test.mtee_target.execute_command("screenshot-fake", expected_return_code=0)

        try:
            self.wait_for_screenshot_conversion(SAFETY_LAYER_CID_FILE_REGEX, safety_layer_screenshot_cid)
        except TimeoutError:
            raise RuntimeError("Screenshot conversion not completed within the defined timeout")

        assert_true(
            os.path.exists(safety_layer_screenshot_cid),
            "Could not find CID safety layer screenshot inside /tmp directory",
        )

        match, _ = match_template(
            image=safety_layer_screenshot_cid,
            image_to_search=parking_break_reference_cid,
            region=CROP_CID_SAFETY_LAYER_RIGHT_REGION,
            results_path=self.test.results_dir,
            context="parking_break",
        )

        assert_true(match, "Parking break light not displayed on CID")

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Instrument Cluster",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-12240",
        traceability={},
    )
    def test_008_verify_range_values(self):
        """
        [SIT_Automated] Verify IDCevo basic features working properly - Range
        Steps:
            - Send the following signal for RANGE:
                PowertrainDriveDisplay.displayRange.basicRange.dataRangeDisplayElectric=125,
                PowertrainDriveDisplay.displayRange.basicRange.unitRangeDisplay=1,
                PowertrainDriveDisplay.displayRange.basicRange.fadeoutRangeDisplayTotal=0,
                PowertrainDriveDisplay.displayRange.WarningStruct.RangeWarningRangeTotal=TotalRangeAllright,
                PowertrainDriveDisplay.displayRange.warning.rangeWarningRangeTotal = 0,
                PowertrainDriveDisplay.displayRange.basicRange.qualifier_Value_dataRangeDisplayElectric = 0
        Expected Outcome:
            - km units are shown along with the value, and the value should be 125km
        """
        expected_range_value = 125
        phud_range_value_signal = [
            "PowertrainDriveDisplay.displayRange.basicRange.dataRangeDisplayElectric=125",
            "PowertrainDriveDisplay.displayRange.basicRange.unitRangeDisplay=1",
            "PowertrainDriveDisplay.displayRange.basicRange.fadeoutRangeDisplayTotal=0",
            "PowertrainDriveDisplay.displayRange.WarningStruct.RangeWarningRangeTotal=TotalRangeAllright",
            "PowertrainDriveDisplay.displayRange.warning.rangeWarningRangeTotal = 0",
            "PowertrainDriveDisplay.displayRange.basicRange.qualifier_Value_dataRangeDisplayElectric = 0",
        ]
        crop_range_in_kms = (1252, 162, 1441, 218)
        self.test.vcar_manager.execute_remote_method("set_vehicle_lifecycle_state_sp25", VehicleCondition.FAHREN)
        for signal in phud_range_value_signal:
            self.test.vcar_manager.send(signal)
            time.sleep(0.1)
        time.sleep(1)
        range_values = get_text_from_phud_with_ocr(
            self.test, "PHUD_range_values.png", crop_range_in_kms, contrast_ratio=3.0
        )
        assert_true(
            f"{expected_range_value}km" == range_values,
            f"Expected range value: {expected_range_value}km. Obtained range value: {range_values}",
        )
