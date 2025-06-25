# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Verify if all kernel configurations related to kernel crash handling are enabled"""
import configparser
import logging
import os
import re
import time
from pathlib import Path
from unittest import skipIf


from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import (
    TimeoutCondition,
    assert_false,
    assert_is_not_none,
    assert_true,
    metadata,
    run_command,
)
from si_test_idcevo.si_test_config.kernel_consts import (
    DEBUG_SNAPSHOT_DRIVER_CONFIGS,
    KERNEL_PROCESS_CRASH_CONFIGS,
    SAMSUNG_EXYNOS_CONFIGS,
)
from si_test_idcevo.si_test_helpers.file_path_helpers import (
    verify_file_in_host_with_timeout,
    verify_file_in_target_with_timeout,
)
from si_test_idcevo.si_test_helpers.linux_commands_handlers import LinuxCommandsHandler
from validation_utils.utils import CommandError, TimeoutError

EXPECTED_CRASHES = "expected_crashes"

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

SET_COREDUMP_SIZE_CMD = "ulimit -c unlimited"
SET_COREDUMP_NAME_CMD = "sysctl kernel.core_pattern=/tmp/core%e.%p.%h.%t"

COREDUMP_ECUID_CMD_REGEX_DICT = {
    "idcevo": {
        "service_name": "safety_A",
        "service_grep_command": "ps | grep safety_A",
        "coredump_file_regex": re.compile(r".*coresafety_A.*"),
    },
    "rse26": {
        "service_name": "log-trace-manager",
        "service_grep_command": "ps | grep log-trace-manager",
        "coredump_file_regex": re.compile(r".*corelog.*trace.*manag.*rse26.*"),
    },
    "cde": {
        "service_name": "log-trace-manager",
        "service_grep_command": "ps | grep log-trace-manager",
        "coredump_file_regex": re.compile(r".*corelog.*trace.*manag.*cde.*"),
    },
}

CRASH_TRIGGER_CMD = "echo c > /proc/sysrq-trigger"
KERNEL_CRASH_PATTERN = r".*Kernel panic - not syncing: sysrq triggered crash.*"

COREDUMP_ECUID_COMMON_PATTERNS = {
    "grep_cmd": "ps | grep sm_monit*",
    "service_pid_reg": re.compile(r"(\d+).*sm_monit"),
    "log_path": "/var/data/node0/health/coredumper/dumps/",
    "log_folder_reg": re.compile(r"monitor.*"),
    "log_file_reg": re.compile(r"core.*monitor.*gz"),
}

COREDUMP_ECUID_CMD_REGEX_PATTERNS = {
    "rse26": COREDUMP_ECUID_COMMON_PATTERNS,
    "cde": COREDUMP_ECUID_COMMON_PATTERNS,
    "idcevo": {
        "grep_cmd": "ps | grep safety_A*",
        "service_pid_reg": re.compile(r"(\d+).*safety_A"),
        "log_path": "/var/data/node0/health/coredumper/dumps/",
        "log_folder_reg": re.compile(r"safety_A.*"),
        "log_file_reg": re.compile(r"core.*safety_A.*gz"),
    },
}


