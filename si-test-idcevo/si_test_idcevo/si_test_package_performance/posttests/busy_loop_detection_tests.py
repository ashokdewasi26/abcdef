# Copyright (C) 2025. BMW CTW PT. All rights reserved.
"""BusyLoop Detection post tests"""
import configparser
import logging
import os
from pathlib import Path

from mtee.testing.tools import metadata
from si_test_idcevo import INPUT_CSV_FILE, LIFECYCLES_PATH
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.csv_handlers import CSVHandler
from si_test_idcevo.si_test_helpers.dlt_logs_handlers import DLTLogsHandler

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)


@metadata(testsuite=["SI", "SI-performance", "IDCEVO-SP21"])
class BusyLoopDetectionPostTest(object):
    __test__ = True

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)
        lifecyle_full_path = os.path.join(cls.test.mtee_target.options.result_dir, LIFECYCLES_PATH)
        csv_handler = CSVHandler(INPUT_CSV_FILE)
        cls.files_path = csv_handler.get_csv_files_path(lifecyle_full_path, ["00"])
        cls.dlt_logs_handler = DLTLogsHandler(logger, cls.files_path)

    def search_busy_loop_logs(self, config, test_name):
        """
        Parse 'dlt_msgs_of_interest.csv' in all Lifecycles and search for DLT logs that match the given config.
        :param config: dict containing the DLT configuration parameters to search for
        :return: assert that no DLT messages with the given configuration are found
        """
        logs_found = self.dlt_logs_handler.parse_dlt_logs(config, detailed_payload=True)
        logs_found_list = []
        error_message = ""
        maximum_number_of_payloads_to_output = 10
        error_message = "The following Busy Loop logs were detected during test execution:\n"

        for payload, list_lifecycles_found in logs_found.items():
            logs_found_list.append(f"The payload '{payload}' was found on lifecycles: {list_lifecycles_found}")
            if maximum_number_of_payloads_to_output:
                error_message += f"'{payload}'\n"
                maximum_number_of_payloads_to_output -= 1

        csv_handler_obj = CSVHandler(test_name + ".csv", self.test.results_dir)
        csv_handler_obj.exports_list_to_csv(logs_found_list)

        error_message += "\nCheck results/busy_loop_detection_tests/.csv for more information."

        assert not logs_found_list, error_message

    def test_001_busy_loop_detection_node0(self):
        """
        [SIT_Automated] BusyLoop Detection - Node0

        Steps:
            1 - Define DLT Busy Loop message parameters for Node0
            2 - Search for Busy Loop messages in all 'dlt_msgs_of_interest' csv's

        Expected outcome:
            1 - No Busy Loop messages are found in 'dlt_msgs_of_interest'
        """
        node0_loop_messages_config = {
            "apid": ["MON"],
            "ctid": ["LOOP"],
            "pattern": [
                [r".*on cpu.*"],
            ],
        }
        self.search_busy_loop_logs(node0_loop_messages_config, "busy_loop_detection_node0")

    def test_002_busy_loop_detection_android(self):
        """
        [SIT_Automated] BusyLoop Detection - Android

        Steps:
            1 - Define DLT Busy Loop message parameters for Android
            2 - Search for Busy Loop messages in all 'dlt_msgs_of_interest' csv's

        Expected outcome:
            1 - No Busy Loop messages are found in 'dlt_msgs_of_interest'
        """
        android_loop_messages_config = {
            "apid": ["AMON"],
            "ctid": ["LOOP"],
            "pattern": [
                [r".*on cpu.*"],
            ],
        }
        self.search_busy_loop_logs(android_loop_messages_config, "busy_loop_detection_android")
