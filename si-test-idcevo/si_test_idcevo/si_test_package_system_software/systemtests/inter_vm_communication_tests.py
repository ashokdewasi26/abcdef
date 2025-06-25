# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Inter VM Communication tests"""
import configparser
import logging
import re
import string
from pathlib import Path
from unittest import SkipTest, skip

from mtee.testing.tools import (
    assert_equal,
    assert_false,
    assert_regexp_matches,
    assert_true,
    metadata,
)
from si_test_idcevo.si_test_config.virtual_links_consts import VEVENT0_EXPECTED_CONTENT, VLINK_EXPECTED_CONTENT
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.command_helpers import run_cmd_and_check_result
from si_test_idcevo.si_test_helpers.linux_commands_handlers import LinuxCommandsHandler
from si_test_idcevo.si_test_helpers.reboot_handlers import (
    reboot_and_wait_for_android_target,
    wait_for_application_target,
)
from si_test_idcevo.si_test_helpers.test_helpers import check_ipk_installed
from tee.target_common import NsmRestartReasons

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

# Transfer & install the latest ipk, for reference "virtio-utils_1.0-r0.0_cortexa76.ipk"
required_target_packages = ["virtio-utils"]

# Check if service is running
REGEX_CHECK_IF_SERVICE_IS_ACTIVE = re.compile(r".*Active:.*\(running\).*")
REGEX_CHECK_IF_SERVICE_IS_DEACTIVE = re.compile(r".*Active:.*\(dead\).*")
# Search for all virtio devices available
REGEX_SEARCH_FOR_DEVICE = re.compile(r".*(virtio\d).*")
REGEX_OPERATIONAL_VIRTIO_DEVICES = re.compile(r"(?<=virtio-)\w+")

CROSVM_DEVICE_BLOCK_PATTERN = r".*crosvm device block.*"
DD_OUTPUT_FULL_BLOCK = r".*1\+0 records in.*\n.*1\+0 records out.*"
DD_OUTPUT_PARTIAL_BLOCK = r".*0\+1 records in.*\n.*0\+1 records out.*"
LOOP_DEVICE_PATTERN = r"/dev/(loop\d): 0 disk.img"
UDEV_RULE_ATTRS_PATTERN = r'ATTRS{name}=="(.*?)"'
VIRTIO_BLK_PATTERN = r".*virtio_blk.*"
VLINK_VSXGMAC_PATTERN = r"/proc/device-tree/ethernet[^/]+/sxgmac,vlink-compatible"
VLINK_VUFS_PATTERN = r"/proc/device-tree/ufs[^/]+/vlink-compatible"

list_of_services_to_validate = [
    "vhost-user-slave-crosvm-block.service",
    "vhost-user-slave-crosvm-console.service",
    "vhost-user-slave-crosvm-filesystem.service",
    "vhost-user-slave-crosvm-input.service",
    "vhost-user-slave-crosvm-net.service",
    "vhost-user-slave-crosvm-socket.service",
]

DEFAULT_NUMBER_VEVENTS = 5  # VEVENT0 to VEVENT4
MESSAGE_NODE0 = "writing form sys to ivi"
MESSAGE_IVI = "writing from ivi to sys"

CHANGES_VINPUTDEV_CREATOR_SERVICE = r"""[Unit]
Description=Virtual Input (device) Creator
DefaultDependencies=no

[Service]
Type=exec
Restart=on-failure
ExecStart=/usr/bin/vinputsimulator

[Install]
WantedBy=multi-user.target"""

CHANGES_BLOCK_SERVICE = r"""[Unit]
Description=Crosvm vhost-user-slave block device.

Requires=vhost-user-master-vlx-vblock.service
Before=vhost-user-master-vlx-vblock.service

[Service]
Type=simple
ExecStartPre=mkdir -p /run/vhost-user-vblock
ExecStartPre=mount -o remount,rw /
ExecStartPre=-rm /root/disk.img
ExecStartPre=dd if=/dev/zero of=/root/disk.img bs=1M count=100
ExecStart=/usr/bin/crosvm device block --socket /run/vhost-user-vblock/virtio-vm3-vblock --file /root/disk.img
MemoryMax=50M
KillSignal=SIGTERM
FinalKillSignal=SIGABRT

[Install]
WantedBy=infrastructure.target
"""

CAT_EXPECTED_OUTCOMES = {
    "vbpipe": [
        "vbpipe1",
        "vbpipe10",
        "vbpipe11",
        "vbpipe12",
        "vbpipe13",
    ],
    "vrpc": [
        "vtrustonic_ivi",
        "vdmaheap,260272",
        "vsmfcdec,2k",
        "vsmfcenc,2k",
        "vrtc",
        "vthermal",
        "vclk_ctrl",
        "vtrustonic_ivi cb",
        "vdmaheap",
        "vcam2",
        "vcam1",
        "vcam0",
        "vvra",
    ],
    "veth": [
        "vnet23_0",
    ],
    "vevdev": [
        "gpiokey-wakeup",
        "CVM2RB_UINPUT_EVDEV",
    ],
}

DMESG_EXPECTED_OUTCOMES = {
    "vbpipe": [
        "VBPIPE: device vbpipe0 is created for",
        "VBPIPE: device vbpipe1 is created for",
        "VBPIPE: device vbpipe2 is created for",
        "VBPIPE: device vbpipe3 is created for",
        "VBPIPE: device vbpipe4 is created for",
        "VBPIPE: module loaded, major 223",
    ],
    "vrpc": [
        "VRPC: module loaded",
        "VLX_CLK-BE: VRPC device created for peer 3",
    ],
    "veth": [
        "vnet23_0",
        "mtu 1500",
    ],
    "vevdev": [
        "VBPIPE: device vbpipe0 is created for",
        "VBPIPE: device vbpipe1 is created for",
        "VBPIPE: device vbpipe2 is created for",
        "VBPIPE: device vbpipe3 is created for",
        "VBPIPE: device vbpipe4 is created for",
        "VBPIPE: module loaded, major 223",
    ],
}

LS_VEVDEV_EXPECTED_OUTCOME = [
    "/dev/input/event0",
    "/dev/input/event1",
]

GPU_SHARING_EXPECTED = [
    "EGL implementation : 1.5 Android META-EGL",
    "OpenGL ES 3.2 ANGLE git hash: d611f7568c21",
    "Vulkan device initialized: 1",
    "Vulkan protected device initialized: 1",
]