class TestsKernelCrash(object):
    target = TargetShare().target
    linux_handler = LinuxCommandsHandler(target, logger)
    target_type = target.options.target
    hw_revision = target.options.hardware_revision

    def fetch_expected_patterns_based_on_target(self):
        """Based on target_type under test, this functions extracts expected safety service process patterns,
         coredump folder/files related data from dict "COREDUMP_ECUID_CMD_REGEX_PATTERNS"
         and returns the data via multiple variables.

        :return process_cmd: grep cmd to fetch safety service process
        :return service_pid_reg: safety service pid pattern
        :return folder_path: coredump folder root path
        :return folder_name_reg: coredump folder name pattern
        :return file_name_reg: coredump log file name pattern
        """

        if self.target_type in COREDUMP_ECUID_CMD_REGEX_PATTERNS.keys():
            process_cmd = COREDUMP_ECUID_CMD_REGEX_PATTERNS[self.target_type]["grep_cmd"]
            service_pid_reg = COREDUMP_ECUID_CMD_REGEX_PATTERNS[self.target_type]["service_pid_reg"]
            folder_path = COREDUMP_ECUID_CMD_REGEX_PATTERNS[self.target_type]["log_path"]
            folder_name_reg = COREDUMP_ECUID_CMD_REGEX_PATTERNS[self.target_type]["log_folder_reg"]
            file_name_reg = COREDUMP_ECUID_CMD_REGEX_PATTERNS[self.target_type]["log_file_reg"]
            return process_cmd, service_pid_reg, folder_path, folder_name_reg, file_name_reg
        else:
            raise AssertionError(f"This target type {self.target_type} isn't supported for this test.")

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
        duplicates="IDCEVODEV-13501",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "GENERAL_INFRASTRUCTURE_CRASH_HANDLING"),
            },
        },
    )
    def test_001_verify_kernel_crash(self):
        """
        [SIT_Automated] Verify Kernel Crash Handling Related Kernel Configurations

        Steps:
            1 - Check configurations to enable manual kernel crash trigger (to aid testing)
            2 - Check configurations related to debug snapshot driver
            3 - Check other configurations related to Samsung Exynos
        """

        logger.info("Starting test to verify kernel crash handling.")

        invalid_features_list = self.linux_handler.search_features_in_kernel_configuration(
            features_list=DEBUG_SNAPSHOT_DRIVER_CONFIGS
        )
        assert_false(
            invalid_features_list,
            f"The following features are not configured: {invalid_features_list} in {DEBUG_SNAPSHOT_DRIVER_CONFIGS}",
        )
        invalid_features_list = self.linux_handler.search_features_in_kernel_configuration(
            features_list=SAMSUNG_EXYNOS_CONFIGS
        )
        assert_false(
            invalid_features_list,
            f"The following features are not configured: {invalid_features_list} in {SAMSUNG_EXYNOS_CONFIGS}",
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
        duplicates="IDCEVODEV-13498",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "GENERAL_INFRASTRUCTURE_CRASH_HANDLING"),
            },
        },
    )
    def test_002_verify_kernel_process_crash(self):
        """
        [SIT_Automated] Verify Process Crash Handling Related Kernel Configurations

        Steps:
            1 - Execute "zcat /proc/config.gz" and grep for following output
                - "CONFIG_COREDUMP=y"
                - "CONFIG_ELF_CORE=y"
                - "CONFIG_STATIC_USERMODEHELPER is not set"
                - "CONFIG_ALLOW_DEV_COREDUMP=y"
            Expected outcome:
                All the above string is observed after executing the above command.
        """
        invalid_features_list = self.linux_handler.search_features_in_kernel_configuration(
            features_list=KERNEL_PROCESS_CRASH_CONFIGS
        )
        assert_false(
            invalid_features_list,
            f"The following features are not configured: {invalid_features_list} in {KERNEL_PROCESS_CRASH_CONFIGS}",
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
        duplicates="IDCEVODEV-13680",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "GENERAL_INFRASTRUCTURE_CRASH_HANDLING"),
            },
        },
    )
    def test_003_verify_service_crash(self):
        """
        [SIT_Automated] Verify Coredump Generation after Service Crash

        Steps:
        1. Set coredump file size limit and name using commands,
            size - "ulimit -c unlimited"
            name - "sysctl kernel.core_pattern=/tmp/core%e.%p.%h.%t"
        2. Wait for 20 seconds
        3. Find the process ID for safetyA service (for IDCEvo) or log-trace-manager service (for RSE26/CDE),
        using the command:
            for IDCEvo - "ps | grep safetyA"
            for RSE/CDE - "ps | grep log-trace-manager"
        4. Kill the respective service using the command:
            "kill -11 <service_pid obtained in step 3>"
        5. Verify whether the coredump file for the killed service is generated in the '/tmp' directory within 5
        seconds after killing the service.

        Expected result:
            Coredump file of the killed service is present in the '/tmp' directory
        """
        if self.target_type in COREDUMP_ECUID_CMD_REGEX_DICT.keys():
            service_name = COREDUMP_ECUID_CMD_REGEX_DICT[self.target_type]["service_name"]
            service_fetch_cmd = COREDUMP_ECUID_CMD_REGEX_DICT[self.target_type]["service_grep_command"]
            coredump_file_name_regex = COREDUMP_ECUID_CMD_REGEX_DICT[self.target_type]["coredump_file_regex"]
        else:
            raise AssertionError(f"This target type {self.target_type} isn't supported for this test.")

        self.target.execute_command(SET_COREDUMP_SIZE_CMD, expected_return_code=0)
        self.target.execute_command(SET_COREDUMP_NAME_CMD, expected_return_code=0)

        if self.target_type == "idcevo":
            time.sleep(40)
        else:
            time.sleep(20)

        result_stdout, _, _ = self.target.execute_command(service_fetch_cmd, expected_return_code=0)

        service_pid = str(result_stdout).strip().split(" ")[0]
        logger.debug(f"{service_name} service PID: {service_pid}")

        if service_pid:
            kill_service_cmd = f"kill -11 {service_pid}"
            self.target.execute_command(kill_service_cmd, expected_return_code=0)
        else:
            raise RuntimeError(f"Failed to fetch {service_name} service PID")

        coredump_file_path = None
        timeout = 5
        coredump_generation_timeout_condition = TimeoutCondition(timeout)

        while coredump_generation_timeout_condition:
            result_stdout, _, _ = self.target.execute_command("ls -la /tmp/core*")
            paths = str(result_stdout).split()
            for path in paths:
                if re.search(coredump_file_name_regex, path):
                    coredump_file_path = path
                    break
            if coredump_file_path:
                break

        assert_true(
            coredump_file_path,
            f"Coredump file did not get generated within {timeout} seconds after killing {service_name} service",
        )
        result_stdout, _, _ = self.target.execute_command(f"stat -c %s {coredump_file_path}")
        assert_true(int(result_stdout) != 0, f"Coredump file size for {service_name} is zero")

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
        duplicates="IDCEVODEV-13628",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "GENERAL_INFRASTRUCTURE_CRASH_HANDLING"),
            },
        },
    )
    @skipIf(
        (target_type == "idcevo" or target_type == "rse26" or target_type == "cde"),
        "Test not applicable for this ECU",
    )
    def test_004_verify_kernel_crash_trigger(self):
        """
        [SIT_Automated] Verify Kernel Crash Trigger via /proc/sysrq-trigger
        Steps:
            - Trigger kernel crash by executing below command
               ~ # echo c > /proc/sysrq-trigger
            - Open serial_console_ttySOCHU.log
            - Search pattern KERNEL_CRASH_PATTERN
            - Create and populate 'expected_crashes.csv' with the current lifecycle stage.

            Expected Results -
            - serial_console_ttySOCHU.log file should display contain below string
               "Kernel panic - not syncing: sysrq triggered crash"
        """

        logger.info("Starting test to trigger kernel crash via /proc/sysrq-trigger")
        try:
            return_stdout, _, return_code = self.target.execute_command(CRASH_TRIGGER_CMD)
        except (CommandError, TimeoutError) as capture_exception:
            logger.debug(f"Timeout error occurred while capturing logs: {capture_exception}")
        finally:
            self.target.reboot(prefer_softreboot=False)
            self.target._recover_ssh(record_failure=False)

        log_file = Path(self.target.options.result_dir) / "serial_console_ttySOCHU.log"
        log_message_found = False

        with open(log_file) as file_handler:
            for file_line in file_handler.readlines():
                if re.compile(KERNEL_CRASH_PATTERN).search(file_line):
                    logger.info("Trigger kernel crash log message found")
                    log_message_found = True
                    break

        assert_true(log_message_found, "Failed to trigger kernel crash via /proc/sysrq-trigger")

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
        duplicates="IDCEVODEV-13722",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "GENERAL_INFRASTRUCTURE_CRASH_HANDLING"),
            },
        },
    )
    @skipIf(
        (target_type == "idcevo" and "C" not in hw_revision),
        "Test not applicable for non C1 EVO samples",
    )
    def test_005_verify_correct_core_dump_obtained_after_service_crash(self):
        """
        [SIT_Automated] Verify Extraction of Coredump via DLT
        Steps:
            1- Reboot the device
            2- Fetch the expected values of coredump folder / files and safety service process patterns
               as per target type from dict - "COREDUMP_ECUID_CMD_REGEX_PATTERNS"
            3- On target, grep the safety service process details via Linux console.
            4- Kill the safety service process via pid fetched from above o/p.
            5- Use coredump folder / files patterns from step 1 to ensure log file is generated on target.
            6- Ensure log file is transferred to host PC via DLT automatically.
            7- Check the log file size on host PC and target and make sure it's same.
        """

        # Rebooting the target to make sure all services are up and running.
        self.target.reboot(prefer_softreboot=False)
        self.target._recover_ssh(record_failure=False)

        # Fetch the expected coredump folder / files and safety service process patterns as per target type
        process_cmd, service_id, folder_path, folder_name, file_name = self.fetch_expected_patterns_based_on_target()

        # On target, grep the safety service process details via Linux console.
        # Wait for 40 sec as safety service may take time to  start.
        safety_service_pid = None
        timer = TimeoutCondition(40)
        while timer:
            result_stdout, _, _ = self.target.execute_command(process_cmd)
            safety_service_pid = service_id.search(str(result_stdout))
            if safety_service_pid is not None:
                time.sleep(1)
                break
        assert_is_not_none(
            safety_service_pid,
            f"Service Safety process not found after waiting for 40 sec on reboot. "
            f"Grep cmd executed: {process_cmd}. Actual o/p found: {result_stdout}",
        )

        # Kill the safety service process via pid fetched from above o/p
        kill_early_cluster_cmd = f"kill -11 {safety_service_pid.group(1)}"
        self.target.execute_command(kill_early_cluster_cmd)

        # Ensure log file is generated on target.
        target_folder_path, target_filename = verify_file_in_target_with_timeout(
            self.target, folder_path, folder_name, file_name
        )
        assert_is_not_none(
            target_filename, "Core dumps logs didn't get generated as expected on killing service process"
        )

        # Ensure log file is transferred to host PC via DLT automatically.
        filepath_on_pc = os.path.join(self.target.options.result_dir, "extracted_files", "Coredumps", target_filename)
        assert_true(
            verify_file_in_host_with_timeout(filepath_on_pc),
            f"File {target_filename} not found at path {filepath_on_pc} on Host PC.",
        )

        # Get the log file size from target
        file_size_on_target, _, _ = self.target.execute_command(f"stat -c %s {target_folder_path}")
        logger.info(f"File Size in target- {file_size_on_target}")

        # Get the log file size from host PC.
        file_size_on_pc, _, _ = run_command(f"stat -c %s {filepath_on_pc}", shell=True)
        logger.info(f"File size on host PC {file_size_on_pc}")

        # Ensure the log file size on host PC and target are same.
        assert_true(
            int(file_size_on_target) == int(file_size_on_pc),
            f"File size on target = {file_size_on_target} bytes, "
            f"does not matches with the file size on PC i.e {file_size_on_pc} bytes after transfer",
        )
