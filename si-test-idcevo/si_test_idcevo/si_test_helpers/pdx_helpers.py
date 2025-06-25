# Copyright (C) 2023. BMW CTW PT. All rights reserved.
import glob
import logging
import lxml.etree as ET  # noqa: N812
import os  # noqa: AZ100
import shutil
import textwrap

from pathlib import Path

from esys import EsysError
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import assert_false, assert_process_returncode, assert_true, run_command
from mtee_idcevo.pre_test_validator import PreTestVerification
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target
from tee.target_common import VehicleCondition
from tee.tools.secure_modes import SecureECUMode
from validation_utils.utils import TimeoutCondition

logger = logging.getLogger(__name__)

PROCESS_CLASS_DICT = {"01": "HWEL", "02": "HWAP", "05": "CAFD", "06": "BTLD", "07": "FLSL", "08": "SWFL", "0D": "SWFK"}
PROCESS_CLASS_DICT_INV = {v: k for k, v in PROCESS_CLASS_DICT.items()}

NS_TAG = "ns0"
NS = {NS_TAG: "http://bmw.com/2005/psdz.data.svt"}

MANDATORY_SWES = {
    "idcevo": ["0000BBBE", "0000BBBF"],
    "rse26": [
        "0000DED8",
        "0000DEE0",
        "0000DED2",
        "0000DED7",
        "0000DED3",
        "0000DED4",
        "0000DED5",
        "0000DED6",
    ],
    "cde": ["0000DEDF", "0000DECE"],
}

MANDATORY_SWES_B506 = ["0000BBBA"]

CERTIFICATE = "/opt/esysdata/persistency_backup/Esys_NCD_key.p12"


def process_svk(svk, logger):
    """Parses SVK and returns a dict with SVK content
    Format of output:
    obtained_sgdb_dict = {"HWEL": [], "HWAP": [], "CAFD": [], "BTLD": [], "SWFL": [], "SWFK": []}
    """
    obtained_sgdb_dict = {key: [] for key in PROCESS_CLASS_DICT_INV.keys()}
    svk_chunk_size_nibble = 16
    sgbm_id_offset_nibble = 16
    logger.debug("SVK is: %s", svk)
    sgbm_ids = textwrap.wrap(svk.replace(" ", "")[sgbm_id_offset_nibble:], svk_chunk_size_nibble)
    logger.info("sgbm_ids : {}".format(sgbm_ids))
    for sgbm_id in sgbm_ids:
        obtained_sgdb_dict[PROCESS_CLASS_DICT[sgbm_id[0:2]]].append((sgbm_id[0:16]))
    logger.info("processed SVK: {}".format(obtained_sgdb_dict))
    return obtained_sgdb_dict


def perform_uds_pdx_flash(test_result_dir, vin, generation, vehicle_order, target_type, pdx, svk_all, vehicle_type):
    """Perform PDX using UDS

    :param test_result_dir: Path to results folder to save pdx flash artifacts
    :param vin: Target vehicle identifier number
    :param generation: Target generation
    :param vehicle_order: Path to vehicle order (FA)
    :param target_type: Target type
    :param pdx: Path to pdx container
    :param svk_all: Expected svks (software units) to be flashed to target
    :param vehicle_type: Vehicle type
    """
    cmd = [
        "pdx-flash",
        "--results",
        test_result_dir,
        "--context",
        "FullFlash",
        "--vin",
        vin,
        "--generation",
        generation,
        "--fa",
        vehicle_order,
        "--target-ecu",
        target_type,
        "--pdx",
        pdx,
        "--svk-soll",
        svk_all,
        "--vehicle-type",
        vehicle_type,
        "--tal-filter",
        "/resources/TAL_filter_idcevo.xml",
        "--no-begu-mc",
        "--direct-connection",
    ]
    try:
        timeout = 3600
        logger.info("Waiting for full PDX flash to finish. Timeout: %s", timeout)
        result = run_command(cmd, timeout=timeout)
        logger.debug("Full PDX flash results: %s", result)
        assert_process_returncode(0, result, "PDX flash failed. See logs for details.")
        logger.info("Full PDX flash is finished.")
    finally:
        # remove PSDZdata folder from results
        result = run_command(["rm", "-rf", os.path.join(test_result_dir, "psdzdata")])
        logger.debug("Cleanup psdz data results: %s", result)


