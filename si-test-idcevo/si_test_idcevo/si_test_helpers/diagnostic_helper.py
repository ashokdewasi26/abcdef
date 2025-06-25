# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Helpers for diagnostic tests"""

import logging
import re
import time

from diagnose.tools import enhex, unhex
from mtee.testing.tools import assert_equal, assert_true
from validation_utils.utils import TimeoutCondition, TimeoutError

logger = logging.getLogger(__name__)

diagnostic_job_data = {
    "startCertificateManagementReadoutStatus": {
        "hexadecimal_paring": {
            "OK": "00",
            "UNCHECKED": "01",
            "MALFORMED": "02",
            "EMPTY": "03",
            "INCOMPLETE": "04",
            "SECURITY_ERROR": "05",
            "WRONG_VIN_17": "06",
            "CHECK_RUNNING": "07",
            "ISSUER_CERT_ERROR": "08",
            "WRONG_ECU_UID": "09",
            "DECRYPTION_ERROR": "0A",
            "OWN_CERT_NOT_PRESENT": "0B",
            "OUTDATED": "0C",
            "KEY_ERROR": "0D",
            "NOT_USED": "FE",
            "OTHER": "FF",
        },
        "filter_of_response": {
            "certificates": {"size": 1},
            "bindings": {"size": 1},
            "otherBindings": {"size": 1},
            "onlineCertificates": {"size": 1},
            "onlineBindings": {"size": 1},
        },
    },
    "statusKdsAction": {
        "kdsId": {
            "0101": "HEADUNIT",
            "0301": "BZF_GWS",
            "0302": "ZBE",
            "0303": "BZM_OR_BIM",
            "0401": "DSM_TPT_DRIVER_AIRBAG",
            "0402": "DSM_TPT_STEERING_WHEEL",
            "0501": "HEADLIGHT_RIGHT",
            "0502": "HEADLIGHT_LEFT",
            "0601": "FRR_V",
            "0602": "MRR",
            "0608": "FRR_HR",
            "0609": "FRR_HL",
            "FF01": "ALL_CLIENTS_KNOWN_IN_SW",
            "FF10": "MASTER_AS_PARTICIPANT",
            "FF11": "ALL_CLIENTS_IN_MASTER_LIST_OF_PAIRED_COMPONENTS",
            "FF12": "ALL_CLIENTS_IN_MASTER_LIST_OF_COMPONENTS",
        },
        "kdsactionId": {
            "11": "TRIGGER_FREE_PAIRING",
            "21": "TRIGGER_VERIFICATION",
            "31": "RE_PAIR_OR_CLEAR_DATA",
            "41": "LOCK",
            "42": "UNLOCK",
            "51": "RUN_QUICK_CHECK_FOR_PAIRING_CONSISTENCY",
            "61": "CREATE_TEST_SIGNATURE",
            "63": "SHOW_REACTION",
            "99": "UPDATE_COMPONENTLIST",
            "E1": "TRIGGER_INDIVIDUALIZATION",
        },
        "kdsactionResult": {
            "00": "SUCCESS",
            "01": "IN_PROGRESS",
            "02": "PARTIAL",
            "10": "ERROR",
            "11": "FORBIDDEN",
            "12": "TIMEOUT",
        },
    },
    "SfaDiscoverFeatureIds": {
        "hexadecimal_paring": {
            "Plant Mode": "000000",
            "Engineering Mode": "000001",
            "Service Pack Switch": "000100",
            "SecOC Switch": "000101",
            "IuK Cluster Configuration Switch": "000104",
            "Test Switch": "0001FE",
            "Internal Debug Access and DLT external tracing": "001D1A",
            "link deactivation (SP21 only)": "00151D",
            "Function Group Level 1": "005DF1",
            "Function Group Level 2": "005DF2",
            "Function Group Level 3": "005DF3",
            "Flash Protection Plant Mode": "006879",
            "Flash Protection Field Mode": "006880",
            "Client re-pairing": "009C9C",
            "Audit (Operation) Mode": "00AAFC",
            "Delete client pairing": "00DC9D",
            "Test Feature ID": "010001",
            "Deactivation Central Error Memory": "01D2FD",
            "DLT internal tracing": "001D1D",
        },
        "feature_validations": {
            "00": "No secure token received",
            "01": "Enabled",
            "02": "Disabled",
            "03": "Expired",
        },
        "feature_status": {
            "00": "OK",
            "01": "UNCHECKED",
            "02": "MALFORMED",
            "03": "EMPTY",
            "04": "ERROR",
            "05": "SECURITY_ERROR",
            "06": "WRONG_LINKTOID",
            "07": "CHECK_RUNNING",
            "08": "TIMESTAMP_TOO_OLD",
            "09": "VERSION_NOT_SUPPORTED",
            "0A": "FEATURE_ID_NOT_SUPPORTED",
            "0B": "UNKNOWN_LINKTYPE",
            "FF": "OTHER",
        },
    },
}


