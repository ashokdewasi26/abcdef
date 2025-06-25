# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Target Diagnostic UI tests"""
import configparser
import logging
from pathlib import Path

from diagnose.tools import unhex

from mtee.testing.test_environment import TEST_ENVIRONMENT as TE, require_environment, require_environment_setup
from mtee.testing.tools import (
    assert_equal,
    metadata,
)
import si_test_idcevo.si_test_helpers.test_helpers as utils
from si_test_idcevo.si_test_helpers.android_helpers import ensure_launcher_page
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.diagnostic_helper import (
    fetch_and_validate_airplane_mode_status_via_diag,
    parse_cert_management_readout_status_output,
    steuern_airplane_mode,
    wait_for_start_check_to_complete,
)
from si_test_idcevo.si_test_helpers.pages.idcevo.connectivity_page import ConnectivityPage as Connectivity
from si_test_idcevo.si_test_helpers.reboot_handlers import reboot_and_wait_for_android_target
from tee.tools.secure_modes import SecureECUMode

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

TEST_ENVIRONMENT = (TE.target.hardware.idcevo,)


@require_environment(*TEST_ENVIRONMENT)
class TestDiagnosticUICases(object):
    @classmethod
    @require_environment_setup(*TEST_ENVIRONMENT)
    def setup_class(cls):
        """
        Setup class:
        1 - Verifies if the target is in engineering mode.
            If not by default, it will switch the target to engineering mode.
        """
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(enable_appium=True, root=True)
        cls.secure_mode_object = SecureECUMode(cls.test.mtee_target)
        current_mode = cls.secure_mode_object.current_mode
        logger.info(f"Current target mode: {current_mode}")

        if current_mode != "ENGINEERING":
            cls.secure_mode_object.switch_mode("ENGINEERING")
            logger.info("Engineering mode activated.")

    @classmethod
    @require_environment_setup(*TEST_ENVIRONMENT)
    def teardown_class(cls):
        reboot_and_wait_for_android_target(cls.test, prefer_softreboot=False)
        cls.test.teardown_base_class()

    def setup(self):
        """before each test ensure:
        - There is an active Diagnostic session
        - Set energy mode to normal
        - Target has certificates
        - Ensure target is on launcher page
        """

        self.test.diagnostic_client.default_session()
        status_diag_session_lesen_output = self.test.diagnostic_client.status_diag_session_lesen()
        assert_equal(
            status_diag_session_lesen_output,
            "01",
            "Expected output was not obtained for DiagJob STATUS_DIAG_SESSION_LESEN. "
            f"Obtained output: {status_diag_session_lesen_output}",
        )

        self.test.diagnostic_client.set_energy_mode("NORMAL")

        output_cert_mngmt_status = self.test.diagnostic_client.certificate_management_readout_status()
        status = parse_cert_management_readout_status_output(output_cert_mngmt_status)
        if status["certificates"] != "OK":
            logger.info("Certificates are not OK. Restoring persistence CSRS keys and certs...")
            self.test.mtee_target.restore_persistence_csrs_keys()
            self.test.mtee_target.restore_persistence_certs()
            wait_for_start_check_to_complete(self.test.diagnostic_client)

        ensure_launcher_page(self.test)

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["BAT", "SI-diag"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-52452",
        traceability={""},
    )
    def test_001_rdbi_airplane_mode_status_diagjob(self):
        """[SIT_Automated] [Diagnostics] 22 7A 20 RDBI_AIRPLANE_MODE
        Steps:
            1 - Disable Airplane mode via RDBI_AIRPLANE_MODE Diagjob and ensure it's disabled
                22 7A 20 00
            2 - Enable BT and WiFi via UI
            3 - Enable Airplane mode via RDBI_AIRPLANE_MODE Diagjob and ensure it's enabled
                22 7A 20 01
            4 - Ensure that BT and WiFi are turned Off after enabling Airplane mode.
            5 - Disable Airplane mode via RDBI_AIRPLANE_MODE Diagjob and ensure it's disabled
                22 7A 20 00
        """
        try:

            steuern_airplane_mode(diag_client=self.test.diagnostic_client, data=unhex("00"))
            fetch_and_validate_airplane_mode_status_via_diag(
                diag_client=self.test.diagnostic_client,
                expected_state="00",
            )

            Connectivity.turn_on_bt_and_validate_the_status(self.test)
            Connectivity.turn_on_wifi_and_validate_the_status(self.test)

            steuern_airplane_mode(diag_client=self.test.diagnostic_client, data=unhex("01"))
            fetch_and_validate_airplane_mode_status_via_diag(
                diag_client=self.test.diagnostic_client,
                expected_state="01",
            )

            if Connectivity.check_bluetooth_state_ui():
                utils.get_screenshot_and_dump(self.test, self.test.results_dir, "bt_state_after_airplane_mode_on")
                ensure_launcher_page(self.test)
                raise AssertionError("BT didn't turned Off after enabling airplane mode via diag")
            utils.get_screenshot_and_dump(self.test, self.test.results_dir, "turning_off_bt_via_airplane_mode")

            if Connectivity.check_wifi_state_ui():
                utils.get_screenshot_and_dump(self.test, self.test.results_dir, "wifi_state_after_airplane_mode_on")
                ensure_launcher_page(self.test)
                raise AssertionError("Wifi didn't turned Off after enabling airplane mode via diag")
            utils.get_screenshot_and_dump(self.test, self.test.results_dir, "turning_off_wifi_via_airplane_mode")

        finally:
            steuern_airplane_mode(diag_client=self.test.diagnostic_client, data=unhex("00"))
            Connectivity.turn_on_bt_and_validate_the_status(self.test)
            Connectivity.turn_on_wifi_and_validate_the_status(self.test)
