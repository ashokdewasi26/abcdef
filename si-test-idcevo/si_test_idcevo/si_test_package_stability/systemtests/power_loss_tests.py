# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Verify that power-loss is working correctly"""
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

POWER_LOSS_CYCLES = 50


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
    duplicates="IDCEVODEV-8940",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": config.get("FEATURES", "STABILITY_KPI_MONITORING"),
        },
    },
)
class TestsPowerLossStability(object):
    number_of_failed_iterations = 0
    msg_dict = {}

    @classmethod
    def setup_class(cls):
        # TestBase is a singleton class to re-use appium driver and target vars
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

    def _power_loss_cycle(self, iteration, sleep_time_sec=90):
        random_number = random.randint(0, 60)
        time.sleep(random_number)
        logger.info(f"Starting power loss cycle {iteration} after waiting {random_number} sec")
        # Turn off power supply without cleanly shutting down
        self.test.mtee_target._power_off()
        time.sleep(5)
        self.test.mtee_target._power_on()
        time.sleep(sleep_time_sec)
        self.test.mtee_target.reboot(prefer_softreboot=True)

    def test_power_loss_stability(self):
        """[SIT_Automated] Cyclic power-loss test

        Steps:
            - Boot headunit to application mode (node0 containers and Android VM)
            - Wait random time between 0 - 60 seconds
            - Turn off power supply without cleanly shutting down the system
            - Wait couple of seconds
            - Turn on the power and boot the headunit back to application mode
            - Wait 90 seconds so that possible coredumps, context files, etc. can be collected from the system
            - Reboot the headunit to application mode with nsm soft reboot
            - Continue with step 2
        """
        self.test.mtee_target.boot_into_appl()
        self.test.apinext_target.wait_for_boot_completed_flag()

        for iteration in range(POWER_LOSS_CYCLES):
            try:
                # Run power-loss cycle
                self._power_loss_cycle(iteration)
            except Exception as error_msg:
                self.number_of_failed_iterations += 1
                self.msg_dict.update({f"Cycle_{iteration}": error_msg})

        assert_equal(
            len(self.msg_dict),
            0,
            "In {} power loss cycles, {} failed for the following reason(s): {}".format(
                POWER_LOSS_CYCLES, self.number_of_failed_iterations, self.msg_dict
            ),
        )