# Certificate information to be used in the test: test_006_cer_mgmt_csr_diagjob
CERTIFICATE_INFORMATION = {
    "VERSION": {
        "match": "1 (0x0)",
        "pattern": re.compile(r"Version: (?P<v_1>\d+) \((?P<v_2>0x\d+)\)"),
    },
    "ST": {
        "match": "Production",
        "pattern": re.compile(r"ST = (?P<string>\w+)"),
    },
    "O": {
        "match": "BMW Group",
        "pattern": re.compile(r"O = (?P<string>\w+\s\w+)"),
    },
    "OU": {
        "match": "VehiclePKI-ECU",
        "pattern": re.compile(r"OU = (?P<string>\w+\S\w+)"),
    },
    "PUBLIC_KEY_ALGORITHM": {
        "match": "id-ecPublicKey",
        "pattern": re.compile(r"Public Key Algorithm: (?P<string>\w+\S\w+)"),
    },
    "PUBLIC_KEY": {
        "match": "384 bit",
        "pattern": re.compile(r"Public-Key: \((?P<string>\d+ \w+)\)"),
    },
    "SIGNATURE_ALGORITHM": {
        "match": "ecdsa-with-SHA512",
        "pattern": re.compile(r"Signature Algorithm: (?P<string>\w+\S\w+\S\w+)"),
    },
    "ECU-ID": {
        "match": "",  # ECU-ID will be obtained from the target ( mtee_target.options.target_ecu_uid )
        "pattern": re.compile(r"serialNumber = ECU-UID:(?P<serial_number>[A-Za-z0-9]+)"),
    },
}

STEUERN_DISABLE_POSTPONE_SHUTDOWN_RID = 0xA577


def check_individualization(hex_data):
    """Parse the kds action readout status output and check if individualization is success

    :param hex_data: Output of the kds action readout status
    """
    hex_data_split = hex_data.upper().split()

    kdsid_hex = "".join(hex_data_split[:2])
    actionid_hex = hex_data_split[2]
    actionresult_hex = hex_data_split[3]
    kds_response = diagnostic_job_data["statusKdsAction"]

    kdsid_str = kds_response["kdsId"].get(kdsid_hex, "Unknown KDS ID")
    logger.info(f"Found kdsId of {kdsid_str} from the response")
    actionid_str = kds_response["kdsactionId"].get(actionid_hex, "Unknown Action ID")
    action_str = kds_response["kdsactionResult"].get(actionresult_hex, "Unknown Action Result")
    assert_true(
        (actionid_str == "TRIGGER_INDIVIDUALIZATION" and action_str == "SUCCESS"),
        "Expected action_id: TRIGGER_INDIVIDUALIZATION and action_result: SUCCESS. "
        f"Obtained action_id: {actionid_str} and action_result: {action_str}",
    )


def custom_read_data_by_did(diag_client, data):
    """
    Trigger read_data_by_did for all methods not available in tee/tools/diagnosis.py

    :param diag_client (DiagnosticClient): Client to execute Diag Jobs
    :param bytes data: 2 bytes data
    :return: bytes
    """
    try:
        with diag_client.diagnostic_session_manager() as ecu:
            status_output = enhex(ecu.read_data_by_did(data))
            return status_output
    except Exception as e:
        logger.exception(f"Unable to perform diag action. Got exception: {e}")
        raise


def execute_and_validate_kds_action_data(diag_client):
    """Execute and validate kds_action & kds_data for all kds tests

    1 - Execute steuern_kds_action
    2 - Execute status_kds_action
    3 - Execute steuern_kds_data
    4 - Execute status_kds_data
    5 - Validate if "02" is the 11th bit in the output response

    :param diag_client: Client to execute Diag Jobs
    """
    diag_client.steuern_kds_action(unhex("00 00 E1"))
    status_kds_action_output = diag_client.status_kds_action()
    logger.info(f"Output of status_kds_action_output Diagjob: {status_kds_action_output}")
    check_individualization(status_kds_action_output)
    diag_client.steuern_kds_data(unhex("00 00"))
    validate_kds_individualization_state(diag_client)


