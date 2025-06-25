# Copyright (C) 2023. CTW PT. All rights reserved.
"""Metric extraction post test"""
import configparser
import csv
import glob
import logging
import os
import re
import sys
import xml.etree.ElementTree as ET  # noqa: N817
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import assert_is_none, assert_not_equal, assert_true, metadata, nottest
from nose.plugins.skip import SkipTest

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")

METRICS_FILE_NAME = "metrics.csv"

target = None

share = TargetShare()
if share and hasattr(share, "target"):
    target = share.target

logger = logging.getLogger(__name__)


@metadata(
    testsuite=["BAT", "domain", "SI", "SI-performance", "IDCEVO-SP21"],
    component="tee_idcevo",
    domain="IDCEvo Test",
    asil="None",
    testmethod="Analyzing Requirements",
    testtype="Requirements-based test",
    testsetup="SW-Component",
    categorization="functional",
    priority="1",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": config.get("FEATURES", "TEE_FEATURE"),
        },
    },
)
class ExtractMetricPostTest(object):
    """Extract metrics from log post tests"""

    __test__ = True

    def __init__(self):
        self.result_dir = None
        self.log_file_path = None
        self.serial_file_path = None
        self.extract_file_dir = None

        if target:
            self.result_dir = target.options.result_dir

            self.log_file_path = target.options.log_file
            logger.info(f"Using log_file_path: {self.log_file_path}")

            # There isn't currently a "public" serial console getter method.
            # Using _console which is configured by TargetGen22:start_serial().
            # There can be multiple "serials" but we use only the "main" one.
            if hasattr(target, "_console"):
                console = target._console
                logger.info(f"Using console: {console}")
                if console.dumpfilename:
                    logger.info(f"Using console: {console} - dumpfilename: {console.dumpfilename}")
                    self.serial_file_path = console.dumpfilename

            self.extract_file_dir = os.path.join(self.result_dir, "extracted_files")

    def test_serial_console_file_exists(self):
        """Tests if the serial console exists (when detected/specified) and contains any data."""

        if not self.serial_file_path:
            # Serial console is optional
            raise SkipTest("Test requires a serial file and none was detected/specified")

        assert_not_equal(os.stat(self.serial_file_path).st_size, 0, f"Serial log is empty: {self.serial_file_path}")

    def test_serial_console_bootloader_to_kernel_time(self):
        """Extracts time to boot from bootloader (U-Boot) to kernel using serial console"""

        if not self.serial_file_path:
            # Serial console is optional
            raise SkipTest("Test requires a serial file and none was detected/specified")

        log_ts_format = "%H:%M:%S,%f"  # too bad it isn't any standard/known/iso format timestamp

        with open(self.serial_file_path) as file_handler:
            ts_u_boot = None
            kernel_starting = None
            kernel_booting = None
            for file_line in file_handler.readlines():
                tokens = file_line.strip().split()
                if len(tokens) > 1:
                    token_ts, *token_others = tokens

                    try:
                        ts = datetime.strptime(token_ts, log_ts_format)
                    except:  # noqa
                        # This is intentionally ignored: the logs have no strict pattern with timestamp
                        continue

                    if "U-Boot" in file_line:
                        ts_u_boot = ts
                        logger.debug(f"{ts:{log_ts_format}} - {token_others}")
                    elif "Starting kernel" in file_line:
                        kernel_starting = ts
                        if ts_u_boot:
                            delta = kernel_starting - ts_u_boot
                            logger.debug(f"{ts:{log_ts_format}} - {token_others} (delta={delta})")
                            self.metric_handler("kernel_starting", delta.total_seconds())
                    elif "Booting Linux" in file_line:
                        kernel_booting = ts
                        if ts_u_boot:
                            delta = kernel_booting - ts_u_boot
                            logger.debug(f"{ts:{log_ts_format}} - {token_others} (delta={delta})")
                            self.metric_handler("kernel_booting", delta.total_seconds())

    def test_serial_console_kernel_panics(self):
        """Check serial console for unwanted kernel panics"""

        if not self.log_file_path:
            # When target exists the target.options.log_file is used (see __init__)
            raise SkipTest("Test requires log file and none was specified/detected")

        kernel_panic_regex = re.compile(r".*Kernel.*panic.*")
        intended_crash = "sysrq triggered crash"
        with open(self.serial_file_path) as file_handler:
            for line_num, file_line in enumerate(file_handler, 1):
                regex_data = kernel_panic_regex.search(file_line)
                if intended_crash not in file_line:
                    assert_is_none(
                        regex_data,
                        f"Found Kernel panic at line {line_num} on serial log. Here is the line: '{file_line}'",
                    )
                else:
                    logger.info(f"Found an intended kernel panic on line {line_num}: '{file_line}'")

    def test_counter(self):
        """Counts number of tests from each domain"""

        if not self.result_dir:
            # When target exists the target.options.result_dir is used (see __init__)
            raise SkipTest("Test requires results dir and none was specified/detected")

        if target.has_capability(TE.test_bench.rack):
            test_results_files = glob.glob(os.path.join("/ws/results", "targetmanager*test_results.xml"))
        else:
            # When results dir was specified (directly or via target) it *must* test results xunit (xml)
            test_results_files = glob.glob(os.path.join(self.result_dir, "targetmanager*test_results.xml"))
        assert_true(len(test_results_files) == 1, "Missing test results xunit file")
        test_results = test_results_files[0]
        logger.debug(f"Using xunit result file: {test_results}")

        tree = ET.parse(test_results)
        testcases = tree.getroot()

        total_tests = testcases.attrib["tests"]

        domains = defaultdict(int)
        for testcase in testcases:
            for metadata_items in testcase:
                items = metadata_items.findall("item")
                for item in items:
                    if item.attrib["name"] == "domain":
                        domains[item.text] += 1

        header_names = ["domain", "count"]
        csv_filename = "domain_test_counter.csv"
        with open(os.path.join(self.extract_file_dir, csv_filename), "a", newline="") as csv_handler:
            writer = csv.DictWriter(csv_handler, header_names)
            writer.writeheader()
            for domain, count in domains.items():
                writer.writerow({header_names[0]: domain, header_names[1]: count})

            writer.writerow({header_names[0]: "total_domain_tests", header_names[1]: str(sum(domains.values()))})
            writer.writerow({header_names[0]: "total_tests", header_names[1]: total_tests})

    def metric_handler(self, metric, data):
        header_names = ["metric", "data"]
        csv_filename = METRICS_FILE_NAME

        if not isinstance(data, Iterable):
            data = [data]

        with open(os.path.join(self.extract_file_dir, csv_filename), "a", newline="") as csv_handler:
            writer = csv.DictWriter(csv_handler, header_names)
            if not csv_handler.tell():
                writer.writeheader()
            for data_point in data:
                row = dict(zip(header_names, [metric, data_point]))
                writer.writerow(row)

    @staticmethod
    def flash(data, csv_handler):
        """Callback that handle flash time metric
        :param list data: data to process
        :param file csv_handler: csv file descriptor
        """
        header_names = ["target", "duration", "success", "retries"]
        writer = csv.DictWriter(csv_handler, header_names)
        writer.writeheader()

        pattern = re.compile(r"duration=([0-9.]*) success=(True|False) retries=(\d)")
        for data_unit in data:
            result = pattern.search(data_unit)
            if result is not None:
                writer.writerow(
                    {
                        header_names[0]: "idcevo",
                        header_names[1]: result.group(1),
                        header_names[2]: result.group(2),
                        header_names[3]: result.group(3),
                    }
                )

    @staticmethod
    @nottest
    def test_module(data, csv_handler):
        """Callback that handle test_module time metric
        :param list data: data to process
        :param file csv_handler: csv file descriptor
        """
        header_names = ["module", "duration"]
        writer = csv.DictWriter(csv_handler, header_names)
        writer.writeheader()

        pattern = re.compile(r"module='(?P<module>.*)' duration=(?P<duration>[0-9.]*)")
        for data_unit in data:
            result = pattern.search(data_unit)
            if result is not None:
                writer.writerow({header_names[0]: result.group(1), header_names[1]: result.group(2)})


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <result_dir> <log_file_path> <serial_file_path>")  # noqa: T201
        sys.exit(1)

    logging.basicConfig()
    logger.setLevel(logging.DEBUG)

    extractor = ExtractMetricPostTest()
    extractor.result_dir = sys.argv[1]
    extractor.log_file_path = sys.argv[2]
    extractor.serial_file_path = sys.argv[3]
    extractor.extract_file_dir = os.path.join(extractor.result_dir, "extracted_files")

    test_attrs = [attr for attr in dir(extractor) if attr.startswith("test_")]
    for test_attr in test_attrs:
        attr = getattr(extractor, test_attr)
        if callable(attr) and hasattr(attr, "__self__"):  # only callable bound methods
            attr()
