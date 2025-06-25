# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Target Diagnostic tests"""
import configparser
import logging
import os
import re
import time
from pathlib import Path
from unittest import skipIf

from diagnose.tools import enhex
from mtee.metric import MetricLogger
from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import (
    assert_equal,
    assert_is_none,
    assert_is_not_none,
    assert_true,
    check_process_returncode,
    metadata,
    run_command,
)
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.diagnostic_helper import (
    CERTIFICATE_INFORMATION,
    check_and_disable_postpone_shutdown,
    custom_read_data_by_did,
    diagnostic_job_data,
    enable_postpone_shutdown,
    execute_and_validate_kds_action_data,
    get_dtc_list,
    parse_cert_management_readout_status_output,
    trigger_start_check_and_wait_for_completion,
    validate_kds_individualization_state,
    wait_for_start_check_to_complete,
    wipe_csrs,
)
from si_test_idcevo.si_test_helpers.dlt_logs_handlers import validate_expected_dlt_payloads_in_dlt_trace
from si_test_idcevo.si_test_helpers.parsing_handlers import match_string_with_regex
from si_test_idcevo.si_test_helpers.pdx_helpers import process_svk
from si_test_idcevo.si_test_helpers.reboot_handlers import (
    reboot_and_wait_for_android_target,
    wait_for_application_target,
)
from si_test_idcevo.si_test_helpers.test_helpers import skip_unsupported_ecus
from tee import const
from tee.target_common import PARTIALNETWORKS2BITFIELD, VehicleCondition
from tee.tools.lifecycle import LifecycleFunctions
from tee.tools.secure_modes import SecureECUMode
from tee.tools.utils import convert_integer_to_hex_string

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
metric_logger = MetricLogger()
lf = LifecycleFunctions()

target = TargetShare().target

ENERGIESPARMODE_DIAGJOB_DLT_REGEX_PATTERN = r".*71 01 0F 0C.*"
STATUS_DIAG_SESSION_LESEN_DLT_REGEX_PATTERN = r".*62 F1 86 01.*"
SERIENNUMMER_LESEN_DLT_REGEX_PATTERN = r"^(?:\d{2}\s+){9}\d{2}$"
SGBM_IDENTIFIERS = ["BTLD", "HWEL", "SWFK", "SWFL", "CAFD"]

PROCESS_CLASS_DICT = {"01": "HWEL", "02": "HWAP", "05": "CAFD", "06": "BTLD", "07": "FLSL", "08": "SWFL", "0D": "SWFK"}
PROCESS_CLASS_DICT_INV = {v: k for k, v in PROCESS_CLASS_DICT.items()}
PROTOCOL_FACTOR = 64  # this is 1/0.015625
VEHICLE_SPEED_SIGNAL = "IK.V_VEH_COG"

ACL_OPERATION_NOT_STARTED_DTC = 0x026379
CERTIFICATES_AND_BINDINGS_DTC_TEMPLATE = "0x02{diag_addr}80"
IDENT_DIAGJOB_OUTPUT = {
    "cde": "0F 37 D0",
    "idcevo": "0F 32 30",
    "rse26": "0F 37 E0",
}
KDS_NOT_INDIVIDUALIZED_DTC = 0x0263B2
KDS_NOT_LOCKED_DTC = 0x0263B0
TIME_DATA_CHECK_COMPLETED = 10  # seconds
POSTPONE_SHUTDOWN_DISABLED = {
    "idcevo": "0XA76331",
    "rse26": "0XA79831",
    "cde": "0XA7A731",
}
ECU_NOT_IN_FIELD_MODE_DTC_REG = r"0X02[a-zA-Z0-9]{2}85"


