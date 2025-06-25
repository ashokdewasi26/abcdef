# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Check for failures which caused a recovery event"""
import configparser
import csv
import logging
import os
import re
from pathlib import Path

from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import metadata
from si_test_idcevo import INPUT_CSV_FILE, LIFECYCLES_PATH
from si_test_idcevo.si_test_helpers.csv_handlers import CSVHandler

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)


APID_FILTER = "RECM"
CTID_FILTER = "RECO"
PAYLOAD_FILTER = "recovery event"


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
class RecoveryEventPostTest(object):

    __test__ = True

    target = TargetShare().target

    @classmethod
    def setup_class(cls):
        if cls.target:
            lifecyle_full_path = os.path.join(cls.target.options.result_dir, LIFECYCLES_PATH)

            csv_handler = CSVHandler(INPUT_CSV_FILE)
            # gets list containing all csv files path
            cls.files_path = csv_handler.get_csv_files_path(lifecyle_full_path)

    def test_001_recovery_event(self):
        """[SIT_Automated] Check for recovery events with action field different from 'none'
        resorting on dlt_list_of_interest_android plugin"""

        logger.info("Starting recovery event post test.")
        recovery_events_found = {}
        error_message = "The following recovery event(s) were found in the listed lifecycles:"

        for csv_file in self.files_path:
            with open(csv_file) as f:
                reader = csv.DictReader(f)

                for row in reader:
                    if (row["apid"] == APID_FILTER) and (row["ctid"] == CTID_FILTER):
                        if PAYLOAD_FILTER in row["payload"].lower():
                            # search for an expression comprised between 'action' and ']'
                            payload_filtered = re.search(r"action(.+?)\]", row["payload"].lower())

                            if payload_filtered:
                                try:
                                    if "none" not in payload_filtered.group(1):
                                        # add recovery event to dict keys, in case does not exist yet
                                        if row["payload"] not in recovery_events_found:
                                            recovery_events_found[row["payload"]] = []

                                        # lifecycle folder is located on the penultimate position [-2] of the file path
                                        # e.g. [..., 'extracted_files', 'Lifecycles', '02', 'dlt_msgs_of_interest.csv']
                                        current_lifecycle = csv_file.split(os.sep)[-2]

                                        if current_lifecycle not in recovery_events_found[row["payload"]]:
                                            recovery_events_found[row["payload"]].append(current_lifecycle)

                                except IndexError as error:
                                    aux = row["payload"]
                                    logger.info(f"An exception was raised: {aux}")
                                    logger.error(error)

        if len(self.files_path) == 0:
            recovery_events_found["Error"] = "No csv file(s) were found."
            error_message = "An error was encountered while running 'test_001_recovery_event':"

        assert len(recovery_events_found) == 0, error_message + f" {recovery_events_found}"
