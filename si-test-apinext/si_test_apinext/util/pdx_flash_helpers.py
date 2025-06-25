# Copyright (C) 2021. BMW Car IT GmbH. All rights reserved.
"""
Helpers for PDX flashing
"""

import glob
import logging
import os
import sys
import xml.etree.ElementTree as eTree

from pathlib import Path
from typing import List, Optional, Union
from time import sleep

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT
from mtee.testing.tools import assert_equal, assert_process_returncode, assert_true, run_command
from tee.target_common import VehicleCondition
from tee.tools.secure_modes import SecureECUMode
from tee.tools.diagnosis import DiagClient
from si_test_apinext.util.screendump import ScreenDump

from esys import EsysError

logger = logging.getLogger(__name__)
target = TargetShare().target

diag_client = DiagClient(target.diagnostic_address, target.ecu_diagnostic_id)

PDX_FOLDER_PATTERN = "*pdx"
PDX_PATTERN = {"mgu22": "**/HU__MGU_02_L*.pdx", "idc23": "**/HU__MGU_02_A*.pdx", "rse22": "**/RSE_*.pdx"}
SVK_PATTERN = {
    "mgu22": "**/SVT_HU__MGU2_L.xml",
    "mgu22_gnss": "**/SVT_HU__MGU2_L_GNSS.xml",
    "idc23": {
        "U006": {
            "row": "**/SVT_U06_HU__MGU2_A.xml",
            "china": "**/SVT_U06_HU__MGU2_A_CHINA.xml",
        },  # noqa: E231
        "U011": {
            "row": "**/SVT_U11_HU__MGU2_A.xml",
            "china": "**/SVT_U11_HU__MGU2_A_CHINA.xml",
        },  # noqa: E231
    },
    "idc23_gnss": {
        "U006": {
            "row": "**/SVT_U06_HU__MGU2_A_GNSS.xml",
            "china": "**/SVT_U06_HU__MGU2_A_GNSS_CHINA.xml",
        },  # noqa: E231
        "U011": {
            "row": "**/SVT_U11_HU__MGU2_A_GNSS.xml",
            "china": "**/SVT_U11_HU__MGU2_A_GNSS_CHINA.xml",
        },  # noqa: E231
    },
    "rse22": {
        "padi": "**/SVT_RSE__PADI-01_ROW.xml",
        "padi_china": "**/SVT_RSE__PADI-01_CHINA.xml",
    },  # noqa: E231
}
TAL_FILTER = {"mgu22": "TAL_filter_mgu22.xml", "idc23": "TAL_filter_mgu22.xml", "rse22": "TAL_filter_rse22.xml"}
IDC_HOME_SCREEN_ACT = [
    "com.bmwgroup.idnext.launcher/.MainActivity",
    "com.bmwgroup.idnext.navigation/.widget.map.MapWidgetActivity",
    "com.bmwgroup.apinext.ipaapp/.widget.mini.WidgetMiniActivity",
    "com.bmwgroup.apinext.livevehicle/.startmenu.StartMenuLiveVehicleActivity",
]

CERTIFICATE = "/opt/esysdata/persistency_backup/Esys_NCD_key.p12"


def is_release_pdx(path: Union[str, Path]) -> bool:
    """Detect the path is a release pdx or dev pdx

    The pdx versioning format is `<major>_<minor>_<patch>`. When the patch is
    255, it's a developer pdx.

    For example:
        HU__MGU_02_L__DEV_21W4151.001_022_021.pdx <- a release pdx (not ending with 255.pdx)
        HU__MGU_02_L__DEV_21W4151.001_022_255.pdx <- a developer pdx (ending with 255.pdx)

    :param Union[str, Path] path: the pdx file path
    :return bool: True presents a release pdx, False presents a dev pdx
    """
    pdx_path = Path(path) if isinstance(path, str) else path
    logger.debug("Start to detect pdx type. pdx_path: %s, path: %s", pdx_path, path)
    try:
        pdx_filename = pdx_path.name

        pdx_version = pdx_filename.split(".")[1]
        logger.debug("pdx version: %s, filename: %s", pdx_version, pdx_filename)

        pdx_patch_version = pdx_version.split("_")[-1]
        logger.debug(
            "pdx patch version: %s, pdx_version: %s, filename: %s", pdx_patch_version, pdx_version, pdx_filename
        )

        return pdx_patch_version != "255"
    except Exception as err:
        raise Exception(
            f"Failed to determine the pdx type (release/developer) for the filename {pdx_filename}, path: {pdx_path}"
        ) from err


