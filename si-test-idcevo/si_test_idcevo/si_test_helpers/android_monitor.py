# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Android monitoring CPU load and MEM usage using ADB

[DEPRECATED] Currently this helper is not being used, as it was replaced by new dltlyse plugins:
    - AndroidTotalCPUPlugin
    - AndroidPackagesCPUPlugin
    - AndroidTotalMemPlugin
    - AndroidPackagesMemPlugin
"""
import logging
import os
import re
import subprocess
import threading
import time

from datetime import datetime

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

TOTAL_CPUINFO_FILE = "report_cpuinfo_total.csv"
TOTAL_MEMINFO_FILE = "report_meminfo_total.csv"
PACKAGES_CPUINFO_FILE = "report_cpuinfo_per_package.csv"
PACKAGES_MEMINFO_FILE = "report_meminfo_per_package.csv"

DATE_FORMAT = "%a %b %d %H:%M:%S.%f %Y"


class SIAndroidMonitor:
    """Class for SI android monitoring
    :param Target target: Target object
    :param List attributes: List with what we want to monitor, meminfo or cpuinfo or both
    :param List packages: Name of the packages to be monitored. If no package name is
                           specified, all packages are monitored.
    :param int interval: Interval of time to wait between samples.
    """

    def __init__(self, target, attributes, packages=None, interval=10):
        self._sample_time = interval
        self._valid_attributes = ["cpuinfo", "meminfo"]
        self._target = target
        self.packages = packages
        self._attributes = attributes
        self._monitor_threads = []
        self._stop_flags = []

    def _sanity_check(self):
        """Ensure that the attribute to monitor is valid"""
        for attribute in self._attributes:
            if attribute not in self._valid_attributes:
                raise RuntimeError(
                    "Attribute {} is not supported by performance monitor. Supported attributes are {}".format(
                        attribute, self._valid_attributes
                    )
                )

    def _setup(self):
        """Create the files required to log the data"""
        extract_file_dir = os.path.join(self._target.options.result_dir, "extracted_files")
        self.result_relative_path = os.path.join(extract_file_dir, "android_monitor")
        os.makedirs(self.result_relative_path, exist_ok=True)

        if "meminfo" in self._attributes:
            self.total_memory_attrs = {
                "Used RAM": r" Used RAM: ([\d|,]*)K",
                "Free RAM": r" Free RAM: ([\d|,]*)K",
                "Total RAM": r"Total RAM: ([\d|,]*)K",
            }
            self.mem_output_file = os.path.join(self.result_relative_path, TOTAL_MEMINFO_FILE)
            if not os.path.exists(self.mem_output_file):
                with open(self.mem_output_file, mode="w") as f:
                    f.write(f"datetime,{','.join(self.total_memory_attrs.keys())}\n")

            if self.packages:
                self.packages_mem_output_file = os.path.join(self.result_relative_path, PACKAGES_MEMINFO_FILE)
                if not os.path.exists(self.packages_mem_output_file):
                    with open(self.packages_mem_output_file, mode="w") as f:
                        f.write("datetime,Package,RSS(MB),PSS(MB),Pid\n")

        if "cpuinfo" in self._attributes:
            self.cpu_output_file = os.path.join(self.result_relative_path, TOTAL_CPUINFO_FILE)
            if not os.path.exists(self.cpu_output_file):
                with open(self.cpu_output_file, mode="w") as f:
                    f.write("datetime,CPU(%)\n")

            if self.packages:
                self.packages_cpu_output_file = os.path.join(self.result_relative_path, PACKAGES_CPUINFO_FILE)
                if not os.path.exists(self.packages_cpu_output_file):
                    with open(self.packages_cpu_output_file, mode="w") as f:
                        f.write("datetime,Package,CPU(%),Pid\n")

    def start(self):
        """Start SI android monitoring
        Create a new thread per each attribute to be monitored
        """
        self._sanity_check()
        self._setup()
        for attribute in self._attributes:
            logger.debug(f"Starting monitor for {attribute}")
            stop_flag = threading.Event()
            monitor_thread = threading.Thread(
                target=self._monitor,
                kwargs={
                    "attribute": attribute,
                    "sample_time": self._sample_time,
                    "stop_flag": stop_flag,
                },
            )
            self._monitor_threads.append(monitor_thread)
            self._stop_flags.append(stop_flag)
            monitor_thread.start()

    def parse_total_cpu_to_csv(self, output):
        """Parse the output of 'dumpsys cpuinfo' to a CSV with total CPU load

        :param output: Output decoded of a 'dumpsys cpuinfo'
        :type output: String
        """
        lines = output.splitlines()
        for line in lines:
            reg_pattern = re.compile(r"(.*)% TOTAL:")
            if match := reg_pattern.match(line):
                total_cpu_usage = float(match.group(1))
                logger.debug(f"TOTAL: {total_cpu_usage}%")
                with open(self.cpu_output_file, encoding="utf-8", mode="a") as f:
                    f.write(f"{self.cmd_time},{total_cpu_usage}\n")

    def parse_total_mem_to_csv(self, output):
        """Parse the output of 'dumpsys meminfo' to a CSV with total MEM usage

        :param output: Output decoded of a 'dumpsys meminfo'
        :type output: String
        """
        memory_attrs_dict = {
            "Used RAM": "",
            "Free RAM": "",
            "Total RAM": "",
        }

        lines = output.splitlines()
        footer = len(lines) - 10
        total_section = lines[footer:]
        for line in total_section:
            for attr, pattern in self.total_memory_attrs.items():
                if match := re.match(pattern, line):
                    memory_attrs_dict[attr] = int(str(match.group(1)).replace(",", "")) / 1024  # to MB

        # Only write if all values were parsed
        if all(memory_attrs_dict.values()):
            with open(self.mem_output_file, encoding="utf-8", mode="a") as f:
                line = ",".join([f"{value}" for _, value in memory_attrs_dict.items()])
                f.write(f"{self.cmd_time},{line}\n")
        else:
            logger.debug(f"Couldn't parse all memory values. {memory_attrs_dict}")

    def parse_cpu_per_process_to_csv(self, output):
        """Parse the output of 'dumpsys cpuinfo' to a CSV with info per package

        :param output: Output decoded of a 'dumpsys cpuinfo'
        :type output: String
        """
        lines = output.splitlines()
        for line in lines:
            reg_pattern = re.compile(r"(?P<cpu_load>\d+\.\d+|\d+)% (?P<pid>\d+)\/(?P<package>.*?)(?::|@)")
            if match := reg_pattern.search(line):
                cpu_load = float(match.group("cpu_load"))
                pid = match.group("pid")
                package = match.group("package")
                if package in self.packages:
                    with open(self.packages_cpu_output_file, encoding="utf-8", mode="a") as f:
                        f.write(f"{self.cmd_time},{package},{cpu_load},{pid}\n")

    def process_section(self, section):
        """Process a section of the output from 'dumpsys meminfo' to a dict

        :param section: Section of output decoded of a 'dumpsys cpuinfo'
        :type section: String
        :return: Dict with package and corresponding memory.
        :rtype: Dict
        """
        mem_list_values = {}
        pattern = re.compile(r"(?P<mem>[\d|,]*)K: (?P<package>.*) \(pid (?P<pid>\d*).*")
        for line in section:
            if match := pattern.search(line):
                mem = int(str(match.group("mem")).replace(",", "")) / 1024
                pid = match.group("pid")
                package = match.group("package")
                if package in self.packages:
                    mem_list_values.update({package: {"mem": mem, "pid": pid}})
                    if len(mem_list_values) == len(self.packages):
                        return mem_list_values
        logger.debug("Unable to find all packages")
        return mem_list_values

    def parse_mem_per_process_to_csv(self, output):
        """Parse the output of 'dumpsys meminfo' to a CSV with info per package

        :param output: Output decoded of a 'dumpsys meminfo'
        :type output: String
        """
        mem_pss = {}
        mem_rss = {}

        body = output.split(3 * os.linesep)
        sections = body[1].split(2 * os.linesep)
        for section in sections:
            lines = section.splitlines()
            if "Total RSS by process" in lines[0]:
                mem_rss.update(self.process_section(lines))
            if "Total PSS by process" in lines[0]:
                mem_pss.update(self.process_section(lines))

        for package in self.packages:
            if package in mem_pss.keys() or package in mem_rss.keys():
                with open(self.packages_mem_output_file, encoding="utf-8", mode="a") as f:
                    f.write(
                        f"{self.cmd_time},{package},{mem_rss.get(package).get('mem')},"
                        f"{mem_pss.get(package).get('mem')},{mem_pss.get(package).get('pid')}\n"
                    )

    def _monitor(self, attribute, sample_time, stop_flag):
        """Monitor specified attribute and generates a report"""
        while not stop_flag.is_set():
            try:
                cmd = ["adb", "shell", "dumpsys", attribute]
                output = subprocess.check_output(cmd)
                self.cmd_time = datetime.now().strftime(DATE_FORMAT)
                if attribute == "cpuinfo":
                    self.parse_total_cpu_to_csv(output.decode())
                    if self.packages:
                        self.parse_cpu_per_process_to_csv(output.decode())
                elif attribute == "meminfo":
                    self.parse_total_mem_to_csv(output.decode())
                    if self.packages:
                        self.parse_mem_per_process_to_csv(output.decode())
            except Exception as e:
                logger.debug(f"Unable to extract, {e}")
            time.sleep(sample_time)

    def stop(self):
        """Stop all monitor threads"""
        logger.info("Stopping performance monitoring...")
        for stop_flag in self._stop_flags:
            logger.debug("Setting stop flag for performance monitor thread")
            stop_flag.set()
        for monitor_thread in self._monitor_threads:
            if monitor_thread:
                logger.debug("Waiting for performance monitor thread to finish")
                monitor_thread.join()
                monitor_thread = None