class TestsInterVMCommunication(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(root=True, disable_dmverity=True)

        cls.test.mtee_target.execute_command("sync", expected_return_code=0)
        reboot_and_wait_for_android_target(cls.test)
        cls.test.mtee_target.remount()

        vlink_obtained_content, _, _ = cls.test.mtee_target.execute_command("cat /proc/nk/vlinks")
        cls.vlink_obtained_content_splitted = vlink_obtained_content.splitlines()
        logger.info(f"cat vlinks: {cls.vlink_obtained_content_splitted}")

        cls.vlink_vufs_found = []
        cls.vthermal_on_status_count = 0
        cls.vlink_vsxgmac_found = []
        cls.vlink_vdpu_found = []
        for item in cls.vlink_obtained_content_splitted:
            if "vufs" in item:
                cls.vlink_vufs_found.append(item)
            if "ON/'vthermal'" in item:
                cls.vthermal_on_status_count += 1
            if "vsxgmac" in item:
                cls.vlink_vsxgmac_found.append(item)
            if "vdpu" in item:
                cls.vlink_vdpu_found.append(item)
        cls.kernel_modules = cls.test.apinext_target.execute_command(["lsmod"])
        logger.info(f"lsmod found: {cls.kernel_modules}")
        cls.touchcid_file_path = "/etc/udev/rules.d/99-touchcid.rules"
        cls.vhost_user_slave_crosvm_input_path = "/etc/systemd/system/vhost-user-slave-crosvm-input.service"
        cls.list_of_services_to_enable = [
            "vhost-user-slave-crosvm-block.service",
            "vhost-user-slave-crosvm-console.service",
        ]
        cls.selinux_config_file_original_content = ""
        cls.vinputdev_creator_original_content = ""
        cls.vhost_block_service_original_content = ""
        cls.udev_rule_original_content = ""
        cls.restore_selinux_config = False
        cls.restore_vinputdev_creator_content = False
        cls.restore_vhost_block_service_content = False
        cls.restore_udev_rule_content = False
        cls.disable_vinputdev_creator_service = False
        cls.disable_vhost_block_service = False

        cls.ipk_checked = check_ipk_installed(required_target_packages)
        cls.linux_helpers = LinuxCommandsHandler(cls.test.mtee_target, logger)

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def teardown(self):
        logger.info("Starting Test Teardown!")

        # Restore original content of vinputdev-creator.service
        if self.restore_vinputdev_creator_content:
            self.test.mtee_target.execute_command(
                f"echo '{self.vinputdev_creator_original_content}' > /etc/systemd/system/vinputdev-creator.service"
            )

        # Deactivate vinputdev-creator service
        if self.disable_vinputdev_creator_service:
            cmd_to_disable_service = "systemctl disable vinputdev-creator.service"
            _, _, returncode = self.test.mtee_target.execute_command(cmd_to_disable_service)
            assert_equal(returncode, 0, f"Error while disabling service: {cmd_to_disable_service}")

        # Restore original content of vhost-user-slave-crosvm-block service
        if self.restore_vhost_block_service_content:
            self.test.mtee_target.execute_command(
                f"echo '{self.vhost_block_service_original_content}' > "
                "/etc/systemd/system/vhost-user-slave-crosvm-block.service"
            )

        # Disable vhost-user-slave-crosvm-block service
        if self.disable_vhost_block_service:
            cmd_to_disable_service = "systemctl disable vhost-user-slave-crosvm-block.service"
            _, _, returncode = self.test.mtee_target.execute_command(cmd_to_disable_service)
            assert_equal(returncode, 0, f"Error while disabling service: {cmd_to_disable_service}")

        # Restore original content of /etc/udev/rules.d/99-touchcid.rules
        if self.restore_udev_rule_content:
            self.test.mtee_target.execute_command(
                f"echo '{self.udev_rule_original_content}' > {self.touchcid_file_path}"
            )

        # Restore original SELinux config file content
        if self.restore_selinux_config:
            self.test.mtee_target.execute_command(
                f"echo '{self.selinux_config_file_original_content}' > /etc/selinux/config"
            )

        if self.restore_selinux_config or self.disable_vinputdev_creator_service or self.disable_vhost_block_service:
            # Sync, reboot and remount target
            self.test.mtee_target.execute_command("sync", expected_return_code=0)
            reboot_and_wait_for_android_target(self.test)
            self.test.mtee_target.remount()

            # Check if SELinux is in original state
            if self.restore_selinux_config:
                selinux_after_reboot, _, _ = self.test.mtee_target.execute_command("cat /etc/selinux/config")
                assert (
                    self.selinux_config_file_original_content == selinux_after_reboot
                ), f"Failed to restore SELinux to original state. Current SELinux config: {selinux_after_reboot}"

            # Check if vinputdev-creator service is disabled
            if self.disable_vinputdev_creator_service:
                service_status_cmd = "systemctl status vinputdev-creator.service"
                service_status_output, _, _ = self.test.mtee_target.execute_command(service_status_cmd)
                assert_regexp_matches(
                    service_status_output,
                    REGEX_CHECK_IF_SERVICE_IS_DEACTIVE,
                    "'vinputdev-creator.service' not disabled after rebooting target.",
                )

            # Check if vhost-user-slave-crosvm-block service is disabled
            if self.disable_vhost_block_service:
                service_status_cmd = "systemctl status vhost-user-slave-crosvm-block.service"
                service_status_output, _, _ = self.test.mtee_target.execute_command(service_status_cmd)
                assert_regexp_matches(
                    service_status_output,
                    REGEX_CHECK_IF_SERVICE_IS_DEACTIVE,
                    "'vhost-user-slave-crosvm-block.service' not disabled after rebooting target.",
                )

        self.selinux_config_file_original_content = ""
        self.vinputdev_creator_original_content = ""
        self.vhost_block_service_original_content = ""
        self.udev_rule_original_content = ""
        self.restore_selinux_config = False
        self.restore_vinputdev_creator_content = False
        self.restore_vhost_block_service_content = False
        self.restore_udev_rule_content = False
        self.disable_vinputdev_creator_service = False
        self.disable_vhost_block_service = False

        logger.info("Test Teardown completed with success!")

    def remove_non_ascii_characters(self, input_string):
        """Removes non ASCII characteres and whitespace characters,
        including newline characters ('\n') from string"""
        return "".join(filter(lambda x: x in string.printable and x not in string.whitespace, input_string))

    def check_vthermal_virtual_links(self):
        """Checks vthermal related virtual links.

        Steps:
        1 - Check the number of 'vl,thermal-sensor' obtained as output of command:
            # cat /proc/device-tree/vltsensor_*/compatible (android console)
        2 - Check if the number of vthermal vlinks with ON status is equal, using command:
            # cat /proc/nk/vlinks

        :return: In case of unexpected result, append an error message to 'self.vlink_error_list'
        """

        logger.info("Starting vthermal related virtual links check.")

        vthermal_devices = self.test.apinext_target.execute_command(
            ["cat", "/proc/device-tree/vltsensor_*/compatible"]
        )
        logger.info(f"vthermal vlink devices: {vthermal_devices}")
        number_vthermal_devices = vthermal_devices.count("vl,thermal-sensor")

        if number_vthermal_devices != self.vthermal_on_status_count:
            error_message = (
                "Error in vthermal check. "
                f"'cat /proc/device-tree/vltsensor_*/compatible': {number_vthermal_devices} devices. "
                f"'cat /proc/nk/vlinks': {self.vthermal_on_status_count} ON status."
            )
            self.vlink_error_list.append(error_message)

    def check_vdmaheap_virtual_links(self):
        """Checks vdmaheap related virtual links.

        Steps:
        1 - The output of the following command must be 'vdmaheap' (indicating that its status is ON):
            # cat /proc/device-tree/vl,vdmaheap/dma-heap,name (android console)

        :return: In case of unexpected result, append an error message to 'self.vlink_error_list'
        """
        logger.info("Starting vdmaheap related virtual links check.")

        vdmaheap_output = self.test.apinext_target.execute_command(
            ["cat", "/proc/device-tree/vl,vdmaheap/dma-heap,name"]
        )
        vdmaheap_output = self.remove_non_ascii_characters(str(vdmaheap_output))
        logger.info(f"vdmaheap vlink output: {vdmaheap_output}")

        if vdmaheap_output != "vdmaheap":
            error_message = f"Error in vdmaheap check. vdmaheap output different from 'vdmaheap': {vdmaheap_output}"
            self.vlink_error_list.append(error_message)

    def check_vrtc_related_vlinks(self):
        """Checks vrtc related virtual links.

        Steps:
        1 - The output of the following command must be 'okay' (indicating that its status is ON):
            # cat /proc/device-tree/vrtc/status && echo (android console)

        :return: In case of unexpected result, append an error message to 'self.vlink_error_list'
        """
        vrtc_output = self.test.apinext_target.execute_command(["cat", "/proc/device-tree/vrtc/status", "&&", "echo"])
        vrtc_output = self.remove_non_ascii_characters(str(vrtc_output))
        logger.info(f"vrtc vlink output: {vrtc_output}")

        if vrtc_output != "okay":
            error_message = f"Error in vrtc check. vrtc output different from 'okay': {vrtc_output}"
            self.vlink_error_list.append(error_message)

    def check_virtual_links_device_status(
        self, vlink_device, command_check_devices, check_status_keyword_to_replace, vlink_pattern, vlink_found
    ):
        """Checks vufs/vsxgmac related virtual links.

        :param vlink_device: vlink device name (e.g. vufs or vsxgmac)
        :param command_check_devices: command to check vlink devices list
        :param check_status_keyword_to_replace: keyword to be replaced for 'status',
            in the previous command outputs, in order to check the respective device status.
        :param vlink_pattern: regex pattern used to count the number of vufs/vsxgmac devices
        :param vlink_found: list containing the vufs/vsxgmac vlinks found in command outut:
            # cat /proc/nk/vlinks

        Steps:
        1 - Get the list of vufs/vsxgmac devices, using command (android console):
            # ls /proc/device-tree/ufs*/vlink-compatible (vufs)
            # ls /proc/device-tree/*/sxgmac,vlink-compatible (vsxgmac)

            Example of expected output for vufs:
            "/proc/device-tree/ufs@0x16E10000/vlink-compatible
            /proc/device-tree/ufs@0x17E10000/vlink-compatible"

        2 - For each vufs/vsxgmac device found, determine its value and status.
            Example for vufs, considering the example device:
            - "/proc/device-tree/ufs@0x16E10000/vlink-compatible"

            Command to find vufs example device value (andorid console):
            # cat /proc/device-tree/ufs@0x16E10000/vlink-compatible && echo
            Expected output: vufs0 or vufs1

            Command to find vufs example device status (android console):
            # cat /proc/device-tree/ufs@0x16E10000/status && echo
            Expected output: okay or disabled (depending if the status its ON or OFF)

        3 - From the previous step result, verifies if vufs/vsxgmac devices contain the
            right status, using the following command output:
            # cat /proc/nk/vlinks (output saved in input variable 'vlink_found')

            - If the output is 'okay' it means the vlink status is ON
            - If the output is 'disabled' it means the vlink status is OFF

        :return: In case of unexpected result, append an error message to 'self.vlink_error_list'
        """

        logger.info(f"Starting {vlink_device} related virtual links check.")
        vlink_devices_output = self.test.apinext_target.execute_command(["ls", command_check_devices])
        vlink_devices_list = re.findall(vlink_pattern, str(vlink_devices_output))
        logger.info(f"{vlink_device} devices list: {vlink_devices_list}")

        for device in range(len(vlink_devices_list)):
            logger.info(f"{vlink_device} device: {vlink_devices_list[device]}")

            vlink_value = self.test.apinext_target.execute_command(["cat", vlink_devices_list[device], "&&", "echo"])
            vlink_value = self.remove_non_ascii_characters(str(vlink_value))
            logger.info(f"{vlink_device} value: {vlink_value}")

            command_check_status = vlink_devices_list[device].replace(check_status_keyword_to_replace, "status")
            vlink_status = self.test.apinext_target.execute_command(["cat", command_check_status, "&&", "echo"])
            vlink_status = self.remove_non_ascii_characters(str(vlink_status)).lower()
            logger.info(f"{vlink_device} status: {vlink_status}")

            if vlink_status == "disabled":
                vlink_device_pattern = re.compile(r".*" + vlink_value + r".*\/OFF\/.*")
            elif vlink_status == "okay":
                vlink_device_pattern = re.compile(r".*" + vlink_value + r".*\/ON\/.*")
            else:
                vlink_device_pattern = re.compile(r"Error! Device status not recognisable")

            matching_vufs_device = [element for element in vlink_found if vlink_device_pattern.match(element)]
            if len(matching_vufs_device) == 0:
                error_message = (
                    f"Error in {vlink_device} check. "
                    f"Unmatching pattern: {vlink_device_pattern}. "
                    f"Device value: {vlink_value}. Device status: {vlink_status}."
                    f"{vlink_device} vlink found items: {vlink_found}"
                )
                self.vlink_error_list.append(error_message)

    def check_kernel_modules(self, module, vlink_name):
        """Validates vcam and vvra related vlinks.

        :param module: vlink device module name (e.g. vcam_fe_module, vvra_fe_module)
        :param vlink_name: vlink device name (e.g. vcam, vvra)

        Steps:
        1 - Checks vcam/vvra devices with ON status in the following command output:
            # cat /proc/nk/vlinks (output saved in 'self.vlink_obtained_content_splitted')
            If status_on_match is True, at least one vcam/vvra device status is 'ON'

        2 - Checks kernel module on IVI console using command: 'lsmod' (output saved in 'self.kernel_modules')
            If kernel_module_match is True, at least one vcam/vvra device status is 'ON'

        3 - Verify if steps 1 and 2 results are coherent.
            In case vcam/vvra device is not listed by 'lsmod' (kernel_module_match = False), all respective vlinks
            listed by 'cat /proc/nk/vlinks' must have status OFF

        :return: In case of unexpected result, append an error message to 'self.vlink_error_list'
        """
        logger.info(f"Starting {vlink_name} related virtual links check.")
        vlink_device_pattern = re.compile(r".*" + vlink_name + ".*/ON/.*")
        status_on_match = any(vlink_device_pattern.match(element) for element in self.vlink_obtained_content_splitted)
        logger.info(f"{vlink_name} status on match: {status_on_match}")

        kernel_module_match = any(module in m for m in self.kernel_modules)
        logger.info(f"{vlink_name} kernel_module_match: {kernel_module_match}")

        # kernel_module_match: True if the module was listed by 'lsmod' command.
        # status_on_match: True if at least one vlink was listed with 'ON' status with 'cat /proc/nk/vlinks'
        if (not kernel_module_match and status_on_match) or (kernel_module_match and not status_on_match):
            error_message = (
                f"Error in {vlink_name} check. "
                f"{vlink_name} 'lsmod': (match if higher or equal to 0): {kernel_module_match}. "
                f"{vlink_name} vlinks found with 'ON' status: {status_on_match}."
            )
            self.vlink_error_list.append(error_message)

    def check_vdpu_virtual_links(self):
        """Checks vdpu related virtual links.

        Steps:
        1 - Check the number of available vdpu vlinks, using command:
            # ls /proc/device-tree/ | grep wod@* (android console)

            Expected output format:
                "wod@0
                (...)
                wod@4"

        2 - Check the vdpu vlinks value, using command (android console):
            # od -t x1 -An /proc/device-tree/wod@*/samsung,decon_idx | xargs -n4

            Expected output format (hexadecimal):
                "00 00 00 00
                (...)
                00 00 00 07"

        3 - Check if the number and value of vdpu vlinks with ON status is equal, using command:
            # cat /proc/nk/vlinks

            Expected output:
                "vdpu,0 serv 2/ON/'0' cli 3/ON/'' paddr 0x8fc01820
                (...)
                vdpu,4 serv 2/ON/'7' cli 3/ON/'' paddr 0x8fc01920"

        :return: In case of unexpected result, append an error message to 'self.vlink_error_list'
        """

        logger.info("Starting vdpu related virtual links check.")

        vdpu_links_number = self.test.apinext_target.execute_command(["ls /proc/device-tree/ | grep wod@*"])
        vdpu_links_number_splitted = str(vdpu_links_number).splitlines()
        logger.info(f"vdpu links number: {vdpu_links_number_splitted}")

        vdpu_links_value_hex = self.test.apinext_target.execute_command(
            ["od -t x1 -An /proc/device-tree/wod@*/samsung,decon_idx | xargs -n4"]
        )
        vdpu_links_value_hex_list = str(vdpu_links_value_hex).splitlines()
        logger.info(f"vdpu links value: {vdpu_links_value_hex_list}")

        if len(vdpu_links_number_splitted) != len(vdpu_links_value_hex_list):
            error_message = (
                "Error in vdpu check. Different vdpu list dimension. "
                f"vdpu links number: {vdpu_links_number_splitted}. "
                f"vdpu links value: {vdpu_links_value_hex_list}."
            )
            self.vlink_error_list.append(error_message)

        # convert hexadecimal values to int
        vdpu_links_value_int_list = [
            int(vdpu_value_hex.replace(" ", ""), 16) for vdpu_value_hex in vdpu_links_value_hex_list
        ]
        vdpu_regex_patterns = [re.compile(f".*vdpu.*/ON/'{value}.*") for value in vdpu_links_value_int_list]

        for pattern in vdpu_regex_patterns:
            test = any(pattern.match(vlink_string) for vlink_string in self.vlink_vdpu_found)
            logger.info(f"vdpu pattern '{pattern}' match result: {test}")
            if not any(pattern.match(vlink_string) for vlink_string in self.vlink_vdpu_found):
                error_message = (
                    f"Error in vdpu check. The following pattern was not found: {pattern.pattern}. "
                    f"The following vdpu devices were obtained: {self.vlink_vdpu_found}"
                )
                self.vlink_error_list.append(error_message)

    def set_vevent_expected_content(self):
        """
        Get the total number of virtual events and set the content to be verified.
        """
        return_stdout, _, _ = self.test.mtee_target.execute_command("ls /dev/input/ev* | wc -l")
        num_active_vevents = int(return_stdout)
        logger.debug(f"The total number of active virtual events is {num_active_vevents}")

        list_of_vevents_expected_content = []
        for i in range(max(num_active_vevents, DEFAULT_NUMBER_VEVENTS)):
            status_cli_2 = "RST" if i < num_active_vevents else "OFF"
            status_cli_3 = "ON" if i < num_active_vevents else "OFF"
            if i == 0:
                list_of_vevents_expected_content.extend(
                    [
                        VEVENT0_EXPECTED_CONTENT[0].replace("status", status_cli_3),
                        VEVENT0_EXPECTED_CONTENT[1].replace("status", status_cli_2),
                    ]
                )
            else:
                list_of_vevents_expected_content.extend(
                    [
                        rf"vevent,{i} serv 2/{status_cli_2}/'' cli 2/OFF/'' paddr .*",
                        rf"vevent,{i} serv 2/{status_cli_3}/'' cli 3/{status_cli_3}/'' paddr .*",
                    ]
                )
        logger.debug(f"List of vevent expected content: {list_of_vevents_expected_content}")
        VLINK_EXPECTED_CONTENT["vevent"] = list_of_vevents_expected_content

    def check_virtual_links(self, content, type_vlink):
        """Checks virtual links.
        In case of unexpected result, append an error message to 'self.vlink_error_list'

        Steps:
        1 - Verifies if all elements set on content are obtained using command:
            "# cat /proc/nk/vlinks" (output saved in 'self.vlink_obtained_content_splitted')

        :return: In case of unexpected result, append an error message to 'self.vlink_error_list'
        """
        vlinks_missing = []
        for expected_content in content:
            if not any(
                re.search(re.compile(expected_content), vlink_content)
                for vlink_content in self.vlink_obtained_content_splitted
            ):
                vlinks_missing.append(expected_content)

        if len(vlinks_missing) > 0:
            error_message = f"Error in {type_vlink} vlinks check. Missing expected output: {vlinks_missing}."
            self.vlink_error_list.append(error_message)

    def check_losetup_output(self):
        """
        Check if loop device output matches LOOP_DEVICE_PATTERN
        """
        try:
            self.test.mtee_target.execute_command("losetup -d /dev/loop0")
        except Exception:
            logger.info("Ignoring Error in execution of 'losetup -d /dev/loop0' command")
        self.test.mtee_target.execute_command("losetup -f disk.img")
        result_stdout, _, _ = self.test.mtee_target.execute_command("losetup -a")
        match = re.compile(LOOP_DEVICE_PATTERN).search(result_stdout)
        if match:
            loop_device = match[1]
            logger.info(f"Loop device: {loop_device} is mapped to disk image")

        assert_true(match, "Loop device and/or backing file did not match the expected output")

    def check_text_file_content(self, target, file_path, expected_content):
        cmd = f"cat {file_path}"
        if target == "apinext":
            result = self.test.apinext_target.execute_command(cmd)
            match = re.compile(rf"{expected_content}.*").search(result.stdout.decode("utf-8"))
            assert_true(match, "Data written on Node-0 side is not reflected in IVI side")
        elif target == "node-0":
            result = self.test.mtee_target.execute_command(cmd)
            match = re.compile(rf"{expected_content}.*").search(result.stdout)
            assert_true(match, "Data written on IVI side is not reflected in Node-0 side")
        else:
            raise AssertionError("Invalid target")

    def fetch_linux_and_android_frontend_and_backend_vbufq_vals(self):
        """This function fetches linux and android frontend and backend values from config.gz file
        using zcat and grep operations.
        """
        config_vlx_vbufq_pattern = r".*CONFIG_VLX_VBUFQ_(BE|FE)(\s|=)(.*)"
        linux_be = linux_fe = android_be = android_fe = None

        stdout, _, _ = self.test.mtee_target.execute_command("zcat /proc/config.gz | grep VBUFQ_BE")
        l_be = re.compile(config_vlx_vbufq_pattern).search(stdout)
        stdout, _, _ = self.test.mtee_target.execute_command("zcat /proc/config.gz | grep VBUFQ_FE")
        l_fe = re.compile(config_vlx_vbufq_pattern).search(stdout)
        stdout = self.test.apinext_target.execute_command("zcat /proc/config.gz | grep VBUFQ_BE")
        a_be = re.compile(config_vlx_vbufq_pattern).search(str(stdout))
        stdout = self.test.apinext_target.execute_command("zcat /proc/config.gz | grep VBUFQ_FE")
        a_fe = re.compile(config_vlx_vbufq_pattern).search(str(stdout))

        if l_be and l_fe and a_be and a_fe:
            linux_be, linux_fe, android_be, android_fe = l_be.group(3), l_fe.group(3), a_be.group(3), a_fe.group(3)

        logger.info(
            f"Actual Linux backend value: {linux_be}. Actual Linux frontend value: {linux_fe}."
            f"Actual android backend value: {android_be}. Actual android frontend value: {android_fe}."
        )
        return linux_be, linux_fe, android_be, android_fe

    def validate_vlinks_for_vbufq_vm3(self, linux_be_output, android_fe_output):
        """Validate vlinks for vm3.

        Step: To validate with vlinks
        a) vbufq-VM3 vlink will be up when backend drivers enabled in Android and
            frontend driver enabled in Linux
            ~ # cat /proc/nk/vlinks | grep vbufq-VM3

            Output:
            bufq,0 serv 3/OFF/'be,32,vbufq-VM3' cli 2/OFF/'' paddr 0xf5200220
            bufq,0 serv 2/OFF/'' cli 3/OFF/'be,32,vbufq-VM3' paddr 0xf5200280

        b) vbufq-VM3 vlink will be either OFF or RESET for other combinations of android
            and linux frontend and linux drivers

        :return: In case of unexpected result, append an error message to 'self.vlink_error_list'
        """
        vbufq_vm3_pattern = [
            r".*(cli 2/OFF).*\n.*(cli 3/OFF).*",
            r".*(cli 2/RST).*\n.*(cli 3/OFF).*",
            r".*(cli 2/OFF).*\n.*(cli 3/RST).*",
            r".*(cli 2/ON).*\n.*(cli 3/ON).*",
        ]

        if not (linux_be_output and android_fe_output):
            error_message = (
                f" Either Linux frontend or Android backend value is None."
                f" linux_be_output: {linux_be_output} android_fe_output: {android_fe_output} "
            )
            self.vlink_error_list.append(error_message)
            return False

        result_stdout, _, _ = self.test.mtee_target.execute_command("cat /proc/nk/vlinks | grep vbufq-VM3")
        # For vbufq-VM3 vlink
        match = None
        if "not set" in linux_be_output and "not set" in android_fe_output:
            match = re.compile(vbufq_vm3_pattern[0]).search(result_stdout)
        elif "y" in linux_be_output and "m" in android_fe_output:
            match = re.compile(vbufq_vm3_pattern[3]).search(result_stdout)
        elif "y" in linux_be_output and "not set" in android_fe_output:
            match = re.compile(vbufq_vm3_pattern[1]).search(result_stdout)
        elif "not set" in linux_be_output and "m" in android_fe_output:
            match = re.compile(vbufq_vm3_pattern[2]).search(result_stdout)

        if match is None:
            error_message = (
                f"Expected 'vbufq-VM3 vlink' output for combination of linux frontend: {linux_be_output}"
                f"and android backend: {android_fe_output} was not found in actual vm3 output: {result_stdout}."
            )
            self.vlink_error_list.append(error_message)

    def validate_vlinks_for_vbufq_vm2(self, linux_be_output, linux_fe_output, android_be_output, android_fe_output):
        """Validate vlinks for vm2.

        Step: To validate with vlinks
        a) vbufq-VM2 vlink will be up when backend drivers enabled in Android and
            frontend driver enabled in Linux
            ~ # cat /proc/nk/vlinks | grep vbufq-VM2

            Output:
            bufq,1 serv 2/ON/'be,32,vbufq-VM2' cli 3/ON/'' paddr 0xf5201240
            bufq,1 serv 3/ON/'' cli 2/ON/'be,32,vbufq-VM2' paddr 0xf52012a0

        b) vbufq-VM2 vlink will be either OFF or RESET for other combinations of android
            and linux frontend and linux drivers

        :return: In case of unexpected result, append an error message to 'self.vlink_error_list'
        """
        vbufq_vm2_pattern = [
            r".*(cli 3/OFF).*\n.*(cli 2/OFF).*",
            r".*(cli 3/RST).*\n.*(cli 2/OFF).*",
            r".*(cli 3/OFF).*\n.*(cli 2/RST).*",
            r".*(cli 3/ON).*\n.*(cli 2/ON).*",
        ]

        if not (linux_be_output and linux_fe_output and android_be_output and android_fe_output):
            error_message = (
                f" Either of the linux or android, backend or frontend is None."
                f" linux_be_output: {linux_be_output} linux_fe_output: {linux_fe_output}"
                f" android_be_output: {android_be_output} android_fe_output: {android_fe_output}."
            )
            self.vlink_error_list.append(error_message)
            return False

        result_stdout, _, _ = self.test.mtee_target.execute_command("cat /proc/nk/vlinks | grep vbufq-VM2")
        # For vbufq-VM2 vlink
        match = None

        if "not set" in linux_fe_output and "not set" in android_be_output:
            match = re.compile(vbufq_vm2_pattern[0]).search(result_stdout)
        elif "y" in linux_be_output and "m" in android_fe_output:
            match = re.compile(vbufq_vm2_pattern[3]).search(result_stdout)
        elif "y" in linux_fe_output and "not set" in android_be_output:
            match = re.compile(vbufq_vm2_pattern[2]).search(result_stdout)
        elif "not set" in linux_fe_output and "y" in android_be_output:
            match = re.compile(vbufq_vm2_pattern[1]).search(result_stdout)

        if match is None:
            error_message = (
                f"Expected 'vbufq-VM2 vlink' output for combination of linux frontend - {linux_fe_output}"
                f"and linux backend - {linux_be_output} android frontend - {android_fe_output}"
                f"and android backend - {android_be_output} was not found in actual vm2 output: {result_stdout}."
            )
            self.vlink_error_list.append(error_message)

    def sync_reboot_remount_target(self):
        """Perform actions of sync, rebooting and remounting target, in succession"""
        self.test.mtee_target.execute_command("sync", expected_return_code=0)
        reboot_and_wait_for_android_target(self.test)
        self.test.mtee_target.remount()

    def disable_and_validate_selinux_routine(self):
        """Disable SELinux via config file, reboot target and check if SELinux is in permissive mode"""
        # Check SELinux config file original content
        self.selinux_config_file_original_content, _, _ = self.test.mtee_target.execute_command(
            "cat /etc/selinux/config"
        )
        if "SELINUX=permissive" not in self.selinux_config_file_original_content:
            # Change SELinux to permissive mode
            self.test.mtee_target.execute_command(
                "sed -i 's/\\(SELINUX=\\).*/\\1permissive/' /etc/selinux/config", expected_return_code=0
            )
            self.restore_selinux_config = True
            self.sync_reboot_remount_target()

            # Ensure SELinux is in permissive mode after reboot
            selinux_after_reboot, _, _ = self.test.mtee_target.execute_command("cat /etc/selinux/config")
            assert (
                "SELINUX=permissive" in selinux_after_reboot
            ), f"Failed to change SELinux to permissive mode. Current SELinux config: {selinux_after_reboot}"

    def enable_and_validate_vhost_block_service_routine(self):
        """
        Enable 'vhost-user-slave-crosvm-block.service', reboot target and check all expected services are running
        """
        # Ensure vhost-user-slave-crosvm-block service has the correct content
        self.vhost_block_service_original_content, _, _ = self.test.mtee_target.execute_command(
            "cat /etc/systemd/system/vhost-user-slave-crosvm-block.service"
        )
        if self.vhost_block_service_original_content != CHANGES_BLOCK_SERVICE:
            # Change content of vhost-user-slave-crosvm-block service
            self.test.mtee_target.execute_command(
                f"echo '{CHANGES_BLOCK_SERVICE}' > /etc/systemd/system/vhost-user-slave-crosvm-block.service",
                expected_return_code=0,
            )
            self.restore_vhost_block_service_content = True

        # Activate vhost-user-slave-crosvm-block service
        cmd_to_enable_service = "systemctl enable vhost-user-slave-crosvm-block.service"
        _, _, returncode = self.test.mtee_target.execute_command(cmd_to_enable_service)
        assert returncode == 0, f"Error while enabling service: {cmd_to_enable_service}"
        self.disable_vhost_block_service = True

        self.sync_reboot_remount_target()

        # Check if virtio service is running
        cmd = "ps -ww | grep crosvm"
        result_stdout, _, _ = self.test.mtee_target.execute_command(cmd)
        assert_regexp_matches(result_stdout, CROSVM_DEVICE_BLOCK_PATTERN, "Virtio service is not running in node-0")

        # Check if vhost-user-slave-crosvm-block service is enabled
        service_status, _, _ = self.test.mtee_target.execute_command(
            "systemctl status vhost-user-slave-crosvm-block.service"
        )
        assert_regexp_matches(
            service_status,
            REGEX_CHECK_IF_SERVICE_IS_ACTIVE,
            "'vhost-user-slave-crosvm-block.service' not active after rebooting target",
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
        duplicates="IDCEVODEV-13476",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "INTER_VM_COMMUNICATION"),
                    config.get("FEATURES", "INTER_VM_COMMUNICATION_SHARED_MEMORY"),
                ],
            },
        },
    )
    def test_001_virtual_links(self):
        """
        [SIT_Automated] Verify Virtual Links / VLINK, VDEV

        Steps:
        The following methods will be called to validate different vlink devices:
            1 - Validates vthermal related vlinks
            2 - Validates vufs related vlinks
            3 - Validates vdmaheap related vlinks
            4 - Validates vrtc related vlinks
            5 - Validates vsxgmac related vlinks
            6 - Validates vcam related vlinks
            7 - Validates vvra related vlinks
            8 - Validates vdpu related vlinks
            9 - Validates vbufq related vlinks
            10 - Validates remaining vlinks

        The description of the validation performed in each method can be found in the respective docstring.

        In case a given method detects an unexpected result, an error message will be added to the following list:
            - self.vlink_error_list

        At the end of the test method, the error list dimension will be asserted.
        """
        logger.info("Starting test to verify virtual links")
        self.vlink_error_list = []

        self.check_vthermal_virtual_links()
        vufs_command_check_devices = "/proc/device-tree/ufs*/vlink-compatible"
        vufs_devices_status_keyword_to_replace = "vlink-compatible"
        self.check_virtual_links_device_status(
            "vufs",
            vufs_command_check_devices,
            vufs_devices_status_keyword_to_replace,
            VLINK_VUFS_PATTERN,
            self.vlink_vufs_found,
        )
        self.check_vdmaheap_virtual_links()
        self.check_vrtc_related_vlinks()
        vsxgmac_command_check_devices = "/proc/device-tree/*/sxgmac,vlink-compatible"
        vsxgmac_devices_status_keyword_to_replace = "sxgmac,vlink-compatible"
        self.check_virtual_links_device_status(
            "vsxgmac",
            vsxgmac_command_check_devices,
            vsxgmac_devices_status_keyword_to_replace,
            VLINK_VSXGMAC_PATTERN,
            self.vlink_vsxgmac_found,
        )
        self.check_kernel_modules("vcam_fe_module", "vcam")
        self.check_kernel_modules("vvra_fe_module", "vvra")
        self.check_vdpu_virtual_links()

        self.set_vevent_expected_content()

        linux_be, linux_fe, android_be, android_fe = self.fetch_linux_and_android_frontend_and_backend_vbufq_vals()
        self.validate_vlinks_for_vbufq_vm3(linux_be, android_fe)
        self.validate_vlinks_for_vbufq_vm2(linux_be, linux_fe, android_be, android_fe)
        assert_equal(
            len(self.vlink_error_list),
            0,
            f"{len(self.vlink_error_list)} error(s) detected in vlink test: {self.vlink_error_list}",
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
        duplicates="IDCEVODEV-13479",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "INTER_VM_COMMUNICATION"),
                    config.get("FEATURES", "INTER_VM_COMMUNICATION_SHARED_MEMORY"),
                ],
            },
        },
    )
    def test_002_verify_virtio_devices(self):
        """
        [SIT_Automated] Verify VirtIO devices are operational

        Steps:
            1 - Check if required IPK "virtio-utils" is installed
            2 - Remount system for Read and Write permissions
            3 - Change SELinux to be in enforcing mode
            4 - Change content of vinputdev_creator.service
            5 - Enable vinputdev_creator.service
            6 - Modify content of touchcid udev rule
            7 - Enable vhost services included in list_of_services_to_enable
            8 - Reboot and remount target
            9 - Check if all vhost services included in list_of_services_to_validate are active
            10 - Run "ls -l /sys/bus/virtio/devices/*" on android console
            11 - Check if all the expected virtio devices are operational
            12 - Disable the vhost-user-slave-crosvm-block.service
            13 - Restore original content of SELinux config file
            14 - Restore content of vinputdev_creator.service
            15 - Disable vinputdev_creator.service
            16 - Restore original content of touchcid udev rule
            17 - Disable vhost-user-slave-crosvm-block.service
            18 - Reboot and remount target
            19 - Check if vinputdev_creator and block services are disabled

        Expected outcome:
            1 - All expected virtio devices successfully enabled
            2 - All expected virtio devices are operational
        """
        if not self.ipk_checked:
            raise SkipTest(
                f"Skipping this test because the required IPKs, {required_target_packages}, "
                "weren't installed successfully!"
            )

        self.test.mtee_target.remount()

        # Ensure SELinux is in enforcing mode
        self.selinux_config_file_original_content, _, _ = self.test.mtee_target.execute_command(
            "cat /etc/selinux/config"
        )
        if "SELINUX=enforcing" not in self.selinux_config_file_original_content:
            self.test.mtee_target.execute_command(
                "sed -i 's/\\(SELINUX=\\).*/\\1enforcing/' /etc/selinux/config", expected_return_code=0
            )
            self.restore_selinux_config = True

        # Ensure vinputdev-creator.service has the correct content
        self.vinputdev_creator_original_content, _, _ = self.test.mtee_target.execute_command(
            "cat /etc/systemd/system/vinputdev-creator.service"
        )
        if self.vinputdev_creator_original_content != CHANGES_VINPUTDEV_CREATOR_SERVICE:
            self.test.mtee_target.execute_command(
                f"echo '{CHANGES_VINPUTDEV_CREATOR_SERVICE}' > /etc/systemd/system/vinputdev-creator.service",
                expected_return_code=0,
            )
            self.restore_vinputdev_creator_content = True

        cmd_to_enable_service = "systemctl enable vinputdev-creator.service"
        _, _, returncode = self.test.mtee_target.execute_command(cmd_to_enable_service)
        assert_equal(returncode, 0, f"Error while enabling service: {cmd_to_enable_service}")
        self.disable_vinputdev_creator_service = True

        # Ensure /etc/udev/rules.d/99-touchcid.rules has the correct content
        self.udev_rule_original_content, _, _ = self.test.mtee_target.execute_command(
            "cat /etc/udev/rules.d/99-touchcid.rules"
        )
        match = re.compile(UDEV_RULE_ATTRS_PATTERN).search(self.udev_rule_original_content)
        if match:
            if match.group(1) != "CVM2RB_UINPUT_EVDEV":
                old_pattern = re.escape(match.group(1))
                self.test.mtee_target.execute_command(
                    f"sed -i 's/{old_pattern}/CVM2RB_UINPUT_EVDEV/' {self.touchcid_file_path}",
                    expected_return_code=0,
                )
                self.restore_udev_rule_content = True

        # Enable vhost services included in list_of_services_to_enable
        for service in self.list_of_services_to_enable:
            cmd_to_enable_service = f"systemctl enable {service}"
            _, _, returncode = self.test.mtee_target.execute_command(cmd_to_enable_service)
            assert_equal(returncode, 0, f"Error while enabling service: {cmd_to_enable_service}")
            if service == "vhost-user-slave-crosvm-block.service":
                self.disable_vhost_block_service = True

        self.sync_reboot_remount_target()

        # Check if all vhost services included in list_of_services_to_validate are enabled
        list_of_services_deactivated = []
        for service in list_of_services_to_validate:
            service_status, _, _ = self.test.mtee_target.execute_command(f"systemctl status {service}")
            match = REGEX_CHECK_IF_SERVICE_IS_ACTIVE.search(service_status)
            if not match:
                list_of_services_deactivated.append(service)

        assert_equal(
            len(list_of_services_deactivated),
            0,
            f"The following service(s) is/are not active: {list_of_services_deactivated}",
        )

        cmd_to_list_virtio_devices = "ls -l /sys/bus/virtio/devices/*"
        list_virtio_devices_output = self.test.apinext_target.execute_command(cmd_to_list_virtio_devices)
        logger.debug(f"List of operational virtio devices: \n{list_virtio_devices_output.stdout.decode('utf-8')}")

        # Parse /sys/bus/virtio/devices/ to check if all expected virtio devices are operational
        list_of_unoperational_virtio_devices = []
        for service in list_of_services_to_validate:
            virtio_device_operational = False
            for devices in list_virtio_devices_output.stdout.decode("utf-8").splitlines():
                match = REGEX_OPERATIONAL_VIRTIO_DEVICES.search(devices)
                if match:
                    if match.group() in service:
                        logger.debug(f"{service} virtio device is operational")
                        virtio_device_operational = True
                        break
            if not virtio_device_operational:
                logger.debug(f"The virtio device associated with {service} is not operational")
                list_of_unoperational_virtio_devices.append(service)

        assert_equal(
            len(list_of_unoperational_virtio_devices),
            0,
            "The virtio device(s) associated with the following services "
            f"were expected to be operational but are not: {list_of_unoperational_virtio_devices}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="IDCEvo Test",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-9903",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "HARDWARE_ACCESS_VIRTIO"),
            },
        },
    )
    def test_003_verify_virtio_blk_driver(self):
        """
        [SIT_Automated] To verify Virtio-BLK driver for Block device access

        Steps:
            1 - Check if required IPK "virtio-utils" is installed
            2 - Remount system for Read and Write permissions
            3 - Disable SELinux
            4 - Reboot and remount target
            5 - Check SELinux is disabled
            6 - Enable the vhost-user-slave-crosvm-block.service
            7 - Reboot and remount target
            8 - Check if vhost_user_slave_crosvm_block_service is active
            9 - Check in node-0 for virtio service running
            10 - Check which loop device is mapped to out block drive image
            11 - Check which virtio device node is mapped to block device
            12 - Check which virtio device is the virtio_blk
            13 - Re-enable SELinux
            14 - Disable the vhost-user-slave-crosvm-block.service
            15 - Reboot and remount target
            16 - Check if SELinux is enabled
            17 - Check if vhost_user_slave_crosvm_block_service is disabled

        Expected outcome:
            1 - Virtio-blk driver is associated with a virtio device
        """

        if not self.ipk_checked:
            raise SkipTest(
                f"Skipping this test because the required IPKs, {required_target_packages}, "
                "weren't installed successfully!"
            )

        self.test.mtee_target.remount()

        self.disable_and_validate_selinux_routine()

        self.enable_and_validate_vhost_block_service_routine()

        self.check_losetup_output()

        # Check which virtio device has block access
        cmd = "ls -ld /sys/bus/virtio/devices/virtio*/block/vda"
        result = self.test.apinext_target.execute_command(cmd)
        match = REGEX_SEARCH_FOR_DEVICE.search(result.stdout.decode("utf-8"))
        if match:
            virtio_device = match[1]
            logger.info(f"Virtio device: {virtio_device} is mapped to block device")
        else:
            raise AssertionError("Could not find a virtio device mapped to block device")

        # Check if virtio_blk is found in the block device
        cmd = f"ls -l /sys/bus/virtio/devices/{virtio_device}/"
        result = self.test.apinext_target.execute_command(cmd)
        match = re.compile(VIRTIO_BLK_PATTERN).search(result.stdout.decode("utf-8"))
        if match:
            logger.info(f"virtio_blk is in {virtio_device}")
        else:
            raise AssertionError("Could not find virtio_blk")

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
        duplicates="IDCEVODEV-25767",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "HARDWARE_ACCESS_VIRTIO"),
            },
        },
    )
    def test_004_verify_virtio_blk_access(self):
        """
        [SIT_Automated] Verify the virtio_blk access

        Steps:
            1 - Check if required IPK "virtio-utils" is installed
            2 - Remount system for Read and Write permissions
            3 - Disable SELinux
            4 - Reboot and remount target
            5 - Check SELinux is disabled
            6 - Enable the vhost-user-slave-crosvm-block.service
            7 - Reboot and remount target
            8 - Check if vhost_user_slave_crosvm_block_service is active
            9 - Run 'losetup -a' on Node0
            10 - Run 'echo "writing from sys to ivi" > /tmp/sys_to_ivi.txt' on Node0
            11 - Run 'dd if=/tmp/sys_to_ivi.txt of=/dev/loop0 bs=25 count=1' on Node0
            12 - Run su in IVI console
            13 - Run 'dd if=/dev/block/vda of=/data/test.txt bs=25 count=1' on IVI console
            14 - Check content of /data/test.txt on IVI console
            15 - Run 'echo "writing from ivi to sys" > /data/test.txt' on IVI console
            16 - Run 'cat /data/test.txt' on IVI console.
            17 - Run 'dd if=/data/test.txt  of=/dev/block/vda bs=25 count=1' on IVI console
            18 - Run 'dd if=/dev/loop0 of=/tmp/test1.txt bs=25 count=1' on Node0
            19 - Check content of /tmp/test1.txt on Node0
            20 - Re-enable SELinux
            21 - Disable the vhost-user-slave-crosvm-block.service
            22 - Reboot and remount target
            23 - Check if SELinux is enabled
            24 - Check if vhost_user_slave_crosvm_block_service is disabled

        Expected outcome:
            1 - All expected outcomes are present in the command outputs.
        """

        if not self.ipk_checked:
            raise SkipTest(
                f"Skipping this test because the required IPKs, {required_target_packages}, "
                "weren't installed successfully!"
            )

        self.test.mtee_target.remount()

        self.disable_and_validate_selinux_routine()

        self.enable_and_validate_vhost_block_service_routine()

        self.check_losetup_output()

        cmd = f"echo {MESSAGE_NODE0} > /tmp/sys_to_ivi.txt"
        self.test.mtee_target.execute_command(cmd)

        cmd = "dd if=/tmp/sys_to_ivi.txt of=/dev/loop0 bs=25 count=1"
        result = self.test.mtee_target.execute_command(cmd)
        match = re.compile(DD_OUTPUT_PARTIAL_BLOCK).search(result.stderr)
        assert_true(result.returncode == 0 and match, "Error while executing 'dd' command on Node-0")

        result = self.test.apinext_target.execute_command("su")

        cmd = "dd if=/dev/block/vda of=/data/test.txt bs=25 count=1"
        result = self.test.apinext_target.execute_command(cmd, privileged=True)
        match = re.compile(DD_OUTPUT_FULL_BLOCK).search(result.stderr.decode("utf-8"))
        assert_true(match, "Error while executing 'dd' command on IVI console")

        self.check_text_file_content("apinext", "/data/test.txt", MESSAGE_NODE0)

        cmd = f"echo {MESSAGE_IVI} > /data/test.txt"
        self.test.apinext_target.execute_command(cmd)

        self.check_text_file_content("apinext", "/data/test.txt", MESSAGE_IVI)

        cmd = "dd if=/data/test.txt  of=/dev/block/vda bs=25 count=1"
        result = self.test.apinext_target.execute_command(cmd, privileged=True)
        match = re.compile(DD_OUTPUT_PARTIAL_BLOCK).search(result.stderr.decode("utf-8"))
        assert_true(match, "Error while executing 'dd' command on IVI console")

        cmd = "dd if=/dev/loop0 of=/tmp/test1.txt bs=25 count=1"
        result = self.test.mtee_target.execute_command(cmd)
        match = re.compile(DD_OUTPUT_FULL_BLOCK).search(result.stderr)
        assert_true(result.returncode == 0 and match, "Error while executing 'dd' command on Node-0 console")

        self.check_text_file_content("node-0", "/tmp/test1.txt", MESSAGE_IVI)

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
        duplicates="IDCEVODEV-13475",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "INTER_VM_COMMUNICATION_SHARED_MEMORY"),
            },
        },
    )
    def test_005_verify_vbpipes(self):
        """
        [SIT_Automated] Verify Virtual Stream(Bi directional Pipe) / VBPIPE

        Steps:
            - Execute cat and dmesg commands
            - Compare both outputs to expected outcomes

        Expected outcome:
            - All expected outcomes are present in the command outputs

        Note:
        A test based on the same manual steps is also implemented on the repo "bat-automation-tests-systemsw",
        in the "si_job_ready" branch,
        inside the test file named "verify_virtual_stream_bi_directional_pipe_vbpipe_tests.py",
        with the test method "test_001_verify_virtual_stream_bi_directional_pipe_vbpipe".
        """
        _, missing_entry_cat = run_cmd_and_check_result("cat /proc/nk/vbpipe", CAT_EXPECTED_OUTCOMES["vbpipe"])
        _, missing_entry_dmesg = run_cmd_and_check_result(
            'dmesg | grep -nri "vbpipe"', DMESG_EXPECTED_OUTCOMES["vbpipe"]
        )

        error_message = "Fail on checking if VBpipe device is operational."
        if missing_entry_cat:
            error_message += f"\nEntries missing from cat operation: {missing_entry_cat}"
        if missing_entry_dmesg:
            error_message += f"\nEntries missing from dmesg operation: {missing_entry_dmesg}"

        assert_false(missing_entry_cat or missing_entry_dmesg, error_message)

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
        duplicates="IDCEVODEV-13478",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "INTER_VM_COMMUNICATION_SHARED_MEMORY"),
            },
        },
    )
    def test_006_verify_vrpc(self):
        """
        [SIT_Automated] Verify VRPC device is operational

        Steps:
            - Execute cat and dmesg commands
            - Compare both outputs to expected outcomes

        Expected outcome:
            - All expected outcomes are present in the command outputs.

        Note:
        A test based on the same manual steps is also implemented on the repo "bat-automation-tests-systemsw",
        in the "si_job_ready" branch,
        inside the test file named "verify_vrpc_device_is_operational_tests.py",
        with the test method "test_001_verify_vrpc_device_is_operational".
        """
        _, missing_entry_cat = run_cmd_and_check_result("cat /proc/nk/vrpc", CAT_EXPECTED_OUTCOMES["vrpc"])
        _, missing_entry_dmesg = run_cmd_and_check_result('dmesg | grep -nri "vrpc"', DMESG_EXPECTED_OUTCOMES["vrpc"])

        error_message = "Fail on checking if VRPC device is operational."
        if missing_entry_cat:
            error_message += f"\nEntries missing from cat operation: {missing_entry_cat}"
        if missing_entry_dmesg:
            error_message += f"\nEntries missing from dmesg operation: {missing_entry_dmesg}"

        assert_false(missing_entry_cat or missing_entry_dmesg, error_message)

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
        duplicates="IDCEVODEV-13477",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "INTER_VM_COMMUNICATION_SHARED_MEMORY"),
            },
        },
    )
    @skip("Test is inactive: IDCEVODEV-420534")
    def test_007_verify_veth(self):
        """
        [SIT_Automated] Verify VETH device is operational
        Steps:
            - Execute cat and dmesg commands
            - Compare both outputs to expected outcomes
        Expected outcome:
            - All expected outcomes are present in the command outputs.
        Note:
        A test based on the same manual steps is also implemented on the repo "bat-automation-tests-systemsw",
        in the "si_job_ready" branch,
        inside the test file named "verify_veth_device_is_operational_tests.py",
        with the test method "test_001_verify_veth_device_is_operational".
        """
        _, missing_entry_cat = run_cmd_and_check_result("cat /proc/nk/veth2", CAT_EXPECTED_OUTCOMES["veth"])
        _, missing_entry_dmesg = run_cmd_and_check_result('dmesg | grep -nri "veth"', DMESG_EXPECTED_OUTCOMES["veth"])

        error_message = "Fail on checking if VETH device is operational."
        if missing_entry_cat:
            error_message += f"\nEntries missing from cat operation: {missing_entry_cat}"
        if missing_entry_dmesg:
            error_message += f"\nEntries missing from dmesg operation: {missing_entry_dmesg}"

        assert_false(missing_entry_cat or missing_entry_dmesg, error_message)

    @metadata(
        testsuite=["BAT", "domain", "SI-SIT-Automated", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-13352",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "VM_MANAGEMENT_LIFECYCLE_CONTROL"),
            },
        },
    )
    def test_008_reboot_of_whole_system_using_vshutdown(self):
        """
           [SIT_Automated] Verify the reboot of whole system using vshutdown
            Steps:
                - Execute "nsg_control --setNodeState 8 --requestRestart NsmRestartReasons.Application  "
            Expected Results:
                - The whole system should reboot.
        '"""
        cmd = f"nsg_control --setNodeState 8 --requestRestart {NsmRestartReasons.Application}"
        self.test.mtee_target.execute_command(cmd)
        self.test.mtee_target.prepare_for_reboot()
        self.test.mtee_target.wait_for_reboot(serial=False, skip_ready_checks=True)
        self.test.mtee_target.resume_after_reboot(skip_ready_checks=False)

        wait_for_reboot_result = wait_for_application_target(self.test.mtee_target)
        assert_true(wait_for_reboot_result, "Failed to perform a reboot based in vshutdown")

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
        duplicates="IDCEVODEV-13481",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "INTER_VM_COMMUNICATION_SHARED_MEMORY"),
            },
        },
    )
    def test_009_verify_vevdev(self):
        """
        [SIT_Automated] Verify VEVDEV device is operational

        Steps:
            1 - Check if required IPK "virtio-utils" is installed
            2 - Remount system for Read and Write permissions
            3 - Change content of vinputdev_creator.service
            4 - If it isn't enabled, enable it again
            5 - Enable vinputdev_creator.service
            6 - Modify content of touchcid udev rule
            7 - Reboot and remount target
            8 - Check status of vhost-user-slave-crosvm-input.service
            9 - Execute cat, dmesg and ls commands
            10 - Compare expected outputs to the received outputs. Fail test if any are missing.
            11 - Restore content of vinputdev_creator.service
            12 - Disable vinputdev-creator.service
            13 - Reboot and remount target
            14 - Check if vinputdev-creator.service is disabled

        Expected outcome:
            1 - All expected outcomes are present in the command outputs.
        """

        if not self.ipk_checked:
            raise SkipTest(
                f"Skipping this test because the required IPKs, {required_target_packages}, "
                "weren't installed successfully!"
            )
        self.test.mtee_target.remount()

        # Ensure vinputdev-creator.service has the correct content
        self.vinputdev_creator_original_content, _, _ = self.test.mtee_target.execute_command(
            "cat /etc/systemd/system/vinputdev-creator.service"
        )
        if self.vinputdev_creator_original_content != CHANGES_VINPUTDEV_CREATOR_SERVICE:
            self.test.mtee_target.execute_command(
                f"echo '{CHANGES_VINPUTDEV_CREATOR_SERVICE}' > /etc/systemd/system/vinputdev-creator.service",
                expected_return_code=0,
            )
            self.restore_vinputdev_creator_content = True

        cmd_to_enable_service = "systemctl enable vinputdev-creator.service"
        _, _, returncode = self.test.mtee_target.execute_command(cmd_to_enable_service)
        assert_equal(returncode, 0, f"Error while enabling service: {cmd_to_enable_service}")

        # Ensure /etc/udev/rules.d/99-touchcid.rules has the correct content
        self.udev_rule_original_content, _, _ = self.test.mtee_target.execute_command(
            "cat /etc/udev/rules.d/99-touchcid.rules"
        )
        match = re.compile(UDEV_RULE_ATTRS_PATTERN).search(self.udev_rule_original_content)
        if match:
            if match.group(1) != "CVM2RB_UINPUT_EVDEV":
                old_pattern = re.escape(match.group(1))
                self.test.mtee_target.execute_command(
                    f"sed -i 's/{old_pattern}/CVM2RB_UINPUT_EVDEV/' {self.touchcid_file_path}",
                    expected_return_code=0,
                )
                self.restore_udev_rule_content = True

        self.sync_reboot_remount_target()

        # Check if vhost-user-slave-crosvm-input.service is enabled
        service_status_cmd = "systemctl status vhost-user-slave-crosvm-input.service"
        service_status_output, _, _ = self.test.mtee_target.execute_command(service_status_cmd)
        assert_regexp_matches(
            service_status_output,
            REGEX_CHECK_IF_SERVICE_IS_ACTIVE,
            "'vhost-user-slave-crosvm-input.service' not active after rebooting target.",
        )

        _, cat_cmd_missing_results = run_cmd_and_check_result(
            "cat /proc/nk/vevdev-be", CAT_EXPECTED_OUTCOMES["vevdev"]
        )
        _, dmesg_cmd_missing_results = run_cmd_and_check_result(
            'dmesg | grep -nri "vrpc"', DMESG_EXPECTED_OUTCOMES["vrpc"]
        )
        _, ls_cmd_missing_results = run_cmd_and_check_result("ls /dev/input/event*", LS_VEVDEV_EXPECTED_OUTCOME)

        error_message = "Fail on checking if VEVDEV device is operational."
        if cat_cmd_missing_results:
            error_message += f"\nEntries missing from cat operation: {cat_cmd_missing_results}"
        if dmesg_cmd_missing_results:
            error_message += f"\nEntries missing from dmesg operation: {dmesg_cmd_missing_results}"
        if ls_cmd_missing_results:
            error_message += f"\nEntries missing from ls operation: {ls_cmd_missing_results}"

        assert_false(cat_cmd_missing_results or dmesg_cmd_missing_results or ls_cmd_missing_results, error_message)

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
        duplicates="IDCEVODEV-8740",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "HARDWARE_ACCESS_PASSTHROUGH_SUPPORT"),
            },
        },
    )
    def test_010_verify_gpu_sharing_between_multiple_vm(self):
        """
        [SIT_Automated] GPU Sharing between multiple VMs
        Steps:
            1. Collect the dumpsys for SurfaceFlinger service using command,
                "adb shell dumpsys SurfaceFlinger"
            2. Validate the logs.

        Expected result -
            - Logs for EGL implementation version and git hash for OpenGL ES ANGLE are present.
        """
        result = self.test.apinext_target.execute_command("dumpsys SurfaceFlinger")
        assert_true(
            any(expected_out in result for expected_out in GPU_SHARING_EXPECTED),
            f"Failed to validate GPU sharing between multiple VM's.Expected any of below strings:"
            f"\n{GPU_SHARING_EXPECTED}\n Received output - {result}",
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
        duplicates="IDCEVODEV-13349",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "VM_MANAGEMENT_LIFECYCLE_CONTROL"),
            },
        },
    )
    def test_011_standalone_start_ivi(self):
        """
        [SIT_Automated] [RSE]Verify the standalone start of IVI (Android)

        Steps:
            1. Run " echo 3 > /proc/nk/vmstop " on NODE0 side
            2. Run " echo 3 > /proc/nk/vmstart " on NODE0 side
            3. Switch to IVI console by giving ( esc -> capslock -> o alpha -> 6 -> r )
            4. Switch back to NODE0 ( esc -> capslock -> o alpha -> 6 -> q )

        Expected result:
            - Node0 console and IVI console should be accessible as expected
        """
        self.linux_helpers.verify_standalone_stop_ivi()
        self.linux_helpers.verify_standalone_start_ivi()
        self.test.mtee_target.switch_serial_console_to_android()
        assert_true(self.linux_helpers.verify_switch_to_android(), "Unable to switch the serial to IVI console")
        self.test.mtee_target.switch_serial_console_to_node0()
        assert_true(self.linux_helpers.verify_switch_to_node0(), "Unable to switch the serial to Node0 console")
