# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Generic DLT msgs collection from DLT log"""
import configparser
import inspect
import logging
import os
from pathlib import Path

from mtee.testing.tools import assert_false, metadata
from si_test_idcevo import INPUT_CSV_FILE, LIFECYCLES_PATH
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.csv_handlers import CSVHandler
from si_test_idcevo.si_test_helpers.dlt_logs_handlers import DLTLogsHandler

try:
    from .search_dlt_log_config import DLT_LOG_VERIFICATION
except ImportError:
    from search_dlt_log_config import DLT_LOG_VERIFICATION

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

DLT_LOGS_PATH = os.path.join("extracted_files", "search_logs_tests")


class SearchDLTLogsPostTest(object):

    __test__ = True

    def generate_tests(self):
        for dlt_log_test, settings in DLT_LOG_VERIFICATION.items():
            logger.info(f"Generating test method for: '{dlt_log_test}'...")

            feature_tickets_list = []
            for ticket in range(len(settings["feature"])):
                feature_tickets_list.append(config.get("FEATURES", settings["feature"][ticket]))

            @metadata(
                testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
                component="tee_idcevo",
                domain=settings["domain"],
                asil="None",
                testmethod="Analyzing Requirements",
                testtype="Requirements-based test",
                testsetup="SW-Component",
                categorization="functional",
                priority="1",
                duplicates=settings["duplicates"],
                traceability={
                    config.get("tests", "traceability"): {
                        "FEATURE": feature_tickets_list,
                    },
                },
                test_case_description_docstring=settings["docstring"],
            )
            def search_dlt_logs(test_name=dlt_log_test, config=settings):
                """
                Test function template, used to search for DLT log messages defined in DLT_LOG_VERIFICATION
                :param config: dict containing configurations needed for each SearchDLTLogs test.
                It corresponds to the items format of DLT_LOG_VERIFICATION dict
                :return: assert if encountered at least one DLT log for each lifecycle
                """

                logs_found = self.dlt_logs_handler.parse_dlt_logs(config)
                patterns_not_found = ""
                logs_found_list = []
                for pattern, list_lifecycles_found in logs_found.items():
                    logs_found_list.append(f"The pattern '{pattern}' was found on lifecycles: {list_lifecycles_found}")
                    if not list_lifecycles_found:
                        patterns_not_found += "- " + pattern + "\n"

                dir_path = os.path.join(self.test.mtee_target.options.result_dir, DLT_LOGS_PATH)
                csv_handler_obj = CSVHandler(test_name + ".csv", dir_path)
                csv_handler_obj.exports_list_to_csv(logs_found_list)

                error_message = f"\n\nError in {test_name} test.\nNo logs found for pattern(s):\n" + patterns_not_found
                assert_false(patterns_not_found, error_message)

            search_dlt_logs.__name__ = f"test_{dlt_log_test}"
            search_dlt_logs.__doc__ = settings["docstring"]

            if inspect.ismethod(search_dlt_logs):
                search_dlt_logs.__func__.description = settings["docstring"]
            else:
                search_dlt_logs.description = settings["docstring"]

            yield search_dlt_logs, dlt_log_test

    def __init__(self):
        logger.info("Starting search logs tests.")

        for test_func, _ in self.generate_tests():
            logger.info(f"Generated method: '{test_func.__name__}'")

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)
        lifecyle_full_path = os.path.join(cls.test.mtee_target.options.result_dir, LIFECYCLES_PATH)
        csv_handler = CSVHandler(INPUT_CSV_FILE)
        # gets list containing all csv files path
        cls.files_path = csv_handler.get_csv_files_path(lifecyle_full_path)
        cls.dlt_logs_handler = DLTLogsHandler(logger, cls.files_path)
