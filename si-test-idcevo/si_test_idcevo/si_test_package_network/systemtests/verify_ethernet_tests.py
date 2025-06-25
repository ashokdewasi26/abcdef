# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Verify if verify Ethernet - Traffic Shaping works"""
import configparser
import logging
import re
from pathlib import Path
from unittest import skip, skipIf

from mtee.testing.tools import assert_equal, assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.dmverity_helpers import validate_output, validate_output_using_regex_list
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target
from si_test_idcevo.si_test_helpers.test_helpers import skip_unsupported_ecus

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

# List of linux commands.
COMMANDS_LIST = [
    "tc qdisc add dev socnet0 handle 1:0 root htb",
    "tc class add dev socnet0 parent 1:0 classid 1:1 htb rate 1250000bps prio 8",
    "tc class add dev socnet0 parent 1:0 classid 1:2 htb rate 2500000bps prio 8",
    "tc class add dev socnet0 parent 1:0 classid 1:3 htb rate 6250000bps prio 7",
    "tc class add dev socnet0 parent 1:0 classid 1:4 htb rate 5000000bps prio 6",
    "tc filter add dev socnet0 parent 1:0 protocol all prio 1 handle 1:0:0 u32 divisor 1",
    "tc filter add dev socnet0 parent 1:0 protocol all prio 1 u32 match u8 0x6 0xff "
    "at 9 offset at 0 mask 0f00 shift 6 eat link 1:0:0",
    "tc filter add dev socnet0 parent 1:0 protocol all prio 1 handle 1:0:1 u32 ht "
    "1:0:0 match u16 0x11d7 0xffff at 0 classid 1:1",
    "tc filter add dev socnet0 parent 1:0 protocol all prio 1 handle 2:0:0 u32 divisor 1",
    "tc filter add dev socnet0 parent 1:0 protocol all prio 1 u32 match u8 0x6 0xff at 9 "
    "offset at 0 mask 0f00 shift 6 eat link 2:0:0",
    "tc filter add dev socnet0 parent 1:0 protocol all prio 1 handle 2:0:1 u32 ht 2:0:0 "
    "match u16 0x11d7 0xffff at 2 classid 1:2",
    "tc filter add dev socnet0 parent 1:0 protocol all prio 1 handle 3:0:0 u32 divisor 1",
    "tc filter add dev socnet0 parent 1:0 protocol all prio 1 u32 match u8 0x6 0xff at 9 "
    "match u32 0xa030c72e 0xffffffff at 16 offset at 0 mask 0f00 shift 6 eat link 3:0:0",
    "tc filter add dev socnet0 parent 1:0 protocol all prio 1 handle 3:0:1 u32 ht 3:0:0 "
    "match u16 0x1de6 0xffff at 2 classid 1:3",
    "tc filter add dev socnet0 parent 1:0 protocol all prio 1 u32 match u32 0xa030c72e "
    "0xffffffff at 16 classid 1:4",
]

IP_DETAILS_CMD = "ip -d a s "
INET4_ROUTING_CONFIGURATION_CMD = "ip -4 route show table all"
INET6_ROUTING_CONFIGURATION_CMD = "ip -6 route show table all"
IP_RULE_CMD = "ip rule"
IP_ROUTING_CMD = "ip route"

