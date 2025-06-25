# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Key Performance Indicators tests"""
import configparser
import logging
import time
from pathlib import Path

from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import assert_equal, metadata

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)


@metadata(
    testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
    component="tee_idcevo",
    domain="System Software",
    asil="None",
    testmethod="Analyzing Requirements",
    testtype="Requirements-based test",
    testsetup="SW-Component",
    categorization="functional",
    priority="1",
    duplicates="IDCEVODEV-10723",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": [
                config.get("FEATURES", "KEY_PERFORMANCE_INDICATORS"),
                config.get("FEATURES", "KEY_PERFORMANCE_INDICATORS_CORE_HV_KPIS"),
                config.get("FEATURES", "KEY_PERFORMANCE_INDICATORS_GUEST_VM_KPIS"),
            ],
        },
    },
)
class TestsKPIPerformanceIndicators(object):
    target = TargetShare().target

    def test_001_verify_kpi_for_vm2_image_is_ready(self):
        """
        [SIT_Automated] Verify KPI for VM2 image is ready
        Steps:
            1 - Run "cat /dev/vlx-history > /tmp/vlx-history" for 15 seconds
            2 - Search for "VM2 image is ready" on the previous log: /tmp/vlx-history
        """

        logger.info("Starting test to verify KPI for VM2 image is ready")

        # Start a process in background
        with self.target.execute_background_task(
            "cat /dev/vlx-history > /tmp/vlx-history", shell=True
        ) as exec_background_task:
            time.sleep(15)
            background_task_output = exec_background_task.recv_stdout()
            logger.debug(f"background_task_output: {background_task_output}")
            assert_equal(exec_background_task.exit_status, None, "Error while running the task in the background")

        return_stdout, _, return_code = self.target.execute_command(["grep", "VM2 image is ready", "/tmp/vlx-history"])
        logger.debug(f"return_stdout: {return_stdout}")
        assert_equal(return_code, 0, "The expected string was not found in the log")
