# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Verify if correct log level is passed to kernel by LK boot loader via kernel command line"""
import configparser
import logging
from pathlib import Path
from unittest import skipIf

from mtee.testing.tools import assert_equal, assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.parsing_handlers import extracts_target_variable_from_string
from si_test_idcevo.si_test_helpers.test_helpers import skip_unsupported_ecus

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

# Get the value of 'loglevel' variable
REGEX_EXP_GET_LOGLEVEL_VALUE = r"loglevel=([^\s]+)"
# Get the value of 'log_buf_len' variable
REGEX_EXP_GET_LOG_BUF_LEN_VALUE = r"log_buf_len=([^\s]+)"

TARGET_LOGLEVEL_VALUE = "3"
TARGET_LOG_BUF_LEN_VALUE = "4096K"


@metadata(
    testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
    component="tee_idcevo",
    domain="LinuxOS",
    asil="None",
    testmethod="Analyzing Requirements",
    testtype="Requirements-based test",
    testsetup="SW-Component",
    categorization="functional",
    priority="1",
    duplicates="IDCEVODEV-7066",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": config.get("FEATURES", "GENERAL_INFRASTRUCTURE_LOG_AND_TRACE"),
        },
    },
)
class TestsVerifyKernelLogs(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)

    def _check_kernel_log_value(
        self, kernel_log_obtained_string, regex_pattern, kernel_log_expected_value, variable_name
    ):
        """
        Compares obtained kernel log variable value with target value.
        :param kernel_log_string: string containing the obtained kernel log.
        :param regex_pattern: regex pattern to extract target value from kernel log string.
        :param kernel_log_expected_value: kernel log variable target value.
        :param variable_name: kernel log target variable name.
        """

        kernel_log_parsed_value = extracts_target_variable_from_string(regex_pattern, kernel_log_obtained_string)
        assert_equal(
            kernel_log_parsed_value,
            kernel_log_expected_value,
            f"\nFailure: '{variable_name}' got value: '{kernel_log_parsed_value}' when was expecting:"
            + f" '{kernel_log_expected_value}'",
        )

    def test_001_verify_kernel_logs(self):
        """
        [SIT_Automated] Verify Log Level and Log Buffer Length in Kernel Command Line

        Steps:
            1 - Run following command to print kernel command line passed by boot loader:
                # cat /proc/cmdline
            2 - In the output check value of "loglevel" and "log_buf_len" parameters
            3 - Run following command to print kernel command line set via device tree
                # cat /sys/firmware/devicetree/base/chosen/bootargs
            4 - In the output check value of "loglevel" and "log_buf_len" parameters
        """

        logger.info("Starting test to verify kernel log level and log buffer length.")

        kernel_log_bootloader, _, _ = self.test.mtee_target.execute_command("cat /proc/cmdline")
        self._check_kernel_log_value(
            kernel_log_bootloader, REGEX_EXP_GET_LOGLEVEL_VALUE, TARGET_LOGLEVEL_VALUE, "loglevel"
        )
        self._check_kernel_log_value(
            kernel_log_bootloader, REGEX_EXP_GET_LOG_BUF_LEN_VALUE, TARGET_LOG_BUF_LEN_VALUE, "log_buf_len"
        )

        kernel_log_device_tree, _, _ = self.test.mtee_target.execute_command(
            "cat /sys/firmware/devicetree/base/chosen/bootargs"
        )
        self._check_kernel_log_value(
            kernel_log_device_tree, REGEX_EXP_GET_LOGLEVEL_VALUE, TARGET_LOGLEVEL_VALUE, "loglevel"
        )
        self._check_kernel_log_value(
            kernel_log_device_tree, REGEX_EXP_GET_LOG_BUF_LEN_VALUE, TARGET_LOG_BUF_LEN_VALUE, "log_buf_len"
        )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="LinuxOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-12817",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "KERNEL_CONFIGURATION"),
            },
        },
    )
    @skipIf(
        skip_unsupported_ecus(["idcevo"]),
        "The kernel configurations mentioned in this test are disabled for IDCEVO ecus. "
        "Please check: IDCEVODEV-324963",
    )
    def test_002_kernel_event_tracing_for_sched_group(self):
        """
        [SIT_Automated] Verify Kernel Events Tracing for SCHED Group

        Steps:
            1 - Enable tracing of scheduler events by using below cmd.
                # echo 1 > /sys/kernel/debug/tracing/events/sched/enable
            2 - Read trace file by using below cmd.
                # cat /sys/kernel/debug/tracing/trace | grep -m 30 -E 'sched_[st|wa]''
            3 - In the output, check whether scheduler events are present.
                Look for "sched_waking", "sched_wakeup", "sched_stat_runtime" strings.
        """
        sched_events = ["sched_waking", "sched_wakeup", "sched_stat_runtime"]

        logger.info("Enable tracing of scheduler events")
        return_stdout, _, _ = self.test.mtee_target.execute_command(
            "echo 1 > /sys/kernel/debug/tracing/events/sched/enable"
        )

        cmd = "cat /sys/kernel/debug/tracing/trace | grep -m 30 -E 'sched_[st|wa]'"
        res, _, _ = self.test.mtee_target.execute_command(args=cmd, timeout=60)

        logger.info(f"Scheduler trace o/p- {res}")

        assert_true(
            (sched_events[0] in str(res)) and (sched_events[1] in str(res)) and (sched_events[2] in str(res)),
            "Net events not present in cat trace as expected. String 'net_dev_queue' not present",
        )
