# Copyright (C) 2025. BMW CTW PT. All rights reserved.
"""Generic msgs collection from bootlog"""
import configparser
import csv
import inspect
import logging
import os
from pathlib import Path
from unittest import SkipTest

from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import assert_false, metadata
from si_test_idcevo.si_test_config.search_bootlog_config import LK_BOOTLOG_VERIFICATION
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.csv_handlers import CSVHandler


config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
target = TargetShare().target


class SearchLkBootlogMsgsPostTest(object):
    __test__ = True
    csv_file_path = Path(target.options.result_dir) / "extracted_files" / "dynamic_lk_logs.csv"

    def read_and_group_csv_results(self, csv_file_path):
        """
        Reads the CSV file, groups the results by Test Name, and checks for failures.

        Parameters:
        csv_file_path (str): Path to the CSV file.

        Returns:
        dict: A dictionary with test names as keys and a list of results as values.
        """
        grouped_results = {}

        with open(csv_file_path, mode="r", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                test_name = row["Test Name"]
                if test_name not in grouped_results:
                    grouped_results[test_name] = []
                grouped_results[test_name].append(row)

        return grouped_results

    def validate_patterns_from_csv(self, test_name, csv_file_path):
        """
        Validates patterns from the CSV file for each test name.

        Parameters:
        test_name (str): The name of the test to validate.
        csv_file_path (str): Path to the CSV file.
        """
        grouped_results = self.read_and_group_csv_results(csv_file_path)
        logs_found_list = []
        patterns_not_found = ""

        if test_name in grouped_results:
            for result in grouped_results[test_name]:
                status = result["Pass/Fail"]
                details = result["Details"]
                if status == "Failed":
                    patterns_not_found += f"Test Name: {test_name}\n"
                    patterns_not_found += f"  Command: {result['Command']}\n"
                    patterns_not_found += f"  Details: {details}\n"
                else:
                    logs_found_list.append(f"The test '{test_name}' passed.")

        return logs_found_list, patterns_not_found

    def generate_tests(self):
        for lk_test, settings in LK_BOOTLOG_VERIFICATION.items():
            logger.info(f"Generating test method for: '{lk_test}'...")

            feature_tickets_list = []
            for ticket in range(len(settings["feature"])):
                feature_tickets_list.append(config.get("FEATURES", settings["feature"][ticket]))

            @metadata(
                testsuite=["BAT", "domain", "SI"],
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
            def search_lk_msgs(test_name=lk_test, config=settings):
                """
                Test function template, used to search for bootlog messages defined in LK_BOOTLOG_VERIFICATION
                :param config: dict containing configurations needed for each SearchBootlogMsgs test.
                It corresponds to the items format of LK_BOOTLOG_VERIFICATION dict
                :return: assert if encountered at least one bootlog message
                """
                if not os.path.isfile(self.csv_file_path):
                    logger.info(
                        f"It appears this Ecu version, does not support the test.\
                                 Warning: {self.csv_file_path} not found."
                    )
                    raise SkipTest("CSV file not found.")

                logs_found_list, patterns_not_found = self.validate_patterns_from_csv(test_name, self.csv_file_path)

                csv_handler_obj = CSVHandler(test_name + ".csv", self.test.results_dir)
                csv_handler_obj.exports_list_to_csv(logs_found_list)

                error_message = f"\n\nError in {test_name} test.\nNo logs found for pattern(s):\n" + patterns_not_found
                assert_false(patterns_not_found, error_message)

            search_lk_msgs.__name__ = f"test_{lk_test}"
            search_lk_msgs.__doc__ = settings["docstring"]

            if inspect.ismethod(search_lk_msgs):
                search_lk_msgs.__func__.description = settings["docstring"].split("\n")[0]
            else:
                search_lk_msgs.description = settings["docstring"].split("\n")[0]

            yield search_lk_msgs, lk_test

    def __init__(self):
        logger.info("Starting search logs tests.")

        for test_func, _ in self.generate_tests():
            logger.info(f"Generated method: '{test_func.__name__}'")

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)
