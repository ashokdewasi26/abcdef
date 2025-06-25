# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""ECU Reliability tests"""
import configparser
import logging
from pathlib import Path

from mtee.metric import MetricLogger
from mtee.testing.tools import assert_false, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
metric_logger = MetricLogger()

DEFAULT_TARGET_ECU_UID = "000102030405060708090A0B0C0D0EEE"


class TestECUReliability(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

    @metadata(
        testsuite=["domain", "SI", "SI-performance", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Performance",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-32535",
    )
    def test_001_read_ecu_uid(self):
        """[SIT_Automated] BAT ECU UID test"""
        ecu_uid = self.test.diagnostic_client.read_ecu_uid().replace(" ", "").upper()
        logger.debug("Target ECU UID: %s", ecu_uid)
        assert_false(
            ecu_uid in DEFAULT_TARGET_ECU_UID,
            "Target ECU UID matched the default ECU UID value, {}".format(ecu_uid),
        )
