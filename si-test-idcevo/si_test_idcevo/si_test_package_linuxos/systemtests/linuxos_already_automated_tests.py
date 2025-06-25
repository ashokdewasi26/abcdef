# Copyright (C) 2024. BMW Car IT. All rights reserved.
import configparser
import logging
import re
from pathlib import Path
from unittest import skipIf

from mtee.testing.tools import (
    assert_false,
    assert_in,
    assert_is_not_none,
    assert_process_returncode,
    assert_regexp_matches,
    assert_true,
    metadata,
)
from si_test_idcevo.si_test_config.kernel_consts import KERNEL_LOG_TRACE_CONFIGS
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.dmverity_helpers import validate_output_using_regex_list
from si_test_idcevo.si_test_helpers.linux_commands_handlers import LinuxCommandsHandler
from si_test_idcevo.si_test_helpers.test_helpers import check_ipk_installed, skip_unsupported_ecus

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
required_target_packages = ["strace"]

ZCAT_Q_CONF_CMD = "zcat /proc/config.gz | grep -q {}=y"

BCM_ATTR_DIRECTORY_CONTENT = [
    "bcm_bw",
    "bcm_dbg_data_df_attr",
    "bcm_dbg_data_df_event",
    "bcm_dbg_data_df_filter",
    "bcm_dbg_data_df_sample",
    "bcm_dbg_data_pd",
    "dump_addr_info",
    "enable_dump_klog",
    "enable_stop_owner",
    "event_ctrl",
    "event_ctrl_help",
    "filter_id_ctrl",
    "filter_id_ctrl_help",
    "filter_others_ctrl",
    "filter_others_ctrl_help",
    "get_event",
    "get_filter_id",
    "get_filter_id_active",
    "get_filter_others",
    "get_filter_others_active",
    "get_ip",
    "get_mode",
    "get_period",
    "get_run",
    "get_sample_id",
    "get_sample_id_active",
    "get_str",
    "ip_ctrl",
    "ip_ctrl_help",
    "mode_ctrl",
    "mode_ctrl_help",
    "period_ctrl",
    "period_ctrl_help",
    "run_ctrl",
    "run_ctrl_help",
    "sample_id_ctrl",
    "sample_id_ctrl_help",
    "str_ctrl",
    "str_ctrl_help",
]

COMMON_GPIO_CONFIGS_LIST = [
    re.compile(r"gpio-0.*gpio-keys: KEY_WAKEU.*in"),
    re.compile(r"gpio-9.*hpd_gpio.*in"),
    re.compile(r"gpio-163.*inap597t_mb0_gpio.*in"),
    re.compile(r"gpio-164.*inap597t_mb1_gpio.*in"),
    re.compile(r"gpio-187.*inap_link_irq_gpio.*in"),
    re.compile(r"gpio-202.*inap597t_status0_gpi.*in"),
    re.compile(r"gpio-204.*inap_video_irq_gpio.*in"),
    re.compile(r"gpio-207.*inap597t_reset_gpio.*out"),
    re.compile(r"gpio-208.*inap597t_stall_gpio.*in"),
]

