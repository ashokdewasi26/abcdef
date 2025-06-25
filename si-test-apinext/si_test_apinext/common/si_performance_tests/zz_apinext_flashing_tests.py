# Copyright (C) 2023. CTW PT. All rights reserved.
"""
This module flash through PDX the apinext target
"""
import logging
import time
import os
from typing import List
import xml.etree.ElementTree as eTree

from pathlib import Path

from tee.const import SFA_FEATURE_IDS
from tee.tools.sfa_utils import SFAHandler
from mtee.testing.support.target_share import TargetShare
from si_test_apinext.util.pdx_flash_helpers import TestPDXBase, find_artifact
from tee.tools.diagnosis import DiagClient

logger = logging.getLogger(__name__)
target = TargetShare().target
sfa_handler_object = SFAHandler(target)
diag_client = DiagClient(target.diagnostic_address, target.ecu_diagnostic_id)


def get_disabled_package_list(user_id):
    """
    :param user_id: User id of the android user.
    :return: List of packages that are disabled for the user.
    """
    output_rc = target.execute_adb_command(["shell", "pm", "list", "packages", "--user", user_id, "-d"])
    output = output_rc.stdout.decode("UTF-8")
    disabled_packages = [line.split(":")[1].strip() for line in output.split("\n") if line]
    logger.info(f"Disabled packages list: {disabled_packages}")
    return disabled_packages


