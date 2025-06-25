# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Target MACsec Diagnostic tests"""
import configparser
import logging
from pathlib import Path
from unittest import skipIf

from diagnose.tools import enhex
from mtee.metric import MetricLogger
from mtee.testing.tools import (
    assert_equal,
    assert_true,
    metadata,
)
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.diagnostic_helper import (
    custom_read_data_by_did,
    get_dtc_list,
)
from tee.tools.secure_modes import SecureECUMode

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
metric_logger = MetricLogger()

target = TestBase.get_instance()
target.setup_base_class()

ECU_VARIANT = target.mtee_target.options.target_serial_no[2:6].upper()
MACSEC_NOT_STARTED_DTC = 0x026376
START_STOP_DID = 0x1119


class TestDiagnostic(object):
    @classmethod
    def setup_class(cls):
        """
        Setup class:
        - Verifies if the target is in engineering mode.
            If not by default, it will switch the target to engineering mode.
        """

        secure_mode_object = SecureECUMode(target.mtee_target)
        current_mode = secure_mode_object.current_mode
        logger.info(f"Current target mode: {current_mode}")

        if current_mode != "ENGINEERING":
            secure_mode_object.switch_mode("ENGINEERING")
            logger.info("Engineering mode activated.")

    @classmethod
    def teardown_class(cls):
        try:
            target.mtee_target.execute_command("cat /proc/cmdline")
        except Exception as e:
            logger.error(f"Target is in an unhealthy state. Error: '{e}'.")
            target.mtee_target.reboot(prefer_softreboot=False, check_target=True)

    def setup(self):
        """
        Before each test ensure:
        - There is an active Diagnostic session
        - Set energy mode to normal
        """
        target.diagnostic_client.default_session()
        status_diag_session_lesen_output = target.diagnostic_client.status_diag_session_lesen()
        assert_equal(
            status_diag_session_lesen_output,
            "01",
            "Expected output was not obtained for DiagJob STATUS_DIAG_SESSION_LESEN. "
            f"Obtained output: {status_diag_session_lesen_output}",
        )

        target.diagnostic_client.set_energy_mode("NORMAL")

    def macsec_start(self):
        with target.diagnostic_client.diagnostic_session_manager() as ecu:
            macsec_start_output = enhex(ecu.start_routine(START_STOP_DID)).upper()
            logger.debug(f"MACsec start response: {macsec_start_output}")
        return macsec_start_output[-1:]

    def macsec_stop(self):
        with target.diagnostic_client.diagnostic_session_manager() as ecu:
            macsec_stop_output = enhex(ecu.stop_routine(START_STOP_DID)).upper()
            logger.debug(f"MACsec stop response: {macsec_stop_output}")
        return macsec_stop_output[-1:]

    @metadata(
        testsuite=["BAT", "SI-diag", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-5695",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                ],
            },
        },
    )
    @skipIf(ECU_VARIANT != "B505", "MACsec will only run in B505 samples. This is not one.")
    def test_001_macsec_status(self):
        """[SIT_Automated] 22 80 0E RDBI_MACSEC_STATUS Default Session of Engineering Mode
        - Physical addressing.Positive
        Steps:
            1 - Execute STATUS_DIAG_SESSION_LESEN
                # 22 F1 86
            2 - Execute ENERGIESPARMODE 00
                # 31 01 0F 0C 00
            3 - Select RDBI_MACSEC_STATUS
                # 22 80 0E
        """
        did = 0x800E
        rdbi_macsec_status = custom_read_data_by_did(target.diagnostic_client, did)
        assert_true(rdbi_macsec_status, "Failed to read MACsec status")
        logger.info(f"RDBI_MACSEC status: {rdbi_macsec_status}")
        macsec_status = rdbi_macsec_status[0:2]
        logger.info(f"Local MACsec status: {macsec_status}")
        assert_equal(
            macsec_status,
            "00",
            f"Expected local MACsec status to be disabled and unlocked (00). Received: {macsec_status}",
        )

    @metadata(
        testsuite=["BAT", "SI-diag", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-5696",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                ],
            },
        },
    )
    @skipIf(ECU_VARIANT != "B505", "MACsec will only run in B505 samples. This is not one.")
    def test_002_macsec_dtc1(self):
        """[SIT_Automated] 0x026376:DTC MACSEC_NOT_STARTED
        Checks if MACSEC_NOT_STARTED_DTC does not reappear after being cleared when MACsec is started

        Steps:
        1 - Stop MACsec service (it should already be stopped)
        2 - Clear MACSEC_NOT_STARTED_DTC code
        3 - Check if code is still present after being cleared
        4 - Start MACsec service
        5 - Clear code and check it doesn't reappear
        6 - Stop MACsec service
        """

        not_started_string = hex(MACSEC_NOT_STARTED_DTC).upper().replace("0X", "0X0")

        self.macsec_stop()

        # Clear MACSEC_NOT_STARTED_DTC and verify it's still present
        target.diagnostic_client.clear_single_dtc(MACSEC_NOT_STARTED_DTC)
        dtc_list_before_start = get_dtc_list(target.diagnostic_client)
        assert (
            not_started_string in dtc_list_before_start
        ), "Expected 0x026376 DTC because MACsec is stopped but could not find it."

        start_result = self.macsec_start()
        assert start_result == "0", f"Starting MACsec service failed with response: {start_result}"

        # Clear MACSEC_NOT_STARTED_DTC and verify it doesn't reappear
        target.diagnostic_client.clear_single_dtc(MACSEC_NOT_STARTED_DTC)
        dtc_list_after_start = get_dtc_list(target.diagnostic_client)
        assert (
            not_started_string not in dtc_list_after_start
        ), "The order to start MACsec was given, but 0x026376 is present even after clearing"

        stop_result = self.macsec_stop()
        assert stop_result == "0", f"Stopping MACsec service failed with response: {stop_result}"
