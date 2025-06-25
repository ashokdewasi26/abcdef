# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Generic metric collection from DLT using several reboots"""
import configparser
import logging

from collections import defaultdict
from pathlib import Path
from mtee.metric import MetricLogger
from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.csv_handlers import CSVHandler
from si_test_idcevo.si_test_helpers.kpi_handlers import process_kpi_value
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target
from si_test_idcevo.si_test_helpers.report_helpers import MultipleRebootsKPIsReporter

try:
    from .kpi_metrics_config import (
        METRICS_FILE_NAME,
        MULTIPLE_REBOOTS_DLT_KPI_CONFIG,
    )
    from .kpi_threshold_config import ECU_SPECIFIC_KPI
except ImportError:
    from kpi_metrics_config import (
        METRICS_FILE_NAME,
        MULTIPLE_REBOOTS_DLT_KPI_CONFIG,
    )
    from kpi_threshold_config import ECU_SPECIFIC_KPI

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")

logger = logging.getLogger(__name__)
metric_logger = MetricLogger()

# Total time to wait from reboots until all KPIs are collected
KPI_COLLECTION_TIMEOUT = 120  # (seconds)


@metadata(
    testsuite=["BAT", "domain", "SI", "SI-performance"],
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
class TestsMultipleDLTKPIS(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)
        extract_file_dir = Path(cls.test.mtee_target.options.result_dir) / "extracted_files"
        cls.csv_handler = CSVHandler(METRICS_FILE_NAME, extract_file_dir)
        cls.kpi_thresholds = ECU_SPECIFIC_KPI[cls.test.mtee_target.options.target]

        cls.reporter = MultipleRebootsKPIsReporter(
            test_name="multiple_reboots_kpi_tests",
            description="Test report for multiple reboots kpi collection",
            report_filename="multiple_reboots_kpi_tests.json",
        )

    @classmethod
    def teardown_class(cls):
        """Test case teardown"""
        cls.test.mtee_target.resume_after_reboot()

    def test_001_multiple_reboots_kpis_collection(self):
        """[SIT_Automated] Collect all the KPIs from MULTIPLE_REBOOTS_DLT_KPI_CONFIG
        Steps:
            - Reboot Target inside DLTContext
            - Get all DLT filters
            - Open Multi DLT wait for with filters
            - At the end, all metrics should be reported
            - Resume after reboot
            - Repeat as many times as required
            - Generate a report with relevant information
        Note: Amount of reboots is equal to the max amount of reboots requested by
        a metric in kpi_metrics_config.py.
        Success - if all the metrics were processed and reported
        Failure - if some metric failed to be processed
        """

        kpi_filters_dict = []
        processed_kpis = defaultdict(list)
        dlt_filters = []
        for name, config in MULTIPLE_REBOOTS_DLT_KPI_CONFIG.items():
            # Collect all the DLT filters into a list of tuples and remove duplicates
            kpi_filters_dict.append(
                {"apid": config["apid"], "ctid": config["ctid"], "payload_decoded": config["pattern"]}
            )
            dlt_filters.append((config["apid"], config["ctid"]))
            dlt_filters = list(set(dlt_filters))

            # Initialize processed kpis dictionary
            processed_kpis[name] = {"reboot_number": [], "value": []}

        # Find number of reboots to do (biggest amount of reboots in config file)
        reboots_amount = max(int(config["reboots"]) for config in MULTIPLE_REBOOTS_DLT_KPI_CONFIG.values())
        for reboot_counter in range(1, reboots_amount + 1):

            # Wait for previous reboot to finish, in case it hasn't
            # If it times out while waiting, force an hard reboot and wait
            if not wait_for_application_target(self.test.mtee_target):
                self.test.mtee_target.reboot(prefer_softreboot=False)
                wait_for_application_target(self.test.mtee_target)

            with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=dlt_filters) as trace:
                logger.debug(f"Performing reboot number: {reboot_counter}")
                self.test.mtee_target.reboot(prefer_softreboot=True)
                dlt_msgs = trace.wait_for_multi_filters(
                    filters=kpi_filters_dict,
                    drop=True,
                    count=0,
                    timeout=KPI_COLLECTION_TIMEOUT,
                )
                self.test.mtee_target.resume_after_reboot()

            for name, config in MULTIPLE_REBOOTS_DLT_KPI_CONFIG.items():
                for msg in dlt_msgs:
                    if name in processed_kpis and reboot_counter in processed_kpis[name]["reboot_number"]:
                        # Only the first occurrence of each metric is to be processed
                        break

                    match = config["pattern"].search(msg.payload_decoded)

                    if match and config["type"] == "msg_tmsp":
                        process_kpi_value(msg.tmsp, config, self.csv_handler, self.kpi_thresholds)
                        processed_kpis[name]["reboot_number"].extend([reboot_counter])
                        processed_kpis[name]["value"].extend([msg.tmsp])

                    elif match and config["type"] == "regex_group":
                        kpi_value = float(match.group(1))
                        process_kpi_value(kpi_value, config, self.csv_handler, self.kpi_thresholds)
                        processed_kpis[name]["reboot_number"].extend([reboot_counter])
                        processed_kpis[name]["value"].extend([kpi_value])

            reboot_summary = defaultdict(list)
            for name, _ in MULTIPLE_REBOOTS_DLT_KPI_CONFIG.items():
                if name in processed_kpis and reboot_counter in processed_kpis[name]["reboot_number"]:
                    reboot_summary.update({name: "Found"})
                else:
                    reboot_summary.update({name: "Missing"})
            self.reporter._add_boot_cycle_summary(
                reboot_counter,
                reboot_summary,
            )

        # Create a dictionary with the reboots that are not present in processed_kpis for displaying
        not_processed_kpis = {
            name: [num for num in range(1, reboots_amount + 1) if num not in processed_kpis[name]["reboot_number"]]
            for name in processed_kpis
        }
        # Filter out empty values from not_processed_kpis
        not_processed_kpis = {name: value for name, value in not_processed_kpis.items() if value}

        total_kpis_found = sum(len(config["reboot_number"]) for _, config in processed_kpis.items())
        total_kpis_not_found = len(MULTIPLE_REBOOTS_DLT_KPI_CONFIG) * reboots_amount - total_kpis_found

        # Add summary entries to reporter
        self.reporter.reboots_amount = reboots_amount
        self.reporter.individual_KPIs_to_collect = len(MULTIPLE_REBOOTS_DLT_KPI_CONFIG)
        self.reporter.values_collected_amount = total_kpis_found
        self.reporter.values_not_collected_amount = total_kpis_not_found
        self.reporter.missing_kpis = not_processed_kpis
        self.reporter.add_report_summary()

        logger.debug(f"total KPIs found: {total_kpis_found}")
        logger.debug(f"Found these KPIs: {processed_kpis}")
        assert (
            total_kpis_found == len(MULTIPLE_REBOOTS_DLT_KPI_CONFIG) * reboots_amount
        ), f"Failed to process the following KPIs in reboot number (check the report): {not_processed_kpis}"
