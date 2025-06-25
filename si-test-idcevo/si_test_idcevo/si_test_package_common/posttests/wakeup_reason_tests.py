# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Check for unexpected wakeup reasons caused by SW or HW failures"""
import configparser
import csv
import logging
import os
from pathlib import Path

from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import metadata
from si_test_idcevo import INPUT_CSV_FILE, LIFECYCLES_PATH
from si_test_idcevo.si_test_helpers.csv_handlers import CSVHandler

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

APID_FILTER = "HWAb"
CTID_FILTER = "IOLI"
EXPECTED_WAKEUP_REASONS_LIST = [
    "WAKEUP_REASON_APPLICATION",
    "WAKEUP_REASON_SWITCH_TO_POWER",
    "WAKEUP_REASON_SYSTEM_RESET",
    "WAKEUP_REASON_ETHERNET_ACTIVE",
    "WAKEUP_REASON_CAN_BUS_ACTIVE",
    "WAKEUP_REASON_BOOTLOADER",
    "WAKEUP_REASON_CUSTOMER_RESET",
    "WAKEUP_REASON_REMOTE_UPDATE",
    "WAKEUP_REASON_OVERTEMPERATURE",
    "WAKEUP_REASON_HARD_SYSTEM_RESET",
    "WAKEUP_REASON_FACTORY_RESET_JOB",
    "WAKEUP_REASON_FACTORY_RESET_USER",
    "WAKEUP_REASON_GRACEFUL_POWER_OFF",
    "WAKEUP_REASON_ECU_RESET",
    "WAKEUP_REASON_TOUCH",
    "WAKEUP_REASON_APIX",
]
UNEXPECTED_WAKEUP_REASONS_LIST = [
    "WAKEUP_REASON_UNKNOWN",
    "WAKEUP_REASON_ERROR_RESET",
    "WAKEUP_REASON_HARD_ERROR_RESET",
    "WAKEUP_REASON_WATCHDOG_RESET",
    "WAKEUP_REASON_KERNEL_CRASH",
    "WAKEUP_REASON_FACTORY_RESET_RECOVERY",
    "WAKEUP_REASON_IOC_WATCHDOG_RESET",
    "WAKEUP_REASON_IC_SAFETY_VIOLATION_RESET_BLANK",
    "WAKEUP_REASON_IC_SAFETY_VIOLATION_RESET_INTERNAL",
    "WAKEUP_REASON_NOT_SET",
]


@metadata(
    testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
    component="tee_idcevo",
    domain="Stability",
    asil="None",
    testmethod="Analyzing Requirements",
    testtype="Requirements-based test",
    testsetup="SW-Component",
    categorization="functional",
    priority="1",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": config.get("FEATURES", "STABILITY_KPI_MONITORING"),
        },
    },
)
class UnexpectedWakeupReasonPostTest(object):

    __test__ = True

    target = TargetShare().target

    @classmethod
    def setup_class(cls):
        if cls.target:
            lifecyle_full_path = os.path.join(cls.target.options.result_dir, LIFECYCLES_PATH)

            csv_handler = CSVHandler(INPUT_CSV_FILE)
            # gets list containing all csv files path
            cls.files_path = csv_handler.get_csv_files_path(lifecyle_full_path)
            # Remove dlt_msgs_of_interest.csv for lifecycle 00, it is unpredictable
            lifecycle_00 = f"{lifecyle_full_path}/00/dlt_msgs_of_interest.csv"
            if lifecycle_00 in cls.files_path:
                cls.files_path.remove(lifecycle_00)
                logger.info("Will not search for wakeup reason for lifecycle 00.")

    def test_001_unexpected_wakeup_reason(self):
        """
        [SIT_Automated] Check all wakeup reasons and assert if any are unexpected or missing

        Steps:
            1 - Find rows with wake up reason
            2 - Check if wakeup reason is expected, unexpected or unlisted
            3 - Assert if lifecycle's INPUT_CSV_FILE were found
            4 - Assert if any wakeup reason was not found in known lists
            5 - Assert if any unexpected wakeup reason was found
            6 - Assert if the number of expected wakeup reasons is the same as lifecycles
        """

        logger.info("Starting Unexpected wakeup reason post test.")
        unexpected_wakeup_reasons_found = {}
        expected_wakeup_reasons_counter = 0
        wakeup_reason_not_listed = 0
        error_row = {}

        for csv_file in self.files_path:
            with open(csv_file) as f:
                reader = csv.DictReader(f)

                # search for reasons specified at EXPECTED_WAKEUP_REASONS_LIST and UNEXPECTED_WAKEUP_REASONS_LIST
                for row in reader:
                    if (
                        (row["apid"] == APID_FILTER)
                        and (row["ctid"] == CTID_FILTER)
                        and ("WAKEUP REASON:" in row["payload"].upper())
                    ):
                        if any(
                            wakeup_reason in row["payload"].upper() for wakeup_reason in UNEXPECTED_WAKEUP_REASONS_LIST
                        ):
                            # add unexpected wakeup reason to dict keys, in case does not exist yet
                            if row["payload"] not in unexpected_wakeup_reasons_found:
                                unexpected_wakeup_reasons_found[row["payload"]] = []

                            # lifecycle folder is located on the penultimate position ([-2]) of the file path
                            # (e.g. [..., 'extracted_files', 'Lifecycles', '02', 'dlt_msgs_of_interest.csv'])
                            current_lifecycle = csv_file.split(os.sep)[-2]

                            if current_lifecycle not in unexpected_wakeup_reasons_found[row["payload"]]:
                                unexpected_wakeup_reasons_found[row["payload"]].append(current_lifecycle)
                        elif any(
                            wakeup_reason in row["payload"].upper() for wakeup_reason in EXPECTED_WAKEUP_REASONS_LIST
                        ):
                            expected_wakeup_reasons_counter += 1
                        else:
                            # Raise a flag if a wakeup reason is found that isnt in expected and unexpected lists
                            error_row[row["payload"]] = []
                            wakeup_reason_not_listed = 1

        number_lifecycles = len(self.files_path)
        unexpected_wakeup_reasons_counter = sum(len(list) for list in unexpected_wakeup_reasons_found.values())

        result_str = f"{number_lifecycles}/{expected_wakeup_reasons_counter}/{unexpected_wakeup_reasons_counter}"
        logger.info(f"Number of lifecycles/expected wakeups/unexpected wakeups: {result_str}")

        assert (
            number_lifecycles > 0
        ), "An error occurred while running 'test_001_unexpected_wakeup_reason': No csv found."
        assert wakeup_reason_not_listed == 0, (
            "Error: Wakeup reason not in known lists. Related to DLT messages:" + f" {error_row}"
        )
        assert len(unexpected_wakeup_reasons_found) == 0, (
            "Error: The following unexpected wakeup reason(s) were found:" + f" {unexpected_wakeup_reasons_found}"
        )
        # If the above assert passes, the number of expected wakeup reasons should be
        # the same as the number of lifecycles
        assert (
            expected_wakeup_reasons_counter == number_lifecycles
        ), "Error: Number of wakeup messages does not match number of lifecycles."