def perform_mirror_pdx_flash(
    test_result_dir,
    vin,
    generation,
    vehicle_order,
    target_type,
    pdx,
    svk_all,
    vehicle_type,
    tal_filter_path,
    target_ecu_uid,
    mirror_protocol_auth="SIGNED_TOKEN",
    context="FullFlashMirror",
):
    """Perform PDX flash using Mirror Protocol

    :param test_result_dir: Path to results folder to save pdx flash artifacts
    :param vin: Target vehicle identifier number
    :param generation: Target generation
    :param vehicle_order: Path to vehicle order (FA)
    :param target_type: Target type
    :param pdx: Path to pdx container
    :param svk_all: Expected svks (software units) to be flashed to target
    :param vehicle_type: Vehicle type
    :param tal_filter_path: Path to TAL filter
    :param target_ecu_uid: Target ECU UID
    """
    cmd = [
        "pdx-flash",
        "--results",
        test_result_dir,
        "--context",
        context,
        "--vin",
        vin,
        "--generation",
        generation,
        "--fa",
        vehicle_order,
        "--target-ecu",
        target_type,
        "--pdx",
        pdx,
        "--svk-soll",
        svk_all,
        "--vehicle-type",
        vehicle_type,
        "--tal-filter",
        tal_filter_path,
        "--no-begu-mc",
        "--direct-connection",
        "--use-mirror-protocol",
        "--auth-method-mirror-protocol",
        mirror_protocol_auth,
        "--target-ecu-uid",
        target_ecu_uid,
    ]
    use_certificates = Path(CERTIFICATE).exists()
    if use_certificates:
        logger.info("Using certificate for Esys coding: %s", CERTIFICATE)
        cmd += [
            "--use-certificate",
            "--certificate",
            CERTIFICATE,
        ]
    try:
        timeout = 3600
        logger.info("Waiting for full PDX flash via mirror protocol to finish. Timeout: %s", timeout)
        result = run_command(cmd, timeout=timeout)
        logger.debug("Full PDX flash via mirror protocol results: %s", result)
        assert_process_returncode(0, result, "PDX flash failed. See logs for details.")
        logger.info("Full PDX flash via mirror protocol is finished.")
    finally:
        # remove PSDZdata folder from results
        result = run_command(["rm", "-rf", os.path.join(test_result_dir, "psdzdata")])
        logger.debug("Cleanup psdz data results: %s", result)


