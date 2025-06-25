# Copyright (C) 2024. BMW Car IT GmbH. All rights reserved.
"""Tests related with system software"""
import configparser
import logging
import re
from datetime import datetime
from pathlib import Path
from unittest import skipIf

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import assert_equal, assert_false, assert_is_not_none, assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.dlt_logs_handlers import validate_expected_dlt_payloads_in_dlt_trace
from si_test_idcevo.si_test_helpers.dmverity_helpers import validate_output
from si_test_idcevo.si_test_helpers.lk_helper import enter_lk_shell_instance
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target
from si_test_idcevo.si_test_helpers.test_helpers import set_service_pack_value

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
target = TargetShare().target
hw_revision = target.options.hardware_revision

ANDROID_DLT_LOG = [
    {"payload_decoded": re.compile(r".*vendor.bmw.unifiedui.IUnifiedUiHal/default.*")},
    {"payload_decoded": re.compile(r".*ctl.interface_start.*")},
]
DATE_MONTH_PATTERN = r"(\w{3}\s+\w{3}\s+\d{1,2})"
ECU_PATTERN = re.compile("ECU=(.*)")
SERVICE_PACK_PATTERN = re.compile("SP=(.*)")
REGISTRY_PATTERN = re.compile(r"(sys\.registry.*)=\s(.*)")
HWCLOCK_CMD = "hwclock -r"
DATE_CMD = "date"

HWEL_VALUES = {
    "idcevo": {
        "SP21": ["0x0000B493"],
        "SP25": ["0x0000B492", "0x0000B494"],
    },
    "rse26": {
        "SP25": ["0x0000C059"],
    },
    "cde": {
        "SP25": ["0x0000C143"],
    },
}


