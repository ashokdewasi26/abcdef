# Copyright (C) 2024. BMW Car IT. All rights reserved.
import configparser
import logging
import os
import re
from pathlib import Path
from unittest import SkipTest

from mtee.testing.tools import assert_false, assert_is_not_none, assert_process_returncode, assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.dmverity_helpers import validate_output_using_regex_list
from si_test_idcevo.si_test_helpers.parsing_handlers import compares_expected_vs_obtained_output
from si_test_idcevo.si_test_helpers.test_helpers import check_ipk_installed, set_service_pack_value

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

ADJUST_DATA_BINARY_PATH = Path(os.sep) / "resources" / "adjdata_copytouser"

ADJUST_DATA_BINARY_VARIANT = {
    "idcevo": {
        "B3": ["B505", "B506"],
        "B2": ["B502"],
        "B1": ["B506"],
    },
    "rse26": {
        "B2": ["B513"],
    },
    "cde": {
        "B1": ["B541"],
    },
}

EXPECTED_ED_DEV_DIRECTORY_CONTENT = {
    "compatible": ["harman,idcevo-earlydata"],
    "name": ["ed_dev"],
    "status": ["okay"],
}

MACHINE_MODEL_DATA = {
    "idcevo": [
        re.compile(r".*v920-EVT0\sSP21\sB1.*"),
        re.compile(r".*v920-EVT0\sSP25\sB1.*"),
        re.compile(r".*v720\sEVT1\sSP25-PHY\sB2.*"),
        re.compile(r".*v720\sEVT1\sSP25\sB3.*"),
        re.compile(r".*v720\sEVT1\sSP25-PHY\sB3.*"),
        re.compile(r".*v720-EVT2\sSP25-B506-C1.*"),
        re.compile(r".*v720-EVT2\sSP25-B505-C1.*"),
    ],
    "rse26": [
        re.compile(r".*v620\sEVT1\sRSE\sB1.*"),
        re.compile(r".*v620D-EVT2\sRSE-B2.*"),
    ],
    "cde": [
        re.compile(r".*v620D-EVT2\sCDE-B1.*"),
        re.compile(r".*v720-EVT2\sCDE-C1.*"),
    ],
}

PHY_CONFIG_DATA = [
    re.compile(r"mdio_bus.*88Q222X"),
    re.compile(r"Marvell 88Q222X.*dts init"),
    re.compile(r"Marvell 88Q222X.*dts_init"),
    re.compile(r"PHY.*Marvell 88Q222X"),
]

I2C_PATTERNS = {
    "idcevo": {
        "SP21": {
            "B1": [
                re.compile(r"10: 10 (-- )+"),
                re.compile(r"20: (-- )+UU (-- )+"),
                re.compile(r"40: (-- )+42 (-- )+4d"),
            ],
            "B2": [
                re.compile(r"10: 10 (-- )+"),
                re.compile(r"20: (-- )+UU (-- )+"),
                re.compile(r"40: (-- )+42 (-- )+4d"),
            ],
        },
        "SP25": {
            "B2": [re.compile(r"40: (-- )+4f")],
            "B3": [re.compile(r"40: (-- )+UU")],
        },
    },
    "rse26": {
        "SP21": {
            "B1": [re.compile(r"40: (-- )+UU")],
            "B2": [re.compile(r"40: (-- )+UU")],
            "B4": [re.compile(r"20: (-- )+28 (-- )+")],
        },
        "SP25": {
            "B1": [re.compile(r"40: (-- )+UU")],
            "B2": [re.compile(r"40: (-- )+UU")],
            "B4": [re.compile(r"20: (-- )+28 (-- )+")],
        },
    },
    "cde": {
        "SP21": {
            "B1": [re.compile(r"40: (-- )+UU")],
        },
        "SP25": {
            "B1": [re.compile(r"40: (-- )+UU")],
        },
    },
}

required_target_packages = ["i2c-tools"]


