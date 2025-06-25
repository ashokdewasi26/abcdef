# Copyright (C) 2025. BMW CTW PT. All rights reserved.
"""Example tests - Checking the ADB connectivity"""
import logging
import os
import re
import subprocess

from mtee.testing.connectors.connector_dlt import DLTContext

from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.file_path_helpers import create_custom_results_dir
from si_test_idcevo.si_test_helpers.traas.traas_helpers import TRAASHelper

logger = logging.getLogger(__name__)


class TestsDemoExample(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(disable_dmverity=True)

        cls.extract_file_dir = os.path.join(cls.test.mtee_target.options.result_dir, "extracted_files")

        cls.traas_helper = TRAASHelper()

    def test_001_example_adb_device(self):
        """Example test - Check ADB device connectivity"""
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

    def test_002_example_linux_reboot(self):
        """
        Example Linux target - Check DLT messages after reboot
        """
        dlt_filters = [
            {"payload_decoded": re.compile(r".*PowerStateMachine input: pwf is: DIAGNOSE.*")},
            {"payload_decoded": re.compile(r"SHUTDOWN_APPLICATION_RESET\(5\)")},
            {"payload_decoded": re.compile(r".*NsmNodeState_FullyOperational.*5.*=>.*NsmNodeState_FastShutdown 8.*")},
            {"payload_decoded": re.compile(r".*NSM: Starting Collective Timeout for shutdown type FAST.*")},
            {"payload_decoded": re.compile(r"setWakeUpReasonWAKEUP_REASON_APPLICATION\(8\)")},
            {"payload_decoded": re.compile(r".*Current Boot Mode: Application.*")},
            {"payload_decoded": re.compile(r".*application.target.*")},
            {"payload_decoded": re.compile(r".*late.target.*")},
        ]
        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as dlt_trace:
            self.test.mtee_target.reboot(prefer_softreboot=True)
            dlt_msgs = dlt_trace.wait_for_multi_filters(
                filters=dlt_filters,
                count=0,
                drop=True,
                timeout=240,
            )

            for dlt_msg in dlt_msgs:
                logger.info("Found DLT message: %s", dlt_msg.payload_decoded)

    def test_003_example_android_version(self):
        """
        Example Android target - Retrieve information about Android version
        """
        result = self.test.apinext_target.execute_adb_command(["shell", "getprop", "ro.build.version.release"])
        result_output = result.stdout.decode("utf-8")
        logger.info(f"ADB command output: {result_output}")

        android_files_dir = create_custom_results_dir("android_files", self.extract_file_dir)
        file_path = os.path.join(android_files_dir, "android_version.txt")
        with open(file_path, "w") as android_file:
            android_file.write(result_output)

        assert os.path.getsize(file_path) > 0, "The file should contain information about Android"

    def test_004_multiple_ecu(self):
        """
        Example of executing commands both on IDCEVO and ICON - Only possible in TRAAS rack
        """
        # Check version on IDCEVO
        result = self.traas_helper.execute_command_idcevo("cat /etc/os-release")
        logger.info("Result output: %s", result.stdout.decode("utf-8"))

        # Check version on ICON
        result = self.traas_helper.execute_command_icon("cat /etc/os-release")
        logger.info("Result output: %s", result.stdout.decode("utf-8"))

        # Read ECU-UID IDCEVO
        result = self.traas_helper.trigger_diag_job("idcevo", "22 80 00")
        logger.info("Result output: %s", result.stdout.decode("utf-8"))

        # Read ECU-UID ICON
        result = self.traas_helper.trigger_diag_job("icon", "22 80 00")
        logger.info("Result output: %s", result.stdout.decode("utf-8"))
