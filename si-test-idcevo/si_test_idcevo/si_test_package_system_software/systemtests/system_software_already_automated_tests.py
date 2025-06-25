# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Already Automated System Software Tests

These tests were previously automated and created in the domain's repositories.
This file brings them into our codebase,
where they have been adapted to align with our testing standards and updated as needed
"""
import configparser
import logging
import os
import re
import time
from pathlib import Path
from unittest import skip, skipIf

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import (
    assert_equal,
    assert_false,
    assert_is_not_none,
    assert_process_returncode,
    assert_regexp_matches,
    assert_true,
    metadata,
    run_command,
)
from nose.plugins.skip import SkipTest
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.dlt_logs_handlers import validate_expected_dlt_payloads_in_dlt_trace
from si_test_idcevo.si_test_helpers.file_path_helpers import (
    verify_file_in_host_with_timeout,
    verify_file_in_target_with_timeout,
)
from si_test_idcevo.si_test_helpers.linux_commands_handlers import LinuxCommandsHandler
from si_test_idcevo.si_test_helpers.reboot_handlers import (
    reboot_and_wait_for_android_target,
    wait_for_application_target,
)
from si_test_idcevo.si_test_helpers.test_helpers import (
    check_ipk_installed,
    skip_unsupported_ecus,
    validate_output_list,
)
from validation_utils.utils import CommandError, TimeoutError

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
required_target_packages = ["devmem2", "virtio-utils"]

VMCORE_FOLDER_PATH = "/var/data/node0/health/coredumper/dumps"
VMCORE_FILE_NAME_REGEX = re.compile(r"vmcore.*gz.*")
VMCORE_FOLDER_NAME_REGEX = re.compile(r"vmcore.*")

CRASH_TRIGGER_COMMAND = "echo c > /proc/sysrq-trigger"
NK_PANIC_CRASH_COMMAND = "echo 1 > /sys/nk/prop/nk.panic-trigger"
SMALL_RAMDUMP_COMMAND = "echo -e -n '\\x01\\x00\\x00\\x10\\x00\\x02' > /dev/ipc12"


class TestsSystemSW(object):
    test = TestBase.get_instance()
    test.setup_base_class()
    linux_helpers = LinuxCommandsHandler(test.mtee_target, logger)

    def trigger_and_handle_kernel_crash(self):
        """
        This function triggers sysrq-trigger kernel crash on the target and handle timeout execption.
        """
        try:
            self.test.mtee_target.execute_command(CRASH_TRIGGER_COMMAND, expected_return_code=0)
        except (CommandError, TimeoutError) as capture_exception:
            logger.debug(f"Timeout error occurred while capturing logs: {capture_exception}")
        finally:
            self.test.mtee_target.reboot(prefer_softreboot=False)
            self.test.mtee_target._recover_ssh(record_failure=False)

    def trigger_kernel_panic_and_wait_for_recovery_boot_up(self, crash_cmd, console_type="node0"):
        """
        This function will trigger a kernel crash and wait for target "ECU Login" message on Console.
        Later it will wait for the target to be up and in application mode after reset
        param crash_cmd: command to be trigger for crash
        param console_type: console on which commands to be trigger
                            for e.g. console_type == "android" for android console.
                            by default it will be in "node0" for node0 console
        :Raises: AssertionError and reboots the target if the target didn't wake up after crash
        """
        try:
            if console_type == "android":
                self.test.mtee_target.switch_serial_console_to_android()
                assert_true(self.linux_helpers.verify_switch_to_android(), "Unable to switch to Android Console")
                self.test.mtee_target.execute_console_command("su", block=False)
                time.sleep(2)
                self.test.mtee_target.execute_console_command(crash_cmd, block=False)
            elif console_type == "node0":
                self.test.mtee_target._console.write(crash_cmd)
            else:
                raise AssertionError(
                    "Aborting the Test since console_type to enter kernel crash is not provided properly",
                    f'Expected: "android" or "node0", Actual: {console_type}',
                )
            self.test.mtee_target._console.wait_for_re(
                rf".*{self.test.mtee_target.options.target} login.*",
                timeout=120,
            )
            wait_for_application_target(self.test.mtee_target)
        except Exception as e:
            logger.debug("Rebooting the Target, since target didn't wakeup post crash")
            reboot_and_wait_for_android_target(self.test, prefer_softreboot=False)
            raise AssertionError(
                f"Aborting the Test since target didn't wakeup post crash. Error Occured: {e}",
                "Rebooting the target and waiting for application mode",
            )

    def find_coredump_folder(self, new_dump_folder):
        """
        This Function will check the presence of new coredump folder generated.
        :param list new_dump_folder: List of Coredump Folders
        Returns new generated folder name if folder match, else Returns None
        """
        for folder in new_dump_folder:
            folder_match = re.search(VMCORE_FOLDER_NAME_REGEX, str(folder))
            if folder_match:
                logger.debug(f"New Folder: {folder} matches expected pattern: {VMCORE_FOLDER_NAME_REGEX}")
                return folder_match.group(0)
        return None

    def find_coredump_file(self, new_dump_file):
        """
        This Function will check the presence of new coredump file generated.
        :param list new_dump_file: List of Coredump Files
        Returns new generated file name if file match, else returns None
        """
        for file in new_dump_file:
            file_match = re.search(VMCORE_FILE_NAME_REGEX, str(file))
            if file_match:
                logger.debug(f"New File: {file} matches expected pattern: {VMCORE_FILE_NAME_REGEX}")
                return file_match.group(0)
        return None

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
        duplicates="IDCEVODEV-10103",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DEVELOPER_SUPPORT_BOOT_FROM_USB"),
                    config.get("FEATURES", "DEVELOPER_SUPPORT_FASTBOOT_MODE"),
                    config.get("FEATURES", "DEVELOPER_SUPPORT_RECOVERY_MODE"),
                    config.get("FEATURES", "FIRMWARE_STARTUP_START_DSP"),
                ],
            },
        },
    )
    @skip("Test is inactive: IDCEVODEV-420534")
    def test_001_check_devmem_counter(self):
        """
        [SIT_Automated] Verify SFI is running with increasing counter values
        Steps:
            - Execute "devmem 0xF66FFFF8" in node0 console.
            - Check if counter increments.
        """
        devmem_cmd = "devmem 0xF66FFFF8"

        result_1, _, _ = self.test.mtee_target.execute_command(devmem_cmd)
        result_2, _, _ = self.test.mtee_target.execute_command(devmem_cmd)
        result_3, _, _ = self.test.mtee_target.execute_command(devmem_cmd)

        assert_true(
            result_3 > result_2 > result_1,
            "devmem counter did not increase as expected."
            f" result 1 : {result_1}, result 2 : {result_2}, result 3 : {result_3}",
        )

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
        duplicates="IDCEVODEV-9916",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "INTER_VM_COMMUNICATION_SHARED_MEMORY"),
                    config.get("FEATURES", "INTER_VM_VSOCK_SUPPORT"),
                    config.get("FEATURES", "HYPERVISOR_CONFIG_AND_VARIANTS"),
                    config.get("FEATURES", "NODE0_VM_CONFIG"),
                    config.get("FEATURES", "ANDROID_VM_CONFIG"),
                ],
            },
        },
    )
    @skip("Test is inactive: IDCEVODEV-420534")
    def test_002_verify_inter_vm_communication_via_vnet(self):
        """
        [SIT_Automated] To verify Inter VM communication via Vnet
        Steps:
            1. Get IP address of VNET23_0 on Node0 console using command,
                - ip addr show vnet23_0
            2. Switch to android console, and get the IP address of VNET32_0 on android console,
                - ip addr show vnet32_0
            3. Set the routing table "main" as active using command,
                - ip rule add pref 0 table main
            4. Validate if the routing table "main" is active using command,
                - ip rule | grep main
            5. Ping VNET23_0 from android console.
            6. Ping VNET32_0 from Node0 console.
        Expected output -
            - Both ping commands should be succcessful to validate inter VM communication via Vnet
        """
        get_ip_rule_main_cmd = "ip rule | grep main"
        set_routing_table_main_cmd = "ip rule add pref 0 table main"

        vnet_23_ip_cmd = "ip addr show vnet23_0"
        vnet_32_ip_cmd = "ip addr show vnet32_0"
        vnet_ip_regex = re.compile(r"inet (\d+.\d+.\d+.\d+)")

        ping_cmd_expected = "0% packet loss"

        linux_ip_result = self.test.mtee_target.execute_command(vnet_23_ip_cmd)
        vnet23_linux_ip = vnet_ip_regex.search(linux_ip_result.stdout)
        assert_is_not_none(
            vnet23_linux_ip.group(1),
            f"Unable to fetch IP for VNET23_0, output received : {linux_ip_result.stdout}",
        )

        android_ip_result = self.test.apinext_target.execute_command(vnet_32_ip_cmd, privileged=True)
        vnet32_android_ip = vnet_ip_regex.search(str(android_ip_result))
        assert_is_not_none(
            vnet32_android_ip.group(1),
            f"Unable to fetch IP for VNET32_0, output received : {str(android_ip_result)}",
        )

        self.test.apinext_target.execute_command(set_routing_table_main_cmd, privileged=True)
        get_ip_rule_result = self.test.apinext_target.execute_command(get_ip_rule_main_cmd, privileged=True)
        assert_true(
            "main" in get_ip_rule_result,
            f"Failed to validate if rule 'main' is active on routing table. Output received : {get_ip_rule_result}",
        )
        android_ping_result = self.test.apinext_target.execute_command(
            f"ping -c 4 {vnet23_linux_ip.group(1)}",
            privileged=True,
        )
        assert_true(
            ping_cmd_expected in android_ping_result,
            f"Ping to vnet23_0 ip - {vnet23_linux_ip.group(1)} was not successful."
            f"Output received : {android_ping_result}",
        )

        linux_ping_result = self.test.mtee_target.execute_command(f"ping -c 4 {vnet32_android_ip.group(1)}")
        assert_true(
            ping_cmd_expected in linux_ping_result.stdout,
            f"Ping to vnet32_0 ip - {vnet32_android_ip.group(1)} was not successful."
            f"Output received : {linux_ping_result.stdout}",
        )

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
        duplicates="IDCEVODEV-376416",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "FIRMWARE_STARTUP_START_DSP"),
                ],
            },
        },
    )
    @skip("Test is inactive: IDCEVODEV-450969")
    def test_003_verify_dsp_access(self):
        """
        [SIT_Automated] To verify DSP access
        Steps:
            1 - Execute devmem command to read the DSP
            2 - Check if the output contains any error
        """
        result = self.test.mtee_target.execute_command("devmem 0x10000000")
        logger.info(f"Output of devmem command: {result.stdout}")
        assert_process_returncode(
            0,
            result.returncode,
            msg=f"Error occurred while checking DSP access. Output: {result.stdout}. Error: {result.stderr}",
        )

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
        duplicates="IDCEVODEV-21566",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "HARDWARE_ACCESS_VIRTIO"),
            },
        },
    )
    def test_004_verify_virtio_fs_frontend_is_available(self):
        """
        [SIT_Automated] Verify virtio-fs frontend is available
        pre_condition:
            1. Check the status of vhost-user-slave-crosvm-filesystem. Service to see if it is running
                and has the shared-dir
        steps:
            1. Run the below command on Android console
                "ls -l /sys/bus/virtio/devices/virtio*/driver | grep virtiofs"
            2. Validate "virtiofs" string is present in output from step 1
        """
        service = "vhost-user-slave-crosvm-filesystem.service"
        cmd = f"systemctl status {service}"
        service_status, _, _ = self.test.mtee_target.execute_command(cmd)
        assert_true("active (running)" in service_status, f"Service {service} is not running")
        assert_true(
            "--shared-dir /var/ncd" in service_status,
            "Share dir not found on service configuration",
        )
        virtiofs_command = "ls -l /sys/bus/virtio/devices/virtio*/driver | grep virtiofs"
        virtiofs_command_output = self.test.apinext_target.execute_command([virtiofs_command], privileged=True)
        assert_true(
            "virtiofs" in virtiofs_command_output.stdout.decode("utf-8"),
            f"String - 'virtiofs' is not present in output - {virtiofs_command_output.stdout}",
        )

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
        duplicates="IDCEVODEV-13344",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "VM_MANAGEMENT_LIFECYCLE_CONTROL"),
                ],
            },
        },
    )
    def test_005_verify_monitoring_status_of_node0(self):
        """
        [SIT_Automated] Verify the monitoring status of Node0 ( alive status )
        Steps:
            Run the following command to get the status of Node0 VM,
                "cat /proc/nk/props | grep vms.online"

        Expected Result -
            - "nk.vms.online" should be present in the output of the command
            - After converting the hexadecimal value in the output to binary,
            the 3rd bit that is bit[2] from LSB should be 1, VM id for Node0 is 2
        """
        result_stdout, _, _ = self.test.mtee_target.execute_command("cat /proc/nk/props | grep vms.online")
        assert_true(
            "nk.vms.online" in result_stdout,
            f"Failed to validate monitoring alive status of Node0, Expected string - 'nk.vms.online'"
            f"was not not found in output - {result_stdout}",
        )
        vm_status_binary_value = bin(int(result_stdout.split()[-1], 16))[2:]
        logger.debug(f"Converted binary value to check Node0 alive status - {vm_status_binary_value}")
        assert_true(
            vm_status_binary_value[-3] == "1",
            f"Failed to validate monitoring alive status of Node0, Expected Vm status value - 1,"
            f"got status {vm_status_binary_value} in output - {result_stdout}",
        )

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
        duplicates="IDCEVODEV-10102",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "KERNEL_DTB"),
            },
        },
    )
    def test_006_handover_boot_config_protocol(self):
        """
        [SIT_Automated] Handover Boot Config Protocol - SYS
        Steps:
            - Check if the target hardware version contains bootinfo file in path /proc/device-tree/chosen
        Expected Output:
            - Assert if bootinfo file exist in path /proc/device-tree/chosen
        """
        bootinfo_file_path = "/proc/device-tree/chosen/bootinfo"
        assert_true(
            self.test.mtee_target.isfile(bootinfo_file_path),
            f"bootinfo file does not exist on path: {bootinfo_file_path}",
        )

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
        duplicates="IDCEVODEV-13347",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "VM_MANAGEMENT_LIFECYCLE_CONTROL"),
            },
        },
    )
    def test_007_monitoring_status_of_ivi(self):
        """
        [SIT_Automated] Verify the monitoring status of IVI (Android alive status)
        Steps:
            1.  Run " cat /proc/nk/props | grep vms.online " on NODE0 side
            2. Switch to IVI console
        Expected result:
            - When the output value is converted to binary, *4th* bit from *LSB* should be *1*
            - Should be able to switch to IVI console
        """
        ivi_monitoring_status, _, _ = self.test.mtee_target.execute_command("cat /proc/nk/props | grep vms.online")
        assert_true(
            "nk.vms.online" in ivi_monitoring_status,
            f"Failed to validate monitoring alive status of IVI, Expected string - 'nk.vms.online'"
            f" was not not found in output - {ivi_monitoring_status}",
        )
        bin_ivi_monitoring_status = bin(int(ivi_monitoring_status.split()[-1], 16))
        logger.debug(f"Binary Value to check Android IVI alive status: {bin_ivi_monitoring_status}")
        assert_true(
            bin_ivi_monitoring_status[-4] == "1",
            f"Failed to validate monitoring alive status of IVI, Expected Vm status value - 1,"
            f" got status {bin_ivi_monitoring_status[-4]} in output - {ivi_monitoring_status}",
        )
        self.test.mtee_target.switch_serial_console_to_android()
        assert_true(self.linux_helpers.verify_switch_to_android(), "Unable to switch the serial to IVI console")
        # Switching back to Node0
        self.test.mtee_target.switch_serial_console_to_node0()

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
        duplicates="IDCEVODEV-10427",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "FIRMWARE_STARTUP_START_DSP"),
                ],
            },
        },
    )
    def test_008_dsp_loading_successful(self):
        """
        [SIT_Automated] DSP loading successful (A/B support)
        Steps:
            1. Perform Hard Reboot on target
            2. Start SOC DLT traces and ensure that expected payloads mentioned in
                "soc_pattern_payloads" list is found.
        """
        dsp_load_soc_patterns = [
            {"payload_decoded": re.compile(r".*start DSP.*")},
            {"payload_decoded": re.compile(r".*starting ABOX.*")},
        ]
        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as dlt_traces:
            self.test.mtee_target.reboot(prefer_softreboot=False)
            dlt_msgs = dlt_traces.wait_for_multi_filters(
                filters=dsp_load_soc_patterns,
                count=0,
                drop=True,
                timeout=60,
            )
        assert_true(
            wait_for_application_target(self.test.mtee_target, timeout=180),
            "Target is not up after reboot. Waited for 180 seconds.",
        )
        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, dsp_load_soc_patterns, "SOC logs")

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
        duplicates="IDCEVODEV-16307",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "AB_SWITCHING_ANDROID_UFS_BASED_SWITCH"),
                    config.get("FEATURES", "AB_SWITCHING_NODE0_GPIO_BASED_SWITCH"),
                ],
            },
        },
    )
    def test_009_switching_a_b_partition_mount_correct_rootfs(self):
        """
        [SIT_Automated] A/B switching - mount correct rootfs
        Steps:
            1. Execute below command on Node0 Console to get the mounted points
                mount
        Expected Results:
            1. Validate below message in output
                if DM Verity is Enabled
                /dev/dm-0 on / type ext4 (ro,relatime,seclabel)

                if DM Verity is Disabled
                For A-Boot - /dev/sdd21 on / type ext4 (ro,relatime,seclabel)
                For B-Boot - /dev/sde21 on / type ext4 (ro,relatime,seclabel)
        """
        # Verifying if dm-verity is enabled
        dm_verity_output, _, _ = self.test.mtee_target.execute_command("cat /proc/cmdline")
        if "/dev/dm-0" in dm_verity_output:
            expected_output = r"/dev/dm-0"
        else:
            expected_output = r"/dev/(sde21|sdd21)"

        mount_output, _, _ = self.test.mtee_target.execute_command("mount")

        assert_regexp_matches(
            mount_output, expected_output, f"Expected Message {expected_output} not found after Mount command"
        )

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
        duplicates="IDCEVODEV-13484",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "INTER_VM_VSOCK_SUPPORT"),
                    config.get("FEATURES", "HARDWARE_ACCESS_VIRTIO"),
                ],
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["rse26", "cde"]), "This test isn't supported by this ECU!")
    def test_010_verify_virtio_vsock_server_on_node0(self):
        """
        [SIT_Automated] Verify virtio-vsock communication by running vsock server in Node0 and vsock client in IVI
        Pre-Condition -
            - Install "virtio-utils" ipk.
        Steps -
            1. Upload vsock_server binary to the target in /usr/bin folder.
            2. Upload vsock_client binary to the android target in /data folder.
            3. Run the vsock_server on the Node0 side using command - "/usr/bin/vsock_server 8080"
            4. Run the vsock_client on the IVI side using command - "/data/vsock_client 8080"

        Expected Output -
            - Both vsock_server and vsock_client binaries should run successfully and communication logs between them
              should be visible.
        """
        vsock_client_linux_exp_result = [
            "Socket creation successfull",
            "Connected to server",
            "Received message from server: Hello, client",
        ]
        vsock_test_tools_file = Path(os.sep) / "resources" / "vsock-test-tools.tar.gz"
        vsock_server_linux_binary = "/tmp/vsock-test-tools/vsock-test-tools/Linux/vsock_server"
        vsock_client_android_binary = "/tmp/vsock-test-tools/vsock-test-tools/Android/vsock_client"
        vsock_server_node0_path = "/usr/bin/vsock_server"
        vsock_client_ivi_path = "/data/vsock_client"

        if not check_ipk_installed(["virtio-utils"]):
            raise SkipTest(
                "Skipping this test because the required IPK, virtio-utils, was not installed successfully!"
            )
        self.test.mtee_target.remount()
        self.linux_helpers.extract_tar(vsock_test_tools_file)
        result = run_command(["ls", "-R", "/tmp"])
        logger.debug(f"Content of /tmp: \n{result.stdout}")
        self.test.mtee_target.upload(vsock_server_linux_binary, "/usr/bin/")
        self.test.apinext_target.execute_adb_command("root")
        self.test.apinext_target.execute_adb_command(["push", vsock_client_android_binary, "/data"])
        self.test.mtee_target.execute_command(f"chmod 0777 {vsock_server_node0_path}", expected_return_code=0)
        self.test.apinext_target.execute_command(f"chmod 0777 {vsock_client_ivi_path}")
        vsock_server_node0_cmd = vsock_server_node0_path + " 8080"
        with self.test.mtee_target.execute_background_task(vsock_server_node0_cmd, shell=True) as background_task:
            time.sleep(1)
            vsock_server_op = background_task.recv_stdout()
            logger.debug(f"Output after running vsock_server on Node0 side : {vsock_server_op}")
            vsock_client_op = self.test.apinext_target.execute_command(vsock_client_ivi_path + " 8080")
            logger.debug(f"Output after running vsock_client on IVI side : {vsock_client_op}")

        match, failed_output_list = validate_output_list(vsock_client_op, vsock_client_linux_exp_result)
        assert_true(
            match,
            f"Failed to validate communication between server on Node0 side and client on IVI side."
            f"Expected Logs - {vsock_client_linux_exp_result}, Obtained logs - {failed_output_list}",
        )

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
        duplicates="IDCEVODEV-10388",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "HYPERVISOR_LOGGING_LOG_BUFFER"),
            },
        },
    )
    def test_011_verify_hypervisor_logging(self):
        """
         [SIT_Automated] Verify hypervisor-logging - log-buffer
        Steps:
        - Run " echo 1 > /sys/nk/prop/nk.panic-trigger " on android console.
        - check for cpu_bootime_soc_pattern in DLT and hypervisor_regex logs is found in soc console.
        Expected Results:
        - Verify cpu_bootime_soc_pattern in DLT and hypervisor_regex logs are found.
        """

        cpu_boottime_soc_patterns = [
            {"apid": "LOGM", "ctid": "HYPR", "payload_decoded": re.compile(r"CPU0 boot time")},
        ]

        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as dlt_traces:
            try:
                self.test.mtee_target.switch_serial_console_to_android()
                assert_true(self.linux_helpers.verify_switch_to_android(), "Unable to switch to Android Console")
                self.test.mtee_target.execute_console_command("su", block=False)
                time.sleep(2)
                self.test.mtee_target.execute_console_command(NK_PANIC_CRASH_COMMAND, block=False)
                self.test.mtee_target._console.wait_for_re(r".*System-wide panic initiated from VM3.*")
                wait_for_application_target(self.test.mtee_target)
            except Exception as e:
                logger.debug("Rebooting the Target, since target didn't wakeup post crash")
                reboot_and_wait_for_android_target(self.test, prefer_softreboot=False)
                raise AssertionError(
                    f"Aborting the Test since target didn't wakeup post crash. Error Occured: {e}",
                    "Rebooting the target and waiting for application mode",
                )

            dlt_msgs = dlt_traces.wait_for_multi_filters(
                filters=cpu_boottime_soc_patterns,
                count=1,
                drop=True,
                timeout=180,
            )

        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, cpu_boottime_soc_patterns, "SOC logs")

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
        duplicates="IDCEVODEV-18517",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "VM_MANAGEMENT_PANIC_HANDLER"),
            },
        },
    )
    @skip("Test is inactive: IDCEVODEV-420534")
    def test_012_verify_sysrq_trigger(self):
        """
        [SIT_Automated] Verify the panic handling in Node0 with sysrq-trigger
        Steps:
            1. Create Kernel panic using below command
               ~ # echo c > /proc/sysrq-trigger
            2. Verify coredump is generated on target
            3. Verify coredump is generated on Host
            4. Validate pattern sysrq_trigger_pattern under serial_console_ttySOCHU.log

            Expected Results -
            1. Verify small ramp dump generated and target booted to console
        """

        sysrq_trigger_pattern = [
            re.compile(r".*login.*root.*"),
            re.compile(r".*Kernel.*panic.*not.*syncing.*sysrq.*triggered.*crash.*"),
        ]
        self.trigger_and_handle_kernel_crash()

        target_folder_path, target_filename = verify_file_in_target_with_timeout(
            self.test.mtee_target, VMCORE_FOLDER_PATH, VMCORE_FOLDER_NAME_REGEX, VMCORE_FILE_NAME_REGEX
        )
        assert_is_not_none(
            target_filename, "Core dumps logs didn't get generated as expected on killing service process"
        )

        host_filepath = os.path.join(
            self.test.mtee_target.options.result_dir, "extracted_files", "Coredumps", target_filename
        )
        assert_true(
            verify_file_in_host_with_timeout(host_filepath),
            f"File {target_filename} not found at file path {host_filepath} on Host PC.",
        )

        log_file = Path(self.test.mtee_target.options.result_dir) / "serial_console_ttySOCHU.log"
        sysrq_pattern_count = len(sysrq_trigger_pattern)
        expected_regex_pattern_counter = 0

        with open(log_file) as file_handler:
            for file_line in file_handler.readlines():
                for pattern in sysrq_trigger_pattern:
                    if pattern.search(file_line):
                        expected_regex_pattern_counter += 1
                        if expected_regex_pattern_counter == sysrq_pattern_count:
                            break
                if expected_regex_pattern_counter == sysrq_pattern_count:
                    break

        assert_equal(
            len(sysrq_trigger_pattern),
            expected_regex_pattern_counter,
            f"Failed to validate list of expected sysrq-trigger logs - {sysrq_trigger_pattern}",
        )

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
        duplicates="IDCEVODEV-10396",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "VM_MANAGEMENT_PANIC_HANDLER"),
                    config.get("FEATURES", "KERNEL_CRASH_SMALL_RAM_DUMP_WITH_ENCYRPTION"),
                    config.get("FEATURES", "KERNEL_CRASH_SMALL_RAM_DUMP_WITHOUT_ENCYRPTION"),
                ]
            },
        },
    )
    def test_013_verify_able_to_create_kernel_panic_on_android_side(self):
        """
        [SIT_Automated] Verify able to create kernel panic on Android side
        Steps:
            1. Store existing coredump folder names in a list
            2. Execute below cmd on android console to trigger a crash and make sure system is up post crash
               ~ # echo c > /proc/sysrq-trigger
            3. Once target is up and in application mode after crash, repeat Step 1 again
            4. Compare lists data from Step1 and Step3 and ensure new coredump folder is generated
            5. Ensure that the new coredump file is present in the folder found in Step4
        Expected Outcome:
            1. Target can handle kernel panic and boots properly
            2. New coredump folder and respective file is generated
        """
        existing_coredump_folder_lst = self.test.mtee_target.listdir(VMCORE_FOLDER_PATH)

        self.trigger_kernel_panic_and_wait_for_recovery_boot_up(CRASH_TRIGGER_COMMAND, console_type="android")

        generated_coredump_folder_lst = self.test.mtee_target.listdir(VMCORE_FOLDER_PATH)

        # Ensuring that the new coredump folder is present at VMCORE_FOLDER_PATH
        new_dump_folder = set(existing_coredump_folder_lst).symmetric_difference(set(generated_coredump_folder_lst))
        logger.debug(f"New Coredump Files are: {new_dump_folder}")
        assert_true(
            new_dump_folder,
            f"New Coredumps Folder is not generated at Path {VMCORE_FOLDER_PATH} after generating kernel crash",
        )
        new_folder = self.find_coredump_folder(new_dump_folder)
        assert_is_not_none(
            new_folder,
            f"Expected dump folder: {VMCORE_FOLDER_NAME_REGEX} not found, found: {generated_coredump_folder_lst}",
        )

        # Ensuring that the new coredump file is present at new_coredump_folder_path
        new_coredump_folder_path = os.path.abspath(os.path.join(VMCORE_FOLDER_PATH, new_folder))
        new_dump_file = self.test.mtee_target.listdir(new_coredump_folder_path)
        assert_true(
            new_dump_file,
            f"New Coredumps File is not generated at Path {new_coredump_folder_path}",
        )
        new_file = self.find_coredump_file(new_dump_file)
        assert_is_not_none(
            new_file,
            f"Expected dump file: {VMCORE_FILE_NAME_REGEX} not found, found: {new_dump_file}",
        )

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
        duplicates="IDCEVODEV-18530",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "VM_MANAGEMENT_PANIC_HANDLER"),
            },
        },
    )
    def test_014_verify_the_panic_handling_in_ivi_with_nk_panic_trigger_property(self):
        """
        [SIT_Automated] Verify the panic handling in IVI with nk.panic-trigger property
        Steps:
            1. Store existing coredump folder names in a list
            2. Create a small ramdump
            3. Execute below cmd on android console to trigger a crash and make sure system is up post crash
               ~ echo 1 > /sys/nk/prop/nk.panic-trigger
            4. Once target is up and in application mode after crash, repeat Step 1 again
            5. Compare lists data from Step1 and Step4 and ensure new coredump folder is generated
            6. Ensure that the new coredump file is present in the folder found in Step5
        Expected Outcome:
            1. Target can handle kernel panic and boots properly
            2. New coredump folder and respective file is generated
        """
        existing_coredump_folder_lst = self.test.mtee_target.listdir(VMCORE_FOLDER_PATH)

        # Creating a small ramdump
        result = self.test.mtee_target.execute_command(SMALL_RAMDUMP_COMMAND)
        assert_process_returncode(
            0,
            result.returncode,
            msg=f"Error occurred while creating small ramdump. Output: {result.stdout}. Error: {result.stderr}",
        )

        self.trigger_kernel_panic_and_wait_for_recovery_boot_up(NK_PANIC_CRASH_COMMAND, console_type="android")

        generated_coredump_folder_lst = self.test.mtee_target.listdir(VMCORE_FOLDER_PATH)

        new_dump_folder = set(existing_coredump_folder_lst).symmetric_difference(set(generated_coredump_folder_lst))
        logger.debug(f"New Coredump Files are: {new_dump_folder}")
        assert_true(
            new_dump_folder,
            f"New Coredumps Folder is not generated at Path {VMCORE_FOLDER_PATH} after generating kernel crash",
        )
        # Ensuring that the new coredump folder is present at VMCORE_FOLDER_PATH
        new_folder = self.find_coredump_folder(new_dump_folder)
        assert_is_not_none(
            new_folder,
            f"Expected dump folder: {VMCORE_FOLDER_NAME_REGEX} not found, found: {generated_coredump_folder_lst}",
        )

        # Ensuring that the new coredump file is present at new_coredump_folder_path
        new_coredump_folder_path = os.path.abspath(os.path.join(VMCORE_FOLDER_PATH, new_folder))
        new_dump_file = self.test.mtee_target.listdir(new_coredump_folder_path)
        assert_true(
            new_dump_file,
            f"New Coredumps File is not generated at Path {new_coredump_folder_path}",
        )
        new_file = self.find_coredump_file(new_dump_file)
        assert_is_not_none(
            new_file,
            f"Expected dump file: {VMCORE_FILE_NAME_REGEX} not found, found: {new_dump_file}",
        )

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
        duplicates="IDCEVODEV-18522",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "VM_MANAGEMENT_PANIC_HANDLER"),
            },
        },
    )
    def test_015_verify_the_panic_handling_in_node0_with_nk_panic_trigger_property(self):
        """
        [SIT_Automated] Verify the panic handling in Node0 with nk.panic-trigger property
        Steps:
            1. Store existing coredump folder names in a list
            2. Create a small ramdump
            3. Execute below cmd on node0 console to trigger a crash and make sure system is up post crash
               ~ echo 1 > /sys/nk/prop/nk.panic-trigger
            4. Once target is up and in application mode after crash, repeat Step 1 again
            5. Compare lists data from Step1 and Step4 and ensure new coredump folder is generated
            6. Ensure that the new coredump file is present in the folder found in Step5
        Expected Outcome:
            1. Target can handle kernel panic and boots properly
            2. New coredump folder and respective file is generated
        """
        existing_coredump_folder_lst = self.test.mtee_target.listdir(VMCORE_FOLDER_PATH)

        # Creating a small ramdump
        result = self.test.mtee_target.execute_command(SMALL_RAMDUMP_COMMAND)
        assert_process_returncode(
            0,
            result.returncode,
            msg=f"Error occurred while creating small ramdump. Output: {result.stdout}. Error: {result.stderr}",
        )

        self.trigger_kernel_panic_and_wait_for_recovery_boot_up(NK_PANIC_CRASH_COMMAND)

        generated_coredump_folder_lst = self.test.mtee_target.listdir(VMCORE_FOLDER_PATH)

        new_dump_folder = set(existing_coredump_folder_lst).symmetric_difference(set(generated_coredump_folder_lst))
        logger.debug(f"New Coredump Files are: {new_dump_folder}")
        assert_true(
            new_dump_folder,
            f"New Coredumps Folder is not generated at Path {VMCORE_FOLDER_PATH} after generating kernel crash",
        )
        # Ensuring that the new coredump folder is present at VMCORE_FOLDER_PATH
        new_folder = self.find_coredump_folder(new_dump_folder)
        assert_is_not_none(
            new_folder,
            f"Expected dump folder: {VMCORE_FOLDER_NAME_REGEX} not found, found: {generated_coredump_folder_lst}",
        )

        # Ensuring that the new coredump file is present at new_coredump_folder_path
        new_coredump_folder_path = os.path.abspath(os.path.join(VMCORE_FOLDER_PATH, new_folder))
        new_dump_file = self.test.mtee_target.listdir(new_coredump_folder_path)
        assert_true(
            new_dump_file,
            f"New Coredumps File is not generated at Path {new_coredump_folder_path}",
        )
        new_file = self.find_coredump_file(new_dump_file)
        assert_is_not_none(
            new_file,
            f"Expected dump file: {VMCORE_FILE_NAME_REGEX} not found, found: {new_dump_file}",
        )

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
        duplicates="IDCEVODEV-13385",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "VM_MANAGEMENT_LIFECYCLE_CONTROL"),
            },
        },
    )
    def test_016_verify_the_shutdown_of_whole_system(self):
        """
        [SIT_Automated] Verify the shutdown of whole system
        Steps:
            1. Run below command on Serial Console:
                nsg_control --r 0
            2. Trigger Ethernet Wakeup (ETH_WUP)
        Expected Results:
            For Step 1:
               Verify whole system is shutdown and log mentioned in expected_logs_regex_list list
               is found in Serial Console Logs
            For Step 2:
               Ensure root login on Serial Console post WUP Trigger and verify able to switch to Android Console
               as well as NODE0 Console
        """
        expected_logs_regex_list = [r".*reboot.*Power down.*"]
        expected_logs_not_found_list = []

        # Executing NSG_CONTROL command and Verifying System Shutdown in console
        self.test.mtee_target.execute_console_command("nsg_control --r 0")
        for logs in expected_logs_regex_list:
            try:
                self.test.mtee_target._console.wait_for_re(logs, timeout=60)
            except Exception as e:
                expected_logs_not_found_list.append(logs)
                logger.debug(f"Log Validation failed for pattern: {logs}, Exception: {e}")

        # Trigger Ethernet Wakeup(ETH_WUP) and ensuring root login on Serial Console
        self.test.mtee_target.wakeup_from_sleep()
        try:
            self.test.mtee_target._console.wait_for_re(
                rf".*{self.test.mtee_target.options.target} login.*root",
                timeout=60,
            )
        except Exception as e:
            logger.debug("Rebooting the Target, since target didn't wakeup post shutdown")
            reboot_and_wait_for_android_target(self.test, prefer_softreboot=False)
            raise AssertionError(
                f"Aborting the Test since target didn't wakeup post shutdown. Error Occurred: {e}",
                "Rebooting the target and waiting for application mode",
            )

        self.test.mtee_target.switch_serial_console_to_android()
        if not self.linux_helpers.verify_switch_to_android():
            expected_logs_not_found_list.append("Android Console Not-Accessible")

        self.test.mtee_target.execute_console_command("su", block=False)
        self.test.mtee_target.switch_serial_console_to_node0()
        if not self.linux_helpers.verify_switch_to_node0():
            expected_logs_not_found_list.append("Node0 Console Not-Accessible")

        assert_false(
            expected_logs_not_found_list,
            "Validation Failed!!: "
            f"Expected Logs and Results not found. Please find failure logs list: {expected_logs_not_found_list}",
        )
