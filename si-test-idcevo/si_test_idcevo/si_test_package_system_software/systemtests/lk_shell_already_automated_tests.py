# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""
System Software already automated tests - LK shell.

These tests were previously automated in the domain's repositories.
This file brings them into our codebase, where they have been adapted to align with our testing standards.
"""
import configparser
import logging
import re
import subprocess
import time

from pathlib import Path
from unittest import skipIf

from mtee.testing.tools import assert_false, assert_true, metadata, run_command
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.lk_helper import boot_with_log_level, enter_lk_shell_instance
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target
from validation_utils.utils import TimeoutCondition

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)


class TestslkMode(object):
    test = TestBase.get_instance()
    test.setup_base_class()
    hw_model = test.mtee_target.options.target
    hw_revision = test.mtee_target.options.hardware_revision
    hw_variant = test.mtee_target.options.hardware_variant

    def calculate_actual_lun_size_from_serial_console_log_file(self, reg_pattern):
        """
        This function extracts partition details like lun number, default size and count from serial_console file.
        Later it uses the above extracted data to calculate the actual lun size by
        using the below formula and return back the lun number with associated actual size.
        Formula - actual_lun_size = default size * count / 1024
        param reg_pattern reg: regex pattern to detect lun number with size and count.
        Returns:
          -Lun number
          -Actual size
        """

        timer = TimeoutCondition(10)
        log_file = Path(self.test.mtee_target.options.result_dir) / "serial_console_ttySOCHU.log"
        while timer:
            with open(log_file, "r", encoding="utf8") as file:
                content = file.read()
                match = re.compile(reg_pattern).search(content)
            if match:
                break
            time.sleep(2)
        if not match:
            raise AssertionError(f"Lun data pattern: {reg_pattern} not found in file- serial_console_ttySOCHU.log")

        actual_lun_size = (int(match.group(2)) * int(match.group(3))) / 1024
        logger.info(f"lun number : {match.group(1)} and actual size : {actual_lun_size}")
        return match.group(1), int(actual_lun_size)

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
        duplicates="IDCEVODEV-6626",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "DEVELOPER_SUPPORT_RECOVERY_MODE"),
            },
        },
    )
    @skipIf(
        (
            "idcevo" in test.mtee_target.options.target.lower()
            and test.mtee_target.options.hardware_revision.startswith("D")
        ),
        "Test not applicable for D sample.",
    )
    def test_001_verify_target_boots_to_sys_shell(self):
        """
        [SIT_Automated] Support recovery from shell
        Steps:
            - Enter LK mode.
            - In LK prompt type "boot bolo" to enter bolo mode.
            - Wait for pattern on serial r".*idcevo|rse26|cde login.*"
        Expected Outcome:
              Target boots to sys shell on entering "boot bolo".
        """
        test_successfully_logged_in = False
        try:
            enter_lk_shell_instance(self.test)
            self.test.mtee_target._console.write("boot bolo")
            self.test.mtee_target._console.wait_for_re(rf".*{self.test.mtee_target.options.target} login.*")
            test_successfully_logged_in = True
        except Exception as e:
            logger.error(f"Wasn't possible to enter to bolo mode. Error occurred - {e}")
        finally:
            self.test.mtee_target.reboot(prefer_softreboot=False)
            wait_for_application_target(self.test.mtee_target)
            assert_true(test_successfully_logged_in, "Target did not enter in system shell after boot bolo mode")

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
        duplicates="IDCEVODEV-8751",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "BOOTLOADER_SECURITY_SOC_BASIC_SECURITY"),
            },
        },
    )
    @skipIf(
        (
            "idcevo" in test.mtee_target.options.target.lower()
            and test.mtee_target.options.hardware_revision.startswith("D")
        ),
        "Test not applicable for D sample.",
    )
    def test_002_ensure_slot_get_fused(self):
        """
        [SIT_Automated] Ensure slot get fused
        Steps:
            1. Go to fastboot mode
            2. Run the below command on host PC:
                "fastboot oem otp slot_get_fused 1"
            3. Wait for "SUCCESS slot_get_fused" on serial console
            4. Reboot target to resume normal operation
        Expected result:
            Expected message "SUCCESS slot_get_fused" found on logs
        """
        cmd = "fastboot oem otp slot_get_fused 1"

        try:
            self.test.mtee_target.switch_to_fastboot()
            run_command(cmd, shell=True, stderr=subprocess.STDOUT)
            lk_response = self.test.mtee_target._console.wait_for_re(r".*SUCCESS: slot\_get\_fused.*")
        except Exception as e:
            raise AssertionError(f"Exception occurred during Slot test in LK shell mode: {str(e)}")
        finally:
            self.test.mtee_target.reboot(prefer_softreboot=False, serial=True)
            wait_for_application_target(self.test.mtee_target)
        assert_true(lk_response, "Expected 'SUCCESS: slot_get_fused' in output, but wasn't found.")

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
        duplicates="IDCEVODEV-16324",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "BOOTLOADER_SECURITY_SOC_BASIC_SECURITY"),
                ],
            },
        },
    )
    @skipIf("D" in hw_revision, "Test is not applicable for D Samples")
    def test_003_otp_bank_get_lock(self):
        """
        [SIT_Automated] OTP test - bank_get_lock
        Steps -
            1. Go to LK shell with fastboot mode
            2. Execute 'fastboot oem otp bank_get_lock 0b' on node0 console
        Expected Output -
            'SUCCESS: bank_get_lock bank' and 'DK return' is found
            in serial console after executing the fastboot command
        """
        cmd = "fastboot oem otp bank_get_lock 0b"
        expected_out = [r"SUCCESS: bank_get_lock bank.*", r"DK return"]
        try:
            self.test.mtee_target.switch_to_flashing_mode()
            self.test.mtee_target._console.clear_read_queue()
            run_command(cmd, shell=True, stderr=subprocess.STDOUT)
            for each_string in expected_out:
                self.test.mtee_target._console.wait_for_re(each_string)
        except Exception as e:
            raise AssertionError(f"Exception occurred during OTP test in LK shell mode: {str(e)}")
        finally:
            self.test.mtee_target.reboot(prefer_softreboot=False, serial=True)
            wait_for_application_target(self.test.mtee_target)

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
        duplicates="IDCEVODEV-10385",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "HYPERVISOR_LOGGING_LOG_BUFFER"),
            },
        },
    )
    def test_004_verify_transmission_android_logs(self):
        """
        [SIT_Automated] Verify hypervisor is logging early information into serial console
        Steps:
            - Switch to LK Shell
            - Write console cmd: "boot --loglevel=f0100000" to increase the log level.
            - Analyse target serial logs to verify log level
            - Switch to LK Shell
            - Restore log level with: `boot --loglevel=0000000'
        Expected Results:
            - Ensure that all the expected hypervisor boot logs are validated in default and increased log level.
        """
        increased_hypervisor_logs_regex = [
            r".*ticks.*_ea_boot_main.*CHIPID.*Product_ID.*",
            r".*ticks.*_ea_init.*Boot.*CPU.*Init.*",
            r".*ms.*_ea_init.*Boot.*CPU.*Init.*Done.*",
            r".*ms.*VM2.*vm2-kernel.*is.*ready.*",
            r".*ms.*VM2.*jumping.*into.*the.*Guest's.*kernel.*",
        ]

        enter_lk_shell_instance(self.test)
        boot_with_log_level(self.test, "f0100000")

        failed_log_messages = []
        for regex_pattern in increased_hypervisor_logs_regex:
            try:
                self.test.mtee_target._console.wait_for_re(regex_pattern)
            except Exception as e:
                logger.error(f"Wasn't possible to find pattern {failed_log_messages}. \nException: {e}")
                failed_log_messages.append(regex_pattern)

        enter_lk_shell_instance(self.test)
        boot_with_log_level(self.test, "0000000")

        try:
            self.test.mtee_target._console.wait_for_re(r".*HYP\:\[\+\d+.*")
            self.test.mtee_target.resume_after_reboot()
            wait_for_application_target(self.test.mtee_target)
        except Exception as e:
            logger.error(f"Target failed to boot up, hard rebooting... \nException:{e}")
            self.test.mtee_target.reboot(prefer_softreboot=False)
            wait_for_application_target(self.test.mtee_target)

        assert_true(
            len(failed_log_messages) == 0,
            f"The following Hypervisor messages with increase log level were not found: {failed_log_messages}",
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
        duplicates="IDCEVODEV-16145",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "UFS_256GB_PARTITION_TABLES"),
            },
        },
    )
    @skipIf("idcevo" not in hw_model, "Test is only applicable for IDCEVO")
    @skipIf("SP21" not in hw_variant, "Test is only applicable for SP21 HW variant")
    @skipIf("C" not in hw_revision, "Test is only applicable for C Samples")
    def test_005_verify_ufs_support_partition_tables(self):
        """
        [SIT_Automated] 256GB UFS Support - Partition tables
        Steps:
            1 - Enter LK mode.
            2 - Run cmd "show_gpt".
        Expected Results:
            1 - Ensure all lun partitions with expected sizes are present in serial console log.
                Expected partitions values are stored in list name - 'lun_number_and_size_reg'
        """

        lun_number_and_size_reg = [
            r".*lun: 0.*size:4096 bytes.*",
            r".*lun: 3.*size:4096 bytes.*",
            r".*lun: 4.*size:4096 bytes.*",
            r".*lun: 5.*size:4096 bytes.*",
        ]

        failed_msgs = []
        show_gpt_cmd = "show_gpt" + "\n"

        try:
            enter_lk_shell_instance(self.test)
        except Exception as e:
            raise AssertionError(f"Exception occurred while switching the target to lk shell: {str(e)}")
        else:
            self.test.mtee_target._console.write(show_gpt_cmd)
            for lun_data in lun_number_and_size_reg:
                try:
                    self.test.mtee_target._console.wait_for_re(lun_data, timeout=45)
                except Exception as e:
                    failed_msgs.append(
                        {
                            "Expected_pattern": lun_data,
                            "Actual_status": "Not Found",
                            "Error_message": e,
                        }
                    )
            assert_false(
                failed_msgs,
                "Below lun data partition details were not found in serial console output':\n"
                "\n".join(
                    f"Expected_lun data pattern: {msgs['Expected_pattern']}, Actual Status: {msgs['Actual_status']}, "
                    f"Error message: {msgs['Error_message']}"
                    for msgs in failed_msgs
                ),
            )
        finally:
            self.test.mtee_target.reboot(prefer_softreboot=False, serial=True)
            wait_for_application_target(self.test.mtee_target)

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
        duplicates="IDCEVODEV-16309",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "UFS_SUPPORT_256GB_PROVISIONING"),
            },
        },
    )
    @skipIf("idcevo" not in hw_model, "Test is only applicable for IDCEVO")
    @skipIf("SP21" not in hw_variant, "Test is only applicable for SP21 HW variant")
    @skipIf("C" not in hw_revision, "Test is only applicable for C Samples")
    def test_006_verify_ufs_support_provisioning(self):
        """
        [SIT_Automated] 256GB UFS Support - Provisioning
        Steps:
            1. Enter LK mode.
            2. Run cmd "show_gpt" and wait for lun5 data to appear on console to ensure
               complete partition detail till lun 5 appeared.
            3. Open file "serial_console_ttySOCHU.log" and fetch lun0 data with size and count.
            4. Use the size, count values fetched from above step and
               calculate actual lun size using formula: size * count / 1024.
            5. Ensure actual size matches expected size for lun0 as mentioned in dict -
               "lun_part_data_and_expected_sizes_reg"
            6. Repeat step 3 to 5 for lun3 and lun5 aswell.
        """

        lun_part_data_and_expected_sizes_reg = {
            "lun0": [r".*(lun: 0).*LBA size:([0-9]+).*\n.*LBA total cnt\(([0-9]+)\)", 307200],
            "lun3": [r".*(lun: 3).*LBA size:([0-9]+).*\n.*LBA total cnt\(([0-9]+)\)", 2097152],
            "lun5": [r".*(lun: 5).*LBA size:([0-9]+).*\n.*LBA total cnt\(([0-9]+)\)", 242302976],
        }

        failed_msgs = []
        show_gpt_cmd = "show_gpt" + "\n"

        try:
            enter_lk_shell_instance(self.test)
        except Exception as e:
            raise AssertionError(f"Exception occurred while switching the target to lk shell: {str(e)}")
        else:
            self.test.mtee_target._console.write(show_gpt_cmd)
            try:
                self.test.mtee_target._console.wait_for_re(".*lun: 5.*", timeout=45)
            except Exception as e:
                raise AssertionError(
                    f"Complete partition details till lun5 didn't appeared on console log. Error occured - {e}",
                )
            for lun_pattern, expected_size in lun_part_data_and_expected_sizes_reg.values():
                lun_num, actual_size = self.calculate_actual_lun_size_from_serial_console_log_file(lun_pattern)
                if actual_size != expected_size:
                    failed_msgs.append(
                        {"Lun num": lun_num, "Actual Size": actual_size, "Expected size": expected_size},
                    )
            assert_false(
                failed_msgs,
                "Below is the list of lun numbers whose sizes are not as expected:\n" f"{failed_msgs}",
            )

        finally:
            self.test.mtee_target.reboot(prefer_softreboot=False, serial=True)
            wait_for_application_target(self.test.mtee_target)
