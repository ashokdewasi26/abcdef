# Copyright (C) 2024. BMW CTW PT. All rights reserved.
import configparser
import logging
import re
import time
from pathlib import Path

from mtee.testing.tools import assert_true, metadata

from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.dmverity_helpers import disable_dm_verity

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

DM_PATTERN = r".*rodata=y.*root=/dev/dm-0 dm-mod.create=\"vroot,,,ro,0 \d+ verity 1.*"


class TestsDMVeritySignature(object):
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
        duplicates="IDCEVODEV-48464",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "DM_VERITY"),
            },
        },
    )
    def test_001_dm_verity_signature(self):
        """[SIT_Automated] Verify DM-verity Signature Check ok when target boots up normally

        **Required Steps**
            1. Reboot target
            2. Execute command on node0: cat /proc/cmdline and check output for DM_verity signature
        """
        self.test.mtee_target.reboot()

        time.sleep(5)

        return_stdout, _, _ = self.test.mtee_target.execute_command("cat /proc/cmdline")
        stdout_match = re.search(DM_PATTERN, return_stdout)
        assert_true(stdout_match, "DM_verity signature not found")

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
    def test_002_disable_dmverity(self):
        """[SIT_Automated] Disable dm-verity

        **Required Steps**
            * Call helper method to disable dm-verity

        **Expected Outcome**
            * Flag disable_dm_verity set to True
        """
        disable_dm_verity()

        assert_true(self.test.mtee_target.options.disable_dm_verity, "Failed to disable dm-verity!")