class TestsSystemSoftware:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(root=True)
        cls.target_type = cls.test.mtee_target.options.target
        cls.ecu_variant = cls.test.mtee_target.options.target_serial_no[2:6].upper()
        cls.service_pack = set_service_pack_value()

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def match_pattern_and_get_reg_group_value(self, output_string, pattern):
        """
        This function will first match the entire reg pattern with the input provided
        and then return the first matched group value or None if string not match with pattern.
        """
        match = re.match(pattern, output_string)
        if match:
            node0_date = match.group(1)
            return node0_date
        else:
            return None

    def get_symlinks_details_of_target(self, ecu, service_pack):
        """
        :param str ecu: ecu name
        :param str service_pack: service_pack value
        this function execute the commands to fetch the symlinks details and further
        retrieves the symlinks details of the target based on the param supplied in the functions.
        """
        symlinks_cmd = "cat /etc/rvp-symlinks.ini"
        symlinks_output, _, _ = self.test.mtee_target.execute_command(symlinks_cmd, expected_return_code=0)
        if self.ecu_variant == "B506":
            ecu_and_service_pack_pattern = r"(?<=\[IDCEVO25,IDCevo_SP25_XNF_High2,SP25\])(?:(?!\[).)*"
        else:
            ecu_and_service_pack_pattern = rf"(?<=\[{ecu},,{service_pack}\])(?:(?!\[).)*"
        matches = re.search(ecu_and_service_pack_pattern, symlinks_output, re.DOTALL)
        assert_is_not_none(
            matches, f"Expected matches: {ecu_and_service_pack_pattern} not found in the output: {symlinks_output}"
        )
        return matches.group()

    def execute_and_validate_each_symlinks_cmd(self, symlink_details):
        """
        :param str symlink_details: symlink data
        This function splits the symlink details into individual commands, executes each commands.
        """
        symlink_list = symlink_details.split("\n")
        for data in symlink_list:
            if "=" in data:
                cmd_list = data.split("=")
                read_link_output = self.test.mtee_target.execute_command(f"readlink {cmd_list[0]}")
                assert_equal(
                    cmd_list[1],
                    read_link_output.stdout,
                    f"List of expected payloads - {cmd_list[1]}. Actual Payloads found- {read_link_output.stdout}",
                )

    def execute_and_validate_properties_of_registryprop_and_getprop(self):
        """
        This function fetches registry properties from both the Linux and Android consoles by executing the commands,
        compares them, and validates them.
        """
        # Fetch registry prop from linux console
        registry_cmd = "cat /var/ncd/prop/registry.prop"
        registry_cmd_output, _, _ = self.test.mtee_target.execute_command(registry_cmd, expected_return_code=0)
        registry_props_list = registry_cmd_output.strip().split("\n")

        # Fetch registry prop from android console
        getprop_output = self.test.apinext_target.execute_command("getprop")
        decoded_output = getprop_output.stdout.decode("utf-8")

        # Comparing registry_props_list with getprop_output
        for line in registry_props_list:
            matched = REGISTRY_PATTERN.search(line)
            assert_is_not_none(matched, f"Registry pattern is none. Expected Registry Pattern: {REGISTRY_PATTERN}")
            registry_key = (matched.group(1)).strip()
            registry_value = matched.group(2)
            reg_pattern = re.compile(rf"\[.*{registry_key}]: \[{registry_value}]")
            match = reg_pattern.search(decoded_output)
            assert_true(
                match, f"No match found for {registry_key} in getprop output. Expected value: {registry_value}"
            )

    @metadata(
        testsuite=["BAT", "domain", "SI", "ACM", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="LogTrace",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-10665",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "ANDROID_LOGD_READER"),
                    config.get("FEATURES", "SUPPORT_FOR_MDR"),
                ],
            },
        },
    )
    @skipIf(target.has_capability(TE.target.hardware.rse26), "Test not applicable for this ECU")
    @skipIf(target.has_capability(TE.target.hardware.cde), "Test not applicable for this ECU")
    def test_001_verify_transmission_android_logs(self):
        """
        [SIT_Automated] Verify Transmission of Android logs to DLT via remote IP
        Steps:
        * Wait for two Android system messages to appear in DLT with apid "ALD" and ctid "LCAT"
        """
        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as trace:
            self.test.mtee_target.reboot(prefer_softreboot=True)
            dlt_msgs = trace.wait_for_multi_filters(
                filters=ANDROID_DLT_LOG,
                drop=True,
                count=0,
                timeout=180,
            )

        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, ANDROID_DLT_LOG, "Android DLT Logs")

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-33461",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "SYSTEM_TIME_OPERATIONS"),
                    config.get("FEATURES", "SET_SYSTEM_TIME"),
                ],
            },
        },
    )
    def test_002_verify_sync_between_node0_and_android_clock(self):
        """
        [SIT_Automated] Verify Sync between Node0 clock and Android clock
        Steps:
            1. Run following command in node0 to collect CLOCK_REALTIME
                #date
            2. Run the following command in Android console to validate the system clock on android VM.
                $ date
            3. Run following command in node0 to check the RTC HWClock.
                # hwclock -r
            4. Run the following command in android to validate the RTC HWClock on android VM with su permissions.
                $ hwclock -r
        Expected Outcome:
            Ensure that node0 and android date should be in sync.
        """
        node0_result, _, _ = self.test.mtee_target.execute_command(DATE_CMD, expected_return_code=0)
        node0_date = self.match_pattern_and_get_reg_group_value(output_string=node0_result, pattern=DATE_MONTH_PATTERN)

        android_result = self.test.apinext_target.execute_command(DATE_CMD, privileged=True)
        android_date = self.match_pattern_and_get_reg_group_value(
            pattern=DATE_MONTH_PATTERN, output_string=android_result.stdout.decode("utf-8")
        )

        node0_stdout, _, _ = self.test.mtee_target.execute_command(HWCLOCK_CMD, expected_return_code=0)
        node0_hwclock = self.match_pattern_and_get_reg_group_value(
            pattern=DATE_MONTH_PATTERN, output_string=node0_stdout
        )

        android_result = self.test.apinext_target.execute_command(HWCLOCK_CMD, privileged=True)
        android_hwclock = self.match_pattern_and_get_reg_group_value(
            pattern=DATE_MONTH_PATTERN,
            output_string=datetime.strptime(android_result.stdout.decode("utf-8").rstrip(), "%Y-%m-%d %H:%M:%S%z")
            .strftime("%a %b %d %H:%M:%S %Z %Y")
            .replace(" 0", " "),
        )
        assert_equal(
            node0_date.replace(" ", ""),
            android_date.replace(" ", ""),
            "Node0 and Android date command not in sync."
            f"Node0 console Date: {node0_result} \n Android console Date: {android_result.stdout.decode('utf-8')}",
        )
        assert_equal(
            node0_hwclock.replace(" ", ""),
            android_hwclock.replace(" ", ""),
            "Node0 and Android 'hwclock -r' command not in sync."
            f"Node0 console hwclock: {node0_result}\nAndroid console hwclock: {android_result.stdout.decode('utf-8')}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-30962",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "RUNTIME_VARIANT_PROVIDER"),
                    config.get("FEATURES", "RUNTIME_VARIANT_PROVIDER_RVP_SUPPORT"),
                    config.get("FEATURES", "RUNTIME_VARIANT_PROVIDER_POPULATE"),
                    config.get("FEATURES", "RUNTIME_VARIANT_PROVIDER_SYMLINKS"),
                    config.get("FEATURES", "RUNTIME_VARIANT_PROVIDER_REGISTRY"),
                ],
            },
        },
    )
    def test_003_verify_test_for_ecu_hwvariant_and_sp(self):
        """
        [SIT_Automated] Verify "ECU", "HwVariant" and "SP"
        Steps:
            1. Run cmd - "cat /etc/hwel-sp.ini" and validate the expected out as per dict - "HWEL_VALUES"
            2. Run cmd - "cat /run/etc/variant.env" and validate that ECU name and Service pack data is present in o/p.
            Store the ECU name and Servive Pack data in separate variables.
            3. Run cmd - "ls -R /run/variant" and make sure the ECU name and Service pack data from step 2 and present
            in o/p.
            4. Run cmd - "cat /etc/rvp-symlinks.ini" and get the symlinks details of target.
            5. Call the cmd - "readlink" for each of the links fetched in above step and make sure it matches the
            symlink data from above step o/p.
            6. Run cmd - "cat /var/ncd/prop/registry.prop" & cmd - "getprop" and validate registry props are in sync.
        Expected output:
            Pass if expected output is matched
        """
        hwel_values_cmd = "cat /etc/hwel-sp.ini"
        hwel_cmd_output = self.test.mtee_target.execute_command(hwel_values_cmd, expected_return_code=0)
        expected_hwel_list = HWEL_VALUES.get(self.target_type, {}).get(self.service_pack)
        validate_output(hwel_cmd_output, expected_hwel_list)

        variants_env_contents_cmd = "cat /run/etc/variant.env"
        variant_env_contents_output = self.test.mtee_target.execute_command(
            variants_env_contents_cmd, expected_return_code=0
        )

        match_ecu = ECU_PATTERN.search(variant_env_contents_output.stdout)
        assert_is_not_none(
            match_ecu, f"ECU pattern - {ECU_PATTERN.pattern} not found in o/p - {variant_env_contents_output}."
        )
        match_service_pack = SERVICE_PACK_PATTERN.search(variant_env_contents_output.stdout)
        assert_is_not_none(
            match_service_pack,
            f"Service_Pack pattern - {SERVICE_PACK_PATTERN.pattern} not found in o/p - {variant_env_contents_output}.",
        )

        run_variants_cmd = "ls -R /run/variant"
        variants_file_lists_stdout = self.test.mtee_target.execute_command(run_variants_cmd, expected_return_code=0)
        ecu_version = match_ecu.group(1)
        service_pack_version = match_service_pack.group(1)
        validate_output(variants_file_lists_stdout, [ecu_version, service_pack_version])

        symlink_data = self.get_symlinks_details_of_target(ecu_version, service_pack_version)

        self.execute_and_validate_each_symlinks_cmd(symlink_data)

        self.execute_and_validate_properties_of_registryprop_and_getprop()

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-147092",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "UFS_SUPPORT_128GB_PROVISIONING"),
            },
        },
    )
    @skipIf("D" in hw_revision, "Test is not applicable for D Samples")
    def test_004_verify_ufs_support_partition_tables(self):
        """
        [SIT_Automated] UFS 128GB Provisioning
        Steps:
            1 - Enter LK mode.
            2 - Run cmd "show_gpt".
        Expected Results:
            1 - Ensure all lun partitions with expected sizes are present in serial console log.
                Expected partitions sizes are stored in list name - 'lun_number_and_size_reg'
        """

        lun_number_and_size_reg = [
            r".*lun: 0.*size:4096 bytes.*",
            r".*lun: 3.*size:4096 bytes.*",
            r".*lun: 5.*size:4096 bytes.*",
        ]

        show_gpt_cmd = "show_gpt" + "\n"
        failed_msgs = []
        try:
            enter_lk_shell_instance(self.test)
            self.test.mtee_target._console.write(show_gpt_cmd)
            for lun_data in lun_number_and_size_reg:
                try:
                    self.test.mtee_target._console.wait_for_re(lun_data, timeout=120)
                except Exception as e:
                    failed_msgs.append(
                        {
                            "Expected_pattern": lun_data,
                            "Actual_status": "Not Found",
                            "Error_message": e,
                        }
                    )
            assert_false(
                failed_msgs,
                "Below lun data partition details were not found in serial console output':\n"
                "\n".join(
                    f"Expected_lun data pattern: {msgs['Expected_pattern']}, Actual Status: {msgs['Actual_status']}, "
                    f"Error message: {msgs['Error_message']}"
                    for msgs in failed_msgs
                ),
            )
        except Exception as e:
            raise AssertionError(f"Exception occurred while fetching lun partitions with sizes: {str(e)}")
        finally:
            self.test.mtee_target.reboot(prefer_softreboot=False, serial=True)
            wait_for_application_target(self.test.mtee_target)
            self.test.apinext_target.wait_for_boot_completed_flag()
