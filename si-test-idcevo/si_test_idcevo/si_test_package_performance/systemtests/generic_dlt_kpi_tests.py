# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Generic metric collection from DLT using only one reboot"""
import configparser
import logging
import os
from copy import deepcopy
from pathlib import Path

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.csv_handlers import CSVHandler
from si_test_idcevo.si_test_helpers.diagnostic_helper import get_dtc_list
from si_test_idcevo.si_test_helpers.kpi_handlers import process_kpi_value
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target

try:
    from .kpi_metrics_config import (
        GENERIC_DLT_KPI_CONFIG,
        GENERIC_MULTI_MARKERS_KPI_CONFIG,
        METRICS_FILE_NAME,
    )
    from .kpi_threshold_config import ECU_SPECIFIC_KPI
except ImportError:
    from kpi_metrics_config import (
        GENERIC_DLT_KPI_CONFIG,
        GENERIC_MULTI_MARKERS_KPI_CONFIG,
        METRICS_FILE_NAME,
    )
    from kpi_threshold_config import ECU_SPECIFIC_KPI

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")

logger = logging.getLogger(__name__)

# Total time to wait from reboot until all KPIs are collected
KPI_COLLECTION_TIMEOUT = 120  # (seconds)
DISPLAY_NOT_CONNECTED_DTC = "0XA76307"
DISPLAY_METRICS = ["CID Ready Show Content", "PHUD Driver Ready Show Content"]


@metadata(
    testsuite=["BAT", "BAT-mini", "domain", "SI", "SI-performance", "IDCEVO-SP21"],
    component="tee_idcevo",
    domain="IDCEvo Test",
    asil="None",
    testmethod="Analyzing Requirements",
    testtype="Requirements-based test",
    testsetup="SW-Component",
    categorization="functional",
    priority="1",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": config.get("FEATURES", "GENERIC_DLT_KPIS"),
        },
    },
)
class TestsGenericDLTKPIS(object):
    dlt_filters = []
    processed_kpis = {}  # {{name_kpi: kpi_value}, ... }
    processed_multi_marker_kpis = {}  # {{name_kpi: kpi_value}, ... }

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        extract_file_dir = os.path.join(cls.test.mtee_target.options.result_dir, "extracted_files")
        cls.csv_handler = CSVHandler(METRICS_FILE_NAME, extract_file_dir)
        cls.kpi_thresholds = ECU_SPECIFIC_KPI[cls.test.mtee_target.options.target]
        dtc_list_str = get_dtc_list(cls.test.diagnostic_client)
        cls.display_not_detected = DISPLAY_NOT_CONNECTED_DTC in dtc_list_str

        cls.generic_kpis = deepcopy(GENERIC_DLT_KPI_CONFIG)
        cls.multi_marker_kpis = deepcopy(GENERIC_MULTI_MARKERS_KPI_CONFIG)
        if cls.display_not_detected:
            logger.info("Display not detected, removing display KPIs from the list")
            for display_kpi in DISPLAY_METRICS:
                cls.generic_kpis.pop(display_kpi, None)
                cls.multi_marker_kpis.pop(display_kpi, None)

    @classmethod
    def teardown_class(cls):
        """Test case teardown"""
        cls.test.mtee_target.resume_after_reboot(skip_ready_checks=False)

    def test_001_generic_kpis_collection(self):
        """[SIT_Automated] Collect all the KPIs from GENERIC_DLT_KPI_CONFIG
        Steps:
            - Reboot Target
            - Get all DLT filters
            - Open Multi DLT wait for with filters
            - At the end, all metrics should be reported.
            - Resume after reboot
        Note: All the metrics will be logged to the ECU log file and also
              to a CSV file.
        Success - if all the metrics were processed and reported
        Failure - if some metric failed to be processed
        """
        kpi_filters_dict = []
        for _, config in self.generic_kpis.items():
            kpi_filters_dict.append(
                {"apid": config["apid"], "ctid": config["ctid"], "payload_decoded": config["pattern"]}
            )

            # Collect all the DLT filters into a list of tuples and remove duplicates
            self.dlt_filters.append((config["apid"], config["ctid"]))
            self.dlt_filters = list(set(self.dlt_filters))

        # Wait for previous reboot to finish, in case it hasn't
        # If it times out while waiting, force an hard reboot and wait
        if not wait_for_application_target(self.test.mtee_target):
            self.test.mtee_target.reboot(prefer_softreboot=False)
            wait_for_application_target(self.test.mtee_target)

        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=self.dlt_filters) as trace:
            self.test.mtee_target.reboot(prefer_softreboot=True)
            dlt_msgs = trace.wait_for_multi_filters(
                filters=kpi_filters_dict,
                drop=True,
                count=0,
                timeout=KPI_COLLECTION_TIMEOUT,
            )
            self.test.mtee_target.resume_after_reboot(skip_ready_checks=False)

        for name, config in self.generic_kpis.items():
            for msg in dlt_msgs:
                if name in self.processed_kpis.keys():
                    # Only the first occurrence of each metric is to be processed
                    break

                match = config["pattern"].search(msg.payload_decoded)

                if match and config["type"] == "msg_tmsp":
                    process_kpi_value(msg.tmsp, config, self.csv_handler, self.kpi_thresholds)
                    self.processed_kpis.update({name: msg.tmsp})

                elif match and config["type"] == "regex_group":
                    kpi_value = float(match.group(1))
                    process_kpi_value(kpi_value, config, self.csv_handler, self.kpi_thresholds)
                    self.processed_kpis.update({name: kpi_value})

        logger.debug(f"Processed KPI's: {self.processed_kpis.keys()}")

        not_processed_kpis = list(set(self.generic_kpis.keys()) - set(self.processed_kpis.keys()))
        logger.debug(f"KPI's missing: {not_processed_kpis}")

        assert len(self.processed_kpis) == len(self.generic_kpis), f"Failed to process: {not_processed_kpis}"

    def test_002_generic_multi_marker_kpi(self):
        """[SIT_Automated] Collect all the multi markers KPIs
        Steps:
            - Verify if needed kpi's are on processed_kpis list
            - Calculate the difference between time stamps
            - Process the new kpi
        Note: All the metrics will be logged to the ECU log file and also
              to a CSV file.
        Success - if all the metrics were processed and reported
        Failure - if some metric failed to be processed
        """
        for name, config in self.multi_marker_kpis.items():
            if config["kpi_1"] in self.processed_kpis.keys() and config["kpi_2"] in self.processed_kpis.keys():
                tmsp1 = self.processed_kpis[config["kpi_1"]]
                tmsp2 = self.processed_kpis[config["kpi_2"]]
                tmsp_diff = tmsp2 - tmsp1

                process_kpi_value(tmsp_diff, {"metric": config["metric"]}, self.csv_handler, self.kpi_thresholds)

                self.processed_multi_marker_kpis.update({name: tmsp_diff})

        not_processed_multi_marker_kpis = list(
            set(self.multi_marker_kpis.keys()) - set(self.processed_multi_marker_kpis.keys())
        )
        logger.debug(f"KPI's missing: {not_processed_multi_marker_kpis}")

        assert len(self.processed_multi_marker_kpis) == len(
            self.multi_marker_kpis
        ), f"Failed to process: {not_processed_multi_marker_kpis}"
