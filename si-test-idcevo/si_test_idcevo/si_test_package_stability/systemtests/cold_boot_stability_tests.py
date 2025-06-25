# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Verify that cold-boot and shutdown are working correctly"""
import configparser
import logging
import random
import time
from pathlib import Path

from mtee.testing.tools import assert_equal, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

COLD_BOOT_CYCLES = 50


@metadata(
    testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
    component="tee_idcevo",
    domain="Stability",
    asil="None",
    testmethod="Analyzing Requirements",
    testtype="Requirements-based test",
    testsetup="SW-Component",
    categorization="functional",
    priority="1",
    duplicates="IDCEVODEV-8001",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": config.get("FEATURES", "STABILITY_KPI_MONITORING"),
        },
    },
)
class TestsColdBootStability(object):
    number_of_failed_iterations = 0
    msg_dict = {}

    @classmethod
    def setup_class(cls):
        # TestBase is a singleton class to re-use appium driver and target vars
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

    def _cold_boot_cycle(self, iteration, wait_time_sec=90):
        random_number = random.randint(0, 60)
        time.sleep(random_number)
        logger.info(f"Starting cold boot cycle {iteration} after waiting {random_number} sec")
        # Start timer
        start_time = time.time()
        self.test.mtee_target.reboot(prefer_softreboot=False)
        # Make sure we wait 90 seconds
        finish_time = time.time()
        if (finish_time - start_time) < wait_time_sec:
            time.sleep(wait_time_sec - (finish_time - start_time))
        self.test.mtee_target.reboot(prefer_softreboot=True)

    def test_cold_boot_stability(self):
        """[SIT_Automated] Cyclic cold boot

        Steps:
            - Start headunit to application mode (node0 containers and Android VM)
            - Wait SSH to be available
            - Wait random time between 0 - 60 seconds
            - Restart the headunit with nsm soft reboot
            - Wait 90 seconds so that possible coredumps, context files, etc. can be collected from the system
            - Restart the headunit with nsm soft reboot
            - Continue with step 2
        """
        self.test.mtee_target.boot_into_appl()
        self.test.apinext_target.wait_for_boot_completed_flag()

        for iteration in range(COLD_BOOT_CYCLES):
            try:
                # Run cold boot cycle
                self._cold_boot_cycle(iteration)
            except Exception as error_msg:
                self.number_of_failed_iterations += 1
                self.msg_dict.update({f"Cycle_{iteration}": error_msg})

        assert_equal(
            len(self.msg_dict),
            0,
            "In {} cold boot cycles, {} failed for the following reason(s): {}".format(
                COLD_BOOT_CYCLES,
                self.number_of_failed_iterations,
                self.msg_dict,
            ),
        )
