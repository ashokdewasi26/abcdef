# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Reboot the target 10 times and measure CPU load and RAM usage"""
import configparser
import logging
import os
import time
from pathlib import Path
from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import assert_equal, metadata

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

REBOOT_CYCLES = 10


@metadata(
    testsuite=["BAT", "domain", "SI", "SI-performance"],
    component="tee_idcevo",
    domain="Stability",
    asil="None",
    testmethod="Analyzing Requirements",
    testtype="Requirements-based test",
    testsetup="SW-Component",
    categorization="functional",
    priority="1",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": config.get("FEATURES", "STABILITY_KPI_MONITORING"),
        },
    },
)
class TestMultipleRebootPerformance(object):
    target = TargetShare().target
    number_of_failed_iterations = 0
    msg_dict = {}

    def test_001_multiple_reboot(self):
        """[SIT_Automated] Reboot the target 10 times and measure CPU load and RAM usage

        Steps:
            - Wait 90 seconds before rebooting
            - Reboot the headunit to application mode with softreboot
            - Wait until the target is rebooted and SSH is available
        """

        # Added for testing purpose
        metric_extractors_definition_filepath = Path(os.sep) / "resources" / "android_metric_extractors.json"

        for iteration in range(REBOOT_CYCLES):
            try:
                # Run reboot cycle
                logger.debug(f"Starting reboot cycle {iteration}")
                time.sleep(90)
                self.target.reboot()
                self.target.extract_metric_artifacts(
                    extractors_definition_filepath=metric_extractors_definition_filepath
                )
            except Exception as error_msg:
                self.number_of_failed_iterations += 1
                self.msg_dict.update({f"Cycle_{iteration}": error_msg})

        assert_equal(
            len(self.msg_dict),
            0,
            "In {} reboot cycles, {} failed for the following reason(s): {}".format(
                REBOOT_CYCLES, self.number_of_failed_iterations, self.msg_dict
            ),
        )
