# Copyright (C) 2024. BMW Car It. All rights reserved.
"""Verify setting and validating of CPU Frequency for all Modes to all Clusters"""
import configparser
import logging
from pathlib import Path
from unittest import SkipTest

from mtee.testing.tools import assert_equal, assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

DEFAULT_FREQ_CMD = "cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq"
CUR_FREQ_CMD = "cat /sys/devices/platform/cpufreq/cur_freq"
CPU_INFO_CMD = "cat /sys/devices/system/cpu/cpufreq/policy*/cpuinfo_cur_freq"
DEFAULT_MODE_FREQ = "2112000"
EFFICIENT_MODE_FREQ = "1824000"
THERMAL_MODE_FREQ = "1152000"
LOW_POWER_MODE_FREQ = "576000"

CPU_DEFAULT_FREQ = {
    "idcevo": {
        "B3": "2112000",
        "C1": "2112000",
        "D1": "2112000",
    },
    "rse26": {
        "B1": "2304000",
        "B2": "2304000",
    },
    "cde": {
        "B1": "2400000",
        "C1": "2112000",
    },
}


class TestsVerifyCpuFrequency(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)
        cls.target_type = cls.test.mtee_target.options.target
        cls.hw_revision = cls.test.mtee_target.options.hardware_revision
        cls.default_cpu_freq, _, _ = cls.test.mtee_target.execute_command(DEFAULT_FREQ_CMD)
        return_stdout, _, _ = cls.test.mtee_target.execute_command(CPU_INFO_CMD)
        cls.clusters_frequencies = return_stdout.strip().splitlines()
        cls.total_no_clusters_avail = len(cls.clusters_frequencies)

    def teardown(self):
        logger.info("Verify default setting of CPU frequency is set to 'Boost Mode' to all clusters")

        for cluster_num in range(self.total_no_clusters_avail):
            if self.clusters_frequencies[cluster_num] == self.default_cpu_freq:
                logger.debug(f"Default setting of CPU frequency for Cluster {cluster_num} is set to 'Boost Mode'")
            else:
                set_freq_cmd = f"echo {cluster_num} {self.default_cpu_freq} > /sys/devices/platform/cpufreq/cur_freq"
                self.test.mtee_target.execute_command(set_freq_cmd)

    def set_verify_cpu_freq_all_clusters(self, mode_freq):
        """
        Setting CPU Mode Frequency for different Clusters and verifying the set Mode Frequency
        :param mode_freq: (int)Frequency Mode
        """
        for num in range(self.total_no_clusters_avail):
            set_freq_cmd = f"echo {num} {mode_freq} > /sys/devices/platform/cpufreq/cur_freq"

            self.test.mtee_target.execute_command(set_freq_cmd, expected_return_code=0)

            return_stdout, _, _ = self.test.mtee_target.execute_command(CUR_FREQ_CMD)
            total_current_freq = return_stdout.strip().splitlines()
            assert_equal(
                total_current_freq[num],
                f"cluster{num}: frequency: {mode_freq}",
                f"Got an unexpected output of current frequency for cluster {num}: {return_stdout}",
            )

            return_stdout, _, _ = self.test.mtee_target.execute_command(CPU_INFO_CMD)
            total_cpu_info = return_stdout.strip().splitlines()
            assert_equal(
                total_cpu_info[num],
                mode_freq,
                f"Got an unexpected output of cpu information for cluster {num}: {return_stdout}",
            )

    def check_target_eligibility(self):
        """Check if the test is applicable to the target and skip it if not"""
        if self.target_type in CPU_DEFAULT_FREQ:
            if self.hw_revision not in CPU_DEFAULT_FREQ[self.target_type]:
                raise SkipTest(f"This test is not applicable for {self.hw_revision} samples")
        else:
            raise SkipTest(f"This test is not applicable for {self.target_type} target")

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
        duplicates="IDCEVODEV-53183",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "POWER_MANAGEMENT"),
            },
        },
    )
    def test_001_cpu_governer_to_performance(self):
        """
        [SIT_Automated] Verify if CPU Governer is set to 'performance' on SYS Kernel
        Steps:
            1 - Run the following command on Node0:
                # cat /sys/devices/system/cpu/cpufreq/policy0/scaling_available_governors
        """
        result = self.test.mtee_target.execute_command(
            "cat /sys/devices/system/cpu/cpufreq/policy0/scaling_available_governors"
        )
        logger.debug(f"Available governors: {result.stdout}")
        assert_true("performance" in result.stdout, "CPU governor is not set to performance")

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
        duplicates="IDCEVODEV-53184",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "POWER_MANAGEMENT"),
            },
        },
    )
    def test_002_verify_cpu_governer(self):
        """
        [SIT_Automated] Verify if CPU Governer is set to 'performance' on ANDROID Kernel

        Steps:
            1 - Run the following command on Node0:
                # cat /sys/module/cpufreq/parameters/default_governor
            2 - Verify if content of above file is "performance"
        """
        result = self.test.mtee_target.execute_command(
            "cat /sys/module/cpufreq/parameters/default_governor", expected_return_code=0
        )
        logger.debug(f"Available governors: {result.stdout}")
        assert_true("performance" in result.stdout, "CPU governor is not set to performance on ANDROID Kernel")

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
        duplicates="IDCEVODEV-53185",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "POWER_MANAGEMENT"),
            },
        },
    )
    def test_003_verify_default_cpu_frequency(self):
        """
        [SIT_Automated] Verify Default CPU Frequency after Bootup is Set to 'Boost Mode'
        Steps:
            1. Check if this test is applicable to the target and skip it if not
            2. Run the following command to verify default CPU frequency after bootup is set to "Boost Mode":
                # cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq
        Expected Outcome:
            1. CPU frequency is equal to expected 'Boost Mode' frequency

        Note: Boost mode frequency is ECU dependant. See CPU_DEFAULT_FREQ.
        """

        self.check_target_eligibility()

        return_stdout, _, _ = self.test.mtee_target.execute_command(DEFAULT_FREQ_CMD)
        logger.debug(f"Default CPU Frequency is set to: {return_stdout} Hz")

        expected_default_freq = CPU_DEFAULT_FREQ[self.target_type][self.hw_revision]
        assert_true(
            expected_default_freq == return_stdout,
            "Default CPU Frequency is not set to Boost Mode.\n"
            f"Expected frequency: {expected_default_freq} Hz. Obtained frequency: {return_stdout} Hz",
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
        duplicates="IDCEVODEV-54945",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "POWER_MANAGEMENT"),
            },
        },
    )
    def test_004_cpu_frequency_efficient_mode(self):
        """
        [SIT_Automated] Verify setting of CPU frequency for 'Efficient Mode' (e.g. 1824 MHz) to all clusters
        Steps:
            1 - Run following command to verify setting of CPU frequency for "Efficient Mode" to cluster 0:
                # echo 0 1824000 > /sys/devices/platform/cpufreq/cur_freq
            2 - In the output check the currently set frequency values as cluster0: frequency: 1824000:
                # cat /sys/devices/platform/cpufreq/cur_freq
            3 - In the output check the currently set frequency values as 1824000:
                # cat /sys/devices/system/cpu/cpufreq/policy*/cpuinfo_cur_freq
            4 - Repeat the above three steps for cluster 1 i.e
                # echo 1 1824000 > /sys/devices/platform/cpufreq/cur_freq
                # cat /sys/devices/platform/cpufreq/cur_freq
                # cat /sys/devices/system/cpu/cpufreq/policy*/cpuinfo_cur_freq
        """

        logger.info("Verify setting of CPU frequency for 'Efficient Mode' to all clusters")
        self.set_verify_cpu_freq_all_clusters(EFFICIENT_MODE_FREQ)

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
        duplicates="IDCEVODEV-54947",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "POWER_MANAGEMENT"),
            },
        },
    )
    def test_005_cpu_frequency_boost_mode(self):
        """
        [SIT_Automated] Verify setting of CPU frequency for 'Boost Mode' (e.g. 2112 MHz) to all clusters
        Steps:
            1. Check if this test is applicable to the target and skip it if not
            2. Run following command to verify setting of CPU frequency for "Boost Mode" to cluster 0:
                # echo 0 "expected_freq" > /sys/devices/platform/cpufreq/cur_freq
            3. In the output check the currently set frequency values as cluster0: frequency: "expected_freq":
                # cat /sys/devices/platform/cpufreq/cur_freq
            4. In the output check the currently set frequency values as "expected_freq":
                # cat /sys/devices/system/cpu/cpufreq/policy*/cpuinfo_cur_freq
            5. Repeat the above three steps for cluster 1 i.e
                # echo 1 "expected_freq" > /sys/devices/platform/cpufreq/cur_freq
                # cat /sys/devices/platform/cpufreq/cur_freq
                # cat /sys/devices/system/cpu/cpufreq/policy*/cpuinfo_cur_freq
        Expected Outcome:
            1. All clusters have the expected frequency
        """
        self.check_target_eligibility()

        logger.info("Verify setting of CPU frequency for 'Boost Mode' to all clusters")
        expected_freq = CPU_DEFAULT_FREQ[self.target_type][self.hw_revision]
        self.set_verify_cpu_freq_all_clusters(expected_freq)

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
        duplicates="IDCEVODEV-54949",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "POWER_MANAGEMENT"),
            },
        },
    )
    def test_006_cpu_frequency_thermal_throttle_mode(self):
        """
        [SIT_Automated] Verify setting of CPU frequency for 'Thermal Throttle Mode' (e.g. 1152 MHz) to all clusters
        Steps:
            1 - Run following command to verify setting of CPU frequency for "Thermal Throttle Mode" to cluster 0:
                # echo 0 1152000 > /sys/devices/platform/cpufreq/cur_freq
            2 - In the output check the currently set frequency values as cluster0: frequency: 1152000:
                # cat /sys/devices/platform/cpufreq/cur_freq
            3 - In the output check the currently set frequency values as 1152000:
                # cat /sys/devices/system/cpu/cpufreq/policy*/cpuinfo_cur_freq
            4 - Repeat the above three steps for cluster 1 i.e
                # echo 1 1152000 > /sys/devices/platform/cpufreq/cur_freq
                # cat /sys/devices/platform/cpufreq/cur_freq
                # cat /sys/devices/system/cpu/cpufreq/policy*/cpuinfo_cur_freq
        """

        logger.info("Verify setting of CPU frequency for 'Thermal Throttle Mode' to all clusters")
        self.set_verify_cpu_freq_all_clusters(THERMAL_MODE_FREQ)

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
        duplicates="IDCEVODEV-54942",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "POWER_MANAGEMENT"),
            },
        },
    )
    def test_007_cpu_frequency_low_power_mode(self):
        """
        [SIT_Automated] Verify setting of CPU frequency for "Low Power Mode" (e.g. 576 MHz) to all clusters
        Steps:
            1 - Set the frequency value to 576 MHz for all available clusters -
                # echo 0 576000 > /sys/devices/platform/cpufreq/cur_freq
                # echo 1 576000 > /sys/devices/platform/cpufreq/cur_freq
            2 - Check the currently set frequency values -
                # cat /sys/devices/platform/cpufreq/cur_freq
                # cat /sys/devices/system/cpu/cpufreq/policy*/cpuinfo_cur_freq
        Expected Results:
            1. CPU frequency for Low Power Mode could be set for all clusters using CPU DVFS interface
        """

        logger.info("Verify setting of CPU frequency for 'Low Power Mode' to all clusters")
        self.set_verify_cpu_freq_all_clusters(LOW_POWER_MODE_FREQ)
