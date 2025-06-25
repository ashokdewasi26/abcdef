# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Network SOME/IP tests

DO NOT CHANGE THIS FILE WITHOUT AN EXPRESS REQUEST
This file is being used in BAT, so any change must validated by a BAT job
"""
import configparser
import logging
import re
from pathlib import Path

from mtee.metric import MetricLogger  # noqa: AZ100
from mtee.testing.tools import assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
metric_logger = MetricLogger()

ETS_RESPONSE = """Sending 10 echoUINT8 requests
Received echoUINT8 with the responseValue: 1 (requestValue was 1)
Received echoUINT8 with the responseValue: 2 (requestValue was 2)
Received echoUINT8 with the responseValue: 3 (requestValue was 3)
Received echoUINT8 with the responseValue: 4 (requestValue was 4)
Received echoUINT8 with the responseValue: 5 (requestValue was 5)
Received echoUINT8 with the responseValue: 6 (requestValue was 6)
Received echoUINT8 with the responseValue: 7 (requestValue was 7)
Received echoUINT8 with the responseValue: 8 (requestValue was 8)
Received echoUINT8 with the responseValue: 9 (requestValue was 9)
Received echoUINT8 with the responseValue: 10 (requestValue was 10)
"""
PING_SUCCESS = "2 packets transmitted, 2 received"

NODE0_VNET23_0 = "160.48.199.253"
ANDROID_VNET32_0 = "160.48.199.254"

INTERFACES_NAME_REGEX = re.compile(r"(^.\S*).*Link encap.*")


@metadata(
    testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
    component="tee_idcevo",
    domain="Network",
    asil="None",
    testmethod="Analyzing Requirements",
    testtype="Requirements-based test",
    testsetup="SW-Component",
    categorization="functional",
    priority="1",
    duplicates="IDCEVODEV-2163",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": [
                config.get("FEATURES", "NETWORK_SOMEIP"),
            ],
        },
    },
)
class TestsNetworkSOMEIP(object):
    @classmethod
    def setup_class(cls):
        """Setup class"""
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(root=True)

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def test_001_enhanced_testability_client(self):
        """[SIT_Automated] SOME/IP - Android ETS Client works

        Steps:
            - Check vnet32_0 network interface exists on Android
            - Ping from Linux to Android:
                - ping 160.48.199.254
            - Ping from Android to linux:
                - ping 160.48.199.253
            - Run adb shell command:
                /vendor/bin/EnhancedTestabilityClient
            - check all ecoUINT8 request were successful
        """
        cmd = ["ifconfig"]
        result = self.test.apinext_target.execute_command(cmd)
        logger.debug(f"Executed command on ADB: {cmd}. Stdout:\n{result.stdout.decode()}")

        interfaces = []
        for line in result.stdout.decode().splitlines():
            if match := INTERFACES_NAME_REGEX.search(line):
                interfaces.append(match.group(1))

        logger.info(f"Found interfaces: {interfaces}")
        assert_true("vnet32_0" in interfaces, "vnet32_0 interface is missing")
        self.test.mtee_target.execute_command("nft flush ruleset")

        logger.info(f"Ping from linux to {ANDROID_VNET32_0}")
        linux_connectivity = self.test.mtee_target.execute_command(["ping", "-c", "2", ANDROID_VNET32_0])
        assert_true(linux_connectivity.returncode == 0, "Ping from linux to vnet32_0 failed")

        logger.info(f"Ping from Android to {NODE0_VNET23_0}")
        cmd = ["ping", "-c", "2", NODE0_VNET23_0]
        android_connectivity = self.test.apinext_target.execute_command(cmd)
        logger.debug(f"Executed command on ADB: {cmd}. Stdout:\n{android_connectivity.stdout.decode()}")
        assert_true(PING_SUCCESS in android_connectivity.stdout.decode(), "Ping from Android to node0 vnet23_0 failed")

        cmd = ["/vendor/bin/EnhancedTestabilityClient"]
        result = self.test.apinext_target.execute_command(cmd, privileged=True)
        logger.debug(f"Executed command on ADB: {cmd}. Stdout:\n{result.stdout.decode()}")

        output_missing = list(set(ETS_RESPONSE.splitlines()) - set(result.stdout.decode().splitlines()))
        output_unexpected = list(set(result.stdout.decode().splitlines()) - set(ETS_RESPONSE.splitlines()))
        assert_true(
            len(output_missing) == 0 and len(output_unexpected) == 0,
            f"EnhancedTestabilityClient failed. Missing: {output_missing}, Found: {output_unexpected}",
        )
