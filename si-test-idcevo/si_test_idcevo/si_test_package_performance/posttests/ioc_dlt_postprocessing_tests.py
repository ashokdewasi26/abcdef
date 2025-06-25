# Copyright (C) 2025. CTW BMW PT. All rights reserved.
"""IOC non verbose DLT post processing tests"""
import configparser
import logging
import os
import re

from pathlib import Path
from unittest import SkipTest

from dlt import dlt
from mtee.metric import MetricLogger
from mtee.testing.tools import metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

metric_logger = MetricLogger()


@metadata(testsuite=["SI", "SI-performance"])
class IOCdltPostProcessingPostTest(object):
    __test__ = True

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)
        cls.ioc_nonverbose_file_path = os.path.join(
            cls.test.mtee_target.options.result_dir, "serial_console_IOC.log_non_verbose.dlt"
        )
        if not os.path.exists(cls.ioc_nonverbose_file_path):
            raise SkipTest("Unable to find IOC non verbose DLT file, skipping")
        cls.ioc_dlt_msgs = dlt.load(cls.ioc_nonverbose_file_path)
        cls.ioc_dlt_msgs.generate_index()
        logger.info(f"IOC DLT contains: {cls.ioc_dlt_msgs.counter_total} messages")

    @metadata(
        testsuite=["SI", "SI-performance"],
        component="tee_idcevo",
        domain="Performance",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-458609",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "SYSTEM_SHUTDOWN_AFTER_PONR"),
            },
        },
    )
    def test_001_system_shutdown_after_point_of_no_return_kpis(self):
        """
        [SIT_Automated] System shutdown time after Point Of No Return (PONR)

        Steps:
            - Read IOC non verbose dlt file
            - Find the following payloads:
                - Type of shutdown received: 5
                - SoC reached sleep state
            - Compute the time between them in case the lifecycle is bigger than 60 seconds
            - Log the metrics

        Expected outcome:
            - File can be open and read
            - At least one metric can be collected
        """
        shutdown_received_regex = re.compile(r".*Type of shutdown received:.*5.*")
        sleep_state_regex = re.compile(r".*SoC reached sleep state.*")

        number_of_valid_metrics_found = 0
        shutdown_time = 0
        for msg in self.ioc_dlt_msgs:
            if shutdown_received_regex.search(msg.payload_decoded) and msg.tmsp > 60:
                shutdown_time = msg.tmsp
            if sleep_state_regex.search(msg.payload_decoded) and shutdown_time:
                metric_logger.publish(
                    {"name": "system_shutdown_after_ponr", "time_value": round(msg.tmsp - shutdown_time, 4)}
                )
                shutdown_time = 0
                number_of_valid_metrics_found += 1

        assert number_of_valid_metrics_found > 0, (
            f"No valid system shutdown metrics were found on IOC non verbose DLT {self.ioc_nonverbose_file_path} "
            f"Expecting to find following payloads: {shutdown_received_regex}, {sleep_state_regex}",
        )