GPIO_CONFIG_LIST = {
    "idcevo": {
        "v720-EVT2 SP25-B505-C1": [
            *COMMON_GPIO_CONFIGS_LIST,
            re.compile(r"gpio-128.*sysfs.*out"),
            re.compile(r"gpio-137.*inap565t_status0_gpi.*in"),
            re.compile(r"gpio-138.*inap565t_stall_gpio.*in"),
            re.compile(r"gpio-139.*inap565t_link_irq_gp.*in"),
            re.compile(r"gpio-141.*inap565t_mb0_irq_gpi.*in"),
            re.compile(r"gpio-144.*reset.*in"),
            re.compile(r"gpio-209.*inap565t_reset_gpio.*out"),
        ],
        "v720-EVT2 SP25-B505-D1": [
            *COMMON_GPIO_CONFIGS_LIST,
            re.compile(r"gpio-137.*inap565t_status0_gpi.*in"),
            re.compile(r"gpio-138.*inap565t_stall_gpio.*in"),
            re.compile(r"gpio-139.*inap565t_link_irq_gp.*in"),
            re.compile(r"gpio-141.*inap565t_mb0_irq_gpi.*in"),
            re.compile(r"gpio-144.*reset.*out"),
            re.compile(r"gpio-205.*inap597t_faststart_g.*out"),
            re.compile(r"gpio-209.*inap565t_reset_gpio.*out"),
        ],
        "v720-EVT2 SP25-B506-C1": [
            *COMMON_GPIO_CONFIGS_LIST,
            re.compile(r"gpio-137.*inap565t_status0_gpi.*in"),
            re.compile(r"gpio-138.*inap565t_stall_gpio.*in"),
            re.compile(r"gpio-139.*inap565t_link_irq_gp.*in"),
            re.compile(r"gpio-141.*inap565t_mb0_irq_gpi.*in"),
            re.compile(r"gpio-205.*inap597t_faststart_g.*out"),
            re.compile(r"gpio-209.*inap565t_reset_gpio.*out"),
        ],
    },
    "rse26": {
        "v620 EVT1 RSE B1": [
            re.compile(r"gpio-0.*gpio-keys: KEY_WAKEU.*in"),
            re.compile(r"gpio-8.*hpd_gpio.*in"),
            re.compile(r"gpio-144.*reset.*out"),
            re.compile(r"gpio-170.*inap_link_irq_gpio.*in"),
            re.compile(r"gpio-185.*inap597t_status0_gpi.*in"),
            re.compile(r"gpio-187.*inap_video_irq_gpio.*in"),
            re.compile(r"gpio-190.*inap597t_reset_gpio.*out"),
            re.compile(r"gpio-191.*inap597t_stall_gpio.*in"),
        ],
        "v620D-EVT2 RSE-B2": [
            re.compile(r"gpio-0.*gpio-keys: KEY_WAKEU.*in"),
            re.compile(r"gpio-9.*hpd_gpio.*in"),
            re.compile(r"gpio-144.*reset.*in"),
            re.compile(r"gpio-163.*inap597t_mb0_gpio.*in"),
            re.compile(r"gpio-164.*inap597t_mb1_gpio.*in"),
            re.compile(r"gpio-187.*inap_link_irq_gpio.*in"),
            re.compile(r"gpio-202.*inap597t_status0_gpi.*in"),
            re.compile(r"gpio-204.*inap_video_irq_gpio.*in"),
            re.compile(r"gpio-207.*inap597t_reset_gpio.*out"),
            re.compile(r"gpio-208.*inap597t_stall_gpio.*in"),
        ],
    },
    "cde": {
        "v620D-EVT2 CDE-B1": [
            re.compile(r"gpio-0.*gpio-keys: KEY_WAKEU.*in"),
            re.compile(r"gpio-9.*hpd_gpio.*in"),
            re.compile(r"gpio-144.*reset.*in"),
            re.compile(r"gpio-163.*inap597t_mb0_gpio.*in"),
            re.compile(r"gpio-164.*inap597t_mb1_gpio.*in"),
            re.compile(r"gpio-187.*inap_link_irq_gpio.*in"),
            re.compile(r"gpio-202.*inap597t_status0_gpi.*in"),
            re.compile(r"gpio-204.*inap_video_irq_gpio.*in"),
            re.compile(r"gpio-207.*inap597t_reset_gpio.*out"),
            re.compile(r"gpio-208.*inap597t_stall_gpio.*in"),
        ],
        "v720-EVT2 CDE-C1": [
            *COMMON_GPIO_CONFIGS_LIST,
            re.compile(r"gpio-144.*reset.*out"),
        ],
    },
}