def find_pdx_folder(pattern: str = PDX_FOLDER_PATTERN) -> Optional[str]:
    pdx_folders: List[Path] = []
    for path in Path.cwd().glob(pattern):
        if path.is_dir():
            if not path.is_symlink():
                pdx_folders.append(path.resolve())
            else:
                if sys.version_info < (3, 9):
                    real_path = Path(os.readlink(path)).resolve()
                else:
                    real_path = path.readlink().resolve()

                if real_path not in pdx_folders:
                    pdx_folders.append(real_path)

    if pdx_folders:
        if len(pdx_folders) != 1:
            raise RuntimeError(f"Multiple pdx folders are found: {pdx_folders}")

        return str(pdx_folders[0].relative_to(Path.cwd().resolve()))

    return None


def find_artifact(pattern, subdir=None):
    root = os.path.join(os.getcwd(), subdir) if subdir else os.getcwd()
    glob_pattern = os.path.join(root, pattern)
    logger.debug("looking for artifact: %s", glob_pattern)
    artifacts = glob.glob(glob_pattern, recursive=True)
    logger.debug("artifacts found: %s", artifacts)
    if len(artifacts) != 1:
        return None
    return artifacts[0]


def find_and_extract_tar(pattern, artefact_name, subdir):
    """Find and extract tar ball matching pattern into subdir"""
    tar = find_artifact(pattern)
    if tar is None:
        raise AssertionError("No {} found. Flashing cannot be done.".format(artefact_name))
    logger.info("%s: %s", artefact_name, tar)
    os.makedirs(subdir, exist_ok=True)
    extract_command = ["tar", "xfv", tar]
    result = run_command(extract_command, cwd=subdir, timeout=240)
    logger.info("Extracted %s: %s", artefact_name, result)
    assert_process_returncode(0, result, "{} extract failed. See logs for details.".format(artefact_name))
    return tar


def install_coding(vin=None):
    """Install coding on target using E-sys

    :param str vin: vin to be used for coding
    """
    target.prepare_for_reboot()

    try:
        target.install_coding_esys(custom_vin=vin)
        install_coding_status = True
    except EsysError:
        install_coding_status = False

    target.wait_for_reboot()

    return install_coding_status


def _press_home():
    """
    Press android home key
    """
    command = ["shell", "input", "keyevent 3"]
    target.execute_adb_command(command)


def _press_back():
    """
    Press android back key
    """
    command = ["shell", "input", "keyevent 4"]
    target.execute_adb_command(command)


