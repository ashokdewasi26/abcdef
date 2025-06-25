# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Production image tests"""
import configparser
import glob
import json
import logging
import os
import re
from pathlib import Path
from unittest import skip

from gen22_helpers.pdx_utils import PDXUtils
from mtee.testing.tools import assert_false, assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.diagnostic_helper import (
    parse_cert_management_readout_status_output,
)
from si_test_idcevo.si_test_helpers.file_path_helpers import create_custom_results_dir
from si_test_idcevo.si_test_helpers.pdx_helpers import (
    pdx_teardown,
    perform_mirror_pdx_flash,
    remove_swfk_from_svt,
    retrieve_svk,
)
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target
from tee.const import SFA_FEATURE_IDS
from tee.target_common import VehicleCondition
from tee.tools.sfa_utils import SFAHandler

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

GENERATION = "25"


class TestProductionFlashing:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.target_name = cls.test.mtee_target.options.target
        # Set up pdx-required variablees
        cls.pdx = glob.glob(f"/images/pdx/{cls.target_name.upper()}_*.pdx")[0]
        cls.feature_id = SFA_FEATURE_IDS["SFA_INTERNAL_DEBUG_ACCESS_DLT_EXTERNAL_TRACING_ID"]
        cls.sfa_handler_object = SFAHandler(cls.test.mtee_target)
        logistics_dir = cls.test.mtee_target.options.esys_data_dir
        cls.pdx_utils = PDXUtils(target_type="IDCEVO-25", ks_filter="IDCEVO", logistics_dir=logistics_dir)
        cls.tal_filter = f"/resources/TAL_filter_{cls.target_name}.xml"

        cls.dev_svk_response = {}
        cls.prod_unit_svk_response = {}
        cls.pdx_svk_response = {}
        cls.sgbmid_whitelisted = []

        # For pu branches the SWFKs are important
        if cls.test.build_branch == "pu":
            cls.svk_whitelist = ("CAFD", "SWFK")
        elif cls.test.build_branch == "mainline" or cls.test.build_branch == "dirty":
            cls.svk_whitelist = "CAFD"
        if cls.test.mtee_target.options.vehicle_type == "NA05":
            # 0000BBBA - switch firmware
            # DEV flash will flash switch firmware for 506 samples but
            # NA05 cars don't need it and PDX flash will remove it
            # which will then cause a mismatch between dev and pdx
            # 0000C087 - optional SWFK with dummy content being flashed
            # this should be removed in the near future, no need to account for it
            cls.sgbmid_whitelisted = ["0000BBBA", "0000C087"]
            cls.svk_all = "/images/pdx/SVT_IDCEVO-WITHOUT_SWITCH_NA5.xml"
        else:
            cls.svk_all = "/images/pdx/SVT_IDCEVO-WITHOUT_SWITCH.xml"

        cls.file_dir = os.path.join(cls.test.mtee_target.options.result_dir, "production_flashing_tests")
        cls.json_file_path = os.path.join(cls.file_dir, "production_flashing.json")

    def assert_svk_response(self, svk_type):
        """Assert if each type of SVK is the same for all the responses after each flash"""
        if svk_type not in self.svk_whitelist:
            different_ids = []

            for id in set(self.prod_unit_svk_response.get(svk_type)) - set(self.dev_svk_response.get(svk_type)):
                different_ids.append(id)
            for id in set(self.pdx_svk_response.get(svk_type)) - set(self.dev_svk_response.get(svk_type)):
                different_ids.append(id)
            for id in set(self.prod_unit_svk_response.get(svk_type)) - set(self.pdx_svk_response.get(svk_type)):
                different_ids.append(id)

            different_ids = list(set(different_ids))
            if different_ids:
                logger.debug(f"Current IDs found that mismatch: {different_ids}")
                logger.debug(f"Sgmids to be whitelisted: {self.sgbmid_whitelisted}")
                for sgbmid in self.sgbmid_whitelisted:
                    if sgbmid in different_ids:
                        different_ids.remove(sgbmid)

            message_payload = []
            for id in different_ids:
                message_payload.append(
                    {
                        "ID": id,
                        "DEV flash": self.dev_svk_response.get(svk_type).get(id, ""),
                        "Prod unit flash": self.prod_unit_svk_response.get(svk_type).get(id, ""),
                        "PDX flash": self.pdx_svk_response.get(svk_type).get(id, ""),
                    }
                )

            assert_true(
                not bool(different_ids),
                f"SVK response doesn't match on {svk_type}. \n"
                f"Fail on validating the following ID's: {message_payload} \n"
                f"Check {self.json_file_path} for more details.",
            )

    def execute_prod_unit_swipe_flash(self):
        """Perform prod-unit-swipe flash and return SVK response
        Steps:
            - Execute 'prod-unit-swipe' command on the target
            - Reboot target
        """
        cmd = "prod-unit-swipe"
        self.test.mtee_target.execute_command(cmd)
        self.test.mtee_target.reboot()

        return retrieve_svk(self.test, self.pdx_utils, "Prod Unit Swipe")

    def execute_pdx_flash(self):
        """Perform PDX Mirror flash and return SVK response"""
        test_result_dir = create_custom_results_dir("pdx_flashing", self.test.mtee_target.options.result_dir)
        data = (
            test_result_dir,
            self.test.mtee_target.options.vin,
            GENERATION,
            self.test.mtee_target.options.vehicle_order,
            self.test.mtee_target.options.target_type,
            self.pdx,
            self.svk_all,
            self.test.mtee_target.options.vehicle_type,
            self.tal_filter,
            self.test.mtee_target.options.target_ecu_uid,
        )
        perform_mirror_pdx_flash(*data)

        return retrieve_svk(self.test, self.pdx_utils, "PDX")

    def split_version_contents(self, versions):
        """Split values of ks or pdx major/minor versions"""
        splitted_versions = versions.split(".")
        major_version = splitted_versions[0]
        minor_version = splitted_versions[1]

        return major_version, minor_version

    def run_validations(self, phase):
        """
        Run validations on target pre or post flash

         - Check Android software version
         - Check Node0 software version
         - No service/units failures are found
         - Validate the boot slot

        Args:
            phase (str): The validation phase, either "pre_flash" or "post_flash".
        Returns:
            dict: A dictionary containing the output of the commands.
        """
        assert phase in ["pre_flash", "post_flash"], "Invalid phase specified."
        outputs = {}

        command_output = self.test.apinext_target.execute_command("getprop ro.build.fingerprint")
        logger.debug(command_output)
        assert command_output.stdout, f"{phase}: Failed to obtain the android ro.build.fingerprint."
        outputs["android_build_fingerprint"] = command_output.stdout

        command_output = self.test.mtee_target.execute_command("cat /etc/os-release")
        version_pattern = re.compile(r'VERSION="(.*)"')
        match = version_pattern.search(command_output.stdout)
        if match:
            outputs["node0_sw_version"] = match.group(1)
        else:
            raise RuntimeError(f"{phase}: Unable to parse sw version from /etc/os-release")

        command_output = self.test.mtee_target.execute_command("systemctl list-units --state=failed")
        assert command_output.stdout, f"{phase}: Failed to obtain the system failed units."
        outputs["systemctl_failed_units"] = command_output.stdout

        command_output = self.test.mtee_target.execute_command("cat /proc/cmdline")
        bootloader_pattern = re.compile(r".*bootloader\.boot\.om=(\w+).*")
        bootslot = bootloader_pattern.search(command_output.stdout)
        if bootslot:
            outputs["bootslot"] = bootslot.group(1)
        else:
            raise RuntimeError(f"{phase}: Unable to obtain boot slot from /proc/cmdline")

        certificate_management_readout_status_output = (
            self.test.diagnostic_client.certificate_management_readout_status()
        )
        status = parse_cert_management_readout_status_output(certificate_management_readout_status_output)
        assert status["certificates"] == "OK", f"{phase}: Certificates are not OK. Status: {status}"
        outputs["certificates_status"] = status

        return outputs

    def compare_pre_post_validations(self):
        """Comparison between self.pre_flash_outputs and self.post_flash_outputs

        Everything is expected to be the same pre vs post flash except the boot slot
        The boot slot is expected to change from a to b or vice-versa

        Returns:
            List: A list of the errors found
        """
        errors_found = []

        for key in self.pre_flash_outputs:
            if key in self.post_flash_outputs:

                pre_value = self.pre_flash_outputs[key]
                post_value = self.post_flash_outputs[key]

                if key == "bootslot":
                    if pre_value == post_value:
                        errors_found.append(
                            f"Bootslot did not change after flashing! pre_flash: {pre_value}, post_flash: {post_value}"
                        )

                elif pre_value != post_value:
                    errors_found.append(
                        f"Difference found on {key}: pre_flash='{pre_value}', post_flash='{post_value}'"
                    )

        logger.debug(f"Following errors or differences were found:\n{errors_found}")
        return errors_found

    @metadata(
        testsuite=["BAT", "SI-production", "SI"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-20481",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "TIER_1_PLANT_LOGISTICS_SUPPORT"),
                    config.get("FEATURES", "RG4_SWE6_END_TO_END", fallback=""),
                ],
            },
        },
    )
    def test_001_production_flashing(self):
        """Perform DEV, prod-unit-swipe and PDX flashing
        Preconditions:
            Dev flash is performed and the setup of testing environment is successful.
        Steps:
            1. Switch target to DIAGNOSE mode
            2. Capture SVK response(Dev flash)
            3. Perform prod-unit-swipe flash and capture SVK response
            4. Perform PDX flash and capture SVK response
            5. Compare SVK responses between each other
        Expected result:
            All the SVK responses match. No need to validate CAFDs and SWFKs.
        """
        logger.info("Switching target into DIAGNOSE mode")
        self.test.vcar_manager.send("ActivationWireExtDiag.informationExtDiag.statusActivationWireOBD=1")
        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)

        self.dev_svk_response = retrieve_svk(self.test, self.pdx_utils, "DEV")

        self.prod_unit_svk_response = self.execute_prod_unit_swipe_flash()

        self.pdx_svk_response = self.execute_pdx_flash()
        assert_true(wait_for_application_target(self.test.mtee_target), "Not in application mode after PDX flashing")

        with open(Path(self.json_file_path), "w") as outfile:
            data = [
                {"DEV": self.dev_svk_response},
                {"Prod Unit Swipe": self.prod_unit_svk_response},
                {"PDX": self.pdx_svk_response},
            ]
            json.dump(data, outfile)

        for type in self.dev_svk_response:
            self.assert_svk_response(type)

        pdx_teardown(self.test, self.pdx_utils, "test_001_production_flashing")

    @metadata(
        testsuite=["SI", "SI-production"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
    )
    def test_002_validation_pdx_svk(self):
        """Validation of PDX content against SVK

        Preconditions:
            Target has been flash with PDX

        Steps:
            1. Read SVK to get target content
            2. Open PDX and read content
            3. Compare SVK vs PDX content
            4. Check for errors or warnings during the PDX flash

        Expected result:
            Content on target is the same of the PDX
        """
        self.pdx_utils.parse_pdx()

        mismatch_versions_list = self.pdx_utils.pdx_content_against_target(workspace_dir="pdx_flashing")

        error_msg = ""
        if mismatch_versions_list:
            xml_errors = self.pdx_utils.check_executed_tal_xml_file(workspace_dir="pdx_flashing")
            if xml_errors:
                error_msg = f"""Content from PDX does not match the SVK, mismatch list: {mismatch_versions_list},
                and there were errors during PDX flash:\n\n{xml_errors}"""
            else:
                error_msg = f"Content from PDX does not match the SVK, mismatch list: {mismatch_versions_list}"
        assert_true(len(mismatch_versions_list) == 0, error_msg)

    @metadata(
        testsuite=["SI", "SI-production"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
    )
    @skip("Skipped because KS-PDX comparison is not relevant")
    def test_003_validation_of_ks_and_pdx_content(self):
        """
        Validate that PDX and KS contents are synchronized.

        This test collects discrepancies between major and minor versions of PDX and KS,
        and asserts that both are fully aligned.

        Steps:
        1. Parses the PDX content using `parse_pdx`.
        2. Parses the KS file content using `parse_ks_file_content`.
        3. Uses validate_swe method to get the dictionary with the discrepancies between the PDX and KS contents,
        for existing SWEs
        4. Filters the dictionary, as we do not want to consider differences in patch versions

        Expected Output:
        List of SWEs where major and/or minor versions are different between KS and PDX
        """

        self.pdx_utils.parse_pdx()
        self.pdx_utils.parse_ks_file_content()

        discrepancies_between_pdx_and_ks = self.pdx_utils.validate_swe()

        discrepancies_msg = ""
        # Patch version is not taken into account in the discrepancy analysis
        for proc_class_id, pdx_ks_content in discrepancies_between_pdx_and_ks.items():
            if pdx_ks_content["pdx"][:7] != pdx_ks_content["ks"][:7]:
                discrepancies_msg += f"SWE id: {proc_class_id}\n"

                pdx_major_version, pdx_minor_version = self.split_version_contents(pdx_ks_content["pdx"])
                ks_major_version, ks_minor_version = self.split_version_contents(pdx_ks_content["ks"])

                if pdx_major_version != ks_major_version:
                    discrepancies_msg += f"\tMajor versions: PDX: {pdx_major_version}, KS: {ks_major_version}\n"
                if pdx_minor_version != ks_minor_version:
                    discrepancies_msg += f"\tMinor versions: PDX: {pdx_minor_version}, KS: {ks_minor_version}\n"

        assert_true(
            discrepancies_msg == "",
            f"PDX and KS files did not match as expected. "
            f"Discrepancies in major/minor versions were detected in the following SWEs:\n {discrepancies_msg}",
        )

    @metadata(
        testsuite=["SI", "SI-production"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-45204",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "SYSFUNC_PARTITION_FLASHING"),
                ],
            },
        },
    )
    def test_004_remove_swfk(self):
        """
        Remove SWFK from target

        We want to test that removing an swfk is possible without any errors

        Pre-condition:
            Target has been PDX flashed and contains the SWFK to be removed

        Steps:
            1. Check target svk content to find the SWFK
            2. Create a new SVT without the SWFK
            3. Generate TAL to delete SWFK
            4. Switch target to DIAGNOSE mode
            5. Use esys to remove SWFK from target
            6. Make sure target is running

        Expected Result:
            SWFK is deleted from target
            Target is stable afterwards
        """
        logger.info("Switching target into DIAGNOSE mode")
        self.test.vcar_manager.send("ActivationWireExtDiag.informationExtDiag.statusActivationWireOBD=1")
        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)

        swfk_id = "0000C063"

        svk = self.test.diagnostic_client.read_svk()
        obtained_target_svk = self.pdx_utils.format_svk(self.pdx_utils.process_svk(svk.upper()))
        logger.debug("Before flash, obtained processed svk from target: {}".format(obtained_target_svk))

        assert_true(
            swfk_id in obtained_target_svk["SWFK"].keys(),
            f"Pre-condition not met. PDX flash must have failed in previous test or SWFK {swfk_id} is not installed",
        )

        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)

        new_svt_file = f"{self.test.results_dir}/new_svt_missing_swfk.xml"
        remove_swfk_from_svt(self.svk_all, swfk_id, new_svt_file)

        test_result_dir = create_custom_results_dir("pdx_flash_remove_swfk", self.test.mtee_target.options.result_dir)
        data = (
            test_result_dir,
            self.test.mtee_target.options.vin,
            GENERATION,
            self.test.mtee_target.options.vehicle_order,
            self.test.mtee_target.options.target_type,
            self.pdx,
            new_svt_file,
            self.test.mtee_target.options.vehicle_type,
            "/resources/TAL_filter_idcevo_deletion_flash.xml",
            self.test.mtee_target.options.target_ecu_uid,
            "SIGNED_TOKEN",
            "RemoveOneSWFK",
        )
        perform_mirror_pdx_flash(*data)

        self.test.mtee_target._connect_to_target()
        if self.test.mtee_target.vehicle_state != VehicleCondition.FAHREN:
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.FAHREN)

        logger.debug("Wait for application target after pdx flashing")
        assert_true(wait_for_application_target(self.test.mtee_target), "Not in application mode after flashing")

        self.test.take_apinext_target_screenshot(
            results_dir=self.test.results_dir,
            file_name="after_pdx_flash_delete_swfk.png",
        )

        svk = self.test.diagnostic_client.read_svk()
        obtained_target_svk = self.pdx_utils.format_svk(self.pdx_utils.process_svk(svk.upper()))
        logger.debug("After flash processed svk from target: {}".format(obtained_target_svk))

        assert_true(
            swfk_id not in obtained_target_svk["SWFK"].keys(),
            f"SWFK {swfk_id} was not deleted from target. Something went wrong.",
        )

        pdx_teardown(self.test, self.pdx_utils, "test_004_remove_swfk")

    @metadata(
        testsuite=["SI", "SI-production"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-32571",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "SYSFUNC_PARTITION_FLASHING"),
                ],
            },
        },
    )
    def test_005_flash_one_swfk(self):
        """
        Flash only one SWFK to target

        We want to test that flashing one swfk is possible without any errors

        Pre-condition:
            Target has been PDX flashed and does not contains the SWFK to be added

        Steps:
            1. Run some core validations on target before flash
                - Software build on Android and Node0
                - Certificates are OK
                - No failed services
            2. Check target svk content to find the SWFK
            3. Generate TAL to flash SWFK
            4. Set Vehicle condition to PAD
            5. Use esys to flash SWFK to target
            6. Make sure target is up and running
            7. Run validation and compare to the ones before the flash
            8. Check SWFK was installed

        Expected Result:
            SWFK is added to target
            Target is stable afterwards
            No changes to the validation were induced
        """
        self.pre_flash_outputs = self.run_validations("pre_flash")

        svk = self.test.diagnostic_client.read_svk()
        obtained_target_svk = self.pdx_utils.format_svk(self.pdx_utils.process_svk(svk.upper()))
        logger.debug("Before flash, processed svk from target: {}".format(obtained_target_svk))

        swfk_id = "0000C063"
        assert_true(
            swfk_id not in obtained_target_svk["SWFK"].keys(),
            f"Pre-condition not met. The SWFK {swfk_id} is already installed, previous test must have failed",
        )

        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)

        test_result_dir = create_custom_results_dir("pdx_flash_one_swfk", self.test.mtee_target.options.result_dir)
        data = (
            test_result_dir,
            self.test.mtee_target.options.vin,
            GENERATION,
            self.test.mtee_target.options.vehicle_order,
            self.test.mtee_target.options.target_type,
            self.pdx,
            self.svk_all,
            self.test.mtee_target.options.vehicle_type,
            "/resources/TAL_filter_idcevo_optional_flash.xml",
            self.test.mtee_target.options.target_ecu_uid,
            "SIGNED_TOKEN",
            "FlashOneSWFK",
        )
        perform_mirror_pdx_flash(*data)

        self.test.mtee_target._connect_to_target()
        if self.test.mtee_target.vehicle_state != VehicleCondition.FAHREN:
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.FAHREN)

        assert_true(wait_for_application_target(self.test.mtee_target), "Not in application mode after flashing")

        self.test.take_apinext_target_screenshot(
            results_dir=self.test.results_dir,
            file_name="after_pdx_flash_one_swfk.png",
        )

        self.post_flash_outputs = self.run_validations("post_flash")

        validation_errors = self.compare_pre_post_validations()
        assert_false(
            validation_errors,
            f"{len(validation_errors)} errors found on validations pre vs post flash.",
        )

        svk = self.test.diagnostic_client.read_svk()
        obtained_target_svk = self.pdx_utils.format_svk(self.pdx_utils.process_svk(svk.upper()))
        logger.debug("After flash, processed svk from target: {}".format(obtained_target_svk))

        assert_true(
            swfk_id in obtained_target_svk["SWFK"].keys(),
            f"SWFK {swfk_id} was not flashed into the target. Something went wrong.",
        )

        pdx_teardown(self.test, self.pdx_utils, "test_005_flash_one_swfk")
