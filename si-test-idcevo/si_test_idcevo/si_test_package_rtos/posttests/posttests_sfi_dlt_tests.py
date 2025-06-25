# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Check that there are no SFI related error messages in DLT SOC logs."""
import configparser
import csv
import logging
import os
import re
from pathlib import Path

from mtee.testing.tools import metadata
from si_test_idcevo import INPUT_CSV_FILE, LIFECYCLES_PATH
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.csv_handlers import CSVHandler

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

APID_FILTER = "LOGM"
CTID_FILTER = "INTER"
SFI_ERROR_MSG = "processReadDatamcipc open failed"


@metadata(
    testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
    component="tee_idcevo",
    domain="RTOS",
    asil="None",
    testmethod="Analyzing Requirements",
    testtype="Requirements-based test",
    testsetup="SW-Component",
    categorization="functional",
    priority="1",
    duplicates="IDCEVODEV-8469",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": config.get("FEATURES", "INTER_NODE_COMMUNICATION_SFI_LINUX_COMMUNICATION"),
        },
    },
)
class SFIDLTPostTest(object):

    __test__ = True

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)
        lifecyle_full_path = os.path.join(cls.test.mtee_target.options.result_dir, LIFECYCLES_PATH)
        csv_handler = CSVHandler(INPUT_CSV_FILE)
        # gets list containing all csv files path
        cls.files_path = csv_handler.get_csv_files_path(lifecyle_full_path)

    def test_001_inc_communication_sfi(self):
        """
        [SIT_Automated]  Check that there are no SFI related error messages in DLT SOC logs

        Steps:
            1 - Find rows with SFI error message
            2 - Assert if lifecycle's INPUT_CSV_FILE were found
            3 - Validate no error message is found
        """

        error_detected = False
        error_message_files = []
        pattern = re.compile(r"SFIReader_Plugin:")

        number_lifecycles = len(self.files_path)
        assert number_lifecycles > 0, "An error occurred while running 'test_001_inc_communication_sfi': No csv found."

        for csv_file in self.files_path:
            with open(csv_file) as f:
                reader = csv.DictReader(f)

                for row in reader:
                    if (
                        (row["apid"] == APID_FILTER)
                        and (row["ctid"] == CTID_FILTER)
                        and pattern.search(row["payload"])
                    ):
                        if SFI_ERROR_MSG in row["payload"]:
                            error_message_files.append(csv_file)
                            error_detected = True
                            break

        assert (
            not error_detected
        ), f"The error message '{SFI_ERROR_MSG}' was found in the CSV files - '{error_message_files}'"
