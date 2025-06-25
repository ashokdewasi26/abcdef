# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Target UDS startup tests"""
import configparser
import logging
import os
import time
from pathlib import Path

from diagnose.hsfz import HsfzError
from mtee.metric import MetricLogger
from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import assert_less_equal, metadata
from si_test_idcevo import MetricsOutputName
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.csv_handlers import CSVHandler
from si_test_idcevo.si_test_helpers.kpi_handlers import get_specific_kpi_threshold, process_kpi_value
from si_test_idcevo.si_test_helpers.reboot_handlers import reboot_no_wait
from tee.tools.diagnosis import DiagClient
from validation_utils.utils import TimeoutCondition

try:
    from .kpi_metrics_config import METRICS_FILE_NAME
    from .kpi_threshold_config import ECU_SPECIFIC_KPI
except ImportError:
    from kpi_metrics_config import METRICS_FILE_NAME
    from kpi_threshold_config import ECU_SPECIFIC_KPI

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
metric_logger = MetricLogger()

target = TargetShare().target
diagnostic_client = DiagClient(target.diagnostic_address, target.ecu_diagnostic_id)

# DID - Data Identifier
DID_PING_SESSION_STATE = 0xF100
DID_PRIO1_DIAG_JOB = 0xF186


class TestSystemStartup(object):
    def __init__(self):
        self.kpi_thresholds = ECU_SPECIFIC_KPI[target.options.target]
        self.timeout_value_uds_request = get_specific_kpi_threshold(
            MetricsOutputName.UDS_AVAILABITY, self.kpi_thresholds
        )
        self.timeout_value_prio1_diag_session = get_specific_kpi_threshold(
            MetricsOutputName.PRIO1_DIAG_AVAILABILITY, self.kpi_thresholds
        )

        extract_file_dir = os.path.join(target.options.result_dir, "extracted_files")

        self.csv_handler = CSVHandler(METRICS_FILE_NAME, extract_file_dir)

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

    @classmethod
    def teardown_class(cls):
        cls.test.apinext_target.wait_for_boot_completed_flag()

    def setup(self):
        """Test case preparation"""
        target.prepare_for_reboot()

    def teardown(self):
        """Test case teardown"""
        target.resume_after_reboot(skip_ready_checks=False)

    def ping_uds_session_using_read_data_by_did(
        self, data_identifier=DID_PING_SESSION_STATE, timeout=60, poll_interval=1.0
    ):
        """Ping ECU through UDS until request is accepted using read_data_by_did

        *Steps*
        - Start timer
        - Wait 2 seconds
        - Loop:
            - Perform read_data_by_did (0x22) with a given data_identifier
            - Wait poll interval before next request in case timeout or error

        :param data_identifier: (hex) contains data identifier to use. Defaults to DID_PING_SESSION_STATE.
        :param timeout: (int) timeout to stop pinging the session. Defaults to 60 seconds.
        :param timeout: (float) time to wait between pings. Defaults to 0.1 seconds.

        Returns: time it took for request to be accepted.
        Raises: TimeoutError if timeout is reached
        """
        uds_request_timer = TimeoutCondition(timeout)

        time.sleep(2)

        while uds_request_timer:
            logger.info(f"Performing UDS ping with data_identifier {hex(data_identifier)}")
            try:
                with diagnostic_client.diagnostic_session_manager() as ecu:
                    ecu.read_data_by_did(data_identifier)
                    response_time = uds_request_timer.time_elapsed
                    logger.info(f"Job response after {response_time}s")
                    return response_time
            except (EOFError, HsfzError, OSError, RuntimeError):
                logger.debug(
                    f"No response for Data Identifier {hex(data_identifier)}) after {uds_request_timer.time_elapsed}s"
                )

            time.sleep(poll_interval)

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
        duplicates="IDCEVODEV-7870",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "UDS_AVAILABILITY"),
            },
        },
    )
    def test_001_uds_availability_after_reset(self):
        """[SIT_Automated] UDS Availability

        **Steps**
            - Trigger diagnostic ECU-Reset
            - Ping UDS session until request is accepted using:
                RDBI_PING_SESSION_STATE (0x22 f1 00)
            - Compare time with KPI requirement
        """
        diagnostic_client.ecu_reset()

        uds_request_accepted_timestamp = self.ping_uds_session_using_read_data_by_did(DID_PING_SESSION_STATE)

        uds_config = {"metric": MetricsOutputName.UDS_AVAILABITY}

        if uds_request_accepted_timestamp:
            process_kpi_value(uds_request_accepted_timestamp, uds_config, self.csv_handler, self.kpi_thresholds)

        assert_less_equal(
            uds_request_accepted_timestamp,
            self.timeout_value_uds_request,
            f"UDS available time is greater that defined KPI of {self.timeout_value_uds_request}s",
        )

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
        duplicates="IDCEVODEV-7480",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "PRIO1_DIAG_AVAILABILITY"),
            },
        },
    )
    def test_002_prio1_diag_job_availability(self):
        """[SIT_Automated] Prio1 diagnostic job availability

        **Steps**
            - Trigger diagnostic ECU-Reset
            - Ping UDS session until request is accepted using:
                ActiveDiagnosticSession (0x22 f1 86)
            - Compare time with KPI requirement
        """
        reboot_no_wait(mtee_target=target)

        diag_session_active_tmsp = self.ping_uds_session_using_read_data_by_did(DID_PRIO1_DIAG_JOB)

        if diag_session_active_tmsp:
            process_kpi_value(
                diag_session_active_tmsp,
                {"metric": MetricsOutputName.PRIO1_DIAG_AVAILABILITY},
                self.csv_handler,
                self.kpi_thresholds,
            )

        assert_less_equal(
            diag_session_active_tmsp,
            self.timeout_value_prio1_diag_session,
            "ActiveDiagnosticSession available time is greater that defined KPI"
            f" of {self.timeout_value_prio1_diag_session}s",
        )