def generate_tal(target, tal_filter_path=None, timeout=360, tal_log_dir=None, pdx_path=None, svk_file_path=None):
    """Generate TAL file using esys-comander

    :param target (TargetShare): mtee_target
    :param tal_filter_path (Path, str): Path to TAL filter if applicable, defaults to None
    :param timeout (int): Timeout for TAL generation command, defaults to 360
    :param tal_log_dir (Path, str): Path to store generated TAL file, defaults to None
    :param pdx_path (Path, str): Path to pdx container, defaults to None
    :param svk_file_path (Path, str): Path to svk file, defaults to None

    :raises EsysError: On esys generation failure
    :raises AssertionError: If no TAL file is found after generation
    :return: Path to generated TAL file
    """
    if not pdx_path:
        pdx_path = target.pdx_path

    esys_data_folder = target.options.esys_data_dir
    esys_log_folder = tal_log_dir or os.path.join(esys_data_folder, "Logs")

    # Create esys log folder (TAL generation folder) if not exist
    if esys_log_folder and not os.path.isdir(esys_log_folder):
        os.mkdir(esys_log_folder)

    logger.info("Generating TAL file")
    logger.debug(f"Using PDX: {pdx_path}")
    logger.debug(f"Using folder as workspace: {esys_log_folder}")

    svt_ist_path = os.path.join(esys_log_folder, "svt_ist_" + target.options.target_type + ".xml")

    # Store all files in the esys log folder
    shutil.copy(svk_file_path, esys_log_folder)

    generate_tal_command = [
        "esys-commander",
        "--svt-path",
        svt_ist_path,
        "--pdx-file",
        pdx_path,
        "--esys-data",
        esys_data_folder,
        "--esys-properties",
        target.options.esys_properties,
        "--vehicle-type",
        target.options.vehicle_type,
        "--diag-address",
        str(target.ecu_diagnostic_id),
        "--vin",
        target.options.vin,
        "--workspace",
        esys_log_folder,
        "--svk-file",
        svk_file_path,
        "--log-level",
        "DEBUG",
        "--enable-doip-protocol",
    ]

    if hasattr(target, "generation"):
        generate_tal_command.extend(["--generation", target.generation])

    if hasattr(target, "_coding_istep_shipment"):
        generate_tal_command.extend(["--istep-shipment", target._coding_istep_shipment])

    if tal_filter_path:
        shutil.copy(tal_filter_path, os.path.join(esys_log_folder, "backup_tal_filter.xml"))
        generate_tal_command.extend(["--tal-filter-path", tal_filter_path])

    if not target.has_capability(TE.test_bench.rack):
        generate_tal_command.extend(["--direct-connection", "--gateway-ip", target._oabr_ipv4])

    use_certificates = Path(CERTIFICATE).exists()
    if use_certificates:
        logger.info("Using certificate for Esys coding: %s", CERTIFICATE)
        generate_tal_command += [
            "--use-certificate",
            "--swl-cert-path",
            CERTIFICATE,
        ]

    result = run_command(generate_tal_command, timeout=timeout)
    if result.returncode != 0:
        logger.error(f"TAL generation failed: {result}")
        raise EsysError(f"TAL generation failed: {result}")
    logger.debug(f"TAL generation result {result}")
    logger.info("TAL generation is finished")

    try:
        logger.debug(f"Searching generated TAL file under {esys_log_folder}")
        generated_tal_file_path = glob.glob(os.path.join(esys_log_folder, "**/TAL*.xml"), recursive=True)[0]
        logger.debug(f"Tal file found: {generated_tal_file_path}")
    except Exception:
        raise AssertionError("Can't found generated TAL file in :{}.".format(os.path.join(esys_log_folder)))

    return generated_tal_file_path


def is_application_mode(test, timeout):
    command = ["systemctl", "is-active", "application.target"]
    timer = TimeoutCondition(timeout)
    while timer:
        return_stdout, _, return_code = test.mtee_target.execute_command(command)
        if return_code == 0 and return_stdout == "active":
            return True
    else:
        return False


def pdx_teardown(test, pdx_utils, test_name="default"):
    """Ensure mandatory SWEs are present in the SVK response and adb target is enabled, after PDX flash

    :param test_name: Name of the test where this method is called
    """
    logger.debug("Activate engineering mode")
    secure_mode_object = SecureECUMode(test.mtee_target)
    secure_mode_object.switch_mode("ENGINEERING")
    test.mtee_target._connect_to_target()
    if test.mtee_target.vehicle_state != VehicleCondition.FAHREN:
        test.mtee_target.switch_vehicle_to_state(VehicleCondition.FAHREN)
    logger.debug("Ensure already in application mode after pdx flashing")
    assert_true(is_application_mode(test, timeout=120), "Not in application mode after flashing")
    svk_response_processed = retrieve_svk(test, pdx_utils, "PDX")
    missing_swes = check_missing_mandatory_swes_in_svk(test, svk_response_processed)
    assert_false(
        missing_swes,
        f"PDX teardown failed as the following mandatory SWE(s) are not included in the SVK response: {missing_swes}",
    )
    try:
        logger.debug("Validate if adb is enabled")
        test.mtee_target.wait_for_adb_device()
    except TimeoutError:
        logger.debug("Enable adb")
        test.mtee_target.enable_adb()
        assert_true(wait_for_application_target(test.mtee_target), "Not in application mode after enabling adb")

    assert_true(PreTestVerification(test.mtee_target))
    test.take_apinext_target_screenshot(results_dir=test.results_dir, file_name=f"after_pdx_flash_{test_name}.png")