NW_STATE = "state UP"
NW_INTERFACE_NAME_AND_RESULT_DICT = {
    "idcevo": {
        "vlan77": ["vlan77", NW_STATE, "id 77", "inet6 2a03:1e80:a00:4d01::e1/64 scope global"],
        "external": ["external", NW_STATE, "id 69"],
        "vlan73": ["vlan73", NW_STATE, "id 73", "inet 160.48.199.99/25 brd 160.48.199.127 scope global vlan73"],
        "vlan68": ["vlan68", NW_STATE, "id 68", "inet 160.48.249.99/25 brd 160.48.249.127 scope global vlan68"],
        "vlan144": ["vlan144", NW_STATE, "id 144", "inet 160.48.199.161/29 brd 160.48.199.167 scope global vlan144"],
        "socnet0": ["socnet0", NW_STATE],
        "vnet23_0": ["vnet23_0", NW_STATE, "inet 160.48.199.253/30 brd 160.48.199.255 scope global vnet23_0"],
        "vlan65": ["vlan65", NW_STATE, "id 65"],
        "vlan86": ["vlan86", NW_STATE, "vlan protocol 802.1Q id 86"],
    },
    "rse26": {
        "vlan77": ["vlan77", NW_STATE, "id 77", "inet6 2a03:1e80:a00:4d01::e4/64 scope global"],
        "external": ["external", NW_STATE, "id 69"],
        "vlan73": ["vlan73", NW_STATE, "id 73", "inet 160.48.199.40/25 brd 160.48.199.127 scope global vlan73"],
        "vlan68": ["vlan68", NW_STATE, "id 68", "inet 160.48.249.40/25 brd 160.48.249.127 scope global vlan68"],
        "socnet0": ["socnet0", NW_STATE],
        "vnet23_0": ["vnet23_0", NW_STATE, "inet 160.48.199.253/30 brd 160.48.199.255 scope global vnet23_0"],
        "vlan65": ["vlan65", NW_STATE, "id 65"],
    },
}
INET4_EXPECTED_RESULTS = [
    re.compile(r".*(\d+).(\d+).(\d+).(\d+).*[vlan|vnet](\d+).*"),
    re.compile(r"multicast (\d+).(\d+).(\d+).(\d+).*[vlan|vnet].*"),
    re.compile(r"local (\d+).(\d+).(\d+).(\d+).*[vlan|vnet].*(\d+).(\d+).(\d+).(\d+)"),
    re.compile(r"broadcast (\d+).(\d+).(\d+).(\d+).*[vlan|vnet].*(\d+).(\d+).(\d+).(\d+)"),
]
INET6_EXPECTED_RESULTS = [
    re.compile(r"local .*:.*:.*:.*::.*vlan(\d+).*"),
    re.compile(r"multicast .*::.*vlan(\d+).*"),
]
IP_ROUTE_EXPECTED_RESULTS = [
    re.compile(r".*(\d+).(\d+).(\d+).(\d+).*[vlan|vnet](\d+).*"),
    re.compile(r"multicast (\d+).(\d+).(\d+).(\d+).*[vlan|vnet].*"),
]
IP_RULE_EXP = "from all lookup "
IP_RULE_EXPECTED_RESULTS = [
    IP_RULE_EXP + "local",
    IP_RULE_EXP + "220",
    IP_RULE_EXP + "main",
    IP_RULE_EXP + "default",
]


