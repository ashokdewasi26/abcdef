# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Check for permanent ambient light."""
import configparser
import logging
import re
from pathlib import Path

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import assert_true, metadata
from tee.target_common import VehicleCondition
from tee.tools.diagnosis import DiagClient
from tee.tools.dlt_helper import DLTLogLevelMapping, set_dlt_log_level
from tee.tools.secure_modes import SecureECUMode

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

# The following parameters were obtained in https://asc.bmwgroup.net/wiki/pages/viewpage.action?pageId=658167804
# RC_STR_INNENLICHT_SET_API_ELEMENT job' arguments and values
STATE_REQUEST = {
    "PARKEN_BN_IO": b"\x00\x00\x02",
    "WOHNEN": b"\x00\x00\x05",
}
# RC_STR_INNENLICHT_SET_API_ELEMENT job identifier
RID = 0xA42B
# Target log of diagnostic job RC_STR_INNENLICHT_SET_API_ELEMENT
REGEX_EXP_GET_DIAG_JOB_LOG = (
    r"Received update for hardware pixel \[globalHwPixelId=\d+\] with data \[opticalBrightness=\d+.*"
)


@metadata(
    testsuite=["BAT", "domain", "SI", "ACM", "IDCEVO-SP21"],
    component="tee_idcevo",
    domain="Interior Light",
    asil="None",
    testmethod="Analyzing Requirements",
    testtype="Requirements-based test",
    testsetup="SW-Component",
    categorization="functional",
    priority="1",
    duplicates="IDCEVODEV-7797",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": config.get("FEATURES", "PERMANENT_AMBIENT_LIGHT"),
        },
    },
)
class TestsAmbientLight(object):

    target = TargetShare().target
    diagnostic_client = DiagClient(target.diagnostic_address, target.ecu_diagnostic_id)

    def _run_rc_str_innenlicht_diag_job(self, api_value):
        """
        Run diagnostic job RC_STR_INNENLICHT_SET_API_ELEMENT.
        :param api_value: RC_STR_INNENLICHT_SET_API_ELEMENT job API Value
        """

        with self.diagnostic_client.diagnostic_session_manager() as ecu:
            ecu.start_routine(RID, STATE_REQUEST[api_value])
            logger.info(
                f"RC_STR_INNENLICHT_SET_API_ELEMENT diagnostic job triggered. "
                f"API Element: PwfState, API Value: {api_value}"
            )

    def _search_for_dlt_messages(self, regex_pattern_diag_job_output, api_value):
        """
        Search for specific logs in DLT.
        :param regex_pattern_diag_job_output: Target log of diagnostic job RC_STR_INNENLICHT_SET_API_ELEMENT
        :param api_value: RC_STR_INNENLICHT_SET_API_ELEMENT job API Value
        """

        dlt_msgs = []
        with DLTContext(self.target.connectors.dlt.broker, filters=[("LGHT", "LTML")]) as trace:
            dlt_msgs = trace.wait_for(
                attrs=dict(payload_decoded=re.compile(regex_pattern_diag_job_output)),
                timeout=2,
                count=10,
                drop=True,
            )
        assert_true(
            dlt_msgs,
            f"Target log not found for diagnostic job RC_STR_INNENLICHT_SET_API_ELEMENT"
            f"(param1: PwfState, param2: {api_value})",
        )

        for msg in dlt_msgs:
            logger.info(f"Message received: {msg}")
            match = re.search(regex_pattern_diag_job_output, msg.payload_decoded)
            assert_true(
                match,
                f"Target log not found for diagnostic job RC_STR_INNENLICHT_SET_API_ELEMENT"
                f"(param1: PwfState, param2: {api_value})",
            )

    @classmethod
    def setup_class(cls):
        """
        Setup class:
        Verifies if the target is in engineering mode.
        If not by default, it will switch the target to engineering mode.
        """

        secure_mode_object = SecureECUMode(cls.target)
        current_mode = secure_mode_object.current_mode
        logger.info(f"Current target mode: {current_mode}")

        if current_mode != "ENGINEERING":
            secure_mode_object.switch_mode("ENGINEERING")
            logger.info("Engineering mode activated.")

    def test_001_ambient_light(self):
        """
        [SIT_Automated] permanent ambientlight active - Light stack runs_Component integration test_set_api

        Steps:
        - Set PWF-state to PAD
        - Run diagnostic job RC_STR_INNENLICHT_SET_API_ELEMENT
            (param1: PwfState, param2: Parken)
        - Check for a specific message in DLT
        - Run diagnostic job RC_STR_INNENLICHT_SET_API_ELEMENT
            (param1: PwfState, param2: Wohnen)
        - Check for a specific message in DLT
        """

        logger.info("Starting ambient light test.")

        set_dlt_log_level(DLTLogLevelMapping.verbose)
        logger.info("Loglevel changed to verbose.")

        vehicle_condition = VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE
        self.target.switch_vehicle_to_state(vehicle_condition, skip_checks=True)
        logger.info("pwf state changed to PAD.")

        self._run_rc_str_innenlicht_diag_job("PARKEN_BN_IO")
        self._search_for_dlt_messages(REGEX_EXP_GET_DIAG_JOB_LOG, "PARKEN_BN_IO")
        self._run_rc_str_innenlicht_diag_job("WOHNEN")
        self._search_for_dlt_messages(REGEX_EXP_GET_DIAG_JOB_LOG, "WOHNEN")
