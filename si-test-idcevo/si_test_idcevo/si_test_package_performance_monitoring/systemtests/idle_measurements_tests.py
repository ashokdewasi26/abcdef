# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Test to Idle ECU for a long period and verify performance"""
import configparser
import logging
import time
from pathlib import Path

from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import metadata
from tee.target_common import VehicleCondition
from tee.tools.utils import ensure_test_setup_condition

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

SLEEP_MINUTES = 240  # for test_001_target_in_idle_state
IDLE_10_MIN = 10  # for test_002_target_in_idle_for_10_min


class TestsIdleMeasurements(object):
    """Idle tests"""

    target = TargetShare().target

    @classmethod
    def setup_class(cls):
        """setup_class"""
        ensure_test_setup_condition(
            vehicle_condition=VehicleCondition.FAHREN,
            zgw_pwf_state=VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE,
            boot_mode="application.target",
        )
        time.sleep(120)

    @metadata(
        testsuite=["SI-performance"],
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
    def test_001_target_in_idle_state(self):
        """[SIT_Automated] Target in idle for 4 hours"""
        logger.debug(f"Set target to idle for {SLEEP_MINUTES} minutes")
        time.sleep(SLEEP_MINUTES * 60)
        logger.debug(f"End of interval of {SLEEP_MINUTES} minutes in idle")

    @metadata(
        testsuite=["SI", "SI-performance", "IDCEVO-SP21"],
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
    def test_002_target_in_idle_for_10_min(self):
        """[SIT_Automated] Target in idle for 10 min"""
        logger.debug(f"Set target to idle for {IDLE_10_MIN} minutes")
        time.sleep(IDLE_10_MIN * 60)
        logger.debug(f"End of interval of {IDLE_10_MIN} minutes in idle")
