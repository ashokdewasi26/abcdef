# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Tests the ADB connectivity"""
import configparser
import logging
import os
import subprocess
from pathlib import Path
from unittest import skipIf

from mtee.testing.tools import metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.screenshot_utils import take_phud_driver_screenshot
from si_test_idcevo.si_test_helpers.test_helpers import skip_unsupported_ecus

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)


@metadata(
    testsuite=["BAT", "domain", "SI", "IDCEVO-SP21", "SI-GED4K"],
    component="tee_idcevo",
    domain="IDCEvo Test",
    asil="None",
    testmethod="Analyzing Requirements",
    testtype="Requirements-based test",
    testsetup="SW-Component",
    categorization="functional",
    priority="1",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": config.get("FEATURES", "TEE_FEATURE"),
        },
    },
)
class TestsADBConnectivity(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(disable_dmverity=True)

    def test_adb_device_connected_idc_evo(self):
        timeout = 60
        try:
            # The wait-for-device will block until an ADB device is detected
            # and the devices command will list all devices. This basically
            # waits for any adb device to appear and then lists the entire
            # devices collection
            subprocess.check_call(["adb", "wait-for-device", "devices"], timeout=timeout)
        except subprocess.CalledProcessError:
            raise RuntimeError("ADB devices command returned an error. Check the logs")
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"ADB wait-for-device timed out. No ADB devices detected in {timeout} seconds.")

        try:
            subprocess.check_call(["adb", "shell", "echo", "1"], timeout=30)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as ex:
            # Shell command running into errors should be considered a test failure
            raise AssertionError from ex

    def test_002_adb_screenshot_cid(self):
        """Check if CID screenshot via adb is operational"""
        screenshot_path = os.path.join(self.test.results_dir, "adb_screenshot_cid.png")
        logger.info("Taking CID screenshot with adb")
        self.test.take_apinext_target_screenshot(self.test.results_dir, screenshot_path)
        assert (
            os.path.getsize(screenshot_path) != 0
        ), f"adb screenshot command generated an empty screenshot file. Screenshot path: {screenshot_path}"

    @skipIf(not skip_unsupported_ecus(["idcevo"]), "PHUD display is not available in this ECU!")
    def test_003_adb_screenshot_phud_driver(self):
        """Check if PHUD driver screenshot via adb is operational"""
        screenshot_path = os.path.join(self.test.results_dir, "adb_screenshot_phud_driver.png")
        logger.info("Taking phud driver screenshot with adb")
        take_phud_driver_screenshot(self.test, screenshot_path, try_via_diag_job=False)
