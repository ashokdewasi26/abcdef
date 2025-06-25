# Copyright (C) 2025. CTW. All rights reserved.
"""Test that triggers a RAM dump"""
import logging

from mtee.testing.tools import assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.command_helpers import full_ram_dump
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target

logger = logging.getLogger(__name__)


@metadata(testsuite=["SI"])
class TestFullRAMdump(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def test_001_trigger_full_ramdump_on_target(self):
        """
        [SIT_Automated] Simple test to trigger a full RAM dump
        Steps:
            1 - Reboot target
            2 - Wait for Application target
            3 -  Trigger full ramdump

        Expected Outcome:
            - Full RAM dump is successful

        Notes: The RAM dump results in 17 Gigabytes of data stored
        The content should be available on test-artifacts/results/ramdump_content
        """
        self.test.mtee_target.reboot()
        wait_for_application_target(self.test.mtee_target)

        ramdump_successful = full_ram_dump()
        assert_true(ramdump_successful, "Failed to perform the RAM dump, check logs.")
