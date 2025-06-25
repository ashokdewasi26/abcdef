# Copyright (C) 2024. BMW Car IT. All rights reserved.
"""System functions IOlifecycle tests"""
import configparser
import logging
from pathlib import Path

from mtee.testing.tools import assert_equal, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)


class TestIOLifecyle:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

    @classmethod
    def teardown_class(cls):
        cls.test.mtee_target.reboot()
        wait_for_application_target(cls.test.mtee_target)

    @metadata(
        testsuite=["BAT", "domain", "SI", "ACM", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-15372",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "PARTITION_FLASHING_IOLIFECYCLE"),
            },
        },
    )
    def test_001_verify_restart_into_bolo(self):
        """[SIT_Automated] verify restart into bolo works with NSM-Control

        Steps:
        1. Trigger nsm restart by nsm_control --r 3
        2. HMI should be up and running without any unexpected reset and logs are available continuously.
        3. Read Active Session state and look for Positive Response: 01 00 00 00
        """
        self.test.mtee_target.boot_into_flashing(check_target=True, target_verification_timeout=60)
        status_active_session_state_output = self.test.diagnostic_client.status_active_session_state()
        assert_equal(
            status_active_session_state_output,
            "01 00 00 00",
            "Expected output was not obtained for DiagJob status_active_session_state. "
            f"Obtained output: {status_active_session_state_output}",
        )