class TestsLinuxOs(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.target_type = cls.test.mtee_target.options.target

    def execute_and_validate_configurations_zcat(self, zcat_command, configuration_list):
        """
        Execute and validate the zcat command provided to test the kernel configurations.
        :param zcat_command: zcat command to test configuration
        :param configuration_list: list of all the configurations to test
        """
        for configuration in configuration_list:
            result = self.test.mtee_target.execute_command(zcat_command.format(configuration))
            assert_process_returncode(
                0,
                result,
                f"Failed to validate the configuration - {configuration} related feature in kernel configuration. "
                f"Got output - {result.stdout}",
            )

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="LinuxOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-9164",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "KERNEL_CONFIGURATION"),
            },
        },
    )
    def test_001_verify_performance_and_trace_kernel_configuration(self):
        """
        [SIT_Automated] Verify Perf and Trace Related Kernel Configurations
        Steps:
            1. Execute the below command for all configurations mentioned in the below list to test whether the tracing
            and performance related features are enabled in kernel.
            Tracing Configuration list- CONFIG_FTRACE, CONFIG_RCU_TRACE, CONFIG_EXYNOS_ADV_TRACER,
            CONFIG_APP_LOG_TRACER,
            Performance Configuration list- CONFIG_PERF_EVENTS, CONFIG_HAVE_PERF_EVENTS
                ~  zcat /proc/config.gz | grep -q {configuration name}=y

        Expected Result -
            - The command should run successfully
        """
        trace_performance_configuration_list = [
            "CONFIG_FTRACE",
            "CONFIG_RCU_TRACE",
            "CONFIG_EXYNOS_ADV_TRACER",
            "CONFIG_APP_LOG_TRACER",
            "CONFIG_PERF_EVENTS",
            "CONFIG_HAVE_PERF_EVENTS",
        ]
        self.execute_and_validate_configurations_zcat(ZCAT_Q_CONF_CMD, trace_performance_configuration_list)

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="LinuxOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-114979",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "KERNEL_CONFIGURATION"),
            },
        },
    )
    def test_002_verify_proc_filesystem_mount(self):
        """
        [SIT_Automated] Verify Kernel Hardening Related Kernel Configurations
        Steps:
            1. Execute the below command for all configurations mentioned in the below list to test whether the tracing
                and performance related features are enabled in kernel.
                Tracing Configuration list- CONFIG_FTRACE, CONFIG_HAVE_SYSCALL_TRACEPOINTS, CONFIG_TRACEPOINTS
                    ~ zcat /proc/config.gz | grep -q {configuration name}=y
                    ~ zcat /proc/config.gz | grep -i {configuration name}=y
        Expected Result -
            - The command should run successfully
        """
        zcat_i_conf_cmd = "zcat /proc/config.gz | grep -i {}=y"
        trace_config_list = ["CONFIG_HAVE_SYSCALL_TRACEPOINTS", "CONFIG_TRACEPOINTS"]
        self.execute_and_validate_configurations_zcat(ZCAT_Q_CONF_CMD, ["CONFIG_FTRACE"])
        self.execute_and_validate_configurations_zcat(zcat_i_conf_cmd, trace_config_list)

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="LinuxOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-13497",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "GENERAL_INFRASTRUCTURE_LOG_AND_TRACE"),
            },
        },
    )
    def test_003_verify_log_and_trace_kernel_configurations(self):
        """
        [SIT_Automated] Verify Log and Trace Related Kernel Configurations

        Steps:
        Check if log and trace related features are enabled in kernel configuration
        """
        linux_handler = LinuxCommandsHandler(self.test.mtee_target, logger)
        kernel_configuration_list = []

        kernel_configuration_list = linux_handler.search_features_in_kernel_configuration(
            features_list=KERNEL_LOG_TRACE_CONFIGS
        )
        assert_false(
            kernel_configuration_list,
            f"The following features are not configured: {kernel_configuration_list} in {KERNEL_LOG_TRACE_CONFIGS}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="LinuxOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-12829",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "KERNEL_CONFIGURATION"),
            },
        },
    )
    @skipIf(not check_ipk_installed(required_target_packages), "strace ipk not installed")
    def test_004_kernel_system_call_trace_using_strace(self):
        """
        [SIT_Automated] Verify Kernel System Call Tracing using Strace
        Steps:
            1. Verify if IPK strace is installed
            2. Run the below command in Node0 console:
                strace -e t=read ls
            3. Verify the output of command
        """
        command = "strace -e t=read ls"
        expected_regex = r"read.*177ELF.*= \d+"
        exit_msg = "exited with 0"
        # Output of strace is received in stderr. It is expected behaviour.
        _, strace, _ = self.test.mtee_target.execute_command(command, expected_return_code=0)
        assert_regexp_matches(
            strace, expected_regex, f"output of strace command not as expected. output is : {strace}"
        )
        assert_in(
            exit_msg,
            strace,
            f"strace command did not exit with 0. output is {strace}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="LinuxOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-12832",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "KERNEL_CONFIGURATION"),
            },
        },
    )
    def test_005_verify_exynos_advanced_tracker(self):
        """
        [SIT_Automated] Verify Exynos Advanced Tracer
        Steps:
            1. Check content sysfs entry for Exynos Advanced Tracer by using below command
               ls -1 /sys/devices/platform/exynos-bcmdbg/bcm_attr/
        Expected Result -
            - The output from the above step should contain all the bcm attributes mentioned
              in the list "BCM_ATTR_DIRECTORY_CONTENT".
        """
        sysfs_content_cmd = "ls -1 /sys/devices/platform/exynos-bcmdbg/bcm_attr/"
        return_stdout, _, _ = self.test.mtee_target.execute_command(sysfs_content_cmd, trim_log=False)
        assert_true(
            all(expected_out in return_stdout for expected_out in BCM_ATTR_DIRECTORY_CONTENT),
            f"bcm_attr directory content does not match the expected o/p. "
            f"Actual entries- {return_stdout}. Expected entries- {BCM_ATTR_DIRECTORY_CONTENT}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="LinuxOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-9883",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "HYPERVISOR_LOGGING_START_LOGS"),
            },
        },
    )
    def test_006_hypervisor_shall_support_passthrough_pci(self):
        """
        [SIT_Automated] Verify hypervisor shall support passthrough for PCI
        Steps:
            1. Run below commands in Android console
                cat /sys/bus/pci/devices/0000:01:00.0/vendor
                cat /sys/bus/pci/devices/0001:01:00.0/vendor
                cat /sys/bus/pci/devices/0000:01:00.0/device
                cat /sys/bus/pci/devices/0001:01:00.0/device
        Expected Output:
            1. Ensure that vendor is "0x12be" and device is "0xbd31" in the outputs from the above commands.
        """
        hypervisor_pci = {"vendor": "0x12be", "device": "0xbd31"}
        failed_commands = []
        for device_value, command_code in hypervisor_pci.items():
            for increment in range(2):
                cmd = f"cat /sys/bus/pci/devices/000{increment}:01:00.0/{device_value}"
                pci_command_output = self.test.apinext_target.execute_command(cmd, privileged=True)
                if command_code not in pci_command_output:
                    failed_commands.append(
                        {
                            "command": cmd,
                            "expected_command_code": command_code,
                            "actual_value": pci_command_output,
                        }
                    )
        assert_false(
            failed_commands,
            "Some commands failed while testing hypervisor passthrough support for PCI:\n"
            + "\n".join(
                f"Command: {cmd_info['command']}, Expected: {cmd_info['expected_command_code']},"
                f"Actual: {cmd_info['actual_value']}"
                for cmd_info in failed_commands
            ),
        )

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="LinuxOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-13544",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "SOC_PERIPHERAL_SUPPORT"),
            },
        },
    )
    def test_007_verify_hwrng_functionality(self):
        """
        [SIT_Automated] Verify Hardware Random Number Generator Functionality
        Steps:
            1. Execute below command on sys console for multiple times
               head /dev/hwrng | hexdump -n 10
        Expected Result -
            - Execution of command at step 1 produces different(i.e. random) output.
        """
        hwrng_cmd = "head /dev/hwrng | hexdump -n 10"
        output_list = []
        for _ in range(5):
            return_stdout, _, _ = self.test.mtee_target.execute_command(hwrng_cmd, expected_return_code=0)
            output_list.append(return_stdout)
        assert_true(
            len(output_list) == len(set(output_list)),
            f"Excepted distinct output wile executed the Hardware Random Number Generator command multiple times.\n"
            f"Unique output's found in {output_list}.",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="LinuxOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-15287",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "SOC_PERIPHERAL_SUPPORT"),
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["idcevo", "rse26", "cde"]), "This test isn't supported by this ECU!")
    def test_008_verify_gpio_pin_config(self):
        """
        [SIT_Automated] Verify GPIO Pin Configurations

        Steps:
        1 - Run command "cat /proc/device-tree/model"
        2 - Fetch current HW variant details from above cmd o/p
        3 - Run command "cat /sys/kernel/debug/gpio | grep gpio-"

        Expected Output:
            - Validate gpio number, name and direction from above command
            - Matches the expected result in dict GPIO_CONFIG_LIST
        """
        hw_variant, _, _ = self.test.mtee_target.execute_command("cat /proc/device-tree/model", expected_return_code=0)
        hw_variant_regex = re.compile("BMW IDCEvo .(.*?). Linux Sys VM")
        get_hw_variant = hw_variant_regex.search(hw_variant).group(1).strip()
        assert_is_not_none(
            get_hw_variant,
            f"Expected hw_variant pattern:- {hw_variant_regex.pattern} not found in device model tree. "
            f"Actual output of device model tree command:- {hw_variant}",
        )
        gpio_result = self.test.mtee_target.execute_command(
            "cat /sys/kernel/debug/gpio | grep gpio-", expected_return_code=0
        )
        get_gpio_value = GPIO_CONFIG_LIST[self.target_type][get_hw_variant]
        match = validate_output_using_regex_list(gpio_result, get_gpio_value)
        assert_true(
            match, f"Failed to validate gpio number, name and direction. output recieved : {gpio_result.stdout}"
        )
