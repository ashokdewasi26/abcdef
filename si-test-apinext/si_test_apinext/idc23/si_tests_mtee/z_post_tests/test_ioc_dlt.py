# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""System integration Post Tests

This test is a copy of
ascgit487.si-test-mgu22/si_tests_mgu22/si_test_package_ioc_idc23/posttests/posttests_ioc_dlt_tests.py
The reason for this is because in this repo we don't have the mechanisms to run post-tests in place,
so the alternative is to run this as a normal test, by placing it on a folder with a naming that makes it
run last (like 'z_post_tests')
So this should be considered a temporary workaround until we are able to either run post-tests with our tests
(defined in this repo) or to pack our tests and run them by calling a test suite
"""
import logging
import os
from unittest import skipIf

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.test_environment import require_environment
from mtee.testing.tools import assert_false, assert_true, metadata

logger = logging.getLogger(__name__)
target = TargetShare().target

ERROR_MSGS = [
    "DTC reported to RTE newly",
    "EventCollector called with Error",
    "Error reported to EventCollector",
    "Integrity fault, Event Collector called with Error",
    "Error counter = ru8MaxErrorCounter -> nenTimedEntityExpired",
    "Reset counter retrieved: 1",
]

DTCs = [
    "0xB7FB49",
    "0xB7FB42",
    "0xB7FB48",
    "0xB7FB43",
    "0xB7FB4B",
    "0xB7FBA3",
    "0xB7FB7E",
    "0xB7FB78",
    "0xB7FB41",
    "0xB7FB44",
    "0xB7FB45",
    "0xB7FB46",
    "0xB7FB5F",
    "0xB7FB61",
    "0xB7FB63",
    "0xB7FB64",
    "0xB7FB65",
    "0xB7FB66",
    "0xB7FB67",
    "0xB7FB90",
    "0xB7FB8F",
    "0xB7FB9A",
    "0xB7FB98",
    "0xB7FB60",
    "0xB7FB71",
]

IOC_DLT_PATH = os.path.join(
    target.options.result_dir,
    "serial_console_IOC.log.dlt",
)


@require_environment(TE.target.hardware.idc23)
@metadata(
    testsuite=["BAT", "SI", "SI-long", "SI-android", "SI-long-android"],
)
class SystemIntegrationPostTest(object):
    """System integration Post Tests"""

    __test__ = True

    @classmethod
    def setup_class(cls):
        """setup_class"""
        # Assert file
        assert_true(os.path.isfile(IOC_DLT_PATH))

    @skipIf(not target.has_capability(TE.target.hardware.idc23), "Test not applicable for this ECU")
    def test_ioc_dlt_raw(self):
        """Test if ioc dlt has error messages or DTCs using raw dlt"""
        raw_msg_w_error_list = []
        errors_list = ""

        with open(IOC_DLT_PATH, mode="r", errors="replace") as f:
            log_file = f.read()
        dlt_msgs_list = log_file.split("DLT\x01")

        for dlt_msg in dlt_msgs_list:
            if any(error_msg in dlt_msg for error_msg in ERROR_MSGS):
                raw_msg_w_error_list.append(dlt_msg)
            if any(dtc_msg in dlt_msg for dtc_msg in DTCs):
                raw_msg_w_error_list.append(dlt_msg)

        if raw_msg_w_error_list:
            # Count the number of dlt messages for each error message
            for error_msg in ERROR_MSGS:
                count = len(
                    [raw_dlt_error_msg for raw_dlt_error_msg in raw_msg_w_error_list if error_msg in raw_dlt_error_msg]
                )
                errors_list += str(f"\nFound {count} messages containing the error message '{error_msg}'")
        errors_list = f"Found {len(raw_msg_w_error_list)} dlt messages with errors:" + errors_list
        assert_false(bool(raw_msg_w_error_list), errors_list)
