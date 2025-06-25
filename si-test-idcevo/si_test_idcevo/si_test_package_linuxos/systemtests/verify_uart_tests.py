# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Tests to verify drivers for HW peripherals present on system on chip"""
import configparser
import logging
import time
from pathlib import Path
from unittest import SkipTest, skipIf

from mtee.testing.tools import assert_false, assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.diagnostic_helper import get_dtc_list
from si_test_idcevo.si_test_helpers.parsing_handlers import compares_expected_vs_obtained_output
from si_test_idcevo.si_test_helpers.test_helpers import skip_unsupported_ecus

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

DISPLAY_NOT_CONNECTED_DTC = "0XA76307"
EXPECTED_UART_DEVICES_LIST = [
    "10880000.uart",
    "108a0000.uart",
]
EXPECTED_SPI_FILES_LIST = ["apix_page", "apix_reg", "apixreg_read"]


class TestsVerifyUART(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)
        dtc_list_str = get_dtc_list(cls.test.diagnostic_client)
        cls.display_not_detected = DISPLAY_NOT_CONNECTED_DTC in dtc_list_str

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
        duplicates="IDCEVODEV-7339",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "SOC_PERIPHERAL_SUPPORT"),
            },
        },
    )
    def test_001_verify_uart(self):
        """
        [SIT_Automated] Verify UART devices availability

        Steps:
        1 - List all UART Devices configured by Linux kernel using below command:
            #  ls /sys/devices/platform | grep -i uart
        2 - Verifies if the following expected UART devices were found:
            - 10880000.uart
            - 108a0000.uart
        """

        logger.info("Starting test to verify UART")
        return_stdout, _, _ = self.test.mtee_target.execute_command("ls /sys/devices/platform | grep -i uart")

        error_msg = compares_expected_vs_obtained_output(EXPECTED_UART_DEVICES_LIST, return_stdout.splitlines())
        assert_false(error_msg, f"Expected UART devices were not found. {error_msg}")

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
        duplicates="IDCEVODEV-18745",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "SOC_PERIPHERAL_SUPPORT"),
            },
        },
    )
    @skipIf(not skip_unsupported_ecus(["idcevo"]), "This test isn't supported by this ECU!")
    def test_002_verify_spi_communication(self):
        """
        [SIT_Automated] Verify SPI Communication with Display Serializer

        Steps:
        1 - List all files under spi9.0 directory:
            #  ls /sys/devices/platform/10c80000.spi/spi_master/spi9/spi9.0
        2 - Verifies if the following expected entries were found:
            - apix_page
            - apix_reg
            - apixreg_read
        3 - Write apix_page and apix_reg sysfs entries using below command
            - echo 0x02 > apix_page
            - echo 0x99 > apix_reg
        4 - Read apixreg_read sysfs entries using below command
            - cat apixreg_read
        5 - Validate register value from step 4 should be read as 0x0a
        """

        if self.display_not_detected:
            raise SkipTest("Skipping test as it requires display to be connected to the target")
        return_stdout, _, _ = self.test.mtee_target.execute_command(
            "ls /sys/devices/platform/10c80000.spi/spi_master/spi9/spi9.0 | grep -i apix"
        )
        logger.debug(f"Available files: {return_stdout.splitlines()}")
        error_msg = compares_expected_vs_obtained_output(EXPECTED_SPI_FILES_LIST, return_stdout.splitlines())
        assert_false(error_msg, f"Expected SPI files were not found. {error_msg}")
        self.test.mtee_target.execute_command(
            "echo 0x02 > /sys/devices/platform/10c80000.spi/spi_master/spi9/spi9.0/apix_page", expected_return_code=0
        )
        time.sleep(1)
        self.test.mtee_target.execute_command(
            "echo 0x99 > /sys/devices/platform/10c80000.spi/spi_master/spi9/spi9.0/apix_reg", expected_return_code=0
        )
        time.sleep(1)
        result = self.test.mtee_target.execute_command(
            "cat /sys/devices/platform/10c80000.spi/spi_master/spi9/spi9.0/apixreg_read", expected_return_code=0
        )
        assert_true(
            "Val:0x0a" in result.stdout,
            f"Register value is not updated as '0x0a' in apixreg_read file. Instead found {result.stdout}",
        )
