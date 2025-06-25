# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Verify SPI bus configuration"""
import configparser
import logging
from pathlib import Path
from unittest import SkipTest

from mtee.testing.tools import assert_equal, assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.test_helpers import check_ipk_installed, set_service_pack_value

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

required_target_packages = ["spitools"]

EXPECTED_LS_OUTPUT = "/dev/spidev14.0"
EXPECTED_SPI_CONFIG_OUTPUT = "/dev/spidev14.0: mode=0, lsb=0, bits=8, speed=25000000, spiready=0"
SPI_HW_VARIANT = {
    "idcevo": {
        "SP21": {
            # SP21 ECUs are expected to be B506 because of the switch
            # https://asc.bmwgroup.net/wiki/display/IDCEVO/Pinning+and+Connector+Layout
            "B506": "SPI is available",
        },
        "SP25": {
            "B505": "SPI not available",
            "B506": "SPI is available",
        },
    },
    "rse26": {
        "SP21": {
            "B513": "SPI not available",
        },
        "SP25": {
            "B513": "SPI not available",
        },
    },
}


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
    duplicates="IDCEVODEV-7142",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": [
                config.get("FEATURES", "HYPERVISOR_SUPPORT"),
                config.get("FEATURES", "SOC_PERIPHERAL_SUPPORT"),
            ],
        },
    },
)
class TestsSPIBusConfig(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)

        cls.ipk_checked = check_ipk_installed(required_target_packages)
        cls.service_pack = set_service_pack_value()
        cls.target = cls.test.mtee_target.options.target
        cls.hw_variant_code = cls.test.mtee_target.options.target_serial_no[2:6].upper()

    def check_variant_in_dict(self):
        if (
            self.target in SPI_HW_VARIANT
            and self.service_pack in SPI_HW_VARIANT[self.target]
            and self.hw_variant_code in SPI_HW_VARIANT[self.target][self.service_pack]
        ):
            return SPI_HW_VARIANT[self.target][self.service_pack][self.hw_variant_code]
        else:
            return False

    def test_001_verify_spi_bus_config(self):
        """[SIT_Automated] Verify SPI Bus Configuration
        Steps:
            - Store target specs information in variables
            - Run command to check spidev14.0 bus configuration
            - Check if command output matches the expected

        Expected result:
            - Pass if expected output is matched
        """

        if not self.ipk_checked:
            raise SkipTest(
                f"Skipping this test because the required IPKs, {required_target_packages}, "
                "weren't installed successfully!"
            )

        expected_output = self.check_variant_in_dict()

        assert_true(
            expected_output,
            f"Unexpected Hardware Version. Target: {self.target}, Service Pack: {self.service_pack}, "
            f"HW Variant Code: {self.hw_variant_code}",
        )

        return_ls_stdout, _, return_code = self.test.mtee_target.execute_command("ls -la /dev/spi*")
        return_spi_stdout, _, _ = self.test.mtee_target.execute_command("spi-config -d /dev/spidev14.0 -q")

        if expected_output == "SPI is available":
            assert_true(EXPECTED_LS_OUTPUT in return_ls_stdout, "Found an unexpected SPI interface")
            assert_equal(return_spi_stdout, EXPECTED_SPI_CONFIG_OUTPUT, "Found an unexpected SPI configuration")
        else:
            assert_true(return_code != 0, "Found an unexpected SPI interface")
