# Copyright (C) 2025. BMW CTW PT. All rights reserved.
"""
System Software already automated tests - LK shell.

These tests were previously automated in the domain's repositories.

To add a new test to the 'LK_BOOTLOG_VERIFICATION' configuration, follow these steps:

1. Add the needed information to define the test in the `LK_BOOTLOG_VERIFICATION` dictionary:
   - `cmd`: The command to be executed in the LK shell to trigger the test.
   - `pattern`: A list of regular expressions that should match the expected output in the bootlog.
   - `domain`: The domain to which the test belongs (e.g., "System Software").
   - `docstring`: A brief description of the test, including the steps to be performed.
   - `feature`: A list of features that the test verifies.
   - `duplicates`: The ID of any duplicate tickets or issues related to this test.
   - `hardware revision`: A dictionary specifying the hardware revisions for which the test is applicable.

When the specified commands are executed, the patterns are searched for in the bootlog, and the result is recorded in
the `dynamic_lk_logs.csv` file. This CSV file will then be analyzed in the post-test `search_lk_tests.py` script.

"""
import configparser
import csv
import logging
import os
from pathlib import Path
from unittest import skipIf

from si_test_idcevo.si_test_config.search_bootlog_config import LK_BOOTLOG_VERIFICATION
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.lk_helper import enter_lk_shell_instance
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)


class TestslkMode(object):

    test = TestBase.get_instance()
    test.setup_base_class()
    extract_file_dir = test.mtee_target.options.result_dir + "/extracted_files"

    def execute_command_and_log_results(self, test_name, cmd, patterns, writer):
        """
        Executes the command and logs the results to dynamic_lk_logs.csv.

        Parameters:
        test_name (str): Name of the test.
        cmd (str): Command to execute.
        patterns (list): List of regex patterns to check in the output.
        writer (csv.writer): CSV writer to log results.
        """
        logger.info("executing test_name: %s, cmd: %s, patterns: %s", test_name, cmd, patterns)
        try:
            self.test.mtee_target.execute_console_command(cmd, timeout=60, block=False)
            for string in patterns:
                try:
                    match = self.test.mtee_target._console.wait_for_re(string, timeout=120)
                    if match:
                        writer.writerow([test_name, cmd, "Passed", ""])
                    else:
                        writer.writerow([test_name, cmd, "Failed", f"Missing patterns: {string}"])
                except TimeoutError:
                    logger.info("Failed to execute command due to the timeout")
                    writer.writerow([test_name, cmd, "Failed", "Timeout to execute command reached"])
                except Exception as e:
                    writer.writerow([test_name, cmd, "Failed", f"Failed to execute command: {e}"])
                    logger.info("Failed to execute command due to error %s", e)
        except Exception as error:
            writer.writerow([test_name, cmd, "Failed", "Failed to execute command"])
            logger.info("Failed to execute command due to error %s", error)

    @skipIf(
        (
            "idcevo" in test.mtee_target.options.target.lower()
            and test.mtee_target.options.hardware_revision.startswith("D")
        ),
        "Test not applicable for D sample.",
    )
    def test_001_generic_lk_mode(self):
        """
        [SIT_Automated] Generic LK Mode Test logs creator
        Steps:
        - Enter LK shell mode.
        - Create or open a CSV file named "dynamic_lk_logs.csv" in append mode.
        - Iterate over the items in LK_BOOTLOG_VERIFICATION.
            a. For each item, get the command and patterns.
            b. Execute the command and log the results in the CSV file.
        - Reboot target
        """

        try:
            enter_lk_shell_instance(self.test)
            csv_filename = "dynamic_lk_logs.csv"
            file_exists = os.path.isfile(os.path.join(self.extract_file_dir, csv_filename))

            with open(os.path.join(self.extract_file_dir, csv_filename), "a", newline="") as csv_handler:
                writer = csv.writer(csv_handler)
                if not file_exists:
                    writer.writerow(["Test Name", "Command", "Pass/Fail", "Details"])
                for test_name, value in LK_BOOTLOG_VERIFICATION.items():
                    cmd = value["cmd"]
                    patterns = value["pattern"]
                    self.execute_command_and_log_results(test_name, cmd, patterns, writer)
        except Exception as e:
            logger.info(f"Wasn't possible to switch to LK mode. Error occurred - {e}")
        finally:
            self.test.mtee_target.reboot(prefer_softreboot=False)
            wait_for_application_target(self.test.mtee_target)
