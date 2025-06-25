# Copyright (C) 2020 CTW PT. All rights reserved.
import os
import re
import warnings
import logging
import time

from collections import namedtuple

from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import (
    assert_process_returncode,
    assert_false,
    assert_less,
    assert_true,
    WritableRootfs,
)

from si_test_apinext.util.utils import match_string_with_regex

logger = logging.getLogger(__name__)
target = TargetShare().target

REGISTERED_METRIC_CLASSES_HEADERS = {
    "cpu_temperature": ["value"],
    "cpu_usage": ["total_usage_percent", "system_utilization"],
    "disk_partitioning": ["mounted", "size", "used", "free", "percent"],
    "mem_usage": ["usage_percent", "available", "used", "total"],
    "io_throughput_sequential": ["rate", "operation"],
    "io_throughput_random": ["rate", "operation"],
    "ram_usage_component": ["used_ram"],
    "flash": ["duration", "success"],
    "boot_time_measurements": ["value"],
}


class MetricsPublisher:
    """Publish metrics helper"""

    def __init__(self, metric_class, metrics_folder_path=None):
        if metric_class not in REGISTERED_METRIC_CLASSES_HEADERS.keys():
            raise AssertionError(
                "Metric class not registered into list, which contains: {}".format(REGISTERED_METRIC_CLASSES_HEADERS)
            )

        folder = (
            metrics_folder_path if metrics_folder_path else os.path.join(target.options.result_dir, "extracted_files")
        )
        self.metrics_file_path = os.path.join(folder, "{}.csv".format(metric_class))

        if not os.path.exists(self.metrics_file_path):
            self.save_to_metrics_file(
                "{},{}".format(
                    metric_class, ",".join(header for header in REGISTERED_METRIC_CLASSES_HEADERS[metric_class])
                )
            )

    def save_to_metrics_file(self, entry, append_new_line=True):
        """Save content into file"""
        with open(self.metrics_file_path, "a") as metrics_file:
            metrics_file.write(entry)
            if append_new_line:
                metrics_file.write("\n")


