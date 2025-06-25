# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Linux filesystem related tests"""
import configparser
import logging
import re
from pathlib import Path

from mtee.testing.tools import assert_equal, assert_false, assert_regexp_matches, assert_true, metadata
from si_test_idcevo.si_test_config.filesystem_consts import (
    EXPECTED_EXT4_MOUNTS_WITH_ECU,
    EXPECTED_PROC_DIRECTORY_CONTENT,
    EXPECTED_SYSFS_DIRECTORY_CONTENT,
    EXPECTED_TMP_DIRECTORY_CONTENT,
    INT_EXT_FILE_SYSTEM_CONFIGS,
    SECURITY_FILE_SYSTEM_CONFIGS,
    SPECIAL_PURPOSE_FILE_SYSTEM_CONFIGS,
)
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.dmverity_helpers import validate_output, validate_output_using_regex_list
from si_test_idcevo.si_test_helpers.linux_commands_handlers import LinuxCommandsHandler
from si_test_idcevo.si_test_helpers.parsing_handlers import (
    compares_expected_vs_obtained_output,
    keywords_vs_obtained_output,
)

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

EXT4_MOUNT_CMD = "mount | grep 'on / '"


EXPECTED_EXT4_MOUNTS_COMMON_PARTITION = [
    re.compile(r"/dev/sdd24|sde24.* on /sb_signedfw type ext4.*"),
    re.compile(r"/dev/sda17 on /var/ncd type ext4.*"),
    re.compile(r"/dev/mapper/sys on /var/sys type ext4.*stripe=128"),
    re.compile(r"/dev/mapper/data on /var/data type ext4.*stripe=128"),
    re.compile(r"/dev/sdf19 on /var/smacs type ext4.*stripe=2"),
]


