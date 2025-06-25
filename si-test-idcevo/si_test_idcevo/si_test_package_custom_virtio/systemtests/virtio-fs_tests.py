# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Access to virtio-fs tests"""
import configparser
import logging
import re
import time
from pathlib import Path
from unittest import SkipTest, skip

from mtee.testing.test_environment import TEST_ENVIRONMENT
from mtee.testing.tools import assert_false, assert_process_returncode, assert_true, metadata

from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.linux_commands_handlers import LinuxCommandsHandler
from si_test_idcevo.si_test_helpers.reboot_handlers import reboot_and_wait_for_android_target
from si_test_idcevo.si_test_helpers.test_helpers import check_ipk_installed, validate_output_list
from validation_utils.utils import CommandError, TimeoutError


# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

required_target_packages = ["partition-manager-systemtests-targetfiles"]


class TestsVirtiofs(object):
    folder_x = "/x"
    folder_y = "/y"
    folder_z = "/z"
    # Because when listing the directories the folder_x appears as "x/"
    folder_x_ls = folder_x.strip("/") + "/"
    mtee_shared_dir = "/var/ncd"
    apinext_shared_dir = "/vendor/run/ncd"
    full_path_folder = folder_x + folder_y + folder_z
    file1_suffix = f"{folder_x}{folder_y}/file1"
    file2_suffix = f"{full_path_folder}/file2"
    file_content1 = "virtio-fs-content"
    file_content2 = "virtio-fs-contentssssss"

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(root=True)
        cls.ipk_checked = check_ipk_installed(required_target_packages)
        cls.linux_helpers = LinuxCommandsHandler(cls.test.mtee_target, logger)

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def assert_service_active_and_running(self, service):
        """Asserts if a service is active (running)

        Steps:
        1 - Check status of service
            # systemctl status <service>
        :return: service status
        """
        cmd = f"systemctl status {service}"
        service_status, _, _ = self.test.mtee_target.execute_command(cmd)
        assert_true("active (running)" in service_status, f"Service {service} is not running")

        return service_status

    def get_mount_points_from_fstab_file(self, result):
        """
        Extract the expected output from the contents of fstab file, split it on basis of mount points
        :param ProcessResult result: Actual response from the target
        :return list: mount_points
        """
        mount_points_reg = re.compile(r"/\S+/\S+.*/(\S+)\s")
        mount_points = []
        mount_points_expected = mount_points_reg.finditer(result.stdout)
        for item in mount_points_expected:
            mount_points.append(item.group(1))
        return mount_points

    def set_fstab_filename_for_ecu(self):
        self.target_type = self.test.mtee_target.options.target
        if "rse" in self.target_type:
            fstab_filename = "/etc/fstab_a_rse26"
        elif "cde" in self.target_type:
            fstab_filename = "/etc/fstab_a_cde"
        elif "idcevo" in self.target_type:
            if self.test.mtee_target.has_capability(TEST_ENVIRONMENT.service_pack.SP21):
                fstab_filename = "/etc/fstab_a_idcevo_sp21"
            elif self.test.mtee_target.has_capability(TEST_ENVIRONMENT.service_pack.SP25):
                fstab_filename = "/etc/fstab_a_idcevo_sp25"
            else:
                logger.error("Service Pack is different from SP21 or SP25")
        return fstab_filename

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
        duplicates="IDCEVODEV-21565",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "HARDWARE_ACCESS_VIRTIO"),
            },
        },
    )
    def test_001_virtiofs_configuration(self):
        """
        [SIT_Automated] Verify virtio-fs backend is configured properly

        Steps:
            1 - Check the status of  vhost-user-slave-crosvm-filesystem.service to see if is running
                and has the shared-dir:
        """

        logger.info("Starting test to verify virtio-fs backend is configured properly.")
        service_status = self.assert_service_active_and_running("vhost-user-slave-crosvm-filesystem.service")
        logger.info(f"systemctl vhost-user-slave-crosvm-filesystem: {service_status}")

        assert_true("active (running)" in service_status, "Service is not running")
        assert_true(
            f"--shared-dir {self.mtee_shared_dir}" in service_status,
            "Share dir not found on service configuration",
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
        duplicates="IDCEVODEV-24279",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "HARDWARE_ACCESS_VIRTIO"),
            },
        },
    )
    @skip("Test is inactive: IDCEVODEV-420534")
    def test_002_mount_virtiofs(self):
        """
        [SIT_Automated] Verify virtio-fs can be mounted

        Pre-conditions:
            1 - target must have the service virtio-devices initialized with --shared directory
            as it is done on test_001
        Steps:
            1 - Create a directory in android to mount the shared folder:
                # mkdir -p /vendor/run/ncd
            2 - Mount the shared folder:
                # mount -t virtiofs vfs-vm3 /vendor/run/ncd
            3 - Check if the shared folder was mounted:
                # df -h
        """

        self.test_001_virtiofs_configuration()

        list_of_mounted_disks = self.test.apinext_target.execute_command(["df", "-h"])
        logger.debug(f"Before test list of mounted disks: \n{list_of_mounted_disks}")
        if "vfs-vm3" not in list_of_mounted_disks:
            self.test.apinext_target.execute_command(["mkdir", "-p", self.apinext_shared_dir])
            self.test.apinext_target.execute_command(
                ["mount", "-t", "virtiofs", "vfs-vm3", self.apinext_shared_dir],
            )
            list_of_mounted_disks = self.test.apinext_target.execute_command(["df", "-h"])
        logger.debug(f"List of mounted disks: \n{list_of_mounted_disks}")

        assert_true("vfs-vm3" in list_of_mounted_disks, "Shared dir was not mounted")

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
        duplicates="IDCEVODEV-24329",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "HARDWARE_ACCESS_VIRTIO"),
            },
        },
    )
    @skip("Test is inactive: IDCEVODEV-420534")
    def test_003_virtio_verify_contents_node0_to_ivi(self):
        """
        [SIT_Automated] Verify contents created / deleted from Node0 is reflected on IVI side

        Pre-conditions:
            1 - Target must have the shared directory mounted on IVI side as it is done on test_002
        Steps:
            1 - Create folders on node0 and verify if is reflected on IVI:
            2 - Create files on node0 and verify if is reflected on IVI:
            3 - Delete 1 folder and 1 file on node0 and verify if is reflected on IVI:
        """

        self.test_002_mount_virtiofs()

        ls_folder_x, _, _ = self.test.mtee_target.execute_command(["ls", "-alF", self.mtee_shared_dir])

        if self.folder_x_ls in ls_folder_x:
            self.test.mtee_target.execute_command(["rm", "-rf", self.mtee_shared_dir + self.folder_x])
            # sleep for 5 seconds to sync shared directory between Node0 and IVI side
            time.sleep(5)

        self.test.mtee_target.execute_command(["mkdir", "-p", self.mtee_shared_dir + self.full_path_folder])

        results_ivi_dir = self.test.apinext_target.execute_command(["ls", "-alF", self.apinext_shared_dir])

        assert_true(
            self.folder_x_ls in results_ivi_dir,
            "Folders created on Node0 side wasn't created on IVI side",
        )

        cmd = f"echo '{self.file_content1}' > {self.mtee_shared_dir}{self.file1_suffix}"
        self.test.mtee_target.execute_command(cmd)
        cmd = f"echo '{self.file_content2}' > {self.mtee_shared_dir}{self.file2_suffix}"
        self.test.mtee_target.execute_command(cmd)

        results_ivi_dir = self.test.apinext_target.execute_command(
            ["ls", "-alF", self.apinext_shared_dir + self.folder_x + self.folder_y]
        )

        results_ivi_file1 = self.test.apinext_target.execute_command(
            ["cat", self.apinext_shared_dir + self.file1_suffix],
        )
        results_ivi_file2 = self.test.apinext_target.execute_command(
            ["cat", self.apinext_shared_dir + self.file2_suffix],
        )

        assert_true(
            self.file_content1 in results_ivi_file1 and self.file_content2 in results_ivi_file2,
            "Contents created on Node0 side wasn't created on IVI side",
        )

        self.test.mtee_target.execute_command(["rm", "-rf", self.mtee_shared_dir + self.full_path_folder])

        results_ivi_del1 = self.test.apinext_target.execute_command(
            ["cat", self.apinext_shared_dir + self.file1_suffix],
        )
        results_ivi_del2 = self.test.apinext_target.execute_command(
            ["ls", "-alF", self.apinext_shared_dir + self.folder_x + self.folder_y],
        )

        assert_true(
            self.file_content1 in results_ivi_del1 and self.folder_z not in results_ivi_del2,
            "Contents deleted on Node0 side wasn't deleted on IVI side",
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
        duplicates="IDCEVODEV-81485",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "HARDWARE_ACCESS_VIRTIO"),
            },
        },
    )
    @skip("Test is inactive: IDCEVODEV-420534")
    def test_004_virtio_verify_contents_ivi_to_node0(self):
        """
        [SIT_Automated] Verify contents created / deleted from IVI is reflected on Node0 side

        Steps:
            - make sure the following services are running on Node0 side:
                # vhost-user-slave-crosvm-filesystem.service
            - ensure we have the following config files and are accessible from Node0:
                # cat /var/ncd/node0/security/selinux-policy.md5
                # cat /var/ncd/prop/registry.prop
            - check if virtio-fs partition is mounted on android
                # mount | grep ncd
            - ensure we have the following config files and are accessible from android:
                # cat /var/ncd/node0/security/selinux-policy.md5
                # cat /var/ncd/prop/registry.prop
        """
        ncd_files = [
            "lost+found",
            "node0",
            "prop",
            "display",
            "partman",
            "security",
            "selinux-policy.md5",
            "registry.prop",
        ]

        mount_pattern = re.compile(r"vfs-vm3 on /vendor/run/ncd type virtiofs \([a-zA-Z,].*relatime\)")

        self.assert_service_active_and_running("vhost-user-slave-crosvm-filesystem.service")

        return_stdout, _, _ = self.test.mtee_target.execute_command("ls -R /var/ncd")
        ncd_files_status = all(files in return_stdout for files in ncd_files)
        assert_true(
            ncd_files_status,
            f"All files mentioned in list- {ncd_files} were not found in folders and subfolders at path/var/ncd."
            f" Actual list of files present is- {return_stdout}",
        )

        cmd = "cat /var/ncd/node0/security/selinux-policy.md5"
        result = self.test.mtee_target.execute_command(cmd)
        assert_process_returncode(0, result, "selinux-policy.md5 not acessible from Node0")

        cmd = "cat /var/ncd/prop/registry.prop"
        result = self.test.mtee_target.execute_command(cmd)
        assert_process_returncode(0, result, "registry.prop not acessible from Node0")

        cmd = "mount | grep ncd"
        result = self.test.apinext_target.execute_command(cmd)
        assert_true(
            re.search(mount_pattern, result.stdout.decode("utf-8")),
            f"Incorrect mounted filesystem. Output of cmd 'mount | grep ncd'- {result}",
        )

        cmd = "cat /vendor/run/ncd/node0/security/selinux-policy.md5"
        result = self.test.apinext_target.execute_command(cmd)
        assert_true(len(result) > 0, "selinux-policy.md5 not acessible from Android")

        cmd = "cat /vendor/run/ncd/prop/registry.prop"
        result = self.test.apinext_target.execute_command(cmd)
        assert_true(len(result) > 0, "registry.prop not acessible from Android")

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
        duplicates="IDCEVODEV-24582",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "HARDWARE_ACCESS_VIRTIO"),
            },
        },
    )
    @skip("Test is inactive: IDCEVODEV-420534")
    def test_005_contents_after_power_cycle(self):
        """
        [SIT_Automated] After powercycle verify if contents in shared directory

        Steps:
            1 - Run following command to make the system RW:
                # mount -o remount,rw /
            2 - Create a directory in Node0 to share with IVI:
                # mkdir -p /virtio-fs-test
            3 - Modify the /lib/systemd/system/virtio-devices.service file to include a virtio-fs backend like:
                --shared-dir=/var/data/virtio-fs-test/:virtio-fs \
            4 - Reboot the target
            5 - Check the status of virtio-devices.service to see if is running and has the shared-dir:
                # systemctl status virtio-devices
        """

        self.test_003_virtio_verify_contents_node0_to_ivi()

        reboot_and_wait_for_android_target(test=self.test)

        self.test.apinext_target.execute_command(
            ["mount", "-t", "virtiofs", "vfs-vm3", self.apinext_shared_dir], privileged=True
        )
        list_of_mounted_disks = self.test.apinext_target.execute_command(["df", "-h"])
        logger.debug(f"List of mounted disks: \n{list_of_mounted_disks}")

        assert_true("vfs-vm3" in list_of_mounted_disks, "Shared dir was not mounted")

        result_file1 = self.test.apinext_target.execute_command(
            ["cat", self.apinext_shared_dir + self.file1_suffix], privileged=True
        )

        assert_true(self.file_content1 in result_file1, "File was not found on IVI side after power cycle")

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
        duplicates="IDCEVODEV-36852",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "PARTITION_MANAGER_AB_FILE_SYSTEMS"),
            },
        },
    )
    def test_006_verify_mount_points_according_to_fstab_slots(self):
        """
        [SIT_Automated] Verify Mount points are according fstab slot A/B
        Precondition -
            1. Install the "partition-manager-systemtests-targetfiles" ipk.
        Steps:
            1. Remount the partition and give executable right to the partmanproxytest binary.
                - mount -o remount,exec /
                - chmod +x partmanproxytest
            2. As per the service pack, Read fstab for slot A using command "cat /etc/fstab_a_idcevo"
                - Extract the expected output from the contents of fstab file, get MOUNT_POINTS from the output
            3. Fetch the mounted path using the command "mount"
            4. Run the command "./partmanproxytest -a" to get all active partitions

        Expected Result -
            - For step 3, Output should match the content in MOUNT_POINTS from step 2.
            - After triggering partmanproxytest binary, output should match with MOUNT_POINTS from step 2.
        """
        if not self.ipk_checked:
            raise SkipTest(
                f"Skipping this test because the required IPKs, {required_target_packages}, "
                "weren't installed successfully!"
            )
        partmanproxytest_path = "/var/data/systemtests/partition-manager-systemtests/"
        self.test.mtee_target.remount()
        self.test.mtee_target.execute_command(f"chmod +x {partmanproxytest_path}partmanproxytest")

        fstab_filename = self.set_fstab_filename_for_ecu()

        result = self.test.mtee_target.execute_command(f"cat {fstab_filename}")
        assert_process_returncode(0, result, f"fstab file {fstab_filename} not accessible for {self.target_type}")
        mount_points = self.get_mount_points_from_fstab_file(result)

        result = self.test.mtee_target.execute_command("mount")
        match, failed_output_list = validate_output_list(result.stdout, mount_points)
        assert_true(
            match,
            "Not all mount points from fstab_a file were listed in output of mount command, mount points from "
            f"fstab_a file - {mount_points}\nExpected logs not found {failed_output_list}",
        )
        try:
            result = self.test.mtee_target.execute_command("./partmanproxytest -a", cwd=partmanproxytest_path)
        except (CommandError, TimeoutError) as err:
            logger.debug(f"Timeout reached while execute the partmanproxytest binary - {err}")

        logger.info(f"Partmantest binary output - {result.stdout}")
        match, failed_output_list = validate_output_list(result.stdout, mount_points)
        assert_true(
            match,
            f"Mount points do not match the mounted points in stdout. Expected mount points - {mount_points}\n"
            f"partmanproxytest output received - {result.stdout}\nExpected output not found - {failed_output_list}",
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
        duplicates="IDCEVODEV-9924",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "HYPERVISOR_SUPPORT"),
                    config.get("FEATURES", "HARDWARE_ACCESS_VIRTIO"),
                ]
            },
        },
    )
    def test_007_verify_sys_android_ping(self):
        """
        [SIT_Automated] Verify UFS Virtio-net access sys->android and android -> sys ping

        Pre-condition
            1. Execute "nft flush ruleset" on node0 console
        Steps:
            1. Get the ip address of vnet23_0 on node0 console by command: "ifconfig vnet23_0"
            2. Get the ip address of vnet32_0 on android console by command: "ifconfig vnet32_0"
            3. From node0 console "ping 160.48.199.254"
            4. From android console "ping 160.48.199.253"
        Expected result
            - From step 1 make sure ip "160.48.199.253" present in vnet23_0.stdout
            - From step 2 make sure that ip 160.48.199.254 is assigned under "Driver virtio_net" interface
            - From step 4 & 5 ping must be successful with 0% packet loss
        """
        failed_msg = []
        vnet23_addr = "160.48.199.253"
        vnet32_addr = "160.48.199.254"
        expected_driver_interface = "Driver virtio_net"
        expected_ping_result = "0% packet loss"
        self.test.mtee_target.execute_command("nft flush ruleset")

        vnet23_result = self.test.mtee_target.execute_command("ifconfig vnet23_0")
        assert_true(
            vnet23_addr in vnet23_result.stdout,
            "vnet23 ip address is not as expected. "
            f"Actual output: {vnet23_result.stdout}. Expected ip: {vnet23_addr} ",
        )

        vnet32_result = self.test.apinext_target.execute_command("ifconfig vnet32_0", privileged=True)
        logger.debug(f"vnet32_result: {vnet32_result}")
        assert_true(
            vnet32_addr in vnet32_result.stdout.decode("utf-8")
            and expected_driver_interface in vnet32_result.stdout.decode("utf-8"),
            "vnet32 ip address and Driver virtio_net interface are not as expected. "
            f"Actual output: {vnet32_result.stdout}. "
            f"Expected ip: {vnet32_addr} and interface: {expected_driver_interface}",
        )

        logger.info(f"Ping from Android to {vnet23_addr}")
        android_ping_result = self.test.apinext_target.execute_command(
            ["ping", "-c", "4", vnet23_addr], privileged=True
        )
        logger.debug(f"android_ping_result: {android_ping_result}")
        if expected_ping_result not in android_ping_result.stdout.decode("utf-8"):
            failed_msg.append(
                {
                    "command": f"ping -c 4 {vnet23_addr}",
                    "command_output": android_ping_result.stdout.decode("utf-8"),
                }
            )

        logger.info(f"Ping from linux to {vnet32_addr}")
        node0_ping_result = self.test.mtee_target.execute_command(["ping", "-c", "4", vnet32_addr])
        if expected_ping_result not in node0_ping_result.stdout:
            failed_msg.append(
                {
                    "command": f"ping -c 4 {vnet32_addr}",
                    "command_output": node0_ping_result.stdout,
                }
            )
        assert_false(
            failed_msg,
            "Ping operation between node0 and android failed. Below are the details:\n"
            "\n".join(
                f"Command: {cmd_info['command']} \n, Command output:{cmd_info['command_output']}"
                for cmd_info in failed_msg
            ),
        )
