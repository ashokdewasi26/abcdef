# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""IOC dlt Post Tests"""
import logging
import os
from pathlib import Path


from mtee.testing.tools import assert_false, assert_true, metadata
from si_test_idcevo.si_test_config.ioc_error_msgs import SET_ERROR_MSGS
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase

logger = logging.getLogger(__name__)


class IOCDltPostTest(object):
    """IOC dlt Post Tests"""

    __test__ = True

    @classmethod
    def setup_class(cls):
        """setup_class"""
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)

    @metadata(
        testsuite=["SI-android", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="IDCEvo Test",
    )
    def test_ioc_dlt_raw(self):
        """Test if ioc dlt has error messages using raw dlt"""
        raw_msg_w_error_list = []
        errors_list = errors_list_total = ""

        self.ioc_dlt_path = Path(self.test.mtee_target.options.result_dir) / "serial_console_IOC.log_non_verbose.dlt"

        assert_true(os.path.isfile(self.ioc_dlt_path), "File log_non_verbose wasn't created")

        with open(self.ioc_dlt_path, mode="r", errors="replace") as f:
            log_file = f.read()
        dlt_msgs_list = log_file.split("DLT\x01")

        for dlt_msg in dlt_msgs_list:
            for set in SET_ERROR_MSGS:
                if any(error_msg in dlt_msg for error_msg in set["messages"]):
                    raw_msg_w_error_list.append(dlt_msg)

        if raw_msg_w_error_list:
            for set in SET_ERROR_MSGS:
                for error_msg in set["messages"]:
                    count = len(
                        [
                            raw_dlt_error_msg
                            for raw_dlt_error_msg in raw_msg_w_error_list
                            if error_msg in raw_dlt_error_msg
                        ]
                    )
                    if count > 0:
                        errors_list += str(f"\nFound {count} messages containing the error message '{error_msg}'")
                if errors_list:
                    errors_list_total += str(f"\nDomain {set['domain']}: {errors_list}")
                errors_list = ""
        errors_list_total = f"Found {len(raw_msg_w_error_list)} dlt messages with errors {errors_list_total}"
        assert_false(bool(raw_msg_w_error_list), errors_list_total)
