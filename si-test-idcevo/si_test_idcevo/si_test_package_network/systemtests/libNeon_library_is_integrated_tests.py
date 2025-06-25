# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Verify if libNeon library is integrated"""
import configparser
import logging
from pathlib import Path

from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import assert_process_returncode, metadata

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)


@metadata(
    testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
    component="tee_idcevo",
    domain="Network",
    asil="None",
    testmethod="Analyzing Requirements",
    testtype="Requirements-based test",
    testsetup="SW-Component",
    categorization="functional",
    priority="1",
    duplicates="IDCEVODEV-28906",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": config.get("FEATURES", "NETWORK_WEBDAV"),
        },
    },
)
class TestsVerifyLibNeonisIntegrated(object):
    target = TargetShare().target

    def test_001_verify_libneon_is_integrated(self):
        """
        [SIT_Automated] WebDAV - libNeon library is integrated

        Steps:
            1 - Get content of user library using the following command:
                ls -la /usr/lib/libneon*
            2 - In the output check if libNeon is integrated
        """

        logger.info("Starting test to verify if libNeon is integrated.")

        result = self.target.execute_command("ls -la /usr/lib/libneon*")

        assert_process_returncode(0, result, f"Library libNeon is not integrated as expected. Stderr: {result.stderr}")
