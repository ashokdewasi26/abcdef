# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Check bootup with dmverity disabled"""
import configparser
import logging
import os
import re
from pathlib import Path
from unittest import SkipTest

from mtee.testing.tools import assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

BOOT_PATTERN = r"boot args"
ROOT_PARTITION_DM_VERITY_ENABLED = r"root=\/dev\/dm-0"
SUCCESSFUL_BOOT = r"VM3 jumping into the Guest's kernel"


class BootupDMVerityDisabledPostTest(object):

    __test__ = True

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-48465",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "DM_VERITY"),
            },
        },
    )
    def test_001_dmverity_disabled_logs(self):
        """[SIT_Automated] Verify when dm-verity is disabled, target should bootup normally

        Required Steps:
            - Check if dm-verity is disabled. If not, skip test
            - Open serial_console_ttySOCHU.log
            - Search BOOT_PATTERN without dm-verity partition
            - Check if pattern SUCCESSFUL_BOOT is detected before a new BOOT_PATTERN

        Expected Outcome:
            - Pass test if patterns found
        """
        if not self.test.mtee_target.options.disable_dm_verity:
            raise SkipTest("Skipping test as dm-verity is not disabled.")

        log_file = os.path.join(self.test.mtee_target.options.result_dir, "serial_console_ttySOCHU.log")
        root_partition_detected = False
        successful_boot_message_found = False

        with open(log_file) as file_handler:
            for file_line in file_handler.readlines():
                if (
                    re.compile(BOOT_PATTERN).search(file_line)
                    and not re.compile(ROOT_PARTITION_DM_VERITY_ENABLED).search(file_line)
                    and not root_partition_detected
                ):
                    logger.info("Correct root partition found.")
                    root_partition_detected = True
                    continue
                if re.compile(BOOT_PATTERN).search(file_line) and root_partition_detected:
                    logger.info("Failed to detect successful boot message.")
                    if re.compile(ROOT_PARTITION_DM_VERITY_ENABLED).search(file_line):
                        root_partition_detected = False
                    continue
                if re.compile(SUCCESSFUL_BOOT).search(file_line) and root_partition_detected:
                    logger.info("Successful boot message found.")
                    successful_boot_message_found = True
                    break

        assert_true(successful_boot_message_found, "Failed to bootup normally after disabling dm-verity")