class TestVariantsupport:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.hardware_revision = cls.test.mtee_target.options.hardware_revision.upper()
        cls.hw_variant_code = cls.test.mtee_target.options.target_serial_no[2:6].upper()
        cls.hw_model = cls.test.mtee_target.options.target
        cls.service_pack = set_service_pack_value()

        cls.ipk_checked = check_ipk_installed(required_target_packages)

    def verify_model_name_for_all_hw_variant(self, result, model_dict, hw_variant):
        """
        Validate machine model name of all the received H/W variants
        :param ProcessResult result: Actual response from Target
        :param Dict model_dict: Regex Dict to match with output string
        :param Str hw_variant: Hardware model
        """
        match = False
        for hw_model_pattern in model_dict[hw_variant]:
            match = re.search(hw_model_pattern, result)
            if match is not None:
                return match
        return match

    def check_revision_in_dict(self):
        if (
            self.hw_model in I2C_PATTERNS
            and self.service_pack in I2C_PATTERNS[self.hw_model]
            and self.hardware_revision in I2C_PATTERNS[self.hw_model][self.service_pack]
        ):
            return I2C_PATTERNS[self.hw_model][self.service_pack][self.hardware_revision]
        else:
            return False

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="LinuxOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-58213",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "SW_VARIANT_SUPPORT"),
            },
        },
    )
    def test001_verify_reading_of_adjust_data(self):
        """
        [SIT_Automated] Verify Reading of Adjust Data using Test Application

        Steps -
        1. Enable the execution permissions with the below command:
            "mount -o remount,exec /tmp"
        2. Push the earlydata binary "adjdata_copytouser" to the target.
        3. Provide execute permission to the "adjdata_copytouser"
        4. Run the binary on Node0 console to read adjust data, using command
            " ./adjdata_copytouser 0 512"
        5. Verify the variant type number in the adjust data.

        Expected results -
            Correct variant type number should be present in the adjust data.
        """
        if "C" in self.hardware_revision:
            raise SkipTest("HW revision 'C' sample not applicable for this test case")
        if not (
            self.hw_model in ADJUST_DATA_BINARY_VARIANT
            and self.hardware_revision in ADJUST_DATA_BINARY_VARIANT[self.hw_model]
        ):
            raise SkipTest(
                f"HW model {self.hw_model} and hw revision {self.hardware_revision} are not applicable for this test"
            )
        self.test.mtee_target.execute_command("mount -o remount,exec /tmp", expected_return_code=0)
        self.test.mtee_target.upload(ADJUST_DATA_BINARY_PATH, "/tmp/")
        self.test.mtee_target.execute_command("chmod ugo+x adjdata_copytouser", expected_return_code=0, cwd="/tmp/")
        result_stdout, _, _ = self.test.mtee_target.execute_command(
            "./adjdata_copytouser 0 512", cwd="/tmp/", raw=True
        )
        match = False
        if any(byte != 0 for byte in result_stdout):
            substrings = ADJUST_DATA_BINARY_VARIANT.get(self.hw_model, {}).get(self.hardware_revision, [])
            match = any(substring in str(result_stdout) for substring in substrings)
        else:
            logger.error("The Adjust data contains all zeros in the output")

        assert_true(match, "Expected HW variant not found after reading adjustdata.")

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="LinuxOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-58209",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "SW_VARIANT_SUPPORT"),
            },
        },
    )
    def test002_verify_sw_variant(self):
        """
        [SIT_Automated] Verify SW Variant Related Device Tree Configurations for SYS VM

        Steps:
        Execute below commands in the target console and verify expected output
        1. ls /sys/firmware/devicetree/base/ed_dev/
           expected files: compatible, name, status
        2. cat /sys/firmware/devicetree/base/ed_dev/status
           expected content: "okay"
        3. cat /sys/firmware/devicetree/base/ed_dev/compatible
           expected content: "harman,idcevo-earlydata"
        4. cat /sys/firmware/devicetree/base/ed_dev/name
           expected content: "ed_dev"
        """
        ls_ed_dev = "ls /sys/firmware/devicetree/base/ed_dev/"
        cat_status = "cat /sys/firmware/devicetree/base/ed_dev/status | grep ."
        cat_name = "cat /sys/firmware/devicetree/base/ed_dev/name | grep ."
        cat_compatible = "cat /sys/firmware/devicetree/base/ed_dev/compatible | grep ."

        return_stdout, _, _ = self.test.mtee_target.execute_command(ls_ed_dev)
        output_ed_dev_dir = return_stdout.splitlines()
        error_msg = compares_expected_vs_obtained_output([*EXPECTED_ED_DEV_DIRECTORY_CONTENT], output_ed_dev_dir)
        assert_false(error_msg, f"Expected files was not present in ed_dev dir. missing: {error_msg}")

        return_stdout, _, _ = self.test.mtee_target.execute_command(cat_status)
        status_content = return_stdout.splitlines()
        error_msg = compares_expected_vs_obtained_output(EXPECTED_ED_DEV_DIRECTORY_CONTENT["status"], status_content)
        assert_false(error_msg, f"Expected output was not found in status file. Instead found: {error_msg}")

        return_stdout, _, _ = self.test.mtee_target.execute_command(cat_compatible)
        compatible_content = return_stdout.splitlines()
        error_msg = compares_expected_vs_obtained_output(
            EXPECTED_ED_DEV_DIRECTORY_CONTENT["compatible"], compatible_content
        )
        assert_false(error_msg, f"Expected output was not found in compatible file. Instead found: {error_msg}")

        return_stdout, _, _ = self.test.mtee_target.execute_command(cat_name)
        name_content = return_stdout.splitlines()
        error_msg = compares_expected_vs_obtained_output(EXPECTED_ED_DEV_DIRECTORY_CONTENT["name"], name_content)
        assert_false(error_msg, f"Expected output was not found in name file. Instead found: {error_msg}")

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="LinuxOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-12976",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "HW_VARIANT_SUPPORT"),
            },
        },
    )
    def test003_verify_phy_config_on_different_hw_variants(self):
        """
        [SIT_Automated] Verify Setup of Network PHY Based on HW Variant

        Steps -
        1. Fetch HW Variant type by executing the below cmd on Node0 Console:
           - cat /proc/device-tree/model
           Note - This test will be skipped if expected result for found model is not present in test case steps.
        2. Check the PHY configuration by executing the below cmd.
           - dmesg | grep "88Q222X"
        3. If HW variant is "SP25-PHY B2" OR "SP25-PHY B3" OR "SP25-PHY C1"
           make sure below list of strings are present in O/P from step2.
            -"88Q222X"
            -"Marvell 88Q222X"
            -"mdio_bus.*88Q222X"
            -"Marvell 88Q222X.*dts init"
            -"Marvell 88Q222X.*dts_init"
            -"PHY.*Marvell 88Q222X"
        4. If HW var is "SP21 B1" OR "SP25 B1" OR "SP25 B3" OR "SP25 C1"
           make sure none of the strings mentioned below are present in O/P from step2.
            -"88Q222X"
            -"Marvell 88Q222X"
            -"mdio_bus.*88Q222X"
            -"Marvell 88Q222X.*dts init"
            -"Marvell 88Q222X.*dts_init"
            -"PHY.*Marvell 88Q222X"
        """
        hw_model, _, _ = self.test.mtee_target.execute_command("cat /proc/device-tree/model")
        logger.info(f"Current hardware model: {hw_model}")

        # Below is the list of hw variants that supports this test case.
        # In future if new hws are updated in test steps then please add those in the below lists.
        list_of_supported_hw_variants = [
            "SP25-PHY B2",
            "SP25-PHY B3",
            "SP25-PHY C1",
            "SP21 B1",
            "SP25 B1",
            "SP25 B3",
            "SP25 C1",
        ]

        if not any(element in hw_model for element in list_of_supported_hw_variants):
            raise SkipTest(f"Expected result for model- {hw_model} not mentioned in test case")

        cmd = 'dmesg | grep "88Q222X"'
        phy_config_process_result = self.test.mtee_target.execute_command(cmd)
        logger.info(f"dmesg o/p: {phy_config_process_result.stdout}")

        list_of_phy_config_hw = ["SP25-PHY B2", "SP25-PHY B3", "SP25-PHY C1"]
        list_of_switch_config_hw = ["SP21 B1", "SP25 B1", "SP25 B3", "SP25 C1"]

        if any(element in hw_model for element in list_of_phy_config_hw):
            match = validate_output_using_regex_list(phy_config_process_result, PHY_CONFIG_DATA)
            assert_true(
                match, f"Strings- {PHY_CONFIG_DATA} not present in response- {phy_config_process_result.stdout}"
            )

        elif any(element in hw_model for element in list_of_switch_config_hw):
            assert_process_returncode(
                1,
                phy_config_process_result.returncode,
                msg="Strings- '{}' must not be in - {}".format(PHY_CONFIG_DATA, phy_config_process_result.stdout),
            )

        else:
            AssertionError(f"Unable to verify PHY Config for model - {hw_model}")

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="LinuxOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-11012",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "HW_VARIANT_SUPPORT"),
            },
        },
    )
    def test_004_verify_kernel_support_hw_variants(self):
        """
        [SIT_Automated] Verify Kernel Support for All HW Variants
        **Steps**
             1- Reboot Target to clear dmesg buffer.
             2. Fetch model name via below command.
                ~ # cat /proc/device-tree/model
             3. Fetch "Machine model" string using dmesg command
                ~ # dmesg | grep -r "Machine model"
             4. Ensure o/p of above commands are present in DICT - "MACHINE_MODEL_DATA".
                Kernel should correctly detect actual HW variant.
        """
        # Need to add a reboot for this case as per comments in JIRA - IDCEVODEV-188889

        self.test.mtee_target.reboot(prefer_softreboot=False)
        self.test.apinext_target.wait_for_boot_completed_flag(120)

        hw_model_stdout, _, _ = self.test.mtee_target.execute_command("cat /proc/device-tree/model")
        logger.debug(f"'Model Name' string fetched using proc interface using cat command: {hw_model_stdout}")

        match = self.verify_model_name_for_all_hw_variant(hw_model_stdout, MACHINE_MODEL_DATA, self.hw_model)
        assert_true(match, "Didn't get expected output, failed to validate with expected regex list")

        machine_model, _, _ = self.test.mtee_target.execute_command("dmesg | grep -r 'Machine model'")
        logger.debug(f"'Machine Model' string fetched using dmesg command: {machine_model}")

        match = self.verify_model_name_for_all_hw_variant(machine_model, MACHINE_MODEL_DATA, self.hw_model)
        assert_true(match, "Didn't get expected output, failed to validate with expected regex list")

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="LinuxOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-14191",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "SOC_PERIPHERAL_SUPPORT"),
            },
        },
    )
    def test_005_verify_i2c_device_detection(self):
        """
        [SIT_Automated] Verify I2C Device Detection

        Steps -
        Precondition - I2C tool ipk must be installed on target

        1. Fetch HW version and ensure the expected o/p is mentioned in dict - I2C_PATTERNS
        2. Check I2C bus information using below command
           - i2cdetect -l | grep exynosauto
        3. Fetch Bus number from the o/p of above step.
        4. List I2C devices on HU by running the below cmd.
           - i2cdetect -y -r <Bus Number>.
           Note <Bus Number> is found in step3
        5. Make sure that I2C info of HW variant under test matches as values mentioned in dict "I2C_PATTERNS".
        """

        if not self.ipk_checked:
            raise SkipTest(
                f"Skipping this test because the required IPKs, {required_target_packages}, "
                "weren't installed successfully!"
            )

        models_to_skip = [
            ["idcevo", "C1"],
            ["idcevo", "D1"],
            ["rse26", "B2"],
            ["cde", "B1"],
            ["cde", "C1"],
        ]

        # Some samples are not expected to have i2c devices detected
        # Skip the test for the samples defined on models_to_skip list
        if any(model == [self.hw_model, self.hardware_revision] for model in models_to_skip):
            raise SkipTest(
                "Skipping test as no i2c 'exynosauto' buses are expected in "
                f"{self.hw_model}-{self.hardware_revision} samples."
            )

        expected_output = self.check_revision_in_dict()
        logger.info(f"Expected o/p - {expected_output}")
        logger.info(f"Device details {self.hw_model} - {self.service_pack} - {self.hardware_revision}")
        assert_true(
            expected_output,
            f"Unexpected Hardware Version. Target: {self.hw_model}, Service Pack: {self.service_pack}, "
            f"HW Variant Code: {self.hw_variant_code}",
        )

        # Check I2C bus information using below command.
        cmd1 = "i2cdetect -l | grep exynosauto"
        i2c_detect_result, _, return_code = self.test.mtee_target.execute_command(cmd1)
        logger.info(f"I2C bus information: {i2c_detect_result}")
        assert_process_returncode(0, return_code, f"CMD- '{cmd1}' returned none o/p")

        # Fetching Bus number from the o/p of above step.
        bus_num_pattern = re.compile(r"i2c-(\d+)")
        bus_number_details = bus_num_pattern.search(i2c_detect_result)
        assert_is_not_none(
            bus_number_details, f"Could not find bus number in I2C bus information o/p - {i2c_detect_result}"
        )
        bus_number = bus_number_details.group(1)
        logger.info(f"Bus number: {bus_number}")

        # List I2C devices on HU by running the below cmd
        cmd2 = "i2cdetect -y -r " + str(bus_number)
        i2c_output, _, _ = self.test.mtee_target.execute_command(cmd2)
        logger.info(f"I2C o/p: {i2c_output}")

        # Make sure that I2C info of HW variant under test matches as values mentioned in dict "I2C_PATTERNS
        for regex in expected_output:
            match = regex.search(i2c_output)
            logger.info(f"I2C validation match found- {match}")
            assert_is_not_none(
                match,
                f"I2C data of {self.hw_model}-{self.hardware_revision} is not as expected."
                f"Expected value - {expected_output} not found in o/p {i2c_output}",
            )
