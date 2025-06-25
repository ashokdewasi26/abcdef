# Copyright (C) 2022. BMW CTW. All rights reserved.
"""Test to reboot multiple times and verify stability"""
import csv
import logging
import os
import time
from pathlib import Path
from unittest import skipIf

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT, require_environment, require_environment_setup
from mtee.testing.tools import metadata

target = TargetShare().target
logger = logging.getLogger(__name__)
REQUIREMENTS = (TEST_ENVIRONMENT.target.hardware,)


@require_environment(*REQUIREMENTS)
class TestMultipleRebootPerformance:
    verification_startup_time = 5
    n_reboots = 10
    reboot_retries = 3

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def setup_class(cls):
        """Setup class"""
        cls.target_type = target.options.target
        cls.metric_extractors_definition_filepath = (
            Path(os.sep) / "resources" / "multiple_reboot" / "android_metric_extractors.json"
        )

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def teardown_class(cls):
        """Teardown class"""
        pass

    def raw_reboot(self):
        """Perform a raw reboot, meaning a cold reboot, using the power supply and not doing
        the common boot verification. Also start the ssh connection and apply adb workaround"""
        logger.info("Rebooting target using power supply")
        target.extract_metric_artifacts(extractors_definition_filepath=self.metric_extractors_definition_filepath)
        target.prepare_for_reboot()
        target._power_off()
        time.sleep(10)
        target._power_on()
        time.sleep(5)
        target.resume_after_reboot()
        target.apply_adb_workaround()
        logger.info("Target rebooted using raw_reboot")

    def log_to_csv(self, test_case_id, metric_id, timing_secs):
        csv_dir = os.path.join(target.options.result_dir, "extracted_files")
        csv_path = os.path.join(csv_dir, "test_reboot_kombi_boot_kpi.csv")
        csv_header = ["test_case_id", "metric_id", "timing_secs"]

        if not os.path.isdir(csv_dir):
            return

        with open(csv_path, mode="a") as csv_file:
            csv_writter = csv.DictWriter(csv_file, fieldnames=csv_header)
            if csv_file.tell() == 0:
                csv_writter.writeheader()
            csv_writter.writerow({csv_header[0]: test_case_id, csv_header[1]: metric_id, csv_header[2]: timing_secs})

    @metadata(duration="long", testbench=["farm", "rack"])
    @skipIf(
        not (
            target.has_capability(TEST_ENVIRONMENT.target.hardware.rse22)
            or target.has_capability(TEST_ENVIRONMENT.target.hardware.idc23)
        ),
        "Test not applicable for this ECU",
    )
    def test_001_execute_multiple_reboots(self):
        """Execute multiple reboots test"""
        logger.debug("Execution of multiple reboots test")
        for reboot in range(self.n_reboots):
            with DLTContext(target.connectors.dlt.broker, filters=[("ICHM", "HKPI")]) as dlt_detector:
                self.raw_reboot()
                target.wait_for_kpi_boot_completed_flag(wait_time=600)
                dlt_messages = dlt_detector.messages
                # Register kombi kpi boot
                kombi_boot_complete_str_list = ["firstImage", "First image shown"]
                for message in dlt_messages:
                    if any([kombi_str in message.payload_decoded for kombi_str in kombi_boot_complete_str_list]):
                        logger.debug(f"Found message: {message.payload_decoded}")
                        self.log_to_csv(
                            "execute_multiple_reboots", "kombi_boot_kpi_" + str(reboot + 1), str(message.tmsp)
                        )
            logger.debug("Performing reboot %s", reboot + 1)

    def test_002_target_in_idle_state(self):
        """target in idle for 10 min"""
        sleep_time = 10  # Set to 10 minutes
        logger.debug("Set target to idle for {} minutes".format(sleep_time))
        time.sleep(sleep_time * 60)
        logger.debug("End of interval of {} minutes in idle".format(sleep_time))