class TestDiagnostic(object):
    @classmethod
    def setup_class(cls):
        """
        Setup class:
        1 - Verifies if the target is in engineering mode.
            If not by default, it will switch the target to engineering mode.
        2 - Set vehicle speed to 5 km/h
        """

        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)

        cls.secure_mode_object = SecureECUMode(cls.test.mtee_target)
        current_mode = cls.secure_mode_object.current_mode
        logger.info(f"Current target mode: {current_mode}")

        if current_mode != "ENGINEERING":
            cls.secure_mode_object.switch_mode("ENGINEERING")
            logger.info("Engineering mode activated.")

        # Reference:
        # https://cc-github.bmwgroup.net/pages/node0/tee-node0/examples.html#using-the-vcar-functions-library
        speed = 5
        cls.test.vcar_manager.execute_remote_method("set_speed", speed)
        result = cls.test.vcar_manager.execute_remote_method("get_speed")
        logger.info(f"Vehicle speed set to: {result} km/h.")
        cls.hw_model = cls.test.mtee_target.options.target

    def setup(self):
        """before each test ensure:
        - There is an active Diagnostic session
        - Set energy mode to normal
        - Target has certificates
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

    @classmethod
    def teardown_class(cls):
        reboot_and_wait_for_android_target(cls.test, prefer_softreboot=False)

    def verify_system_reset_using_diagnostic(self, vehicle_condition, payload_msg_to_validate):
        """
        System reset using diagnostic on expected vehicle_condition and validate the DLT payloads
        :param vehicle_condition: vehicle condition like VehicleCondition.FAHREN, VehicleCondition.WOHNEN etc.
        :param list payload_msg_to_validate: DLT payload message which we want to validate after reset.
        """
        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
            self.test.mtee_target.switch_vehicle_to_state(vehicle_condition)
            self.test.diagnostic_client.ecu_reset()
            self.test.mtee_target.ssh.wait_for_ssh(self.test.mtee_target.get_address(), timeout=60)
            self.test.mtee_target._recover_ssh(record_failure=False)
            wait_for_application_target(self.test.mtee_target)
            dlt_msgs = trace.wait_for_multi_filters(
                filters=payload_msg_to_validate,
                count=0,
                timeout=180,
            )
        self.test.mtee_target.wait_for_nsm_fully_operational()
        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.FAHREN)
        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, payload_msg_to_validate, "SOC logs")

    def restore_target_if_not_alive(self):
        """Restores target if not alive after LC operations."""
        if not lf.is_alive():
            logger.info("Waking up target from the shutdown state!")
            self.test.mtee_target.wakeup_from_sleep()
            lf.setup_keepalive()
            self.test.mtee_target.resume_after_reboot()

    @metadata(
        testsuite=["BAT", "SI-diag", "SI-staging", "ACM", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-5685",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAG_READ_ECU_UID"),
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                    config.get("FEATURES", "HARDWARE_INFO"),
                    config.get("FEATURES", "PRODUCTION_DATA"),
                ],
            },
        },
    )
    def test_001_read_ecu_uid(self):
        """[SIT_Automated] 22 80 00 ECU_UID_LESEN Default Session of Engineering Mode - Physical addressing.Positive"""
        ecu_uid = self.test.diagnostic_client.read_ecu_uid().replace(" ", "").upper()
        logger.debug("ECU UID: %s", ecu_uid)
        assert_true(
            ecu_uid in self.test.mtee_target.options.target_ecu_uid,
            "ECU UID {} didn't match expected {}".format(
                ecu_uid.upper(), self.test.mtee_target.options.target_ecu_uid
            ),
        )

    @metadata(
        testsuite=["BAT", "SI-diag", "ACM", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-5665",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                    config.get("FEATURES", "HARDWARE_INFO"),
                    config.get("FEATURES", "PRODUCTION_DATA"),
                ],
            },
        },
    )
    def test_002_serial_number_diagjob(self):
        """
        [SIT_Automated] 22 F1 8C SERIENNUMMER_LESEN Default Session of Engineering Mode - Physical addressing.Positive

        Steps:
        1 - Execute STATUS_DIAG_SESSION_LESEN
            22 F1 86
        2 - Execute ENERGIESPARMODE 00
            31 01 0F 0C 00
        3 - Execute SERIENNUMMER_LESEN
            22 F1 8C
        """

        logger.info("Starting test to implement the Serial Number Diagjob.")

        seriennummer_lesen_output = self.test.diagnostic_client.seriennummer_lesen()
        if match := re.search(SERIENNUMMER_LESEN_DLT_REGEX_PATTERN, seriennummer_lesen_output):
            logger.debug(f"seriennummer_lesen diag job output: {match.group(0)}")
        else:
            assert_is_not_none(
                match,
                "Expected output was not obtained for DiagJob SERIENNUMMER_LESEN. "
                f"Obtained output: {seriennummer_lesen_output}",
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
        duplicates="IDCEVODEV-5663",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                    config.get("FEATURES", "HARDWARE_INFO"),
                    config.get("FEATURES", "PRODUCTION_DATA"),
                ],
            },
        },
    )
    def test_003_svk_lesen_diagjob(self):
        """[SIT_Automated] 22 F1 01 STATUS_SVK_LESEN Default Session of Engineering Mode - Physical addressing.Positive

        Steps:
        1 - Execute STATUS_DIAG_SESSION_LESEN
            22 F1 86
        2 - Execute ENERGIESPARMODE 00
            31 01 0F 0C 00
        3 - Read SVK_LESEN
            22 f1 01
        """

        logger.info("Starting test to implement SVK Lesen Diagjob.")

        did = 0xF101
        svk_lesen_output = custom_read_data_by_did(self.test.diagnostic_client, did)
        svk_lesen_output_processed = process_svk(svk_lesen_output.upper(), logger)
        error_list = []
        for identifier in SGBM_IDENTIFIERS:
            # 'SWFK' is optional and may be empty, as per ticket IDCEVODEV-112207.
            if identifier == "SWFK":
                continue
            if (
                identifier in svk_lesen_output_processed
                and isinstance(svk_lesen_output_processed[identifier], list)
                and len(svk_lesen_output_processed[identifier]) > 0
            ):
                pass
            else:
                error_list.append(f"Identifier {identifier} not found.")
        assert_true(len(error_list) == 0, f"Error when reading SVK_LESEN: {error_list}")

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
        duplicates="IDCEVODEV-5668",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                    config.get("FEATURES", "HARDWARE_INFO"),
                    config.get("FEATURES", "PRODUCTION_DATA"),
                ],
            },
        },
    )
    def test_004_production_date_diagjob(self):
        """
        [SIT_Automated] 22 F1 8A STATUS_HERSTELLINFO_LESEN Default Session of Engineering Mode
        - Physical addressing.Positive

        Steps:
        1 - Execute STATUS_DIAG_SESSION_LESEN
            22 F1 86
        2 - Execute ENERGIESPARMODE 00
            31 01 0F 0C 00
        3 - Select herstellinfo_lesen option and Run job
            22 F1 8A
        """

        logger.info("Starting test to implement production date Diagjob.")

        herstellinfo_lesen_output = self.test.diagnostic_client.herstellinfo_lesen()
        logger.info(f"herstellinfo_lesen diagjob output: {herstellinfo_lesen_output}")
        assert_is_not_none(
            herstellinfo_lesen_output,
            f"No positive response obtained for DiagJob herstellinfo_lesen: {herstellinfo_lesen_output}",
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
        duplicates="IDCEVODEV-5671",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                    config.get("FEATURES", "HARDWARE_INFO"),
                    config.get("FEATURES", "PRODUCTION_DATA"),
                ],
            },
        },
    )
    def test_005_ident_diagjob(self):
        """[SIT_Automated] 22 F1 50 IDENT Default Session of Engineering Mode - Physical addressing.Positive

        Steps:
        1 - Execute STATUS_DIAG_SESSION_LESEN
            22 F1 86
        2 - Execute ENERGIESPARMODE 00
            31 01 0F 0C 00
        3 - Select IDENT option and Run job
            22 F1 50
        """

        logger.info("Starting test to implement IDENT Diagjob.")

        ident_diagjob_output = self.test.diagnostic_client.ident()
        assert_equal(
            ident_diagjob_output.upper(),
            IDENT_DIAGJOB_OUTPUT[self.hw_model],
            f"Expected output, {IDENT_DIAGJOB_OUTPUT.get(self.hw_model)}, was not obtained for DiagJob IDENT."
            f" Obtained output: {ident_diagjob_output.upper()}",
        )

    def _verify_openssl_output(self, content_to_be_verified):
        """
        Verify openssl output

        :param content_to_be_verified: openssl output
        """
        mismatched_data = {}  # {{constant_name: found_value}, ... }

        logger.info("Verifying openssl output ...")

        for constant, config in CERTIFICATE_INFORMATION.items():
            match = config["pattern"].search(content_to_be_verified)

            if match:
                if constant == "VERSION":
                    v_1 = match.group("v_1")
                    v_2 = match.group("v_2")
                    version = v_1 + " (" + v_2 + ")"
                    logger.debug(f"Found the following information on the certificate: '{constant}': '{v_1}' '{v_2}'")

                    if config["match"] != version:
                        logger.debug(
                            f"Expected output was not obtained for openssl command. Obtained output: {v_1} {v_2}"
                        )
                        mismatched_data.update({constant: f"{v_1} {v_2}"})

                elif constant == "ECU-ID":
                    serial_number_obtained = match.group("serial_number")
                    logger.debug(
                        f"Found the following information on the certificate: '{constant}': '{serial_number_obtained}'"
                    )

                    if self.test.mtee_target.options.target_ecu_uid != serial_number_obtained:
                        logger.debug(
                            f"Expected output was not obtained for openssl command."
                            f" Obtained output: {serial_number_obtained}"
                        )
                        mismatched_data.update({constant: serial_number_obtained})

                else:
                    logger.debug(
                        f"Found the following information on the certificate: '{constant}': '{match.group('string')}'"
                    )

                    if config["match"] != match.group("string"):
                        logger.debug(
                            f"Expected output was not obtained for openssl command. "
                            f"Obtained output: {match.group('string')}"
                        )
                        mismatched_data.update({constant: match.group("string")})
            else:
                mismatched_data.update({constant: config["match"]})

        assert_true(len(mismatched_data) == 0, f"Error reading openssl output in these fields: {mismatched_data}")

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
        duplicates="IDCEVODEV-5748",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_BASIC_SECURITY_SF_RELATED"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                ],
            },
        },
    )
    def test_006_cer_mgmt_csr_diagjob(self):
        """[SIT_Automated] 31 01 F0 3D STEUERN_CSR_GENERATION Default Session of Engineering Mode
        - Physical addressing.Positive

        Steps:
        1 - Execute STATUS_DIAG_SESSION_LESEN
            22 F1 86
            Expected output: 62 F1 86 01
        2 - Execute ENERGIESPARMODE 00
            31 01 0F 0C 00
            Expected output: 71 01 0F 0C
        3 - Select steuern_routine and send CSR_GENERATION;STR and Run job
            31 01 F0 3D
            Expected output: 71 01 F0 3D
        4 - Select steuern_routine and send CSR_GENERATION;RRR and Run job
            31 03 F0 3D
            Expected output: 71 03 F0 3D 02
        5 - Parse of generated ID.pem file
        """

        control_csr_generation = self.test.diagnostic_client.steuern_csr_generation()
        logger.info(f"control_csr_generation diagjob output: {control_csr_generation}")

        status_csr_generation = self.test.diagnostic_client.status_csr_generation()

        shown_content_cmd = ["ls", "-R", "/var/sys/sysfunc"]
        result = self.test.mtee_target.execute_command(shown_content_cmd)
        logger.info(f"sysfunc folder content: {result.stdout}")

        if status_csr_generation.upper() != "02":
            logger.error(
                "A full set of keys and CSRs is not available in the ECU. Restoring persistence CSRS keys ..."
            )
            self.test.mtee_target.restore_persistence_csrs_keys()
        else:
            assert_equal(
                status_csr_generation.upper(),
                "02",
                f"A full set of keys and CSRs is not available in the ECU. Result obtained: {status_csr_generation}",
            )

        fullname = Path(self.test.mtee_target.options.result_dir) / "extracted_files" / "ID.pem"

        check_if_file_exists_cmd = ["ls", "/var/sys/sysfunc/csrs/ID.pem"]
        result_stdout, _, _ = self.test.mtee_target.execute_command(check_if_file_exists_cmd)

        assert_true("ID.pem" in result_stdout, "File ID.pem not found in the target ...")

        file_to_download = "/var/sys/sysfunc/csrs/ID.pem"
        logger.info(f"Extracting file '{file_to_download}' to '{fullname}'")
        self.test.mtee_target.download(file_to_download, fullname)
        time.sleep(5)

        openssl_cmd = [
            "openssl",
            "req",
            "-text",
            "-noout",
            "-verify",
            "-in",
            "ID.pem",
        ]
        host_path = Path(self.test.mtee_target.options.result_dir) / "extracted_files"

        openssl_stdout, openssl_stderr, openssl_return_code = run_command(openssl_cmd, check=True, cwd=host_path)
        check_process_returncode(0, openssl_return_code, f"openssl command failed: '{openssl_return_code}'")
        assert_true("verify OK" in openssl_stderr, f"openssl command failed: '{openssl_stderr}'")
        self._verify_openssl_output(openssl_stdout)

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
        duplicates="IDCEVODEV-5677",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_BASIC_SECURITY_SF_RELATED"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                ],
            },
        },
    )
    def test_007_cert_mgmt(self):
        """[SIT_Automated] 31 01 10 AC STATUS_CERTIFICATE_MANAGEMENT_READOUT_STATUS Default Session of Engineering Mode
        - Physical addressing.Positive

        Steps:
        1 - Execute STATUS_DIAG_SESSION_LESEN
            22 F1 86
        2 - Execute ENERGIESPARMODE 00
            31 01 0F 0C 00
        3 - Select STATUS_CERTIFICATE_MANAGEMENT_READOUT_STATUS and run job
        """

        certificate_management_readout_status_output = (
            self.test.diagnostic_client.certificate_management_readout_status()
        )
        status = parse_cert_management_readout_status_output(certificate_management_readout_status_output)
        assert_true(status["certificates"] == "OK", f"Certificates are not OK as expected. Status: {status}")

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
        duplicates="IDCEVODEV-5680",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_BASIC_SECURITY_SF_RELATED"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                ],
            },
        },
    )
    def test_008_cert_mgmt_start_check(self):
        """
        [SIT_Automated] 31 01 10 AB STEUERN_CERTIFICATE_MANAGEMENT_START_CHECK
        Default Session of Engineering Mode - Physical addressing.Positive

        Steps:
            1 - Execute STATUS_DIAG_SESSION_LESEN
                22 F1 86
            2 - Execute ENERGIESPARMODE 00
                31 01 0F 0C 00
            3 - Execute STEUERN_CERTIFICATE_MANAGEMENT_START_CHECK(31 01 10 AB) and check output
                71 01 10 AB 00 09
        """
        certificate_management_start_check_output = self.test.diagnostic_client.certificate_management_start_check()
        wait_for_start_check_to_complete(self.test.diagnostic_client)

        assert_equal(
            certificate_management_start_check_output,
            "00 09",
            "Expected output was not obtained for CERTIFICATE_MANAGEMENT_START_CHECK."
            f" Obtained output: {certificate_management_start_check_output}",
        )

    @metadata(
        testsuite=["BAT", "SI-diag", "SI-staging", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-5678",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_BASIC_SECURITY_SF_RELATED"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                ],
            },
        },
    )
    def test_009_certificates_and_bindings_dtc(self):
        """[SIT_Automated] IDCEVO DTC: 0x026380 CERTIFICATES_AND_BINDINGS-TYPE1_PLANT-NOT_READY
        - Physical addressing.Positive

        Pre-Condition:
            - Active diagnostic session
            - Energy mode set to normal
            - ECU has signed certificates

        Steps:
        1 - Execute CERTIFICATE_MANAGEMENT_START_CHECK (31 01 10 AB)
        2 - FS lesen and ensure 0x026380 CERTIFICATES_AND_BINDINGS-TYPE1_PLANT-NOT_READY DTC is not present
        3 - Delete the csrs, certs and keys folders from var/sys/sysfunc path
        4 - Wipe CSRs with the job RC_STEUERN_WIPE_CSR (31 01 F0 45)
        5 - Execute CERTIFICATE_MANAGEMENT_START_CHECK
        6 - FS lesen and ensure 0x026380 CERTIFICATES_AND_BINDINGS-TYPE1_PLANT-NOT_READY DTC is present!

        Expected outcome:
        - DTC 0x026380 CERTIFICATES_AND_BINDINGS-TYPE1_PLANT-NOT_READY is raised

        Finally:
            - Restore certificates
        """
        cert_and_binding_dtc_string = CERTIFICATES_AND_BINDINGS_DTC_TEMPLATE.format(
            diag_addr=f"{self.test.mtee_target.ecu_diagnostic_id:x}"
        ).upper()
        certs_and_binding_dtc_code = int(cert_and_binding_dtc_string, 16)

        self.test.diagnostic_client.clear_single_dtc(certs_and_binding_dtc_code)

        trigger_start_check_and_wait_for_completion(self.test.diagnostic_client)

        dtc_list_str = get_dtc_list(self.test.diagnostic_client)
        assert_true(
            cert_and_binding_dtc_string not in dtc_list_str, f"DTC {cert_and_binding_dtc_string} unexpectedly raised"
        )

        self.test.mtee_target.execute_command(["rm", "-rf", "/var/sys/sysfunc/csrs"])
        self.test.mtee_target.execute_command(["rm", "-rf", "/var/sys/sysfunc/certs"])
        self.test.mtee_target.execute_command(["rm", "-rf", "/var/sys/sysfunc/keys"])

        wipe_csrs(self.test.diagnostic_client)

        trigger_start_check_and_wait_for_completion(self.test.diagnostic_client)

        dtc_list_str = get_dtc_list(self.test.diagnostic_client)

        # We want to restore persistency for the next tests and remove DTC afterwards
        # Reboot is required to recover from the WIPE CSRS job, otherwise ECU does not accept the same persistency
        self.test.mtee_target.reboot(check_target=True)
        self.test.mtee_target.restore_persistence_csrs_keys()
        self.test.mtee_target.restore_persistence_certs()
        wait_for_start_check_to_complete(self.test.diagnostic_client)
        if cert_and_binding_dtc_string in dtc_list_str:
            self.test.diagnostic_client.clear_single_dtc(certs_and_binding_dtc_code)

        assert_true(cert_and_binding_dtc_string in dtc_list_str, f"DTC {cert_and_binding_dtc_string} was not raised")

    @metadata(
        testsuite=["BAT", "SI-diag", "SI-staging", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-5682",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                ],
            },
        },
    )
    def test_010_sfa_token_status(self):
        """[SIT_Automated] 31 01 0F 2E STEUERN_SFA_VERIFY_TOKEN Default Session of Engineering Mode
        - Physical addressing.Positive

        Steps:
        1 - Execute STATUS_DIAG_SESSION_LESEN
            22 F1 86
        2 - Execute ENERGIESPARMODE 00
            31 01 0F 0C 00
        3 - Validate SFA_VERIFY_TOKEN
            31 01 0F 2E
        """
        # Perform SFA_VERIFY_TOKEN. Test will fail if an exception is raised by general reject
        sfa_verify_token_output = self.test.diagnostic_client.sfa_verify_token()
        assert_equal(
            sfa_verify_token_output,
            "",
            "Expected output was not obtained for SFA_VERIFY_TOKEN. Obtained output: {sfa_verify_token_output}",
        )

    @metadata(
        testsuite=["BAT", "SI-diag", "SI-staging", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-5683",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "PRODUCTION_DATA"),
                    config.get("FEATURES", "HARDWARE_INFO"),
                    config.get("FEATURES", "DIAGJOBS_BASIC_SECURITY_SF_RELATED_SFA"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                    config.get("FEATURES", "SECURE_ECU_MODES"),
                ],
            },
        },
    )
    def test_011_ecumodes_read_mode(self):
        """[SIT_Automated] 22 80 02 STATUS_ECUMODES_READ_MODE Default Session of Engineering Mode
        - Physical addressing.Positive
        Pre-conditions:
            Execute STATUS_DIAG_SESSION_LESEN
            Set energy mode as Normal
        Steps:
            1 - Execute ECUMODES_READ_MODE and validate output
                # 22 80 02
        """

        ecumode_output = self.test.diagnostic_client.ecumodes_read_mode()
        assert_equal(
            ecumode_output,
            "00 00 01",
            f"Failed to validate secure ECU mode. Output of ECUMODES_READ_MODE: {ecumode_output}",
        )

    @metadata(
        testsuite=["BAT", "SI-diag", "SI-staging", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-5681",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                ],
            },
        },
    )
    def test_012_sfa_ids_diagjob(self):
        """[SIT_Automated] 31 01 0F 28 STEUERN_SFA_DISCOVER_FEATURE_IDS Default Session of Engineering Mode
        - Physical addressing.Positiv
        Steps:
        1 - Execute STATUS_DIAG_SESSION_LESEN
            22 F1 86
        2 - Execute ENERGIESPARMODE 00
            31 01 0F 0C 00
        3 - Select  STEUERN_SFA_DISCOVER_FEATURE_IDS  31 01 0F 28 00
        """

        translated_hex_to_str_dict = dict()

        hexadecimal_paring = diagnostic_job_data.get("SfaDiscoverFeatureIds", {}).get("hexadecimal_paring")

        assert (
            hexadecimal_paring is not None
        ), "It is not possible to get the 'hexadecimal_paring' in the configuration"

        feature_status = diagnostic_job_data.get("SfaDiscoverFeatureIds", {}).get("feature_status")

        assert (
            feature_status is not None
        ), "It is not possible to get the 'feature_status'\
        in the  configuration"
        feature_validations = diagnostic_job_data.get("SfaDiscoverFeatureIds", {}).get("feature_validations")

        assert (
            feature_validations is not None
        ), "It is not possible to get the 'feature_validations'\
        in the  configuration"

        sfa_discover_feature_ids_output = self.test.diagnostic_client.sfa_discover_feature_ids(
            convert_integer_to_hex_string(
                const.SFA_DISCOVER_FEATURE_IDS_FEATURE_TYPE["ALL_FEATURE_IDS"],
                const.FEATURE_TYPE_LENGTH_BYTES,
            ),
        )
        sfa_discover_first_output, sfa_discover_second_output = sfa_discover_feature_ids_output
        hexa_dict = {
            key: f"({sfa_discover_first_output[key]} {sfa_discover_second_output[key]})"
            for key in sfa_discover_first_output
        }

        for key, value in hexadecimal_paring.items():
            if value in hexa_dict:
                validation_code, status_code = hexa_dict[value][1:-1].split()
                validation_translation = feature_validations[validation_code]
                status_translation = feature_status[status_code]
                translated_hex_to_str_dict[
                    key
                ] = f"feature_validations: {validation_translation}, feature_status: {status_translation}"
            else:
                logger.info(f"Key {value} not found in hexa_dict")

        logger.info(f"The diagnostic jobs have the following status {translated_hex_to_str_dict}")
        error_keys = [key for key, value in translated_hex_to_str_dict.items() if "ERROR" in value]
        assert_true(not error_keys, f"An 'ERROR' value was found in the keys: {error_keys}")

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
        duplicates="IDCEVODEV-5700",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                ],
            },
        },
    )
    def test_013_acl_status_diagjob(self):
        """[SIT_Automated] 22 17 77 ACL_STATUS Default Session of Engineering Mode - Physical addressing.Positive

        Steps:
        1 - Execute STATUS_DIAG_SESSION_LESEN
            22 F1 86
        2 - Execute ENERGIESPARMODE 00
            31 01 0F 0C 00
        3 - Read ACL_STATUS
            22 17 77

        Expected Output: 0x01 DEACTIVATED
        Possible Output: 0x00 ACTIVATED, 0x01 DEACTIVATED, 0xFF INVALID
        """

        did = 0x1777
        acl_status_output = custom_read_data_by_did(self.test.diagnostic_client, did)
        logger.info(f"Output of ACL_STATUS Diagjob: {acl_status_output}")
        assert_equal(
            acl_status_output,
            "01",
            f"Expected ACL mechanism to be deactivated (01). Received ACL_STATUS as: {acl_status_output}",
        )

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
        duplicates="IDCEVODEV-5701",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                ],
            },
        },
    )
    @skipIf(not target.has_capability(TE.target.hardware.idcevo), "Test not applicable for this ECU")
    def test_014_acl_status_read_dtc(self):
        """[SIT_Automated] IDCEVO DTC: 0x026379:DTC ACL_OPERATION_NOT_STARTED

        Steps:
        1 - Execute STATUS_DIAG_SESSION_LESEN and ENERGIESPARMODE as precondition
        2 - Read ACL_STATUS and validate its deactivated.
        3 - Read DTC and check 0x026379 is present.
        4 - Activate ACL by executing ACL_OPERATION_CONTROL
        5 - Read ACL_STATUS and validate its activated.
        6 - Read DTC and validate 0x026379 is not present.

        """

        expected_dtc_string = hex(ACL_OPERATION_NOT_STARTED_DTC).upper().replace("0X", "0X0")
        self.test.diagnostic_client.clear_single_dtc(ACL_OPERATION_NOT_STARTED_DTC)
        did = 0x1777  # ACL_STATUS
        acl_status_output = custom_read_data_by_did(self.test.diagnostic_client, did)
        logger.info(f"Output of ACL_STATUS Diagjob: {acl_status_output}")
        assert_equal(
            acl_status_output,
            "01",
            f"Expected ACL mechanism to be deactivated (01). Received ACL_STATUS as: {acl_status_output}",
        )
        dtc_list_str = get_dtc_list(self.test.diagnostic_client)
        assert_true(expected_dtc_string in dtc_list_str, f"DTC {expected_dtc_string} was not raised")

        rid = 0x1120  # ACL_OPERATION_CONTROL
        with self.test.diagnostic_client.diagnostic_session_manager() as ecu:
            acl_operation_control = enhex(ecu.start_routine(rid))
        logger.info(f"Output of ACL_OPERATION_CONTROL Diagjob: {acl_operation_control}")

        acl_status_output = custom_read_data_by_did(self.test.diagnostic_client, did)
        logger.info(f"Output of ACL_STATUS Diagjob after ACL_OPERATION_CONTROL : {acl_status_output}")
        assert_equal(
            acl_status_output,
            "00",
            f"Expected ACL mechanism to be activated (00). Received ACL_STATUS as: {acl_status_output}",
        )
        dtc_list_str = get_dtc_list(self.test.diagnostic_client)
        assert_true(expected_dtc_string not in dtc_list_str, f"DTC {expected_dtc_string} unexpectedly raised")

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
        duplicates="IDCEVODEV-6979",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                ],
            },
        },
    )
    def test_015_steuern_disable_postpone_shutdown(self):
        """[SIT_Automated] STEUERN_DISABLE_POSTPONE_SHUTDOWN Default Session of Engineering Mode
        - Physical addressing.Positive

        Steps:
        1 - Check the status of postpone shutdown with status_DISABLE_POSTPONE_SHUTDOWN job and make sure it's not set
        2 - Get DTC list and verify POSTPONE_SHUTDOWN_DISABLED is not present
        3 - Enable postpone shutdown
        4 - Get DTC list and verify POSTPONE_SHUTDOWN_DISABLED is present
        5 - Disable postpone shutdown (Clean up after test) and clear generated DTC.

        Assertion:
        Test fails if DTC is not present after enabling postpone shutdown
        """

        dtc_postpone_shutdown_disabled = POSTPONE_SHUTDOWN_DISABLED.get(self.test.mtee_target.options.target, "")
        assert_true(bool(dtc_postpone_shutdown_disabled), "Current target is not associated with a DTC.")

        check_and_disable_postpone_shutdown(self.test.diagnostic_client)

        dtc_list_str = get_dtc_list(self.test.diagnostic_client)
        logger.info(f"DTC List before routine start : {dtc_list_str}")
        assert_true(
            dtc_postpone_shutdown_disabled not in dtc_list_str,
            f"DTC - {dtc_postpone_shutdown_disabled} should not be present in DTC list."
            " Status of postpone_shutdown is 00",
        )

        enable_postpone_shutdown(self.test.diagnostic_client)

        dtc_list_after_enable_postpone_shutdown = get_dtc_list(self.test.diagnostic_client)
        logger.info(f"DTC List after routine start : {dtc_list_after_enable_postpone_shutdown}")
        if dtc_postpone_shutdown_disabled not in dtc_list_after_enable_postpone_shutdown:
            logger.error(f"DTC - {dtc_postpone_shutdown_disabled} should be present in DTC list.")

        # Test cleanup begins here
        check_and_disable_postpone_shutdown(self.test.diagnostic_client)
        self.test.diagnostic_client.clear_single_dtc(int(dtc_postpone_shutdown_disabled, 16))

        dtc_list_str = get_dtc_list(self.test.diagnostic_client)
        logger.info(f"DTC List after DTC cleared : {dtc_list_str}")
        if dtc_postpone_shutdown_disabled in dtc_list_str:
            logger.error(
                f"DTC {dtc_postpone_shutdown_disabled} shouldnt be in DTC list"
                "after being cleared and postpone shutdown disabled."
            )

        assert_true(
            dtc_postpone_shutdown_disabled in dtc_list_after_enable_postpone_shutdown,
            f"test failed: DTC {dtc_postpone_shutdown_disabled} expected after enabling postpone shutdown"
            "but it could not be found.",
        )

    @metadata(
        testsuite=["BAT", "SI-diag", "ACM", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-13088, IDCEVODEV-13092",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                    config.get("FEATURES", "KDS_2_0_INFRASTRUCTURE"),
                ],
            },
        },
    )
    @skipIf(not target.has_capability(TE.target.hardware.idcevo), "Test not applicable for this ECU")
    def test_016_kds_not_individualized(self):
        """[SIT_Automated]  IDCEVO DTC's : 0x0263B2: 'KDS_NOT_INDIVIDUALIZED' & 0x0263B0: 'KDS_NOT_LOCKED'

        Steps:
        1 - Execute STATUS_DIAG_SESSION_LESEN and ENERGIESPARMODE as precondition
        2 - Read DTC of the target
        3 - If DTC 0x0263B2 is present, Follow all the below steps. Else skip steps from 4 to 8.
            Reason for skip - KDS is already individualized.
        4-  0x0263B0 is not present in DTC list
        5 - Clear DTC and validate 0x0263B2 is still present in DTC list
        6 - Execute steuern_kds_action
        7 - Execute status_kds_action
        8 - Execute steuern_kds_data
        9 - Execute status_kds_data
        10 - Validate if 02 is the 11th bit observed in the output response
        11 - Validate 0x0263B2 is not present & 0x0263B0 is present in DTC list
        """

        kds_not_individualized_dtc = hex(KDS_NOT_INDIVIDUALIZED_DTC).upper().replace("0X", "0X0")
        kds_not_locked_dtc = hex(KDS_NOT_LOCKED_DTC).upper().replace("0X", "0X0")
        logger.info("Dtc list before executing kds_Action")
        dtc_list_str = get_dtc_list(self.test.diagnostic_client)

        if kds_not_individualized_dtc in dtc_list_str:
            assert_true(kds_not_locked_dtc not in dtc_list_str, f"DTC {kds_not_locked_dtc} unexpectedly raised")
            self.test.diagnostic_client.clear_dtc(mem="FS")
            dtc_list_str = get_dtc_list(self.test.diagnostic_client)
            assert_true(kds_not_individualized_dtc in dtc_list_str, f"DTC {kds_not_individualized_dtc} was not raised")
            execute_and_validate_kds_action_data(self.test.diagnostic_client)
        else:
            validate_kds_individualization_state(self.test.diagnostic_client)

        logger.info("Dtc list after executing kds_Action")
        dtc_list_str = get_dtc_list(self.test.diagnostic_client)
        assert_true(
            kds_not_individualized_dtc not in dtc_list_str, f"DTC {kds_not_individualized_dtc} unexpectedly raised"
        )
        assert_true(kds_not_locked_dtc in dtc_list_str, f"DTC {kds_not_locked_dtc} was not raised")

    @metadata(
        testsuite=["BAT", "SI-diag", "ACM", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-5686",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                    config.get("FEATURES", "KDS_2_0_INFRASTRUCTURE"),
                ],
            },
        },
    )
    @skipIf(not target.has_capability(TE.target.hardware.idcevo), "Test not applicable for this ECU")
    def test_017_kds_status_diagjob(self):
        """[SIT_Automated] 31 03 0F FF STATUS_KDS_DATA Default Session of Engineering Mode
         - Physical addressing.Positive

        Steps:
        1 - Execute STATUS_DIAG_SESSION_LESEN and ENERGIESPARMODE as precondition
        2 - Execute steuern_kds_action
        3 - Execute status_kds_action
        4 - Execute steuern_kds_data
        5 - Execute status_kds_data
        6 - Validate if 02 is the 11th bit observed in the output response
        """

        execute_and_validate_kds_action_data(self.test.diagnostic_client)

    @metadata(
        testsuite=["BAT", "SI-diag", "ACM", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-5667",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "HARDWARE_INFO"),
                    config.get("FEATURES", "PRODUCTION_DATA"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                ],
            },
        },
    )
    def test_018_check_status_ser_nr_dom(self):
        """[SIT_Automated] Check STATUS_SER_NR_DOM
        Steps:
            1 - Get ECU serial number with STATUS_SER_NR_DOM Diag Job (62 D0 19)
            2 - Compare obtained serial number against the label value (Stored on TEE config)
        Expected Output:
            1 - Validate Positive Response for STATUS_SER_NR_DOM Diag Job
            2 - Values are the same
        """
        expected_output = self.test.mtee_target.options.target_serial_no
        diag_job_output = self.test.diagnostic_client.status_ser_nr_dom()
        actual_output = bytes.fromhex(diag_job_output).decode("utf-8")
        assert_equal(
            actual_output.upper(),
            expected_output.upper(),
            f"Expected Output: {expected_output} was not obtained for DiagJob status_ser_nr_dom."
            f"Obtained output: {actual_output}",
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
        duplicates="IDCEVODEV-5684",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DIAGJOBS"),
                    config.get("FEATURES", "DTC_HANDLING"),
                    config.get("FEATURES", "DTC_HANDLING_DTC_DIAGNOSTIC_JOBS"),
                    config.get("FEATURES", "DTC_HANDLING_INTERFACE_FOR_DTC_QUERYING_SETTING"),
                    config.get("FEATURES", "SECURE_ECU_MODES"),
                    config.get("FEATURES", "DIAGJOBS_BASIC_SECURITY_SF_RELATED_SFA"),
                    config.get("FEATURES", "DIAGJOBS_DIAGNOSTICS_JOBS_PLANT"),
                ],
            },
        },
    )
    def test_019_ecumodes_read_mode(self):
        """[SIT_Automated] 02 xx 85 DTC Secure ECU Modes: ECU not in field mode
        Steps:
            1- Switch Target to Field mode
            2- Execute ECUMODES_READ_MODE and ensure that secure mode is set to field
               # ECUMODES_READ_MODE- 22 80 02, FIELD Mode- 00 00 02
            3- Fetch DTC list and ensure that DTC - 0X026385 is not present.
            4- Switch Target to Eng mode
            5- Fetch DTC list and ensure that DTC - 0X026385 is set.
        """

        self.secure_mode_object.switch_mode("FIELD")

        ecumode_output = self.test.diagnostic_client.ecumodes_read_mode()
        logger.info(f"Current secure mode - {ecumode_output}")
        assert_equal(
            ecumode_output,
            "00 00 02",
            f"Secure mode is not set to Field. Output of ECUMODES_READ_MODE: {ecumode_output}",
        )

        dtc_list_str = get_dtc_list(self.test.diagnostic_client)
        match_found = match_string_with_regex(ECU_NOT_IN_FIELD_MODE_DTC_REG, dtc_list_str)
        assert_is_none(
            match_found,
            f"DTC pattern- {ECU_NOT_IN_FIELD_MODE_DTC_REG} was not expected while in Field mode",
        )

        self.secure_mode_object.switch_mode("ENGINEERING")

        dtc_list_str = get_dtc_list(self.test.diagnostic_client)
        match_found = match_string_with_regex(ECU_NOT_IN_FIELD_MODE_DTC_REG, dtc_list_str)
        assert_is_not_none(
            match_found,
            f"DTC pattern- {ECU_NOT_IN_FIELD_MODE_DTC_REG} is expected to be raised in Engineering mode",
        )

    @metadata(
        testsuite=["BAT", "SI-diag", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-175807",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "PLANT_DIAGNOSTIC_FUNCTIONS"),
                ],
            },
        },
    )
    @skipIf(not target.has_capability(TE.target.hardware.rse26), "Test not applicable for this ECU")
    def test_020_system_reset_using_diagnostic_on_wohnen(self):
        """
        [SIT_Automated] Verify System reset using Diagnostic on WOHNEN
        Steps:
            1. Enable SOC logs using DLT
            2. Set Vehicle Condition Status to WOHNEN
            3. Execute Steuergeraete Reset
        Expected outcome:
            1. System should starts up
            2. Ensure that expected payload mentioned in list - "SYSTEM_RESET_ON_WOHNEN_STATE_PAYLOAD" are
               found in DLT traces.
        """
        system_reset_on_wohnen_state_payload = [
            {"payload_decoded": re.compile(r"Changed NodeState: NsmNodeState_BaseRunning.*")},
            {"payload_decoded": re.compile(r"PowerStateMachine input: pwf is: WOHNEN")},
            {"payload_decoded": re.compile(r"SHUTDOWN_APPLICATION_RESET\(5\)")},
            {"payload_decoded": re.compile(r"NSMA: RequestNodeRestart. restartReason: 7\(Application\).*")},
            {"payload_decoded": re.compile(r".*calling prepareShutdown with shutdownType: ApplicationReset.*")},
            {"payload_decoded": re.compile(r"setWakeUpReason\[WAKEUP_REASON_APPLICATION\(8\)\]")},
        ]
        self.verify_system_reset_using_diagnostic(
            VehicleCondition.WOHNEN,
            system_reset_on_wohnen_state_payload,
        )

    @metadata(
        testsuite=["BAT", "SI-diag", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-175824",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "PLANT_DIAGNOSTIC_FUNCTIONS"),
            },
        },
    )
    @skipIf(not target.has_capability(TE.target.hardware.rse26), "Test not applicable for this ECU")
    def test_021_system_reset_using_diagnostic_on_standfunktionen(self):
        """
        [SIT_Automated] Verify system reset using Diagnostic on STANDFUNKTIONEN
        Steps:
            1. Enable SOC logs using DLT
            2. Set Vehicle Condition Status to STANDFUNKTIONEN
            3. Execute Steuergeraete Reset
        Expected outcome:
            1. System should starts up
            2. Ensure that expected payload mentioned in list - "SYSTEM_RESET_ON_STANDFUNKTIONEN_STATE_PAYLOAD" are
               found in DLT traces.
        """
        system_reset_on_standfunktionen_state_payload = [
            {"payload_decoded": re.compile(r"Changed NodeState: NsmNodeState_BaseRunning.*")},
            {"payload_decoded": re.compile(r"PowerStateMachine input: pwf is: STANDFUNKTIONEN")},
            {"payload_decoded": re.compile(r"SHUTDOWN_APPLICATION_RESET\(5\)")},
            {"payload_decoded": re.compile(r"NSMA: RequestNodeRestart. restartReason: 7\(Application\)")},
            {"payload_decoded": re.compile(r".*calling prepareShutdown with shutdownType: ApplicationReset.*")},
            {"payload_decoded": re.compile(r"setWakeUpReason\[WAKEUP_REASON_APPLICATION\(8\)\]")},
        ]
        self.verify_system_reset_using_diagnostic(
            VehicleCondition.STANDFUNKTIONEN_KUNDE_NICHT_IM_FZG, system_reset_on_standfunktionen_state_payload
        )

    @metadata(
        testsuite=["BAT", "SI-diag", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-175816",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "PLANT_DIAGNOSTIC_FUNCTIONS"),
                ],
            },
        },
    )
    @skipIf(not target.has_capability(TE.target.hardware.rse26), "Test not applicable for this ECU")
    def test_022_system_reset_diag_fahren(self):
        """
        [SIT_Automated] Verify System reset using Diagnostic on FAHREN
        Steps:
            1. Start DLT traces
            2. Trigger vehicle condition FAHREN
            3. Execute Diag job - steuergeraete_reset
            4. Ensure the payloads mentioned in dict "system_reset_on_fahren_state_payload" are found in DLT traces
        """
        system_reset_on_fahren_state_payload = [
            {"payload_decoded": re.compile(r"Changed ShutdownState: Running => ApplicationShutdownNonReversible.*")},
            {"payload_decoded": re.compile(r".*PowerStateMachine input: pwf is: FAHREN")},
            {"payload_decoded": re.compile(r".*SHUTDOWN_APPLICATION_RESET.*")},
            {"payload_decoded": re.compile(r"NSMA: RequestNodeRestart. restartReason: 7\(Application\)")},
            {"payload_decoded": re.compile(r".*setWakeUpReasonWAKEUP_REASON_APPLICATION\(8\).*")},
            {"payload_decoded": re.compile(r".*calling prepareShutdown with shutdownType: ApplicationReset.*")},
            {"payload_decoded": re.compile(r".*Received prepareShutdown result: Ok.*")},
        ]
        self.verify_system_reset_using_diagnostic(
            vehicle_condition=VehicleCondition.FAHREN, payload_msg_to_validate=system_reset_on_fahren_state_payload
        )

    @metadata(
        testsuite=["BAT", "SI-diag"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-368672",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "STARTUP"),
                    config.get("FEATURES", "STARTUP_FIRST_SWITCH_TO_POWER"),
                ],
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["idcevo", "rse26"]), "This test isn't supported by this ECU!")
    def test_023_verify_first_switch_to_power_startup(self):
        """
        [SIT_Automated] Verify first Switch to power Startup
        Steps:
            1. Start DLT traces and reboot the target
            2. Change vehicle status to PRUEFEN ANALYSE DIAGNOSE
            3. Capture a screenshot and check the file size.
            4. Set target to default vehicle state

        Expected Outcome:
            For step 2:
                - Ensure that expected payload mentioned in the list -"pad_pattern" are found in DLT traces.
                - Ensure that target is in application mode to make sure linux booted
            For step 3:
                - Ensure Android VM is up and file size is not 0.
        """
        pad_pattern = {"payload_decoded": re.compile(r".*PowerStateMachine input: pwf is: DIAGNOSE.*")}
        try:
            with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
                self.test.mtee_target.reboot(prefer_softreboot=False)
                self.test.mtee_target.wait_for_nsm_fully_operational()
                self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
                dlt_msgs = trace.wait_for(pad_pattern, count=1, timeout=60)
            validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, [pad_pattern], "SOC logs")

            assert_true(
                wait_for_application_target(self.test.mtee_target, timeout=180),
                "Target is not up after switching to PAD. Waited for 180 seconds.",
            )

            self.test.apinext_target.wait_for_boot_completed_flag()
            file_path = os.path.join(self.test.results_dir, "screenshot_android.png")
            self.test.apinext_target.take_screenshot(file_path)
            screenshot_file_size, _, _ = run_command(f"stat -c %s {file_path}", shell=True)
            assert_true(
                int(screenshot_file_size) != 0, f"Actual file size is {screenshot_file_size}. 0 size not expected"
            )
        finally:
            lf.set_default_vehicle_state()

    @metadata(
        testsuite=["BAT", "SI-diag"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-178949",
        traceability={""},
    )
    @skipIf(not target.has_capability(TE.target.hardware.rse26), "Test not applicable for this ECU")
    def test_024_system_reset_using_diagnostic_while_remote_infotainment(self):
        """
        [SIT_Automated] Verify System reset using Diagnostic while Remote_Infotainment
        Steps:
            1. Start SOC traces and switch to STANDFUNKTIONEN
            2. Request FPN Remote_Infotainment
            3. Execute Steuergeraete Reset
        Expected outcome:
            - Ensure that expected payload mentioned in the list
                "fpn_remote_infotainment_after_standfunktionen_state_payloads" and
                "system_reset_after_fpn_remote_infotainment_payloads" are found in DLT traces.
        """
        fpn_remote_infotainment_after_standfunktionen_state_payloads = [
            {"payload_decoded": re.compile(r".*pwf is: STANDFUNKTIONEN.*")},
            {
                "payload_decoded": re.compile(
                    r".*NetworkManagementUDPFullNW: set attribute FunctionalPartialNetworkStatus.*"
                )
            },
            {"payload_decoded": re.compile(r".*NodeState: NsmNodeState_FullyOperational, NmState: ReadySleepState.*")},
        ]
        system_reset_after_fpn_remote_infotainment_payloads = [
            {"payload_decoded": re.compile(r".* SHUTDOWN_APPLICATION_RESET.*")},
            {"payload_decoded": re.compile(r".* RequestNodeRestart. restartReason: 7.*")},
            {"payload_decoded": re.compile(r".*Shutdown Type: SHUTDOWN_APPLICATION_RESET.*")},
            {"payload_decoded": re.compile(r".*WAKEUP_REASON_APPLICATION.*")},
            {"payload_decoded": re.compile(r".*WakeUpReason: Application.*")},
        ]
        try:
            with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
                self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.STANDFUNKTIONEN_KUNDE_NICHT_IM_FZG)
                lf.set_vcar_func_pn(PARTIALNETWORKS2BITFIELD.REMOTE_INFOTAINMENT_ON)
                time.sleep(5)  # allow FPN to set and verify the behavior via DLT logs
                dlt_msgs = trace.wait_for_multi_filters(
                    filters=fpn_remote_infotainment_after_standfunktionen_state_payloads,
                    count=0,
                    timeout=120,
                )
            validate_expected_dlt_payloads_in_dlt_trace(
                dlt_msgs,
                fpn_remote_infotainment_after_standfunktionen_state_payloads,
                "SOC logs",
            )
            with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
                self.test.diagnostic_client.ecu_reset()
                self.test.mtee_target.ssh.wait_for_ssh(self.test.mtee_target.get_address(), timeout=60)
                dlt_msgs = trace.wait_for_multi_filters(
                    filters=system_reset_after_fpn_remote_infotainment_payloads,
                    count=0,
                    timeout=120,
                )
            self.test.mtee_target.wait_for_nsm_fully_operational()
            validate_expected_dlt_payloads_in_dlt_trace(
                dlt_msgs,
                system_reset_after_fpn_remote_infotainment_payloads,
                "SOC logs",
            )
        finally:
            lf.set_default_vehicle_state()

    @metadata(
        testsuite=["SI", "SI-diag"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-87033",
        traceability={
            config.get("tests", "traceability"): {
                config.get("FEATURES", "PLANT_DIAGNOSTIC_FUNCTIONS"),
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["rse26", "idcevo"]), "This test isn't supported by this ECU!")
    def test_025_verify_ecu_power_down(self):
        """
        [SIT_Automated] ECU mode: Power Down using diagnostics
        Precondition:
            1. Switch to PRUEFEN_ANALYSE_DIAGNOSE state.
        Steps:
            1. Trigger 11 41 diag job to enable power down mode.
            2. Start DLT Traces and switch to PARKEN_BN_IO state.

        Expected Outcome:
            - From step 1 ensure that expected payload mentioned in the list -
                "powerdown_pattern" are found in DLT traces.
            - From step 2 ensure that expected payload mentioned in the list -
               "shutdown_pattern" are found in DLT traces.
        """
        pad_pattern = {"payload_decoded": re.compile(r".*PowerStateMachine.*pwf is: DIAGNOSE.*")}
        powerdown_pattern = [
            {"payload_decoded": re.compile(r".*jobErPowerDown.*")},
            {"payload_decoded": re.compile(r".*mal_cb_is_powerdownmode.*true.*")},
            {
                "payload_decoded": re.compile(
                    r".*LifecycleStubImplBase.*setPowerDownModeStatus.*true Dropping all the PNs due to PowerDownMod.*"
                )
            },
            {"payload_decoded": re.compile(r".*ShutdownStateMachine.*set shutdown type: NormalShutdown.*")},
            {"payload_decoded": re.compile(r".*PowerStateMachine.*setPowerDownMode: true.*isFastShutdown: false.*")},
        ]
        shutdown_pattern = [
            {"payload_decoded": re.compile(r".*PowerStateMachine input: pwf is: PARKEN.*")},
            {"payload_decoded": re.compile(r".*mal_cb_lcm_powerstate_detailed.*SHUTDOWN_MODE.*")},
            {"payload_decoded": re.compile(r".*shutdown type: NormalShutdown.*")},
            {"payload_decoded": re.compile(r".*calling prepareShutdown with shutdownType: FullOff.*")},
        ]
        # Switch to PAD State as a precondition
        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
            dlt_msgs = trace.wait_for(pad_pattern, count=1, timeout=60)
        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, [pad_pattern], "SOC logs")
        assert_true(
            wait_for_application_target(self.test.mtee_target),
            "Target not in application mode after switching to PAD",
        )
        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
            self.test.diagnostic_client.ecu_powerdown()
            dlt_msgs = trace.wait_for_multi_filters(
                filters=powerdown_pattern,
                drop=True,
                count=6,
                timeout=180,
                skip=True,
            )
        self.restore_target_if_not_alive()
        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, powerdown_pattern, "SOC logs")

        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PARKEN_BN_IO)
            lf.stop_keepalive()
            lf.ecu_to_enter_sleep(timeout=80)
            dlt_msgs = trace.wait_for_multi_filters(
                filters=shutdown_pattern,
                drop=True,
                count=5,
                timeout=180,
                skip=True,
            )
        self.restore_target_if_not_alive()
        lf.set_default_vehicle_state()
        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, shutdown_pattern, "SOC logs")