class TestsVerifyKernelLogs(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(root=True)
        cls.hw_model = cls.test.mtee_target.options.target
        cls.hw_variant = cls.test.mtee_target.options.hardware_variant

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def _check_ethernet_commands(self, command):
        """
        Check if a given linux command returns code 0.
        :param command: (str) linux command.
        """
        _, _, return_code = self.test.mtee_target.execute_command(command)
        assert_equal(return_code, 0, f"Command '{command}' returned {return_code}.")

    def _get_ip_details_and_verify(self, nw_interface, exp_output):
        """
        Get the details of a network interface and validate them
        :param nw_interface: (str) name of network interface e.g. vlan77.
        :param exp_output: (list) list of expected output.
        """
        cmd = IP_DETAILS_CMD + nw_interface
        result = self.test.mtee_target.execute_command(cmd, expected_return_code=0)
        validate_output(result, exp_output)

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
        duplicates=["IDCEVODEV-25757", "IDCEVODEV-103013", "IDCEVODEV-103014"],
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "ETHERNET_TRAFFIC_SHAPING"),
            },
        },
    )
    @skip("Test is not applicable as steps are currently performed by an official service, check: IDCEVODEV-378440")
    def test_001_verify_kernel_logs(self):
        """
        [SIT_Automated] Ethernet - Traffic Shaping tool is integrated correctly

        Steps:
            1 - Reboot the target.
            2 - Run list of linux commands and verify if there are no errors.
        """

        logger.info("Starting test to verify Ethernet - Traffic Shaping.")
        self.test.mtee_target.reboot()
        wait_for_application_target(self.test.mtee_target)

        for command in COMMANDS_LIST:
            self._check_ethernet_commands(command)

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
        duplicates="IDCEVODEV-4432",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "ETHERNET_VLAN_IP_ROUTING"),
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["rse26", "cde"]), "This test isn't supported by this ECU!")
    def test_002_verify_ethernet_vlan_configuration(self):
        """
        [SIT_Automated] Ethernet - Linux VLANs - configuration is correct
        Steps:
            1. Verify details of all network interfaces ['vlan77', 'external', 'vlan73', 'vlan68',
                'vlan144', 'socnet0', 'vnet23_0', 'vlan65', 'vlan86'] using command -
                    " ip -d a s {network interface name}"
            2. Verify details of all vlans with inet4 addresses using command -
                "ip -4 route show table all"
            3. Verify details of all vlans with inet6 addresses using command -
                "ip -6 route show table all"
            4. Verify ip rule using command -
                "ip rule"
            5. Verify the ip route using command -
                "ip route"
        """
        for nw_interface, expected_result in NW_INTERFACE_NAME_AND_RESULT_DICT[self.hw_model].items():
            if nw_interface in ["external", "vlan68"] and self.hw_variant == "SP21":
                continue
            else:
                self._get_ip_details_and_verify(nw_interface, expected_result)

        result = self.test.mtee_target.execute_command(INET4_ROUTING_CONFIGURATION_CMD, expected_return_code=0)
        match = validate_output_using_regex_list(result, INET4_EXPECTED_RESULTS)
        assert_true(match, "Didn't get expected output, failed to validate with expected regex list")

        result = self.test.mtee_target.execute_command(INET6_ROUTING_CONFIGURATION_CMD, expected_return_code=0)
        match = validate_output_using_regex_list(result, INET6_EXPECTED_RESULTS)
        assert_true(match, "Didn't get expected output, failed to validate with expected regex list")

        result = self.test.mtee_target.execute_command(IP_RULE_CMD, expected_return_code=0)
        if result:
            validate_output(result, IP_RULE_EXPECTED_RESULTS)

        result = self.test.mtee_target.execute_command(IP_ROUTING_CMD, expected_return_code=0)
        match = validate_output_using_regex_list(result, IP_ROUTE_EXPECTED_RESULTS)
        assert_true(match, "Didn't get expected output, failed to validate with expected regex list")

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="Network",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates=["IDCEVODEV-12886", "IDCEVODEV-102966", "IDCEVODEV-102967"],
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "ETHERNET_MAC_AND_IP_PROTOCOLS"),
            },
        },
    )
    def test_003_verify_ethernet_interface(self):
        """
        [SIT_Automated] Verify Ethernet Interface
        Steps:
            1 - Run cmd "ifconfig" on Android Console.
            2 - Run cmd "dmesg | grep eth" on Android console.
        Expected outcome:
            1 - Ensure that expected "eth0_pattern" should be present in output of ifconfig.
            2 - Ensure that expected "eth0_link_up_pattern" should be present in output.
        """
        eth0_pattern = re.compile(r".*(eth0).*")
        eth0_link_up_pattern = re.compile(r".*(eth0: Link is Up).*")

        ifconfig_cmd = ["ifconfig"]
        ifconfig_result = self.test.apinext_target.execute_command(ifconfig_cmd)
        logger.info(f"ifconfig command output: {ifconfig_result}")
        match = re.compile(eth0_pattern).search(ifconfig_result.stdout.decode())
        assert_true(
            match,
            f"String 'eth0' is not present in ifconfig output. Actual output of ifconfig cmd: {eth0_pattern}",
        )

        dmesg_cmd = ["dmesg | grep eth"]
        dmesg_result = self.test.apinext_target.execute_command(dmesg_cmd)
        logger.info(f"dmesg command output: {dmesg_result}")
        match = re.compile(eth0_link_up_pattern).search(dmesg_result.stdout.decode())
        assert_true(
            match,
            "String 'eth0:Link is Up' is not present in ifconfig output."
            f" Actual output of ifconfig cmd: {eth0_link_up_pattern}",
        )
