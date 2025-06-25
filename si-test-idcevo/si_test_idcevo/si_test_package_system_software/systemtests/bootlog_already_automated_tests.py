# Copyright (C) 2025. BMW CTW PT. All rights reserved.
"""
System Software already automated tests - Bootlog.

These tests were previously automated in the domain's repositories.
This file brings them into our codebase, where they have been adapted to align with our testing standards.
"""
import configparser
import logging
import re
from pathlib import Path
from unittest import skipIf

from mtee.testing.tools import (
    assert_is_not_none,
    assert_regexp_matches,
    assert_true,
    metadata,
)
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.test_helpers import skip_unsupported_ecus

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)


class TestsBootlog(object):
    test = TestBase.get_instance()
    test.setup_base_class(disable_dmverity=True)

    test.setup_base_class()
    hw_revision = test.mtee_target.options.hardware_revision
    hw_model = test.mtee_target.options.target

    def setup(self):
        self.test.mtee_target.remount()

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-10110",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "BOOTLOADER_SECURITY"),
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["idcevo"]), "This test isn't supported by this ECU!")
    def test_001_secure_boot(self):
        """
        [SIT_Automated] Bootloader Security - Secure Boot
        Steps:
            1. Enter the below command on Node0 Console
                command: cat /proc/dram_bootlog | grep "Secure boot success"
            2. Search for the below strings in output from above command.
                (strongbox_a) Secure boot success
                (strongbox_b) Secure boot success
        Expected Outcome:
            Ensure that strings mentioned in step 2 are present in step 1 output
        """
        secure_boot_pattern = re.compile(r".*\(strongbox_[a,b]\) Secure boot success.*")

        command = r"cat /proc/dram_bootlog | grep 'Secure boot success'"
        return_stdout, _, _ = self.test.mtee_target.execute_command(command)
        matches = secure_boot_pattern.search(return_stdout)
        assert_is_not_none(
            matches,
            "'Strongbox: Secure boot success' payload not found."
            f"Pattern- {secure_boot_pattern.pattern} not found in output of command- {command}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-13948",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "BOOTLOADER_RESET"),
                ],
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["idcevo"]), "This test isn't supported by this ECU!")
    def test_002_verify_device_booting_in_virtual_mode(self):
        """
        [SIT_Automated] Verify if device is Booting in Virtual mode (A/B Partition)
        Steps:
            1. Reboot the target by turning KL30 off/on
            2. Run the below command in node0 AND validate device is Booting in Virtual mode
                # cat /proc/dram_bootlog
        Expected Outcome:
            After boot-up, 'boot mode is BootingMode_A [virtual] !!!' or 'boot mode is BootingMode_B [virtual] !!!'
            log should be visible in Node0 console
        """
        virtual_boot_pattern = r"boot mode is (BootingMode_A|BootingMode_B) \[(.+)\] !!!"
        self.test.mtee_target.reboot(prefer_softreboot=False)
        boot_logs_stdout, _, _ = self.test.mtee_target.execute_command(
            "cat /proc/dram_bootlog",
            expected_return_code=0,
        )
        self.test.apinext_target.wait_for_boot_completed_flag(240)

        assert_regexp_matches(
            boot_logs_stdout,
            virtual_boot_pattern,
            f"Boot mode (A/B Partition) text is not found in the logs. "
            f"Expected virtual mode partition:- {virtual_boot_pattern} in Actual log output- {boot_logs_stdout}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-10387",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "HW_VARIANT_BCP"),
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["rse26", "cde"]), "This test isn't supported by this ECU!")
    def test_003_bootloader_support(self):
        """
        [SIT_Automated] Bootloader support for all the hardware variants
        Steps:
            1. Enter the below command on Node0 Console
                command: cat /proc/dram_bootlog
        Expected Outcome:
            1. Check the boot logs for all the hardware variants
        """

        expected_bootloader_support = {
            "idcevo": {
                "C1": [re.compile(".*rpmb.*rev-id.*received.*c1000212.*")],
                "D1": [re.compile(".*rpmb.*rev-id.*received.*d1000232.*")],
            },
            "rse26": {
                "B1": [re.compile(".*rpmb.*rev-id.*received.*b1008143.*")],
                "B2": [re.compile(".*rpmb.*rev-id.*received.*b2008133.*")],
                "C1": [re.compile(".*bcp.*rev-id.*received.*c1008143.*")],
            },
            "cde": {
                "B1": [re.compile(".*rpmb.*rev-id.*received.*b1000333.*")],
                "C1": [re.compile(".*rpmb.*rev-id.*received.*c1000332.*")],
            },
        }

        command = r"cat /proc/dram_bootlog"
        return_stdout, _, _ = self.test.mtee_target.execute_command(command, expected_return_code=0)

        match = False
        if return_stdout:
            substrings = expected_bootloader_support.get(self.hw_model, {}).get(self.hw_revision, [])
            for substring in substrings:
                match = re.search(substring, return_stdout)
                if match is None:
                    break

        assert_true(match, f"Couldn't match output of {command} with expected bootlog value list: {substrings}")

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-10458",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "BOOTLOADER_SECURITY_ANDROID_BOOT"),
            },
        },
    )
    def test_004_verify_starting_tee_binary(self):
        """
        [SIT_Automated] Starting TEE binary
        Steps -
            1. Reboot the target.
            2. Execute the below command to get the bootlogs after reboot,
                "cat /proc/dram_bootlog"

        Expected output -
            - "Wait TEE init done" log should be present in the bootlogs after the reboot
        """
        boot_logs_stdout, _, _ = self.test.mtee_target.execute_command(
            "cat /proc/dram_bootlog",
            expected_return_code=0,
        )
        assert_true(
            "Wait TEE init done" in boot_logs_stdout,
            "Failed to validate starting of TEE binary in bootlogs, Expected string - 'Wait TEE init done'"
            f" Actual bootlogs - {boot_logs_stdout}",
        )
