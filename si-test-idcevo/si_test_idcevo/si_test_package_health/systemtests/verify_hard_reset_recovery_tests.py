# Copyright (C) 2024. BMW Car IT GmbH. All rights reserved.
"""
Crashing a process that is not whitelisted should cause a HardresetRecovery
"""
import configparser
import logging
import re
from pathlib import Path
from unittest import skipIf

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.test_helpers import skip_unsupported_ecus

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

SERVICE_NAME = "udpnm.service"
NEW_ACTIONS = ["RestartPlatform", "HardRestartPlatform"]
RECOVERY_AGENT_PAYLOAD_FILTER = re.compile(r"^Starting Recovery Agent - version: 1\.1\.0.*")
RECOVERY_MANAGER_PAYLOAD_FILTER = re.compile(r"^Starting Recovery Manager - version: 1\.1\.0.*")


class TestsHardResetRecovery:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(disable_dmverity=True)

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    @metadata(
        testsuite=["BAT", "domain", "SI", "ACM", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Health",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-23291",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "BASIC_RECOVERY_STEPS"),
                ],
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["rse26", "cde"]), "This test isn't supported by this ECU!")
    def test_001_verify_recovery_manager_service(self):
        """[SIT_Automated] Verify the recovery-manager service and agent starts as expected on boot

        Steps:
        * Execute command - systemctl status recovery-manager |grep active
        * Login to hu-applications container via *lxc-attach -n hu-applications -c $(id -Z)* command.
        * Execute command - systemctl status recovery-agent|grep active

        Expected Results:
        * The status must be active (running).
        * Verify the payload under DLT
        """
        starting_recovery_command = "systemctl status recovery-manager"
        starting_agent_command = "systemctl status recovery-agent"
        match_found = False

        self.test.mtee_target.remount()

        return_stdout, _, _ = self.test.mtee_target.execute_command(starting_recovery_command, expected_return_code=0)
        assert_true("active" in return_stdout, "The recovery-manager status is not active")

        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("RECM", "RECO")]) as soc_trace:
            self.test.mtee_target.reboot(prefer_softreboot=True)
            messages = soc_trace.wait_for({"payload_decoded": RECOVERY_MANAGER_PAYLOAD_FILTER}, drop=True, timeout=180)
            for message in messages:
                if RECOVERY_MANAGER_PAYLOAD_FILTER.search(message.payload_decoded):
                    match_found = True
                    break

        assert_true(match_found, f"Failed to verify expected payload {RECOVERY_MANAGER_PAYLOAD_FILTER}")

        self.test.mtee_target.execute_command_container(
            "hu-applications", starting_agent_command, shell=True, expected_return_code=0
        )

        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("RMHU", "RECO")]) as soc_trace:
            self.test.mtee_target.reboot(prefer_softreboot=True)
            messages = soc_trace.wait_for({"payload_decoded": RECOVERY_AGENT_PAYLOAD_FILTER}, drop=True, timeout=180)
            for message in messages:
                if RECOVERY_AGENT_PAYLOAD_FILTER.search(message.payload_decoded):
                    match_found = True
                    break

        assert_true(match_found, f"Failed to verify expected payload {RECOVERY_AGENT_PAYLOAD_FILTER}")
