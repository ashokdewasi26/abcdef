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
import subprocess
from pathlib import Path
from unittest import skipIf

from mtee.testing.test_environment import TEST_ENVIRONMENT as TE, require_environment, require_environment_setup
from mtee.testing.tools import (
    assert_false,
    assert_is_not_none,
    assert_regexp_matches,
    metadata,
    run_command,
)
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.dmverity_helpers import disable_dm_verity
from si_test_idcevo.si_test_helpers.linux_commands_handlers import LinuxCommandsHandler
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
required_target_packages = ["devmem2", "virtio-utils"]
TEST_ENVIRONMENT = (TE.target.hardware.idcevo,)


@require_environment(*TEST_ENVIRONMENT)
class TestsSystemSwNpu(object):
    test = TestBase.get_instance()
    test.setup_base_class()
    hw_revision = test.mtee_target.options.hardware_revision
    hw_model = test.mtee_target.options.target
    linux_helpers = LinuxCommandsHandler(test.mtee_target, logger)

    @classmethod
    @require_environment_setup(*TEST_ENVIRONMENT)
    def setup_class(cls):
        disable_dm_verity()
        cls.test.mtee_target.remount()
        enntest64_path = Path(os.sep) / "resources" / "EnnTest_64.tar.gz"
        cls.linux_helpers.extract_tar(enntest64_path)

    def setup(self):
        self.test.mtee_target.remount()

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
        duplicates="IDCEVODEV-13480",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "INTER_VM_COMMUNICATION_SHARED_MEMORY"),
            },
        },
    )
    def test_001_verify_vmq_and_vsmq_device_operational(self):
        """
        [SIT_Automated] Verify VMQ, VSMQ device is operational
        Steps:
            1. Execute "ls -l /proc/nk/vmq*" on Node0 console and validate in the console logs
            2. Execute "cat /proc/nk/vmq*" on Node0 console and validate in the console logs
            3. Execute "ls -l /proc/nk/vsmq*" on Node0 console and validate in the console logs
            4. Execute "cat /proc/nk/vsmq*" on Node0 console and validate in the console logs
        """
        vmq_file_path = ["/proc/nk/vmq.vvideo2-be", "/proc/nk/vmq.vnpu-be", "/proc/nk/vmq.bufq-be"]
        vmq_cat_regex = r"VMQ driver[\s\S]*?RX-Info\|TX-Info"
        vsmq_cat_regex = r"(?:Rx-Msg\s+Rx-Free\s+Rx-IRQ\s+Rx-Sysconf\s+Tx-Sysconf\s+Reset\s+Name|vgpu-arb-comm)\s*"
        vsmq_regex = r"/proc/nk/vsmq-vgpu-arb-comm(.*)"

        vmq_status = [self.test.mtee_target.exists(location) for location in vmq_file_path]
        if not all(vmq_status):
            missing_vmq_files = [[file, exists] for file, exists in zip(vmq_file_path, vmq_status) if not exists]
            raise AssertionError(f"The following VMQ files aren't present on target: {missing_vmq_files}")

        vmq_cat_cmd = "cat /proc/nk/vmq*"
        vmq_cat_result, _, _ = self.test.mtee_target.execute_command(vmq_cat_cmd, expected_return_code=0)
        assert_regexp_matches(
            vmq_cat_result,
            vmq_cat_regex,
            f"Failed to validate device is operational using {vmq_cat_cmd}."
            f"Expected VMQ_CAT_REGEX :- {vmq_cat_regex} in Actual vmq_cat_result - {vmq_cat_result}",
        )

        vmsq_cmd = "ls -l /proc/nk/vsmq*"
        vmsq_ls_stdout, _, _ = self.test.mtee_target.execute_command(vmsq_cmd, expected_return_code=0)
        assert_regexp_matches(
            vmsq_ls_stdout,
            vsmq_regex,
            f"Failed to validate device is operational using {vmsq_cmd}."
            f"Expected vmsq regex:- {vsmq_regex} in Actual log output- {vmsq_ls_stdout}",
        )

        vsmq_cat_cmd = "cat /proc/nk/vsmq*"
        vsmq_cat_result, _, _ = self.test.mtee_target.execute_command(vsmq_cat_cmd, expected_return_code=0)
        vmsq_matches = re.findall(vsmq_cat_regex, vsmq_cat_result, re.DOTALL)
        assert_is_not_none(vmsq_matches, f"Failed to validate device is operational using {vsmq_cat_cmd}.")

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
        duplicates="IDCEVODEV-10447",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "BOOTLOADER_SECURITY_SOC_BASIC_SECURITY"),
                ],
            },
        },
    )
    @skipIf("D" in hw_revision, "Test is not applicable for D Samples")
    def test_003_verify_otp_test_slot_get_revert(self):
        """
        [SIT_Automated] OTP test - slot_get_revert
        Steps:
            1. Go to fastboot mode
            2. Run on host PC
                "fastboot oem otp slot_get_revert 1"
                "fastboot oem otp slot_get_revert 2"
                "fastboot oem otp slot_get_revert 3"
            3. Validate Target output.
        Expected output:
            1. "Slot_get_revert slot {iteration}" found after executing the fastboot command
        """
        failed_commands = []
        try:
            self.test.mtee_target.switch_to_flashing_mode()
            for iteration in range(1, 4):
                cmd = f"fastboot oem otp slot_get_revert {iteration}"
                self.test.mtee_target._console.clear_read_queue()
                run_command(cmd, shell=True, stderr=subprocess.STDOUT)
                lk_response = self.test.mtee_target._console.wait_for_re(
                    f".*SUCCESS: slot_get_revert slot {iteration} = 0"
                )
                logger.debug(f"Command Status: {lk_response}\n Target Output: {str(lk_response.message)}")
                if not lk_response:
                    failed_commands.append(
                        {
                            "command": cmd,
                            "command status": lk_response,
                            "Target output": str(lk_response.message),
                        }
                    )
            assert_false(
                failed_commands,
                "Some commands failed while testing 'fastboot oem otp slot_get_revert':\n"
                "\n".join(
                    f"Command: {cmd_info['command']}, command execution status: {cmd_info['command status']}, "
                    f"Target output:{cmd_info['Target output']}"
                    for cmd_info in failed_commands
                ),
            )
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
        duplicates="IDCEVODEV-7165",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "HARDWARE_ACCESS_PASSTHROUGH_SUPPORT"),
                ],
            },
        },
    )
    def test_004_verify_spi_devices(self):
        """[SIT_Automated] Verify SPI devices availability
        Steps:
            1. Reboot target
            2. Execute 'dmesg | grep spi' and check the spi available ports
            3. In the directory /sys/class/spi_master/ check if the available ports are present
            by running 'ls -la' command"""
        devices_plataform = r"-> ../../devices/platform/(.*)"
        spi_port = r"\[\s*\d+\.\d+\]SYS\[\s*T1\] exynosauto-spi \w+\.spi: PORT (\d+) fifo_lvl_mask = 0x[0-9a-f]+"

        self.test.mtee_target.reboot(prefer_softreboot=False)
        wait_for_application_target(self.test.mtee_target)
        result = self.test.mtee_target.execute_command("dmesg | grep spi")
        missing_ports = []

        existing_ports = re.findall(spi_port, result.stdout, re.MULTILINE)
        if existing_ports:
            command_output = self.test.mtee_target.execute_command("ls -la", cwd="/sys/class/spi_master/")
            logger.info(f"Existing command_output ports: {command_output.stdout}")
            device_existing_ports = re.findall(devices_plataform, command_output.stdout, re.MULTILINE)
            for port in existing_ports:
                if not any(f"spi{port}" in device_port for device_port in device_existing_ports):
                    missing_ports.append(port)
        else:
            raise AssertionError(f"No SPI ports found, command output: {result.stdout}")
        assert_false(missing_ports, f"Missing SPI ports: {missing_ports}")
