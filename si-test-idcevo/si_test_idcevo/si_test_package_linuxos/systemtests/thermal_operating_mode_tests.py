# Copyright (C) 2024. BMW Car IT. All rights reserved.
import configparser
import logging
import re
from pathlib import Path

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import assert_equal, assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

MAX_THERMAL_ZONES = 4
WAKEUP_REASON_PAYLOAD_FILTER = re.compile(
    "wakeupReasonResponseMessage.*Wakeup Reason.*WAKEUP_REASON_OVERTEMPERATURE.*", re.IGNORECASE
)


class TestThermalZones:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

    @classmethod
    def teardown_class(cls):
        cls.test.mtee_target.reboot(prefer_softreboot=False)
        cls.test.apinext_target.wait_for_boot_completed_flag(180)

    def execute_and_validate_thermal_shutdown(self, zone_number):
        """
        Trigger thermal shutdown for individual zones and validate the same.
        :param zone_number: (int)Temp zone number
        """
        trip_point_temp_cmd = f"cat /sys/devices/virtual/thermal/thermal_zone{zone_number}/trip_point_7_temp"
        current_temp_cmd = f"cat /sys/class/thermal/thermal_zone{zone_number}/temp"
        thermal_shutdown_cmd = f"echo 126000 > /sys/class/thermal/thermal_zone{zone_number}/emul_temp"

        result_stdout, _, _ = self.test.mtee_target.execute_command(trip_point_temp_cmd)
        logger.debug("Trip point 7 temperature for zone%s: %s", zone_number, str(result_stdout))
        assert_equal("125000", result_stdout, f"The trip point value is not as expected for {zone_number}")

        result_stdout, _, _ = self.test.mtee_target.execute_command(current_temp_cmd)
        logger.debug("Current temperature for zone%s: %s", zone_number, str(result_stdout))

        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("HWAb", "IOLI")]) as trace:
            self.test.mtee_target.execute_console_command(thermal_shutdown_cmd, block=False)
            messages = trace.wait_for({"payload_decoded": WAKEUP_REASON_PAYLOAD_FILTER}, drop=True, timeout=180)
            match = WAKEUP_REASON_PAYLOAD_FILTER.search(messages[0].payload_decoded)
            self.test.mtee_target._recover_ssh(record_failure=False)

        assert_true(match, f"Failed to verify a thermal shutdown for zone{zone_number}")

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
        duplicates="IDCEVODEV-57248",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "THERMAL_OPERATING_MODES"),
            },
        },
    )
    def test001_verify_reading_temp_for_all_thermal_zones(self):
        """
        [SIT_Automated] Verify Reading of Temperature Value for all Thermal Zones Through sysfs in SYS VM

        Steps:
        1. Check the current temperature of zone0 immediately after bootup using the command:
            "cat /sys/class/thermal/thermal_zone0/temp"
        2. Check the current temperature of zone1 using the command:
            "cat /sys/class/thermal/thermal_zone1/temp"
        3. Check the current temperature of zone2 using the command:
            "cat /sys/class/thermal/thermal_zone2/temp"
        4. Check the current temperature of zone3 using the command:
            "cat /sys/class/thermal/thermal_zone3/temp"

            Note - Only B1 samples have zone4 available,
            and we don't have B1 samples in the test farm.

        Expected Outcome:
            - All temp values can be read
        """
        for each_zone in range(MAX_THERMAL_ZONES):
            result_stdout, _, _ = self.test.mtee_target.execute_command(
                f"cat /sys/class/thermal/thermal_zone{each_zone}/temp", expected_return_code=0
            )
            logger.debug("Current temperature for zone%s: %s", each_zone, str(result_stdout))

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
        duplicates="IDCEVODEV-58086",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "THERMAL_OPERATING_MODES"),
            },
        },
    )
    def test002_verify_thermal_shutdown_at_zone0(self):
        """
        [SIT_Automated] Verify Thermal Shutdown at 126 C for Thermal Zone 0
        Steps:
        1. Get the trip point 7 temperature using the command:
            "cat /sys/devices/virtual/thermal/thermal_zone0/trip_point_7_temp"
        2. Validate current trip point value is 125000
        3. Get the current temperature using the command:
            "cat /sys/class/thermal/thermal_zone0/temp"
        4. Trigger a thermal shutdown using temperature above trip point using command:
            "echo 126000 > /sys//class/thermal/thermal_zone0/emul_temp"
        5. Verify that a thermal shutdown occurs using logs.
        Expected Outcome:
            - A thermal shutdown occurs once temperature is raised above the trip point
        """
        zone_number = 0
        self.execute_and_validate_thermal_shutdown(zone_number)

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
        duplicates="IDCEVODEV-60048",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "THERMAL_OPERATING_MODES"),
            },
        },
    )
    def test003_verify_thermal_shutdown_at_zone1(self):
        """
        [SIT_Automated] Verify Thermal Shutdown at 126 C for Thermal Zone 1
        Steps:
        1. Get the trip point 7 temperature using the command:
            "cat /sys/devices/virtual/thermal/thermal_zone1/trip_point_7_temp"
        2. Validate current trip point value is 125000
        3. Get the current temperature using the command:
            "cat /sys/class/thermal/thermal_zone1/temp"
        4. Trigger a thermal shutdown using temperature above trip point using command:
            "echo 126000 > /sys//class/thermal/thermal_zone1/emul_temp"
        5. Verify that a thermal shutdown occurs using logs.
        Expected Outcome:
            - A thermal shutdown occurs once temperature is raised above the trip point
        """
        zone_number = 1
        self.execute_and_validate_thermal_shutdown(zone_number)

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
        duplicates="IDCEVODEV-60050",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "THERMAL_OPERATING_MODES"),
            },
        },
    )
    def test004_verify_thermal_shutdown_at_zone2(self):
        """
        [SIT_Automated] Verify Thermal Shutdown at 126 C for Thermal Zone 2
        Steps:
        1. Get the trip point 7 temperature using the command:
            "cat /sys/devices/virtual/thermal/thermal_zone2/trip_point_7_temp"
        2. Validate current trip point value is 125000
        3. Get the current temperature using the command:
            "cat /sys/class/thermal/thermal_zone2/temp"
        4. Trigger a thermal shutdown using temperature above trip point using command:
            "echo 126000 > /sys//class/thermal/thermal_zone2/emul_temp"
        5. Verify that a thermal shutdown occurs using logs.
        Expected Outcome:
            - A thermal shutdown occurs once temperature is raised above the trip point
        """
        zone_number = 2
        self.execute_and_validate_thermal_shutdown(zone_number)

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
        duplicates="IDCEVODEV-60056",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "THERMAL_OPERATING_MODES"),
            },
        },
    )
    def test005_verify_thermal_shutdown_at_zone3(self):
        """
        [SIT_Automated] Verify Thermal Shutdown at 126 C for Thermal Zone 3
        Steps:
        1. Get the trip point 7 temperature using the command:
            "cat /sys/devices/virtual/thermal/thermal_zone3/trip_point_7_temp"
        2. Validate current trip point value is 125000
        3. Get the current temperature using the command:
            "cat /sys/class/thermal/thermal_zone3/temp"
        4. Trigger a thermal shutdown using temperature above trip point using command:
            "echo 126000 > /sys//class/thermal/thermal_zone3/emul_temp"
        5. Verify that a thermal shutdown occurs using logs.
        Expected Outcome:
            - A thermal shutdown occurs once temperature is raised above the trip point
        """
        zone_number = 3
        self.execute_and_validate_thermal_shutdown(zone_number)
