# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Generic msgs collection from bootlog"""
import configparser
import inspect
import logging
import re
from pathlib import Path
from unittest import skipIf

from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import assert_false, metadata
from si_test_idcevo import METRIC_EXTRACTOR_ARTIFACT_PATH
from si_test_idcevo.si_test_config.search_bootlog_config import BOOTLOG_VERIFICATION
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.csv_handlers import CSVHandler

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
target = TargetShare().target
target_name = target.options.target


class SearchBootlogMsgsPostTest(object):
    __test__ = True

    def generate_tests(self):
        for bootlog_test, settings in BOOTLOG_VERIFICATION.items():
            logger.info(f"Generating test method for: '{bootlog_test}'...")

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
            @skipIf(
                not re.match(settings["hardware revision"][target_name], target.options.hardware_revision),
                f"This test is not to be run on {target.options.hardware_revision} samples",
            )
            @skipIf(
                "idcevo" in target.options.target,
                "Debugfs has been disabled at this stage of development lifecycle, cannot proceed with bootlog tests",
            )
            def search_bootlog_msgs(test_name=bootlog_test, config=settings):
                """
                Test function template, used to search for bootlog messages defined in BOOTLOG_VERIFICATION
                :param config: dict containing configurations needed for each SearchBootlogMsgs test.
                It corresponds to the items format of BOOTLOG_VERIFICATION dict
                :return: assert if encountered at least one bootlog message
                """
                patterns_not_found = ""
                logs_found_list = []

                for pattern in config["pattern"]:
                    for msg in pattern:
                        if re.search(msg, self.logs_content):
                            logs_found_list.append(f"The pattern '{msg}' was found on bootlog")
                        else:
                            patterns_not_found += "- " + msg + "\n"

                csv_handler_obj = CSVHandler(test_name + ".csv", self.test.results_dir)
                csv_handler_obj.exports_list_to_csv(logs_found_list)

                error_message = f"\n\nError in {test_name} test.\nNo logs found for pattern(s):\n" + patterns_not_found
                assert_false(patterns_not_found, error_message)

            search_bootlog_msgs.__name__ = f"test_{bootlog_test}"
            search_bootlog_msgs.__doc__ = settings["docstring"]

            if inspect.ismethod(search_bootlog_msgs):
                search_bootlog_msgs.__func__.description = settings["docstring"]
            else:
                search_bootlog_msgs.description = settings["docstring"]

            yield search_bootlog_msgs, bootlog_test

    def __init__(self):
        logger.info("Starting search logs tests.")

        for test_func, _ in self.generate_tests():
            logger.info(f"Generated method: '{test_func.__name__}'")

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)

        node0_bootlog_filepath = (
            Path(cls.test.mtee_target.options.result_dir) / METRIC_EXTRACTOR_ARTIFACT_PATH / "node0_bootlog.txt"
        )

        hypervisor_logs_filepath = (
            Path(cls.test.mtee_target.options.result_dir) / METRIC_EXTRACTOR_ARTIFACT_PATH / "hypervisor_history.txt"
        )

        if node0_bootlog_filepath.exists():
            with open(node0_bootlog_filepath, "r") as file_handler:
                cls.node0_bootlog_content = file_handler.read()
        else:
            logger.error(f"{node0_bootlog_filepath} does not exist")
            cls.node0_bootlog_content = ""

        if hypervisor_logs_filepath.exists():
            with open(hypervisor_logs_filepath, "r") as file_handler:
                cls.hypervisor_logs_content = file_handler.read()
        else:
            logger.error(f"{hypervisor_logs_filepath} does not exist")
            cls.hypervisor_logs_content = ""

        cls.logs_content = cls.node0_bootlog_content + cls.hypervisor_logs_content