class TargetSystemStats:
    """Query system status from target"""

    def cpu_times(self, cpustat):
        """Constructs a named tuple representing the following system-wide CPU times
        (user, nice, system, idle, iowait, irq, softirq, steal, guest, guest_nice)

        :param string cpustat: file content of /proc/stat
        :returns: named tuple representing system-wide cpu times
        :rtype: scputimes
        """
        # Number of clock ticks per second
        clock_ticks = 100
        scputimes_ntuple = namedtuple(
            "scputimes",
            ["user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal", "guest", "guest_nice"],
        )
        values = cpustat.splitlines()[0].split()
        fields = values[1 : len(scputimes_ntuple._fields) + 1]  # noqa: E203
        fields = [float(x) / clock_ticks for x in fields]
        return scputimes_ntuple(*fields)

    def calc_cpu_usage(self, t1, t2):
        """Calculates system-wide CPU usage as a percentage
        between two instances of cpu times.

        :param scputimes t1: named tuple of system wide cpu time
        :param scputimes t2: named tuple of system wide cpu time
        :returns: system-wide CPU usage as a percentage
        :rtype: float
        """
        cpu_usage_ntuple = namedtuple("cpu_usage", ["total_usage", "base_system_usage"])
        cpu_usage_percentage = []

        t1_all = sum(t1)
        t1_busy = t1_all - t1.idle
        t1_base_system_usage = t1.system

        t2_all = sum(t2)
        t2_busy = t2_all - t2.idle
        t2_base_system_usage = t2.system

        # this usually indicates a float precision issue
        if t2_busy <= t1_busy:
            return 0.0

        busy_delta = t2_busy - t1_busy
        base_system_usage_delta = t2_base_system_usage - t1_base_system_usage

        logger.debug("busy_delta : {}".format(busy_delta))
        all_delta = t2_all - t1_all
        logger.debug("all_delta : {}".format(all_delta))

        # Total cpu usage calculation
        cpu_usage_percentage.append(self._usage_percent(busy_delta, all_delta, 1))
        # System cpu usage calculation
        cpu_usage_percentage.append(self._usage_percent(base_system_usage_delta, all_delta, 1))

        total_cpu_usage = self._usage_percent(busy_delta, all_delta, 1)
        base_system_cpu_usage = self._usage_percent(base_system_usage_delta, all_delta, 1)

        return cpu_usage_ntuple(total_cpu_usage, base_system_cpu_usage)

    def virtual_memory(self, meminfo):
        """Constructs a named tuple representing the following system-wide virtual memory.
        (total, available, percent, used, free, active, inactive, buffers, cached, shared )

        :param string meminfo: file content of /proc/meminfo
        :returns: named tuple representing system-wide virtual memory.
        :rtype: svmem
        """
        # pylint: disable=too-many-branches

        svmem_ntuple = namedtuple(
            "svmem",
            ["total", "available", "percent", "used", "free", "active", "inactive", "buffers", "cached", "shared"],
        )
        unit_multiplier = 1024  # (kB)
        total = free = available = buffers = shared = cached = active = inactive = None
        for line in meminfo.splitlines():
            if total is None and line.startswith("MemTotal:"):
                total = int(line.split()[1]) * unit_multiplier
            elif free is None and line.startswith("MemFree:"):
                free = int(line.split()[1]) * unit_multiplier
            elif available is None and line.startswith("MemAvailable:"):
                available = int(line.split()[1]) * unit_multiplier
            elif buffers is None and line.startswith("Buffers:"):
                buffers = int(line.split()[1]) * unit_multiplier
            elif shared is None and (
                line.startswith("shared:") or line.startswith("MemShared:") or line.startswith("Shmem:")
            ):
                shared = int(line.split()[1]) * unit_multiplier
            elif cached is None and line.startswith("Cached:"):
                cached = int(line.split()[1]) * unit_multiplier
            elif active is None and line.startswith("Active:"):
                active = int(line.split()[1]) * unit_multiplier
            elif inactive is None and line.startswith("Inactive:"):
                inactive = int(line.split()[1]) * unit_multiplier
        missing = []
        if cached is None:
            missing.append("cached")
            cached = 0
        if active is None:
            missing.append("active")
            active = 0
        if inactive is None:
            missing.append("inactive")
            inactive = 0
        if shared is None:
            missing.append("shared")
            shared = 0
        if missing:
            msg = "%s memory stats couldn't be determined and %s set to 0" % (
                ", ".join(missing),
                "was" if len(missing) == 1 else "were",
            )
            warnings.warn(msg, RuntimeWarning)

        # From https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=34e431b0ae398fc54ea69ff85ec700722c9da773 # noqa: E501
        # We calculate the memory usage with MemTotal-MemAvailable
        used = total - available

        percent = self._usage_percent(used, total, _round=1)
        return svmem_ntuple(total, available, percent, used, free, active, inactive, buffers, cached, shared)

    @staticmethod
    def _usage_percent(used, total, _round=None):
        """Calculate percentage usage of 'used' against 'total'."""
        try:
            ret = (used / total) * 100
        except ZeroDivisionError:
            ret = 0.0 if isinstance(used, float) or isinstance(total, float) else 0
        return ret if _round is None else round(ret, _round)

    def get_memory_usage(self):
        """Get overall memory usage of the target"""
        result = target.execute_command("cat /proc/meminfo")
        assert_process_returncode(0, result, "Unable to read from /proc/meminfo")
        return self.virtual_memory(result.stdout)

    @staticmethod
    def get_kernel_memory_usage():
        """Get memory usage by kernel"""
        sections_of_interest_usage_mb = ["Slab", "KernelStack"]
        kernel_memory_usage_bytes = 0
        result = target.execute_command("cat /proc/meminfo")
        assert_process_returncode(0, result, "Unable to read from /proc/meminfo")
        for soi in sections_of_interest_usage_mb:
            soi_regex = re.compile(".*{}:.* ([0-9]+) kB.*".format(soi))
            kernel_memory_usage_bytes += (
                float(
                    match_string_with_regex(
                        result.stdout, soi_regex, "Usage for {} failed to be parsed".format(soi)
                    ).group((1))
                )
                * 1000
            )
        return kernel_memory_usage_bytes

    @staticmethod
    def get_kernel_modules_memory_usage():
        """Get memory usage by kernel modules"""
        modules_usage_regex = re.compile("[a-zA-z0-9\_]+ ([0-9]+) [0-9]+ .*")  # noqa: W605
        modules_reported_usage_bytes = []
        result = target.execute_command("cat /proc/modules")
        assert_process_returncode(0, result, "Unable to read from /proc/modules")
        for module in result.stdout.split("\n"):
            modules_reported_usage_bytes.append(
                float(
                    match_string_with_regex(
                        module,
                        modules_usage_regex,
                        "Failed to get Krnel module's RAM usage for entry: {}".format(module),
                    ).group(1)
                )
            )

        if not modules_reported_usage_bytes:
            raise AssertionError("No data from Kernel Modules' RAM usage exists")

        return sum(modules_reported_usage_bytes)

    def get_cpu_usage(self, interval=60):
        """Calculate CPU usage over time interval

        :param interval: Time (in seconds) between checks.
        :return: CPU usage. See system_stats.
        """
        cputimes = []
        wait_time = interval
        for _ in range(2):
            result = target.execute_command("cat /proc/stat")
            assert_process_returncode(0, result, "Unable to read from /proc/stat")
            cputimes.append(self.cpu_times(result.stdout))
            time.sleep(wait_time)
            wait_time = 0

        cpu_usage = self.calc_cpu_usage(cputimes[0], cputimes[1])

        return cpu_usage

    def get_cpu_temperature(self):
        """Get target's CPU temperature

        :return int: CPU temperature in degrees celsius
        """
        result = target.execute_command("cat /sys/class/thermal/thermal_zone0/temp")
        assert_process_returncode(0, result, "Unable to get CPU temperature from system")
        return int(result.stdout) / 1000

    def get_disk_usage(self):
        """Get target's disk usage"""
        result = target.execute_command("df -kP", shell=True)
        assert_process_returncode(0, result, "Running 'df' command on target failed")

        # Expected output:
        # Filesystem                         1024-blocks      Used Available Capacity Mounted on
        # /dev/sda1                               240972    107723    120808      48% /boot
        # ...

        return [x.split() for x in result.stdout.split("\n")][1:]

    @staticmethod
    def get_disk_size(device):
        """Get disk size via fdisk command
        :param device: name of the disk device, as in /dev/<device>
        :return: Disk size in bytes.
        """
        disk_size_regex = re.compile(".*Disk /dev/{}: .*, ([0-9]+) bytes.*".format(device))
        disk_size_idx = 1
        result = target.execute_command("fdisk -l")
        assert_process_returncode(0, result, "Error executing command: fdisk -l")
        reported_size = disk_size_regex.search(result.stdout)
        if reported_size is None:
            raise AssertionError("Could not determine size of {}. fdisk returned: {}".format(device, result))
        disk_size = int(
            match_string_with_regex(result.stdout, disk_size_regex, "Could not determine disk size").group(
                disk_size_idx
            )
        )
        return disk_size

    @staticmethod
    def perform_sequential_io_throughput_run(throughput_test_parameters, residual_file_to_remove=""):
        """Get sequential IO throughput
        :param throughput_test_parameters: dictionary containing parameters to be passed to dd command on target
        (if, of, bs, count) as well as calculated size of generated file in MB. Example:
        DD_OPERATION_PARAMETERS = {
            "size_megabytes": 268,
            "if": "/dev/zero",
            "of": "/tmp/test_write.bin",
            "bs": "4k",
            "count": "64k",
        }
        :param residual_file_to_remove: path of the generated file to be removed after throughput test, if applicable
        :return: Transfer speed in MB/s
        """
        execution_time_regex = re.compile(".*real.*([0-9]+)m ([0-9]+\.?[0-9]+)s.*")  # noqa: W605
        execution_time_regex_group_minutes = 1
        execution_time_regex_group_seconds = 2
        with WritableRootfs(target):
            result = target.execute_command(
                "time dd if={} of={} bs={} count={} {}".format(
                    throughput_test_parameters["if"],
                    throughput_test_parameters["of"],
                    throughput_test_parameters["bs"],
                    throughput_test_parameters["count"],
                    throughput_test_parameters["additional_parameters"],
                )
            )
        assert_process_returncode(0, result, "Unable to perform dd command")
        if residual_file_to_remove:
            target.remove(residual_file_to_remove)
            assert_false(
                target.exists(residual_file_to_remove),
                "Unable to remove file: {}".format(residual_file_to_remove),
            )
        execution_time = match_string_with_regex(
            result.stderr, execution_time_regex, "Unable to obtain execution time of operation"
        )

        execution_time_seconds = float(execution_time.group(execution_time_regex_group_seconds)) + (
            60.0 * float(execution_time.group(execution_time_regex_group_minutes))
        )

        transfer_speed_megabytes_per_second = (
            float(throughput_test_parameters["size_megabytes"]) / execution_time_seconds
        )
        logger.debug("Calculated speed: %s MB/s", transfer_speed_megabytes_per_second)

        return transfer_speed_megabytes_per_second

    @staticmethod
    def perform_random_io_throughput_run(throughput_test_parameters, residual_file_to_remove=""):
        """Get random IO throughput
        :param throughput_test_parameters: parameters to be passed to fio tool
        :param residual_file_to_remove: path of the generated file to be removed after throughput test, if applicable
        :return: Matrix with parsed values from tool's stdout with re.findall, regarding measured rate (IOPS) for
        read and/or write operations.
        """
        test_operation_iops_regex = ".*(read|write): IOPS=([0-9]+),.*"
        tool_name = "fio"
        tool_target_path = os.path.join(os.sep, target.user_data_folder, "systemtests", tool_name, tool_name)

        assert_true(
            target.exists(tool_target_path),
            "Required tool called {} not found in expected path: {}".format(tool_name, tool_target_path),
        )

        with WritableRootfs(target):
            result = target.execute_command("{} {}".format(tool_target_path, throughput_test_parameters))
        assert_process_returncode(0, result, "Unable to perform fio command")
        if residual_file_to_remove:
            target.remove(residual_file_to_remove)
            assert_false(
                target.exists(residual_file_to_remove),
                "Unable to remove file: {}".format(residual_file_to_remove),
            )
        extracted_report = re.findall(test_operation_iops_regex, result.stdout)
        if not extracted_report:
            raise AssertionError("Unable to determine random IO throughput test results")
        return extracted_report

    def cpu_usage_metric_collect_publish_check(self, metric_class, metric_name, maximum_threshold, sampling_interval):
        """Get target CPU usage, publish metric and check value against threshold"""
        metrics_collector = MetricsPublisher(metric_class, metrics_folder_path=target.extract_dir)

        # Measure cpu usage
        cpu_usage = self.get_cpu_usage(sampling_interval)
        logger.debug("cpu_usage : {}".format(cpu_usage))

        metrics_collector.save_to_metrics_file(
            "{metric_name},{total_usage}, {system_utilization}".format(
                metric_name=metric_name,
                total_usage=str(cpu_usage.total_usage),
                system_utilization=str(cpu_usage.base_system_usage),
            )
        )

        # cpu system usage within specified threshold
        assert_less(
            cpu_usage.base_system_usage,
            maximum_threshold,
            "CPU base system usage exceeds {} %".format(maximum_threshold),
        )

    def ram_usage_metric_collect_publish(self, metric_class, metric_name):
        """Get target RAM usage and publish metric"""
        metrics_collector = MetricsPublisher(metric_class, metrics_folder_path=target.extract_dir)

        # measure memory usage
        memory_used = self.get_memory_usage()

        metrics_collector.save_to_metrics_file(
            "{metric_name},{percent_usage},{available},{used},{total}".format(
                metric_name=metric_name,
                percent_usage=str(memory_used.percent),
                available=str(memory_used.available),
                used=str(memory_used.used),
                total=str(memory_used.total),
            )
        )

    def cpu_temperature_metric_collect_publish_check(self, metric_class, metric_name, maximum_threshold):
        """Get target CPU temperature, publish metric and check value against threshold"""
        metrics_collector = MetricsPublisher(metric_class, metrics_folder_path=target.extract_dir)

        cpu_temp = self.get_cpu_temperature()

        metrics_collector.save_to_metrics_file(f"{metric_name},{cpu_temp}")

        assert_less(cpu_temp, maximum_threshold, "CPU temperature exceeds {} C.".format(maximum_threshold))

    def disk_usage_metric_collect_publish(self, metric_class):
        """Get target disk usage and publish metric on csv file"""
        metrics_collector = MetricsPublisher(metric_class, metrics_folder_path=target.extract_dir)

        disk_usage = self.get_disk_usage()
        for line in disk_usage:
            if not line[0].startswith("/dev"):
                # Only report physical partitions
                continue

            if line[0].startswith("/dev/loop"):
                # Skip squashfs loop mounts
                continue

            metrics_collector.save_to_metrics_file(
                "{disk_partitioning},{mounted},{size},{used},{free},{percent}".format(
                    disk_partitioning=line[0],
                    mounted=line[5],
                    size=str(1024 * int(line[1])),
                    used=str(1024 * int(line[2])),
                    free=str(1024 * int(line[3])),
                    percent=line[4].rstrip("%"),
                )
            )

    def sequential_io_throughput_metrics_publish(self, metric_name, rate, operation):
        """Publish metrics reported by IO Throughput (sequential) test cases
        :param: rate: transfer speed in MB/s
        :operation: type of operation (Read/Write) covered by test case
        """
        metrics_collector = MetricsPublisher("io_throughput_sequential", metrics_folder_path=target.extract_dir)
        metrics_collector.save_to_metrics_file(f"{metric_name},{rate},{operation}")

    def random_io_throughput_metrics_publish(self, metric_name, rate, operation):
        """Publish metrics reported by IO Throughput (random) test cases
        :param: rate: measured rate in IOPS
        :operation: type of operation (Read/Write) covered by test case
        """
        metrics_collector = MetricsPublisher("io_throughput_random", metrics_folder_path=target.extract_dir)
        metrics_collector.save_to_metrics_file(f"{metric_name},{rate},{operation}")

    def ram_usage_per_component_publish(self, metric_name, metric_value):
        """Publish entry regarding RAM usage of component
        :param metric_name: component name
        :param metric_value: used RAM by component
        """
        metrics_collector = MetricsPublisher("ram_usage_component", metrics_folder_path=target.extract_dir)
        metrics_collector.save_to_metrics_file(f"{metric_name},{metric_value}")

    def boot_time_measurements_publish(self, metric_name, metric_value):
        """Publish entry regarding boot time duration of target
        :param metric_name: type of measured time
        :param metric_value: time measured in seconds
        """
        metrics_collector = MetricsPublisher("boot_time_measurements", metrics_folder_path=target.extract_dir)
        metrics_collector.save_to_metrics_file(f"{metric_name},{metric_value}")
