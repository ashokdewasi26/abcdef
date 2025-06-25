# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Test robustness of the system between switching modes of APP and Bolo"""
import configparser
import datetime
import logging
import random
import re
import time
from pathlib import Path

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import assert_equal, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.report_helpers import RobustnessLifecycleReporter

target = TargetShare().target
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

REBOOT_MODES = ["APP", "BOL"]


class TestsRobustnessSwitchingModes(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)

        cls.modes_mapping = {
            "APP": {
                "reboot_function": cls.test.mtee_target.boot_into_appl,
                "message_mode": "Application",
            },
            "BOL": {
                "reboot_function": cls.test.mtee_target.boot_into_flashing,
                "message_mode": "Bootloader",
            },
        }

        cls.prev_boot_mode, cls.boot_mode = "", ""
        cls.expected_mode, cls.wakeup_reason = "", ""
        cls.error_msg = ""
        cls.waiting_time = 0

        cls.msg_filters = [
            {
                "apid": "NSG",
                "ctid": "NSG",
                "payload_decoded": re.compile(r"\[MARKER\] Got the wakeUpReason from IOLifecycleProxy:.*"),
            }
        ]

        cls.report_filename = "robustness_switch_modes_report.json"

        cls.reporter = RobustnessLifecycleReporter(
            test_name="robustness_switch_modes_tests",
            description="Test report for robustness on switching randomly between APP and Bolo modes",
            report_filename=cls.report_filename,
        )

    def verify_wakeupreason(self, dlt_msg):
        """
        Verify wakeup reason after reboot
        """
        msg_pattern = re.compile(r"\[MARKER\] Got the wakeUpReason from IOLifecycleProxy: (.*?) # .*")
        message_mode = self.modes_mapping[self.expected_mode].get("message_mode", "")

        if dlt_msg:
            match = re.search(msg_pattern, dlt_msg[0].payload_decoded)
            if match:
                wakeup_reason_found = match.group(1)
                if wakeup_reason_found == message_mode:
                    self.wakeup_reason = wakeup_reason_found

    def reboot_randomly_between_modes(self):
        """
        Reboot target randomly according to the reboot_mode and point of time
        after ECU can starting receive requests
        """
        self.prev_boot_mode = self.boot_mode
        self.boot_mode = ""
        self.wakeup_reason = ""

        self.waiting_time = random.randint(0, 300)  # between 0 and 5 minutes
        self.expected_mode = random.choice(REBOOT_MODES)

        reboot_function = self.modes_mapping[self.expected_mode].get("reboot_function", "")

        logger.debug(f"Rebooting target from {self.prev_boot_mode} to {self.expected_mode} mode")
        logger.debug(f"Waiting time to reboot: {self.waiting_time} seconds")
        time.sleep(self.waiting_time)
        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("NSG", "NSG")]) as trace:
            try:
                reboot_function()
            except Exception as err:
                logger.debug(f"Reboot failed: {err}")
                self.error_msg = f"{err}"
                return

            dlt_msg = trace.wait_for_multi_filters(
                filters=self.msg_filters,
                timeout=60,
                count=1,
                drop=True,
            )
            self.verify_wakeupreason(dlt_msg)

            self.test.mtee_target.wait_for_boot_mode()
            self.boot_mode = self.test.mtee_target.connectors.dlt.monitor.boot_mode

    def add_error_msg(self, summary):
        """
        Add error message to the summary in case of failure of reboot.
        Will check if the wakeup_reason is empty and the boot_mode is different
        from the expected_mode
        """
        if self.error_msg:
            summary["error_message"] = self.error_msg
        elif not summary.get("reboot_success"):
            error_msg = ""
            if not self.wakeup_reason:
                error_msg += "Failure on verifying wakeup reason after rebooting."
            if self.expected_mode != self.boot_mode:
                error_msg += "Expected mode and boot mode don't match."
            summary["error_message"] = error_msg

        self.error_msg = ""
        return summary

    def add_boot_cycle_summary_on_report(self, cycle_num, test_status):
        """
        Add boot cycle summary on the report
        """
        boot_cycle_summary = {
            "reboot_success": test_status,
            "previous_boot_mode": self.prev_boot_mode,
            "expected_boot_mode": self.expected_mode,
            "boot_mode": self.boot_mode,
            "wakeup_reason": self.wakeup_reason,
            "waiting_time": self.waiting_time,
        }

        boot_cycle_summary = self.add_error_msg(boot_cycle_summary)

        self.reporter._add_boot_cycle_summary(
            cycle_num,
            boot_cycle_summary,
        )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-94145",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "FLASHING_MIRROR_PROTOCOL"),
                    config.get("FEATURES", "SHUTDOWN_ECU_RESET"),
                ],
            },
        },
    )
    def test_001_switching_modes(self):
        """
        [SIT_Automated] Test robustness of switching between App and Bolo modes

        Precondition:
            - Test must run for 3h, and stop in the next LC after the 3h has been achieved.

        Steps:
            1 - Request reset to APP or Bolo mode randomly and at different point
            of time (0 to 5 mins from the point the ECU can start accepting requests)
            2 - Check startup with the right wakeup reason
            3 - Check startup in the expected mode
            4 - In case of failure continue with the test sequence
        """
        num_of_tries = 0
        to_break = False
        initial_time = time.time()
        run_total_time = 3 * 60 * 60  # 3 hours
        while not to_break:
            if time.time() - initial_time >= run_total_time:
                to_break = True
            num_of_tries += 1
            self.reboot_randomly_between_modes()
            logger.debug(
                f"Try number: {num_of_tries} \n"
                f"Expected mode: {self.expected_mode}, Boot mode: {self.boot_mode} \n"
                f"Wakeup reason: {self.wakeup_reason}"
            )
            test_status = (self.expected_mode == self.boot_mode) and bool(self.wakeup_reason)
            if not test_status:
                self.reporter.num_reboot_failed += 1
            self.add_boot_cycle_summary_on_report(num_of_tries, test_status)

        total_time_elapsed_sec = time.time() - initial_time
        self.reporter.total_execution_time = str(datetime.timedelta(seconds=total_time_elapsed_sec))
        self.reporter.num_reboot = num_of_tries

        self.reporter.add_report_summary()

        assert_equal(
            self.reporter.num_reboot_failed,
            0,
            f"Reboots failed: {self.reporter.num_reboot_failed}. \n"
            f"Check the reports/{self.report_filename} file for more details.",
        )
