# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Tests for instrument cluster functions"""
import csv
import logging
import os
import re

from mtee.testing.tools import assert_true, metadata
from si_test_idcevo import INPUT_CSV_FILE, LIFECYCLES_PATH
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.csv_handlers import CSVHandler

logger = logging.getLogger(__name__)

ANDROID_BOOT_DONE = ".*\\[1\\]:MARKER KPI - kernel_init Done"
ICF_MSG_1 = "IC functions' registration completed\\."
ICF_MSG_2 = "Both Safety Processes found\\."
SETUP_DONE = "SETUP DONE. Starting tests."


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
    duplicates="IDCEVODEV-12227",
    traceability={""},
)
class ICFunctionsMsgsInDLTPostTest(object):

    __test__ = True

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

        cls.csv_handler = CSVHandler(INPUT_CSV_FILE)
        cls.lifecyle_full_path = os.path.join(cls.test.mtee_target.options.result_dir, LIFECYCLES_PATH)

        cls.csv_files_path = cls.get_lifecycle_files_after_setup_done(cls)
        cls.messages_to_check = [
            {"name": ANDROID_BOOT_DONE, "regex": re.compile(ANDROID_BOOT_DONE), "found": False},
            {
                "name": ICF_MSG_1,
                "regex": re.compile(ICF_MSG_1),
                "found": False,
                "missed_lifecycles": [],
                "lifecycles_to_analyze": [],
            },
            {
                "name": ICF_MSG_2,
                "regex": re.compile(ICF_MSG_2),
                "found": False,
                "missed_lifecycles": [],
                "lifecycles_to_analyze": [],
            },
        ]

    def get_lifecycle_files_after_setup_done(self):
        """
        Returns list containing all lifecycle's csv files path after SETUP_DONE message,
        which indicates test execution start.
        """
        return self.csv_handler.get_csv_files_after_given_string(self.lifecyle_full_path, SETUP_DONE)

    def test_001_search_for_ic_functions_dlt_msgs(self):
        """
        [SIT_Automated] Verify if IC-Functions is running properly after cold-boot

        Steps:
            1 - Look for boot completed messages in each lifecyle
            and at the same time look for IC functions started messages
            2 - If boot completed message is missing, append that LC to lifecycles_to_analyze
            or if specific msg is missing, append that LC to missed_lifecycles
        Expected Outcome:
            If boot complete message is present, and all
            IC functions messages are present, pass the test, otherwise it fails, printing an informative message
        """

        for csv_file in self.csv_files_path:
            with open(csv_file) as f:
                reader = csv.DictReader(f)
                current_lifecycle = csv_file.split(os.sep)[-2]

                for message in self.messages_to_check:
                    message["found"] = False

                for row in reader:
                    for message in self.messages_to_check:
                        if message["regex"].search(row["payload"]):
                            message["found"] = True

                for message in self.messages_to_check[1:]:
                    if self.messages_to_check[0]["found"]:
                        if not message["found"]:
                            message["missed_lifecycles"].append(current_lifecycle)
                    else:
                        if not message["found"]:
                            message["lifecycles_to_analyze"].append(current_lifecycle)

                if not self.messages_to_check[0]["found"]:
                    logger.info(f"Did not find boot complete msg in LC {current_lifecycle}.")

        # Create error message with lifecycle of missing messages
        missed_lifecycles_message = ""
        lifecycles_to_analyze_message = ""
        lifecycle_to_analyze_str = (
            "\nMessages below are missing from lifecycles that did not complete the boot procedure. "
            "This is unpredictable and each case should be manually reviewed to determine the cause."
        )

        for message in self.messages_to_check[1:]:
            if message["missed_lifecycles"]:
                missed_lifecycles_message += (
                    f'\nmessage "{message["name"]}" missing from LC with complete boot: '
                    + "/".join(str(num) for num in message["missed_lifecycles"])
                )
            if message["lifecycles_to_analyze"]:
                if lifecycle_to_analyze_str not in lifecycles_to_analyze_message:
                    lifecycles_to_analyze_message += lifecycle_to_analyze_str
                lifecycles_to_analyze_message += (
                    f'\nmessage "{message["name"]}" missing from LC with INCOMPLETE boot: '
                    + "/".join(str(num) for num in message["lifecycles_to_analyze"])
                )

        error_message = missed_lifecycles_message + lifecycles_to_analyze_message

        assert_true(error_message == "", error_message)