class TestPDXBase:
    @classmethod
    def setup_class(cls):
        logger.info("Running setup for PDX flashing tests.")

        cls.target_key = target.options.target
        cls.hw_variant = target.options.hardware_variant
        cls.target_region_variant = getattr(target, "region_variant", None) or getattr(target, "software_variant")
        pdx_subdir = find_pdx_folder(PDX_FOLDER_PATTERN)
        is_check_pdx_folder = cls.target_key == "mgu22" and pdx_subdir

        # Extract and locate pdx container files
        if is_check_pdx_folder:
            # If the pdx folder is downloaded directly to current workspace,
            # find the pdx file through the subdir
            cls.pdx_subdir = pdx_subdir
        else:
            # If the pdx folder does not exists, use the original way to check
            # the pdx tarball, find it and extrat it to the subdir.
            cls.pdx_subdir = "PDX"
            pdx_tar = find_and_extract_tar("*-pdx*.tar.gz", "PDX tar ball", cls.pdx_subdir)

        logger.info("Search pdx container through subdir: %s", cls.pdx_subdir)

        cls.pdx_container = find_artifact(PDX_PATTERN[cls.target_key], subdir=cls.pdx_subdir)
        assert cls.pdx_container is not None, "No PDX container found!"
        logger.info("Found pdx container: %s", cls.pdx_container)

        cls.release_pdx = is_release_pdx(cls.pdx_container) if is_check_pdx_folder else "release" in pdx_tar
        logger.info(
            "%s PDX is used for PDX Tests, path: %s", "Release" if cls.release_pdx else "Developer", cls.pdx_container
        )

        # Extract logistic files
        find_and_extract_tar("*-logistics*.tar.gz", "Logistics tar ball", "logistics")

        target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)

    def setup(self):
        target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)

    def teardown(self):
        target._connect_to_target()

    @classmethod
    def teardown_class(cls):
        target.switch_vehicle_to_state(VehicleCondition.FAHREN)

    def _check_swfks(self):
        """After begu flash, /var/opt/SWFK should be empty"""
        target.connect()
        ls_cmd = "ls /var/opt/SWFK"
        result = target.execute_command(f"{ls_cmd} | wc -l")
        ls_cmd_result = target.execute_command(ls_cmd)
        assert_equal(0, int(result.stdout), f"Folder is not empty as expected. {ls_cmd} output: \n{ls_cmd_result}")

    def _pdx_flash_begu(self, force, results, fa=None, vehicle_type=None, region_variant=None):
        try:
            test_result_dir = os.path.join(target.options.result_dir, results)
            os.makedirs(test_result_dir)
            # run BEGU flashing step:
            begu_flash = [
                "pdx-flash",
                "--vin",
                target.options.vin,
                "--target-ecu",
                target.options.target_type,
                "--generation",
                "22" if self.target_key != "idc23" else "23",
                "--images",
                "/workspace",
                "--results",
                test_result_dir,
                "--context",
                "BEGUFlash",
                "--vehicle-type",
                target.options.vehicle_type if vehicle_type is None else vehicle_type,
                "--fa",
                target.options.vehicle_order if fa is None else fa,
                "--pdx",
                self.pdx_container,
            ]

            if self.target_key == "idc23":
                begu_flash.extend(["--country-variant", region_variant or self.target_region_variant])
            if not target.has_capability(TEST_ENVIRONMENT.test_bench.rack):
                if self.target_key == "mgu22":
                    begu_flash.append("--direct-connection-http")
                else:
                    begu_flash.append("--direct-connection")
            if not force:
                begu_flash.append("--no-tal-filter")
            if target.has_capability(TEST_ENVIRONMENT.peripherals.GNSS):
                begu_flash.append("--gnss-support")

            use_certificates = Path(CERTIFICATE).exists()
            if use_certificates:
                logger.info("Using certificate for Esys coding- %s", CERTIFICATE)
                begu_flash += [
                    "--use-certificate",
                    "--swl-cert-path",
                    CERTIFICATE,
                ]
            else:
                raise AssertionError(f"No Certificate found for Esys coding at path:{CERTIFICATE}. Aborting the test.")

            timeout = 4000
            logger.info("Waiting for BEGU PDX flash to finish. Timeout: %s", timeout)
            result = run_command(begu_flash, timeout=timeout)
            logger.debug("BEGU PDX flash results: %s", result)
            assert_process_returncode(0, result, "PDX flash failed. See logs for details.")
            logger.info("BEGU PDX flash is finished.")
            logger.debug("Checking the contents of /var/opt/SWFK after flashing")
            self._check_swfks()

        finally:
            # remove PSDZdata folder from results
            result = run_command(["rm", "-rf", os.path.join(test_result_dir, "psdzdata")])
            logger.debug("Cleanup psdz data results: %s", result)

    def _pdx_flash_everything(
        self,
        set_idc23_plant_delivery_state=False,
        vehicle_type=None,
        region_variant=None,
        tal_filter=True,
        workspace_folder=None,
    ):

        try:
            esys_data_folder = target.options.esys_data_dir

            if workspace_folder is not None:
                workspace_folder = os.path.join(target.options.result_dir, workspace_folder)
                os.makedirs(workspace_folder)
            else:
                workspace_folder = target.options.result_dir

            # Import PDX container
            import_command = [
                "esys-commander",
                "--import-pdx",
                "--pdx-file",
                self.pdx_container,
                "--esys-data",
                esys_data_folder,
                "--esys-properties",
                target.options.esys_properties,
                "--vehicle-type",
                target.options.vehicle_type,
                "--diag-address",
                str(target.ecu_diagnostic_id),
            ]

            timeout = 720
            logger.info("Waiting for PDX container import to finish. Timeout: %s", timeout)
            result = run_command(import_command, timeout=timeout)
            logger.debug("PDX container import results: %s", result)
            assert_process_returncode(0, result, "PDX container import failed. See logs for details.")
            logger.info("PDX container import is finished.")

            svk_file = ""
            if self.target_key == "mgu22":
                svk_pattern = (
                    SVK_PATTERN[self.target_key + "_gnss"]
                    if target.has_capability(TEST_ENVIRONMENT.peripherals.GNSS)
                    else SVK_PATTERN[self.target_key]
                )
            elif self.target_key == "rse22":
                svk_pattern = SVK_PATTERN[self.target_key][target.options.hardware_variant]
            elif self.target_key == "idc23":
                vehicle_type = vehicle_type or target.options.vehicle_type
                region_variant = region_variant or self.target_region_variant

                # In case of plant delivery state on idc, we create a complete svk file with SWFK from china and row
                if set_idc23_plant_delivery_state:
                    file_eu_pattern, file_ch_pattern = (
                        SVK_PATTERN[self.target_key + "_gnss"][vehicle_type].values()
                        if target.has_capability(TEST_ENVIRONMENT.peripherals.GNSS)
                        else SVK_PATTERN[self.target_key][vehicle_type].values()
                    )
                    svk_idc_eu = find_artifact(file_eu_pattern, subdir=self.pdx_subdir)
                    svk_idc_ch = find_artifact(file_ch_pattern, subdir=self.pdx_subdir)
                    svk_file = self.create_complete_svk_file(svk_idc_eu, svk_idc_ch)
                else:
                    svk_pattern = (
                        SVK_PATTERN[self.target_key + "_gnss"][vehicle_type][region_variant]
                        if target.has_capability(TEST_ENVIRONMENT.peripherals.GNSS)
                        else SVK_PATTERN[self.target_key][vehicle_type][region_variant]
                    )
            else:
                raise AssertionError(f"No SVK pattern found for target key: {self.target_key}")

            if not svk_file:
                svk_file = find_artifact(svk_pattern, subdir=self.pdx_subdir)

            if svk_file is None:
                raise AssertionError("No SVK xml found!")
            flash_command = [
                "esys-commander",
                "--vin",
                target.options.vin,
                "--fa-file",
                target.options.vehicle_order,
                "--esys-data",
                esys_data_folder,
                "--esys-properties",
                target.options.esys_properties,
                "--execute-tal",
                "--vehicle-type",
                target.options.vehicle_type,
                "--diag-address",
                str(target.ecu_diagnostic_id),
                "--workspace",
                workspace_folder,
                "--svk-file",
                svk_file,
            ]

            if tal_filter:
                flash_command.extend(["--tal-filter-path", os.path.join("/resources", TAL_FILTER[self.target_key])])

            if not target.has_capability(TEST_ENVIRONMENT.test_bench.rack):
                if self.target_key == "mgu22":
                    flash_command.append("--direct-connection-http")
                else:
                    flash_command.append("--direct-connection")
                flash_command.extend(["--gateway-ip", target._ip_address])

            if (self.release_pdx and self.target_key == "mgu22") or (
                self.target_key == "idc23" and set_idc23_plant_delivery_state
            ):
                logger.info("Activate plant mode")
                secure_mode_object = SecureECUMode(target)
                secure_mode_object.switch_mode("PLANT")

            use_certificates = Path(CERTIFICATE).exists()
            if use_certificates:
                logger.info("Using certificate for Esys coding- %s", CERTIFICATE)
                flash_command += [
                    "--use-certificate",
                    "--swl-cert-path",
                    CERTIFICATE,
                ]
            else:
                raise AssertionError(f"No Certificate found for Esys coding at path:{CERTIFICATE}. Aborting the test.")

            timeout = 14400 if self.release_pdx else 3000
            logger.info("Waiting for PDX flash to finish. Timeout: %s", timeout)
            result = run_command(flash_command, timeout=timeout)
            logger.debug("PDX flash results: %s", result)
            assert_process_returncode(0, result, "PDX flash failed. See logs for details.")
            logger.info("PDX flash is finished.")

        finally:
            if (self.release_pdx and self.target_key == "mgu22") or (
                self.target_key == "idc23" and set_idc23_plant_delivery_state
            ):
                logger.info("Activate engineering mode")
                secure_mode_object = SecureECUMode(target)
                secure_mode_object.switch_mode("ENGINEERING")
            # reconnect to target to avoid SSH connection lost failure for first executed test case
            target.connect()

        if self.target_key == "rse22":
            target.flash_extension_board()

    def _rsu_flash(self):

        target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
        rsu_timeout = 3000

        if self.target_key in ["idc23", "rse22"]:
            # Generate TAL file
            generated_tal_dir = os.path.join(target.options.esys_data_dir, "Logs", "TAL_test_rsu_flash")
            tal_filter = os.path.join("/resources", TAL_FILTER[self.target_key])
            tal_file_path = self.generate_tal(
                timeout=360, tal_filter_path=tal_filter, tal_log_dir=generated_tal_dir, pdx_path=self.pdx_subdir
            )
        else:
            tal_file_path = next(
                glob.iglob(os.path.join(target.options.result_dir, "**/TAL_file_HU_*.xml"), recursive=True)
            )
        logger.debug("tal_file_path: {}".format(tal_file_path))

        target_type = "padi" if self.target_key == "rse22" else self.target_key

        try:
            rsu_flash_cmd = [
                "rsu-flasher",
                "--pdx-path",
                self.pdx_container,
                "--tal-file-path",
                tal_file_path,
                "--target-type",
                target_type,
                "--vin",
                target.options.vin,
                "--http-server-ip",
                target.options.proxy_ip,
                "--log-level",
                "DEBUG",
                "--result-dir",
                target.options.result_dir,
            ]

            logger.info("rsu_flash_cmd: {}".format(rsu_flash_cmd))

            # Disable ssh connection
            target.prepare_for_reboot()
            result = run_command(rsu_flash_cmd, timeout=rsu_timeout)
            logger.info("RSU flash results: {}".format(result))
            assert_process_returncode(0, result, "RSU flash failed. See logs for details.")
            logger.info("RSU flash is finished.")

            # Enable ssh connections
            target.resume_after_reboot()

            install_coding_status = install_coding()
            assert_true(install_coding_status, "Coding Failed")
        finally:
            if self.release_pdx and self.target_key == "mgu22":
                logger.info("Activate engineering mode")
                secure_mode_object = SecureECUMode(target)
                secure_mode_object.switch_mode("ENGINEERING")
            target.switch_vehicle_to_state(VehicleCondition.FAHREN)

    def _do_coding_iteration(self, vehicle_order_path):

        target.prepare_for_reboot()
        target.install_coding(vehicle_order=vehicle_order_path)
        target.wait_for_reboot()
        target.wait_lxc_android_container_running()
        target.apply_adb_workaround()
        target.wait_for_boot_completed_flag(wait_time=30, adb_wait_time=15)
        target.wait_for_kpi_boot_completed_flag(wait_time=60)
        vehicle_order_name = os.path.splitext(os.path.basename(vehicle_order_path))[0]
        for _ in range(5):
            _press_back()
            sleep(0.5)
            _press_home()
            sleep(0.5)
        target.screendump(filename_base=vehicle_order_name)
        activities = target.execute_adb_command(["shell", "dumpsys activity activities | grep ResumedActivity"])
        for each_act in IDC_HOME_SCREEN_ACT:
            if each_act in activities:
                break
        else:
            RuntimeError(
                f"None of the following expected activities was found on home screen "
                f"(expecting at least one): {IDC_HOME_SCREEN_ACT}"
            )

    def verify_cid_ic(self, coding):
        screen_dump = ScreenDump()
        return screen_dump.test_cid_ic_screen_displayed(fileName=f"coding_{coding}", TestIC=True, TestCID=True)

    def create_complete_svk_file(self, svk_eu, svk_ch):
        logger.debug("Create complete svk file is executing")

        filename = "SVK_COMPLETE.xml"

        text_iter = "{http://bmw.com/2005/psdz.data.svt}partIdentification"
        eTree.register_namespace("", "http://bmw.com/2005/psdz.data.svt")
        elems = eTree.parse(svk_ch)
        ch_root = elems.getroot()
        eu_elems = eTree.parse(svk_eu)
        eu_root = eu_elems.getroot()

        ch_swfk_elems = []

        for iter_elems in ch_root.iter(text_iter):
            for elem in iter_elems.iter():
                if elem.text == "SWFK":
                    ch_swfk_elems.append(iter_elems)

        for iter_elems in eu_root.iter(text_iter):
            for elem in iter_elems.iter():
                if elem.text == "SWFK":
                    for index, item in enumerate(ch_swfk_elems):
                        if eTree.tostring(iter_elems) == eTree.tostring(item):
                            ch_swfk_elems.pop(index)

        for father_node in eu_root.iter("{http://bmw.com/2005/psdz.data.svt}standardSVK"):
            break

        for new_elems in ch_swfk_elems:
            father_node.append(new_elems)

        eu_elems.write(filename, xml_declaration=True, encoding="utf-8")

        svk_complete_path = glob.glob("**/{}".format(filename), recursive=True)

        if svk_complete_path:
            svk_complete_abs_path = os.path.abspath(svk_complete_path[0])
            logger.debug("svk_complete_abs_path : {}".format(svk_complete_path))
            logger.debug("Complete SVK created with success at : {}".format(svk_complete_path[0]))
        else:
            raise AssertionError(" create_complete_svk_file - Can not create complete SVK!")

        return svk_complete_abs_path

    def generate_tal(self, tal_filter_path=None, timeout=360, tal_log_dir=None, pdx_path=None, region_variant="row"):

        if not pdx_path:
            pdx_path = target.pdx_path
        svk_filename = ""
        logger.debug("pdx_path: {}".format(pdx_path))

        # Use a dir for store generated TAL
        esys_data_folder = target.options.esys_data_dir
        # If the user specifies a dir to store generated TAL and respective artifacts use this dir (abs path) if not
        # will be stored in esys data logs folder
        esys_log_folder = tal_log_dir or os.path.join(esys_data_folder, "Logs")

        # Create esys log folder (TAL generation folder) if not exist
        if esys_log_folder and not os.path.isdir(esys_log_folder):
            os.mkdir(esys_log_folder)

        logger.info("Generating TAL file")
        svt_ist_path = os.path.join(esys_log_folder, "svt_ist_" + target.options.target_type + ".xml")

        if self.target_key == "idc23":
            if target.has_capability(TEST_ENVIRONMENT.peripherals.GNSS):
                svk_filename = SVK_PATTERN[self.target_key + "_gnss"][target.options.vehicle_type][region_variant]
            else:
                svk_filename = SVK_PATTERN[self.target_key][target.options.vehicle_type][region_variant]

        elif self.target_key == "rse22":
            if target.hardware_variant == "padi":
                svk_filename = SVK_PATTERN[self.target_key][target.hardware_variant]
                logger.debug("Generating TAL - self.target_key == rse22. SVK file name : {}".format(svk_filename))
            elif target.hardware_variant == "padi_china":
                svk_filename = SVK_PATTERN[self.target_key][target.hardware_variant]
                logger.debug("Generating TAL - self.target_key == rse22. SVK file name : {}".format(svk_filename))

        # Try to find svk file
        try:
            svk_file_path = glob.glob(os.path.join(pdx_path, svk_filename), recursive=True)[0]
        except Exception:
            raise AssertionError("Can't found SVK file :{}.".format(os.path.join(pdx_path, svk_filename)))

        generate_tal_command = [
            "esys-commander",
            "--svt-path",
            svt_ist_path,
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
            "--flash-protocol",
            "HTTP",
            "--workspace",
            esys_log_folder,
        ]

        generate_tal_command.extend(["--svk-file", svk_file_path])

        if tal_filter_path:
            generate_tal_command.extend(["--tal-filter-path", tal_filter_path])

        if not target.has_capability(TEST_ENVIRONMENT.test_bench.rack):
            generate_tal_command.extend(["--direct-connection", "--gateway-ip", target._ip_address])

        use_certificates = Path(CERTIFICATE).exists()
        if use_certificates:
            logger.info("Using certificate for Esys coding- %s", CERTIFICATE)
            generate_tal_command += [
                "--use-certificate",
                "--swl-cert-path",
                CERTIFICATE,
            ]
        else:
            raise AssertionError(f"No Certificate found for Esys coding at path:{CERTIFICATE}. Aborting the test.")

        result = run_command(generate_tal_command, timeout=timeout)
        if result.returncode != 0:
            logger.error("TAL generation failed: %s", result)
            raise EsysError("TAL generation failed: %s", result)
        logger.debug("TAL generation result %s", result)
        logger.info("TAL generation is finished")

        try:
            generated_tal_file_path = glob.glob(os.path.join(esys_log_folder, "**/TAL*.xml"), recursive=True)[0]
            logger.debug("generated tal file path: {}".format(generated_tal_file_path))
        except Exception:
            raise AssertionError("Can't found generated TAL file in :{}.".format(os.path.join(esys_log_folder)))

        return generated_tal_file_path