def remove_swfk_from_svt(svt_all, swfk_id, new_file):
    """Generate new SVT file without specific SWFK

    :param svt_all: Path to full SVT provided with PDX
    :param swfk_id: SWFK id to be removed
    :param new_file: Path to new SVT file
    """
    svt = ET.parse(svt_all)
    svt_root = svt.getroot()
    ecu = svt_root.find("{}:standardSVT".format(NS_TAG), NS).find("{}:ecu".format(NS_TAG), NS)
    standard_svk = ecu.find("{}:standardSVK".format(NS_TAG), NS)
    part_id = standard_svk.find('{0}:partIdentification/[{0}:id="{swfk_id}"]'.format(NS_TAG, swfk_id=swfk_id), NS)

    standard_svk.remove(part_id)

    svt.write(new_file, pretty_print=True, encoding="UTF-8", xml_declaration=True)


def retrieve_svk(test, pdx_utils, flash_type, svk_whitelist=()):
    """Retrieve SVK response and parse it

    :param flash_type (str): Type of flash executed prior to calling this method (DEV, PDX, Prod Unit Swipe, etc.)
    :param svk_whitelist (tuple): SVKs to be removed from the SVK response

    :return: dictionary with SVK contents
    """
    svk_response = test.diagnostic_client.read_svk()
    logger.info(f"{flash_type} flash SVK response: '{svk_response}'")

    svk_response_processed = pdx_utils.format_svk(pdx_utils.process_svk(svk_response.upper()))
    for keys_to_remove in svk_whitelist:
        svk_response_processed.pop(keys_to_remove, None)
    logger.info(f"{flash_type} flash SVK response processed: '{svk_response_processed}'")

    return svk_response_processed


def check_missing_mandatory_swes_in_svk(test, svk_response_processed):
    """Check if mandatory SWEs are present in the SVK response

    :param svk_response_processed (dict): dictionary with SVK contents

    :return: List of missing mandatory SWEs, or empty list if all mandatory SWEs are present
    """
    target_type = test.mtee_target.options.target
    hw_variant_code = test.mtee_target.options.target_serial_no[2:6].upper()

    mandatory_swes = MANDATORY_SWES.get(target_type)
    if not mandatory_swes:
        raise AssertionError(f"Target type '{target_type}' is not applicable to SWE verification")

    swfl_in_svk = svk_response_processed.get("SWFL")
    if not swfl_in_svk:
        raise AssertionError("SWFL is not included in the SVK response")

    mandatory_swes_in_svk = []
    mandatory_b506_swes_in_svk = []
    missing_mandatory_swes_in_svk = []

    for swe_id, _ in swfl_in_svk.items():
        if swe_id in mandatory_swes:
            mandatory_swes_in_svk.append(swe_id)
            if len(mandatory_swes_in_svk) == len(mandatory_swes):
                break

    missing_mandatory_swes_in_svk = list(set(mandatory_swes) - set(mandatory_swes_in_svk))

    if "B506" in hw_variant_code:
        for swe_id, _ in swfl_in_svk.items():
            if swe_id in MANDATORY_SWES_B506:
                mandatory_b506_swes_in_svk.append(swe_id)
                break
        if not mandatory_b506_swes_in_svk:
            missing_mandatory_swes_in_svk += mandatory_b506_swes_in_svk

    if missing_mandatory_swes_in_svk:
        logger.debug(f"Missing mandatory SWEs in SVK response: {missing_mandatory_swes_in_svk}")
    else:
        logger.info("All mandatory SWEs are present in the SVK response!")

    return missing_mandatory_swes_in_svk
