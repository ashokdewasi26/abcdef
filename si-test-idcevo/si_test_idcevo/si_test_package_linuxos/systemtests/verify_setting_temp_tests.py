# Copyright (C) 2024. BMW Car IT. All rights reserved.
"""Verify Setting of Temperature Value for All Thermal Zones"""
import configparser
import logging
from pathlib import Path

from mtee.testing.tools import assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

THERMAL_ZONES = {"0": "121000", "1": "120000", "2": "115000", "3": "110000"}
TOLERANCE_VALUE = 20000


class TestTemperatureValueThermalZones:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

    @classmethod
    def teardown_class(cls):
        cls.test.mtee_target.reboot(prefer_softreboot=False)
        cls.test.apinext_target.wait_for_boot_completed_flag(180)

    def set_verify_temperature_value(self, temp_value, zone_num):
        """
        Setting and Verifying of Temperature Value for Thermal Zone Through emul_temp sysfs Interface
        :param temp_value: int Temperature Value in C to set and verify
        :param zone_num: int Thermal Zone Number
        """
        set_temp_cmd = f"echo {temp_value} > /sys/class/thermal/thermal_zone{zone_num}/emul_temp"

        self.test.mtee_target.execute_command(set_temp_cmd, expected_return_code=0)

        get_temp_cmd = f"cat /sys/class/thermal/thermal_zone{zone_num}/temp"
        result_stdout, _, _ = self.test.mtee_target.execute_command(get_temp_cmd)
        temperature = int(result_stdout.strip())
        get_min_value = int(temp_value) - TOLERANCE_VALUE
        get_max_value = int(temp_value) + TOLERANCE_VALUE
        assert_true(
            get_min_value <= temperature <= get_max_value
        ), f"The Temperature Value for Thermal Zone {zone_num} is not within the required range"
        logger.debug(f"The Temperature Value for Thermal Zone {zone_num} is between the required range")

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
        duplicates="IDCEVODEV-57255",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "THERMAL_OPERATING_MODES"),
            },
        },
    )
    def test_001_verify_temp_to_all_thermal_zones(self):
        """
        [SIT_Automated] Verify Setting of Temperature Value for All Thermal Zones Through emul_temp sysfs Interface

        Steps:
        1. Enter the below command on the SYS console to set and read the temperature for zone0
           "# echo 121000 > /sys/class/thermal/thermal_zone0/emul_temp; cat /sys/class/thermal/thermal_zone0/temp"
        2. Enter the below command on the SYS console to set and read the temperature for zone1
           "# echo 120000 > /sys/class/thermal/thermal_zone1/emul_temp; cat /sys/class/thermal/thermal_zone1/temp"
        3. Enter the below command on the SYS console to set and read the temperature for zone2
           "# echo 115000 > /sys/class/thermal/thermal_zone2/emul_temp; cat /sys/class/thermal/thermal_zone2/temp"
        4. Enter the below command on the SYS console to set and read the temperature for zone3
           "# echo 110000 > /sys/class/thermal/thermal_zone3/emul_temp; cat /sys/class/thermal/thermal_zone3/temp"
        5. Reboot the target with KL30 OFF and ON.

        Expected Outcome:
        - All the values are set for all the sensors and are within the tolerance margin
        """

        logger.info("Verify Setting of Temperature Value for All Thermal Zones Through emul_temp sysfs Interface")

        for zone_num, temp_value in THERMAL_ZONES.items():
            self.set_verify_temperature_value(temp_value, zone_num)
