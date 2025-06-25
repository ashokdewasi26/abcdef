# Copyright (C) 2024. BMW Car IT. All rights reserved.
import logging
import os
import string
import requests
import subprocess  # noqa: AZ100
import time

from pathlib import Path

from mtee.testing.tools import OcrMode, assert_equal, assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.file_path_helpers import deconflict_file_path
from si_test_idcevo.si_test_helpers.pages.idcevo.allapps_page import AllAppsPage
from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage
from si_test_idcevo.si_test_helpers.screenshot_utils import (
    crop_image,
    extract_text,
    fetch_expected_color_present_in_image,
)
from tee.target_common import VehicleCondition

logger = logging.getLogger(__name__)

# IP Configured by TFM team while building the worker
GED_CID_IP = "192.168.1.200"
GED_PHUD_IP = "192.168.2.200"
TRUE_STATUS = 1
VALID_DISTANCE_VALUE = 1
VALID_DISTANCE_VALUE_CM = 100


@metadata(
    testsuite=["CAMERA", "SI-GED4K"],
    component="tee_idcevo",
    domain="DisplayGraphicsInfra",
)
class TestGed4k:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.all_apps = AllAppsPage()
        cls.test.setup_base_class(enable_appium=True, root=True)

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def capture_ged_screenshot(self, ip_addr, file_name="screenshot.jpg"):
        """
        Capture screenshot using GED4K board
        :param ip_addr: IP of GED4K board connected
        :param file_name: Screenshot file name
        :return: Full screenshot file path
        """
        url = f"http://{ip_addr}/cgi-bin/screenshot.cgi"
        file_name = (
            os.path.join(self.test.results_dir, file_name) if self.test.results_dir not in file_name else file_name
        )
        file_name = str(file_name + ".jpg") if ".jpg" not in file_name else file_name
        file_name = deconflict_file_path(file_name, extension=".jpg")

        response = requests.get(url, timeout=5)
        if response.status_code == 200 and response.headers["Content-Type"] == "image/jpeg":
            with open(file_name, "wb") as file:
                file.write(response.content)
            logger.info(f"Screenshot saved as {file_name}")
            return file_name
        else:
            err = "Failed to retrieve screenshot"
            logger.info(err)
            raise RuntimeError(err)

    def capture_ged_video(self, ip_addr, duration=15, output_file="captured_video.mp4"):
        """
        Capture screen recording using GED4K board
        :param ip_addr: IP of GED4K board connected
        :param duration: Duration to capture the video
        :param output_file: Recording file name
        :return: Full recording file path
        """
        url = f"http://{ip_addr}/cgi-bin/video-capture.cgi"

        output_file = (
            os.path.join(self.test.results_dir, output_file)
            if self.test.results_dir not in output_file
            else output_file
        )
        output_file = str(output_file + ".mp4") if ".mp4" not in output_file else output_file
        output_file = deconflict_file_path(output_file, extension=".mp4")
        command = [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-f",
            "hls",
            "-i",
            url,
            "-t",
            str(duration),
            "-codec:v",
            "mpeg1video",
            "-c",
            "copy",
            output_file,
        ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = process.communicate()
        if process.returncode == 0:
            logger.info(f"Video captured and saved as {output_file}")
        else:
            err = f"Failed to capture video. ffmpeg output:\n{stderr.decode()}"
            logger.info(err)
            raise RuntimeError(err)

    def send_pdc_distances(self, location, distance_type, count):
        """Send distance values using Vcar for a specified PDC location (corner or flank)"""
        if distance_type == "corner":
            for i in range(count):
                self.test.vcar_manager.send(
                    f"PdcDistances.{location}.pdcDistanceCornerSector{i}.distanceQualifier={VALID_DISTANCE_VALUE}"
                )
                self.test.vcar_manager.send(
                    f"PdcDistances.{location}.pdcDistanceCornerSector{i}.distanceValueInCm={VALID_DISTANCE_VALUE_CM}"
                )
        elif distance_type == "flank":
            for i in string.ascii_uppercase[:count]:
                self.test.vcar_manager.send(
                    f"PdcDistances.{location}.pdcDistanceFlankSector{i}.distanceQualifier={VALID_DISTANCE_VALUE}"
                )
                self.test.vcar_manager.send(
                    f"PdcDistances.{location}.pdcDistanceFlankSector{i}.distanceValueInCm={VALID_DISTANCE_VALUE_CM}"
                )
        time.sleep(2)

    def test_001_ged_hu_screenshot_and_recording(self):
        """
        [SIT_Automated] Capture and validate screenshot and screen recording of CID using GED4K board

        Steps:
            1. Launch all apps menu using adb activity on CID.
            2. Capture screenshot and screen recording.
            3. Validate the captured screenshot is not completely black by looking for app names.

        Expected Output:
            - Check all apps menu is available
            - Any app name which appears on first all app page is extracted from screenshot.
        """
        all_apps_box = (450, 100, 1540, 630)
        expected_strings = ("apps", "recently", "used", "bmw", "telephone", "climate", "apple", "auto", "android")
        BasePage.check_and_close_emergency_stop_page()
        self.all_apps.start_activity()
        time.sleep(2)
        all_apps_launch_status = self.all_apps.validate_activity()
        screenshot_path = self.capture_ged_screenshot(GED_CID_IP, file_name="screenshot_hu.jpg")
        assert_true(all_apps_launch_status, "All apps page failed to launch via start activity operation.")

        self.capture_ged_video(GED_CID_IP, output_file="captured_video_hu.mp4")
        image_text = extract_text(screenshot_path, region=all_apps_box).lower()
        assert_true(
            any(expected_out in image_text for expected_out in expected_strings),
            f"Unable to find any expected apps in all apps menu. Expected any of below strings\n"
            f"{expected_strings}\n Received output - {image_text}",
        )

    def test_002_ged_phud_screenshot_and_recording(self):
        """
        [SIT_Automated] Capture and validate screenshot and screen recording of PHUD using GED4K board

        Steps:
            1. Set the speed in phud to 0 via vcar.
            2. Capture screenshot and screen recording.
            3. Validate the captured screenshot is not completely black by extracting the speed.

        Expected Output:
            - Speed 0 is extracted from screenshot.
        """
        phud_speed_box = (860, 130, 990, 300)
        self.test.vcar_manager.execute_remote_method("set_speed", 0, True)
        time.sleep(1)

        screenshot_path = self.capture_ged_screenshot(GED_PHUD_IP, file_name="screenshot_phud.jpg")
        self.capture_ged_video(GED_PHUD_IP, output_file="captured_video_phud.mp4")
        speed_text = extract_text(screenshot_path, region=phud_speed_box, pagesegmode=OcrMode.SINGLE_LINE)
        logger.debug(f"Speed text before replacing unexpected characters: {speed_text}")
        speed = speed_text.replace("O", "0").replace("P", "8")
        assert_equal(speed, "0", f"Speed is not 0 or is not showing. Check {screenshot_path}")

    @metadata(
        testsuite=["BAT", "domain", "SI", "SI-GED4K"],
        component="tee_idcevo",
        domain="SichtAbsicht",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-195833",
        traceability={},
    )
    def test_003_verify_mini_pdc_integration_tests(self):
        """
        [SIT_Automated] Verify miniPDC integration tests
        Precondition:
            - PWF Status needs to be set to WOHNEN
        Steps:
            - Send someIP data for all PdcDistances
        Expected Outcome:
            - Verify all the PDC signals are connected
            - Validate miniPDC cloud should show yellow ring on reference image on CID
        """
        # Hex code of yellow color
        expected_color_on_cid = "#f4e600"
        mini_pdc_box = (1770, 672, 1773, 675)
        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.WOHNEN)

        self.test.vcar_manager.send(f"ParkingUserInteractionControl.requestDisplayPdcMiniView={TRUE_STATUS}")
        self.send_pdc_distances("pdcDistancesCornerFrontLeft", "corner", 5)
        self.send_pdc_distances("pdcDistancesCornerFrontRight", "corner", 5)
        self.send_pdc_distances("pdcDistancesCornerRearLeft", "corner", 5)
        self.send_pdc_distances("pdcDistancesCornerRearRight", "corner", 5)
        self.send_pdc_distances("pdcDistancesFlankLeft", "flank", 4)
        self.send_pdc_distances("pdcDistancesFlankRight", "flank", 4)

        mini_pdc_screenshot_cid = self.capture_ged_screenshot(GED_CID_IP, file_name="screenshot_mini_pdc.jpg")
        cropped_image = Path(Path(mini_pdc_screenshot_cid).parent, Path(mini_pdc_screenshot_cid).stem + "_cropped.png")
        crop_image(mini_pdc_screenshot_cid, mini_pdc_box, cropped_image)
        validation_flag = fetch_expected_color_present_in_image(cropped_image, expected_color_on_cid, threshold=30)
        assert_true(validation_flag, "The miniPDC cloud does not show a yellow ring on CID")