def validate_kds_individualization_state(diag_client):
    """
    Validate if "02" is the 11th bit in the output response

    :param diag_client: Client to execute Diag Jobs
    """
    status_kds_data_output = diag_client.status_kds_data()
    logger.info(f"Output of status_kds_data_output Diagjob: {status_kds_data_output}")
    assert_equal(
        status_kds_data_output.split()[10],
        "02",
        f"Expected 10th bit of status_kds_data response to be 02. "
        f"Instead found: {status_kds_data_output.split()[10]}",
    )


def enable_postpone_shutdown(diag_client):
    """This method starts routine STEUERN_DISABLE_POSTPONE_SHUTDOWN with argument 01
    :param diag_client: Client to execute Diag Jobs
    """
    argument = b"\x01"
    try:
        with diag_client.diagnostic_session_manager() as ecu:
            ecu.start_routine(STEUERN_DISABLE_POSTPONE_SHUTDOWN_RID, argument)
    except Exception as e:
        logger.exception(f"Unable to send STEUERN_DISABLE_POSTPONE_SHUTDOWN with arg 01 because of error: {e}")

    get_postpone_shutdown_status(diag_client)


def check_and_disable_postpone_shutdown(diag_client):
    """This method checks status of postpone shutdown, and if its different from "00",
    starts routine STEUERN_DISABLE_POSTPONE_SHUTDOWN with argument 00
    Parameters:
    diag_client (Client): The client to execute the Diag Jobs.

    Return type:bytes
    returns the status after disabling the postpone shutdown feature, if it was
    enabled, or the status if it was already disabled.
    """
    status = get_postpone_shutdown_status(diag_client)

    if status != "00":
        argument = b"\x00"
        try:
            with diag_client.diagnostic_session_manager() as ecu:
                ecu.start_routine(STEUERN_DISABLE_POSTPONE_SHUTDOWN_RID, argument)
        except Exception as e:
            logger.exception(f"Unable to send STEUERN_DISABLE_POSTPONE_SHUTDOWN with arg 00 because of error: {e}")

        status = get_postpone_shutdown_status(diag_client)

    return status


def get_postpone_shutdown_status(diag_client):
    """Get status of postpone shutdown

    :param diag_client: Client to execute Diag Jobs
    Full request message eg: - 0x31 03 A5 77

    :rtype: bytes
    '00' = Disabled
    '01' = Enabled
    """
    with diag_client.diagnostic_session_manager() as ecu:
        return enhex(ecu.read_routine(STEUERN_DISABLE_POSTPONE_SHUTDOWN_RID, b""))


def get_dtc_list(diag_client, mem="FS"):
    """Read the dtc and return the list in standard format

    :param diag_client (DiagnosticClient): Client to execute Diag Jobs
    :param str mem: FS, IS or BOTH. Defaults to FS.
    :returns: list of DTCs stored in memory in standard format
    """
    dtc_list = diag_client.read_dtc(mem=mem)
    dtc_list_str = [str(entry.dtc).upper() for entry in dtc_list]
    logger.debug("Read the following DTCs from the target: %s", ", ".join(dtc_list_str))
    return dtc_list_str


def is_dtc_active(diag_client, dtc, mem="FS"):
    """Read the status of a particular primary DTC

    :param diag_client (DiagnosticClient): Client to execute Diag Jobs
    :param str mem: FS, IS or BOTH. Defaults to FS.
    :param str dtc: hexadecimal DTC ID
    :returns bool: 'True' for DTC active and 'False' for DTC inactive or DTC not found.
    """
    # Read DTC memory
    dtc_list = diag_client.read_dtc(mem=mem)
    # Check if DTC is active
    found = False
    for entry in dtc_list:
        if (
            dtc in str(entry.dtc).upper()
            and hasattr(entry.flags, "status_test_failed")
            and entry.flags.status_test_failed
        ):
            found = True
    return found


