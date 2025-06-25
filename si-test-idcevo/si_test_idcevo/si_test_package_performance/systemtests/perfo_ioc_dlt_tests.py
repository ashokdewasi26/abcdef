# Copyright (C) 2024. BMW CAR IT. All rights reserved.
"""SOC startup time"""
import configparser
import logging
import re
from pathlib import Path

from mtee.metric import MetricLogger
from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase

# Config parser reading data from config file.
config = configparser.ConfigParser()

config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
metric_logger = MetricLogger()

SOC_RELEASE_PATTERN = re.compile(r"SOC_RST_OUT_Q setting time ms:us  (?P<time>\d+ : \d+)")
REBOOT_CYCLES = 5


@metadata(
    testsuite=["SI", "SI-performance", "IDCEVO-SP21"],
    component="tee_idcevo",
    domain="Performance",
    asil="None",
    testmethod="Analyzing Requirements",
    testtype="Requirements-based test",
    testsetup="SW-Component",
    categorization="functional",
    priority="1",
    duplicates="IDCEVODEV-7779",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": config.get("FEATURES", "SOC_STARTUP_TIME"),
        },
    },
)
class TestSocStartuptime:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        if not cls.test.mtee_target.connectors.ioc_dlt.broker.isAlive():
            cls.test.mtee_target.connectors.ioc_dlt.start()

    def convert_to_seconds(self, time_str):
        """
        Converts a time duration from milliseconds:microseconds format to seconds.

        :param time_str: Time duration in milliseconds:microseconds format
        :return: Time duration in seconds
        """
        ms, us = time_str.split(":")
        time_in_seconds = int(ms) * 1e-3 + int(us) * 1e-6
        return time_in_seconds

    def test_001_measure_soc_time(self):
        """
        [SIT_Automated] Start of SOC, measured since the wake-up of the unit

        **Steps**
            - Reset HU using power-supply to force restart of IOC
            - Search in DLT logs for SOC_RELEASE_PATTERN
            - Get the time mentioned in the payload and store it
            - Repeat the above 3 steps for 5 times
            - Calculate the average time taken
            - Publish the average time taken in the metric file

        """

        for reboot in range(REBOOT_CYCLES):
            with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker, filters=[("SYST", "")]) as dlt_detector:
                logger.debug(f"Performing reboot no: {reboot + 1}")
                self.test.mtee_target.reboot(prefer_softreboot=False)
                soc_release_msg = dlt_detector.wait_for(
                    attrs=dict(payload_decoded=SOC_RELEASE_PATTERN),
                    drop=True,
                )
                match = SOC_RELEASE_PATTERN.search(soc_release_msg[0].payload_decoded)
                if match:
                    logger.debug(f"Found SOC startup time message: {soc_release_msg[0].payload_decoded}")
                    time_taken = match.group("time")
                    start_time = self.convert_to_seconds(time_taken)
                    metric_logger.publish(
                        {"name": "perfo_ioc_dlt", "kpi_name": "soc_startup_time", "value": start_time}
                    )