class TestPDX(TestPDXBase):
    # IDC23 specific SWFKs
    ASSETS_SWFKS = {"U006": "0000a324", "U011": "0000a323"}
    PRODUCT_SWFKS = {"row": "0000a4fe", "china": "0000a4ff"}

    SWFK_DIR = "/var/data/SWFK/"
    PARTITIONS = ["/dev/disk/by-partlabel/assets_a", "/dev/disk/by-partlabel/a_product_a"]

    BEGU_DTC = "0XB7F908"

    # IDC23 specific
    TAL_SWFKs_id = {
        "0000A4FF": "china",
        "0000A4FE": "row",
        "0000A324": "U006",
        "0000A323": "U011",
    }
    # PaDi specific
    TAL_SWFLs_id = {"0000A2E1": "china", "0000A2E0": "row"}
    TAL_SWEs_id = {"SWFK": TAL_SWFKs_id, "SWFL": {"0000A2E1": "china", "0000A2E0": "row"}}

    PROCESS_CLASS_DICT = {"01": "HWEL", "02": "HWAP", "05": "CAFD", "06": "BTLD", "08": "SWFL", "0D": "SWFK"}
    PROCESS_CLASS_DICT_INV = {v: k for k, v in PROCESS_CLASS_DICT.items()}

    @classmethod
    def setup_class(cls):
        """setup_class"""
        super().setup_class()
        logger.info("Activate External DLT trace")
        cls.vcar_manager = TargetShare().vcar_manager
        sfa_handler_object.activate_feature(SFA_FEATURE_IDS["SFA_INTERNAL_DEBUG_ACCESS_DLT_EXTERNAL_TRACING_ID"])
        cls.metric_extractors_definition_filepath = (
            Path(os.sep) / "resources" / "multiple_reboot" / "android_first_boot_metric_extractors.json"
        )
        user_id_rc = target.execute_adb_command(["shell", "am", "get-current-user"])
        cls.user_id = int(user_id_rc.stdout.decode("UTF-8").strip())
        cls.disabled_packages_start = get_disabled_package_list(cls.user_id)

    @classmethod
    def teardown_class(cls):
        """Target is alive"""
        sfa_handler_object.clear_feature(SFA_FEATURE_IDS["SFA_INTERNAL_DEBUG_ACCESS_DLT_EXTERNAL_TRACING_ID"])
        disabled_packages_end = get_disabled_package_list(cls.user_id)
        for each_package in disabled_packages_end:
            if each_package not in cls.disabled_packages_start:
                logger.info(f"Enabling package: {each_package}")
                target.execute_adb_command(["shell", "su", "0", "pm", "enable", "--user", cls.user_id, each_package])
        super().teardown_class()

    def raw_reboot(self):
        """Perform a raw reboot, meaning a cold reboot, using the power supply and not doing
        the common boot verification. Also start the ssh connection and apply adb workaround"""
        logger.info("Rebooting target using power supply")
        target.extract_metric_artifacts(extractors_definition_filepath=self.metric_extractors_definition_filepath)
        target.prepare_for_reboot()
        target._power_off()
        time.sleep(10)
        target._power_on()
        time.sleep(5)
        target.ssh.wait_for_ssh(target.get_address())
        target._connect_to_target()
        target.apply_adb_workaround()
        logger.info("Target rebooted using raw_reboot")
        target.wait_for_adb_device(wait_time=120)
        target.wait_for_boot_completed_flag(wait_time=120)
        target.wait_for_kpi_boot_completed_flag(wait_time=60)

    def _str_to_hex(self, value):
        """Converts an int represented in str to hex"""
        value_hex = hex(int(value)).replace("0x", "")
        if len(value_hex) == 1:
            value_hex = "0" + value_hex
        return value_hex

    def _populate_sgbmids(
        self, tal_line: eTree.Element, root_tag: str, all_sgbmids: List[str], key: str, operation: str
    ) -> None:
        """Populate SGBM id list if found at a given xml element reagardion de operation of Delete or Deploy"""
        key_items = tal_line.find(root_tag + key)
        if key_items:
            for key_item in key_items:
                current_process_class = None
                tmp = {}
                if not key_item.tag.endswith(operation + "TA"):
                    # Only collect SGBM ids from argument passed
                    continue

                for sgmid_item in key_item.find(root_tag + "sgbmid"):
                    attrib = sgmid_item.tag.replace(root_tag, "")

                    if attrib == "processClass":
                        current_process_class = sgmid_item.text

                    if current_process_class:
                        tmp[attrib] = sgmid_item.text

                if tmp:
                    all_sgbmids.append(tmp)

    def _tal_parser(self, tal_path: str, operation: str) -> List[str]:
        """Tal parser to get the list of delete ids that will be deleted on target

        :param tal_path[str, Path] path: the TAL file path
        :param operation[str]: Operation to be found in the tal file. [swDeploy, swDelete, cdDeploy, blFlash]

        :return List[str]: Returns a list with the sgbmids found
        """

        if operation in ("swDeploy", "swDelete"):  # delete and deploy
            key = "swDeploy"
        elif operation == "cdDeploy":  # coding
            key = "cdDeploy"
        elif operation == "blFlash":  # flash
            key = "blFlash"
        else:
            return "Operation not supported"

        diag_addres = hex(target.ecu_diagnostic_id).replace("0x", "").upper()
        tree = eTree.parse(tal_path)
        root = tree.getroot()

        root_tag = root.tag[:-3]

        tal_lines = root.findall("{}talLine".format(root_tag))
        if len(tal_lines) == 0:
            raise RuntimeError("TalLines not found")

        all_sgbmids = []
        for line in tal_lines:
            if line.get("diagAddress") == diag_addres:
                # Tal file can have information for more than one ECU
                self._populate_sgbmids(line, root_tag, all_sgbmids, key, operation)

        processed_sgbmids = []
        for sgbmid in all_sgbmids:
            sgbmid["swe_name_processed"] = (
                self.PROCESS_CLASS_DICT_INV[sgbmid["processClass"]]
                + sgbmid["id"]
                + self._str_to_hex(sgbmid["mainVersion"])
                + self._str_to_hex(sgbmid["subVersion"])
                + self._str_to_hex(sgbmid["patchVersion"])
            )
            processed_sgbmids.append(sgbmid)
        return processed_sgbmids

    def _check_tal_swe(self, swe_class, tal_path, operation, expected_swes, error_msg, strict_check=True):
        """Checks if TAL contains specific SWFK given the the transation operation (swDelete or swDeploy)

        :param swe_class: SWE class to look for, e.g SWFK, SWFL
        :type swe_class: str
        :param tal_path: Path to the tal file
        :type tal_path: str
        :param operation: Transation operation, should be swDelete or swDeploy
        :type operation: str
        :param expected_swes: Set with the expected SWEs given the transation method
        :type expected_swes: set[str]
        :param error_msg: List to add error message in case of failure on finding expected swfks
        :type error_msg: list[str]
        :param strict_check: Flag that if set as true expected that all SWE on tal should match the expected.
            If set as False, check if found any expected SWEs on TAL
        :raises Exception: When transation method is not the expected
        """
        if operation not in ("swDelete", "swDeploy"):
            raise Exception(f"Unexpected method {operation}, should be either swDelete or swDeploy")

        logger.debug(
            "Looking for: {} {} on tal {}. Expected SWEs: {}".format(swe_class, operation, tal_path, expected_swes)
        )

        result_swes = set()
        result = self._tal_parser(tal_path, operation)
        # Get a list only with the parsed ids of the swfks
        for element in result:
            logger.debug("Got element from TAL: {} : {}".format(tal_path, element))
            if element["processClass"] == swe_class:
                elem = self.TAL_SWEs_id[swe_class].get(element["id"], None)
                if elem is None:
                    if strict_check:
                        raise Exception("Unknown {}: {}".format(swe_class, element["id"]))
                else:
                    result_swes.add(elem)

        if strict_check:
            if result_swes == expected_swes:
                logger.info("TAL {} {} {}".format(operation, swe_class, result_swes))
            else:
                error_msg.append(
                    "TAL file {} {} don't match the FA. Expected {} got {}".format(
                        operation, swe_class, expected_swes, result_swes
                    )
                )
        else:
            if result_swes.intersection(expected_swes):
                logger.info("TAL contains {} {} {}".format(operation, swe_class, result_swes))
            else:
                error_msg.append(
                    "TAL file {} {} don't match the FA. Expected {} to contain {}".format(
                        operation, swe_class, expected_swes, result_swes
                    )
                )

    def _validate_regular_pdx_flash(self, results, current_fa, previous_fa):
        """Validate TAL file generated from a previous to the current FA"""
        error_msg = []

        # check generated TAL file to get swDeleted and swDeployed
        logger.debug("Validating TAL from previous FA {} to the current {}".format(previous_fa, current_fa))
        tal_path = os.path.join(target.options.result_dir, results)
        tal_file_suffix = "HU_MGU2" if self.target_key == "idc23" else "RSE_MGU2"
        tal_filename = f"TAL_file_{tal_file_suffix}.xml"
        tal = find_artifact(tal_filename, tal_path)
        if tal:
            deployed_swfks = set(current_fa) - set(previous_fa)
            deleted_swfks = set(previous_fa) - set(current_fa)

            if self.target_key == "rse22":
                # In case of padi we only care about region_variant
                deployed_swfks = {current_fa[1]}
                self._check_tal_swe("SWFL", tal, "swDeploy", deployed_swfks, error_msg, strict_check=False)
            else:
                self._check_tal_swe("SWFK", tal, "swDeploy", deployed_swfks, error_msg)
                self._check_tal_swe("SWFK", tal, "swDelete", deleted_swfks, error_msg)

        else:
            error_msg.append("Could not find TAL file : {} in path {}".format(tal_filename, tal_path))

        error_complete_msg = ["Error validating regular pdx flash:"] + error_msg
        error_complete_msg = "\n\t".join(error_complete_msg).strip()
        logger.debug(error_complete_msg)
        assert not error_msg, error_complete_msg

    def _do_regular_pdx_flash_interaction(self, results_folder, current_fa, previous_fa, tal_filter=False):
        self._pdx_flash_everything(
            vehicle_type=current_fa[0],
            region_variant=current_fa[1],
            tal_filter=tal_filter,
            workspace_folder=results_folder,
        )

        self._validate_regular_pdx_flash(results_folder, current_fa, previous_fa)

    def test_000_regular_pdx_flash(self):
        # Regular PDX flash with changing FAs
        #
        # **Pre-conditions**
        #     N/A
        #
        # **Required Steps**
        #     - Import PDX container
        #     - Flash PDX
        #     - Validate the TAL file
        #
        # **Expected outcome**
        #     - PDX flash successful
        #     - TAL file contains correct deploy and delete SWFKs
        # Sequence of flash FAs (vehicle_type, region_variant)

        if self.target_key == "idc23":
            if "china" in self.target_region_variant:
                flash_sequence = [("U006", "china"), ("U011", "china")]
            else:
                flash_sequence = [("U006", "row"), ("U011", "row")]
        elif self.target_key == "rse22":
            if "china" in target.options.hardware_variant:
                flash_sequence = [(target.options.vehicle_type, "china")]
            else:
                flash_sequence = [(target.options.vehicle_type, "row")]
        else:
            raise AssertionError(f"Unknown target key: {self.target_key}")

        for index, fa in enumerate(flash_sequence):
            previous_fa = flash_sequence[index - 1] if index else set()
            yield (
                self._do_regular_pdx_flash_interaction,
                "test_000_regular_pdx_flash_{}_{}_{}".format(index, *fa),
                fa,
                previous_fa,
                index == 0,  # If index is 0 means that we are doing a full flash, therefore using the tal filter
            )
        self.raw_reboot()
        self.vcar_manager.send("LifecycleRear.requestEntertainmentMode = 1")
        self.vcar_manager.send('msg_emit("20.0000B0A8.0002.01")')