class TestsLinuxFilesystem(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)
        cls.target_name = cls.test.mtee_target.options.target

    def verify_ext4_filesystem_mount(self):
        """
        Verifying EXT4 File System Mount in 3 Different Validations
        1. With respect to DM-verity
        2. With respect to ECU
        3. Common partition irrespective of any ECU
        """
        result = self.test.mtee_target.execute_command("mount | grep ext4")

        # Verifying with respect to DM-Verity
        if "/dev/dm-0" in result.stdout:
            expected_output = r"/dev/dm-0"
        elif "/dev/sdd21" in result.stdout:
            expected_output = r"/dev/sdd21 on.*"
        elif "/dev/sde21" in result.stdout:
            expected_output = r"/dev/sde21 on.*"
        elif "/dev/sde24" in result.stdout:
            expected_output = r"/dev/sde24 on.*"
        elif "/dev/sdd24" in result.stdout:
            expected_output = r"/dev/sdd24 on.*"
        else:
            raise AssertionError(f"Unexpected root partition: {result.stdout}")

        assert_regexp_matches(
            result.stdout, expected_output, f"Expected Message {expected_output} not found after Mount command"
        )

        # Verifying with respect to ECU
        ext4_mounts = EXPECTED_EXT4_MOUNTS_WITH_ECU[self.target_name]
        validate_output(result, ext4_mounts)

        # Verifying with Common Partition irrespective of any ECU
        common_partition = validate_output_using_regex_list(result, EXPECTED_EXT4_MOUNTS_COMMON_PARTITION)
        assert_true(common_partition, f"Verification Failed for Common Partition : {common_partition}")

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
        duplicates="IDCEVODEV-13364",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "LINUX_FILESYSTEM"),
            },
        },
    )
    def test_001_filesystem_related_kernel_configs(self):
        """
        [SIT_Automated] Verify Filesystem Related Kernel Configurations

        Steps:
        * Connect to system console (ssh).
        * Access the config file and search for a config with:
            **zcat /proc/config.gz | grep -q {*}CONFIG_EXT4_FS{*}=y

        * In case configuration is found command returns 0 and test is a PASS
            any other return code is a FAIL.

        Repeat the command for each configuration

        * Check Internal/External File System Configs
            - CONFIG_EXT4_FS=y
            - CONFIG_FAT_FS=y
            - CONFIG_MSDOS_FS=y
            - CONFIG_VFAT_FS=y

        * Check Special Purpose File System Configs
            - CONFIG_SYSFS=y
            - CONFIG_TMPFS=y
            - CONFIG_KERNFS=y
            - CONFIG_PROC_FS=y

        * Check Security File System Configs:
            - CONFIG_SECURITYFS=y
            - CONFIG_DM_VERITY=y
            - CONFIG_BLK_DEV_DM=y
            - CONFIG_BLK_DEV_DM_BUILTIN=y

        """
        logger.info("Starting test to verify filesystem related kernel configs")
        linux_handler = LinuxCommandsHandler(self.test.mtee_target, logger)
        invalid_features_list = []

        invalid_features_list = linux_handler.search_features_in_kernel_configuration(
            features_list=INT_EXT_FILE_SYSTEM_CONFIGS
        )

        assert_equal(
            len(invalid_features_list),
            0,
            f"The following features are not configured: {invalid_features_list} in {INT_EXT_FILE_SYSTEM_CONFIGS}",
        )

        invalid_features_list = linux_handler.search_features_in_kernel_configuration(
            features_list=SPECIAL_PURPOSE_FILE_SYSTEM_CONFIGS
        )

        assert_equal(
            len(invalid_features_list),
            0,
            "The following features are not configured: "
            f"{invalid_features_list} in {SPECIAL_PURPOSE_FILE_SYSTEM_CONFIGS}",
        )

        invalid_features_list = linux_handler.search_features_in_kernel_configuration(
            features_list=SECURITY_FILE_SYSTEM_CONFIGS
        )

        assert_equal(
            len(invalid_features_list),
            0,
            f"The following features are not configured: {invalid_features_list} in {SECURITY_FILE_SYSTEM_CONFIGS}",
        )

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
        duplicates="IDCEVODEV-13371",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "LINUX_FILESYSTEM"),
            },
        },
    )
    def test_002_ext4_filesystem_mount(self):
        """[SIT_Automated] Verify EXT4 Filesystem Mount

        Steps:
         This test has to be verified by 3 different checkpoints as stated below
         1. With respect to DM-verity
         2. With respect to ECU
         3. Common partion irrespective of any ECU
        """
        self.verify_ext4_filesystem_mount()

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
        duplicates="IDCEVODEV-13402",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "LINUX_FILESYSTEM"),
            },
        },
    )
    def test_003_verify_tmpfs_filesystem_mount(self):
        """
        [SIT_Automated] Verify TMPFS Filesystem Mount

        Steps:
            1 - Check mount point for tmpfs filesystem
            2 - Move to the mount point i.e. "/tmp" directory
            3 - List contents of /tmp directory
        """

        logger.info("Starting test to verify TMPFS filesystem mount")
        return_stdout, _, _ = self.test.mtee_target.execute_command("mount | grep tmpfs")
        assert_true("tmpfs on /run type tmpfs" in return_stdout, "Expected output was not obtained in test step 2.")

        return_stdout, _, _ = self.test.mtee_target.execute_command("cd /tmp; ls *.lock")
        error_msg = keywords_vs_obtained_output(EXPECTED_TMP_DIRECTORY_CONTENT, return_stdout.splitlines())

        assert_false(error_msg, f"Expected output was not obtained in test step 3. Missing files: {error_msg}")

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
        duplicates="IDCEVODEV-13406",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "LINUX_FILESYSTEM"),
            },
        },
    )
    def test_004_verify_proc_filesystem_mount(self):
        """
        [SIT_Automated] Verify PROC Filesystem Mount

        Steps:
            1 - Check mount point for proc filesystem
            2 - Move to the mount point i.e. "/proc" directory
            3 - List contents of /proc directory
        """

        logger.info("Starting test to verify PROC filesystem mount")
        return_stdout, _, _ = self.test.mtee_target.execute_command("mount | grep proc")
        assert_true(
            "proc on /proc type proc" in return_stdout,
            f"Test step 1 has an unexpected output: {return_stdout}",
        )

        return_stdout, _, _ = self.test.mtee_target.execute_command("ls /proc")
        output_proc_dir = [dir for dir in return_stdout.splitlines() if not dir.isdigit()]
        error_msg = compares_expected_vs_obtained_output(EXPECTED_PROC_DIRECTORY_CONTENT, output_proc_dir)
        assert_false(error_msg, "Expected output was not obtained in test step 2.")

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
        duplicates="IDCEVODEV-13401",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "LINUX_FILESYSTEM"),
            },
        },
    )
    def test_005_verify_sysfs_filesystem_mount(self):
        """
        [SIT_Automated] Verify SYSFS Filesystem Mount
        Steps:
            1 - Check mount point for sysfs filesystem
            2 - Move to the mount point i.e. "/sys" directory
            3 - List contents of /sys directory
        """

        logger.info("Starting test to verify SYSFS filesystem mount")
        return_stdout, _, _ = self.test.mtee_target.execute_command("mount | grep sysfs")
        assert_equal(
            return_stdout,
            "sysfs on /sys type sysfs (rw,nosuid,nodev,noexec,relatime,seclabel)",
            f"Test step 1 has an unexpected output: {return_stdout}",
        )

        return_stdout, _, _ = self.test.mtee_target.execute_command("ls /sys")
        output_sys_dir = return_stdout.splitlines()
        error_msg = compares_expected_vs_obtained_output(EXPECTED_SYSFS_DIRECTORY_CONTENT, output_sys_dir)
        assert_false(error_msg, f"Expected output was not obtained in test step 2. {error_msg}")

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
        duplicates="IDCEVODEV-13399",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "LINUX_FILESYSTEM"),
            },
        },
    )
    def test_006_verify_read_write_functionality_filesystem(self):
        """
        [SIT_Automated] Verify Read and Write Support for EXT4 Filesystem
        Steps:
            1 - Check if root partition is mounted properly
            2 - Remount the root partition as READ/WRITE from READ ONLY
            3 - Cross check if root partition is mounted as READ/WRITE
            4 - Create a test file with "EXT4 Filesystem Test" string in root partition
            5 - Verify contents of newly created test file
            6 - Reboot HU
            7 - Check if test file exists
            8 - Check contents of test file
        """

        logger.info("Starting test to verify READ and WRITE support for EXT4 filesystem")

        return_stdout, _, _ = self.test.mtee_target.execute_command("mount | grep 'on / '")

        if "/dev/sdd21" in return_stdout:
            root = "sdd21"
        elif "/dev/sde21" in return_stdout:
            root = "sde21"
        else:
            raise AssertionError(f"Unexpected root partition: {return_stdout}")

        return_stdout, _, _ = self.test.mtee_target.execute_command(f"mount | grep /dev/{root}")
        assert_equal(
            return_stdout,
            f"/dev/{root} on / type ext4 (ro,relatime,seclabel)",
            f"Test step 1 has an unexpected output: {return_stdout}",
        )

        return_stdout, _, return_code = self.test.mtee_target.execute_command("mount -o remount,rw /")
        assert_equal(
            return_code,
            0,
            f"Test step 2 return code is different from 0: {return_stdout}",
        )

        return_stdout, _, _ = self.test.mtee_target.execute_command(f"mount | grep {root}")
        assert_equal(
            return_stdout,
            f"/dev/{root} on / type ext4 (rw,relatime,seclabel)",
            f"Test step 3 has an unexpected output: {return_stdout}",
        )

        return_stdout, _, return_code = self.test.mtee_target.execute_command(
            "echo 'EXT4 Filesystem Test' > /read_write_test.txt"
        )
        assert_equal(
            return_code,
            0,
            f"Test step 4 return code is different from 0: {return_stdout}",
        )

        return_stdout, _, _ = self.test.mtee_target.execute_command("cat /read_write_test.txt")
        assert_equal(
            return_stdout,
            "EXT4 Filesystem Test",
            f"Test step 5 has an unexpected output: {return_stdout}",
        )

        self.test.mtee_target.reboot()

        return_stdout, _, _ = self.test.mtee_target.execute_command("ls / | grep 'read_write_test.txt'")
        assert_true(len(return_stdout) > 0, f"Test file 'read_write_test.txt' does not exist: {return_stdout}")

        return_stdout, _, _ = self.test.mtee_target.execute_command("cat /read_write_test.txt")
        assert_equal(
            return_stdout,
            "EXT4 Filesystem Test",
            f"Test file content is different from 'EXT4 Filesystem Test: {return_stdout}",
        )

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
        duplicates="IDCEVODEV-7136",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "EXTERNAL_PERIPHERAL_SUPPORT"),
            },
        },
    )
    def test_007_verify_ufs_partitioning_and_mounting(self):
        """
        [SIT_Automated] Verify UFS Partitioning and Mounting

        Steps:
        1. Check the list of disk partitions using command,
            "fdisk -l"
        2. Check the list of mounted disk partitions using command,
            "df -h"
        3. Check whether the partition is mounted successfully using command,
            "mount | egrep ext4"
        """
        view_disk_partition_cmd = "fdisk -l"
        result = self.test.mtee_target.execute_command(view_disk_partition_cmd)
        disk_partition_expected_result = [
            "/dev/sda",
            "/dev/sdb",
            "/dev/sdc",
            "/dev/sdd",
            "/dev/sde",
            "/dev/sdf",
            "/dev/sdg",
            "/dev/dm-",
        ]
        validate_output(result, disk_partition_expected_result)
        view_mounted_disk_partition_cmd = "df -h"

        result = self.test.mtee_target.execute_command(view_mounted_disk_partition_cmd)
        mounted_disk_partition_expected_resukt = [
            "/dev/root",
            "devtmpfs",
            "tmpfs",
            "/dev/mapper/sys",
            "/dev/mapper/data",
            "/dev/sdf",
        ]

        validate_output(result, mounted_disk_partition_expected_resukt)
        self.verify_ext4_filesystem_mount()