def parse_cert_management_readout_status_output(output):
    """Parse the certificate management readout status output

    :param output (str): Output of the certificate management readout status
    :return (dict): Dictionary with the status of the certificate management readout
    """
    relevant_bytes = output.split()[:5]
    translated_hex_to_str_dict = dict()

    hexadecimal_paring = diagnostic_job_data.get("startCertificateManagementReadoutStatus", {}).get(
        "hexadecimal_paring"
    )
    assert hexadecimal_paring is not None, "It is not possible to get the 'hexadecimal_paring' in the configuration"

    certificate_job_filters = diagnostic_job_data.get("startCertificateManagementReadoutStatus", {}).get(
        "filter_of_response"
    )

    assert (
        certificate_job_filters is not None
    ), "It is not possible to get the 'certificate_job_filters'\
    in the configuration"
    for job_byte, filter_key_value in zip(relevant_bytes, certificate_job_filters.keys()):
        if job_byte.upper() in hexadecimal_paring.values():
            key_for_job_byte = [
                decoded_key
                for decoded_key, corresponded_byte in hexadecimal_paring.items()
                if corresponded_byte == job_byte.upper()
            ][0]
            translated_hex_to_str_dict[filter_key_value] = key_for_job_byte
        else:
            raise ValueError(f"Value {job_byte.upper()} not found in startCertificateManagementReadoutStatus")

    logger.info(f"The certificate management has the following status {translated_hex_to_str_dict}")
    return translated_hex_to_str_dict


def trigger_start_check_and_wait_for_completion(diag_client, timeout=300):
    """Trigger the start check and wait for completion

    :param diag_client (DiagnosticClient): Client to execute Diag Jobs
    :param timeout (int): Time to wait check to finish, Default 300
    :return: None
    :Raises: TimeoutError if check is still running after timeout
    """
    diag_client.certificate_management_start_check()
    wait_for_start_check_to_complete(diag_client)


def wait_for_start_check_to_complete(diag_client, timeout=300):
    """Wait for the start check to complete

    :param diag_client (DiagnosticClient): Client to execute Diag Jobs
    :param timeout (int): Time to wait check to finish, Default 300
    :return: None
    :Raises: TimeoutError if check is still running after timeout
    """
    timeout_job_status_complete = TimeoutCondition(timeout)
    logger.info(f"Starting the certificate management check with timeout of {timeout}s")
    while timeout_job_status_complete:
        output_cert_mngmt_status = diag_client.certificate_management_readout_status()
        status = parse_cert_management_readout_status_output(output_cert_mngmt_status)
        if status["certificates"] != "CHECK_RUNNING":
            logger.info(f"The check has completed in: {timeout_job_status_complete.time_elapsed}s")
            return None
        time.sleep(10)
    raise TimeoutError("The certificate management check did not complete in the expected time")


def wipe_csrs(diag_client):
    """Wipe ECU certificates

    Execute the diag job RC_STEUERN_WIPE_CSR (31 01 0F 45)

    :param diag_client (DiagnosticClient): Client to execute Diag Jobs
    :return: Returns the job response
    """
    rid = 0xF045
    with diag_client.diagnostic_session_manager() as ecu:
        return enhex(ecu.start_routine(rid))


def steuern_airplane_mode(diag_client, data):
    """
    Enable or disable airplane mode
    :param diag_client (DiagnosticClient): Client to execute Diag Jobs
    :param data (bytes): 1 byte (ARG_AIRPLANE_ACTIVATION: OFF=00, ON=01, NOT DEFINED=FF)

    Full request message for activation eg: 0x2E 7A 20 01
    Full request message for deactivation eg: 0x2E 7A 20 00
    """
    did = 0x7A20
    with diag_client.diagnostic_session_manager() as ecu:
        ecu.write_data_by_did(did, data)


def fetch_and_validate_airplane_mode_status_via_diag(diag_client, expected_state, timeout=5):
    """
    Fetches airplane mode state for a specific duration to validate actual and expected states are same.
    Note: Reason for timer - When toggled between airplane mode, the actual state takes time to reflect.
    :param diag_client (DiagnosticClient): Client to execute Diag Jobs
    :param expected_state (str): expected airplane mode for validation.
    :param timeout (int): Timeout counter to fetch airplane mode status. Default 5
    :return airplane_state: Actual airplane mode state.
    :Raises: TimeoutError if actual airplane mode state does not matches the expected state.
    """
    timer = TimeoutCondition(timeout)
    did = 0x7A20
    try:
        while timer:
            airplane_state = custom_read_data_by_did(diag_client, did)
            logger.info(f"Output of RDBI_AIRPLANE_MODE Diagjob: {airplane_state}")
            if airplane_state == expected_state:
                return True
            else:
                time.sleep(1)
    except TimeoutError:
        raise RuntimeError(
            f"{timeout} second timeout reached while waiting for expected airplane mode - ({expected_state})"
        )
