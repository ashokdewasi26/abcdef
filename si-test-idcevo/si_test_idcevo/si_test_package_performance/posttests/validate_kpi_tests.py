# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Generic metric collection from DLT msgs"""
import configparser
import csv
import inspect
import logging
import os
from pathlib import Path

from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import metadata

try:
    from .kpi_metrics_config import METRICS_FILE_NAME
    from .kpi_threshold_config import ECU_SPECIFIC_KPI, TRACEABILITY_CONFIG
except ImportError:
    from kpi_metrics_config import METRICS_FILE_NAME
    from kpi_threshold_config import ECU_SPECIFIC_KPI, TRACEABILITY_CONFIG

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)


@metadata(testsuite=["SI", "SI-performance", "IDCEVO-SP21"])
class ValidateKPIPostTest(object):

    __test__ = True

    metric_list = []

    """
    This comment can be interpreted as the doc_string of the gen_test() method, and it's placed here on purpose,
    because we don't want the method to have a defined docstring, so it can have a dynamic name on the xml
    results file
    The following method generates test methods dynamically to validate each of the metrics present on
    ECU_SPECIFIC_KPI against their KPI threshold, assuming they were previously correctly collected
    Each method generated will have a different name based on the metric being tested and a
    different metadata
    """

    def gen_test(self):
        for metric in self.metric_list:
            logger.info(f"Generating test method for: '{metric}'")

            @metadata(
                testsuite=["domain", "SI", "SI-performance", "IDCEVO-SP21"],
                component="tee_idcevo",
                domain=TRACEABILITY_CONFIG[metric]["domain"],
                asil="None",
                testmethod="Analyzing Requirements",
                testtype="Requirements-based test",
                testsetup="SW-Component",
                categorization="functional",
                priority="1",
                traceability={
                    config.get("tests", "traceability"): {
                        "FEATURE": TRACEABILITY_CONFIG[metric]["feature"],
                    },
                },
                test_case_description_docstring=TRACEABILITY_CONFIG[metric]["docstring"],
            )
            def validate_metric(metric_name=metric):
                """Validate kpi metric value against it's threshold

                Get the value and threshold of a kpi metric and validate it

                :param str metric_name: name of metric to search, defaults to metric
                """
                metric_value, kpi_threshold = self.get_metric_and_threshold_value(metric_name)
                logger.info(
                    f"Validating metric: '{metric_name}' with value: '{metric_value}' against the\
                          kpi threshold: '{kpi_threshold}'"
                )
                assert (
                    metric_value <= kpi_threshold
                ), f"{metric_name} validation failed, metric value is over kpi_threshold -> {metric_value} > \
                    {kpi_threshold}"

            validate_metric.__name__ = f"test_{metric}"
            validate_metric.__doc__ = TRACEABILITY_CONFIG[metric]["docstring"]

            if inspect.ismethod(validate_metric):
                validate_metric.__func__.description = TRACEABILITY_CONFIG[metric]["docstring"]
            else:
                validate_metric.description = TRACEABILITY_CONFIG[metric]["docstring"]
            yield validate_metric, metric

    def __init__(self):
        """Set the generated methods as class methods so they are picked up as tests by nose"""
        logger.info("Doing init for: TestsValidateKPI")
        for test_func, _ in self.gen_test():
            logger.info(f"Generated method: '{test_func.__name__}'")

    @classmethod
    def setup_class(cls):
        """Setup class
        Ensure csv file exists on extracted files
        Read CSV data to a dictionary
        """
        cls.target = TargetShare().target
        cls.target_name = cls.target.options.target
        branch = "master"

        extract_file_dir = os.path.join(cls.target.options.result_dir, "extracted_files")
        cls.csv_file = os.path.join(extract_file_dir, METRICS_FILE_NAME)
        assert os.path.exists(cls.csv_file)

        with open(cls.csv_file) as f:
            reader = csv.DictReader(f)
            cls.csv_data = list(reader)
            cls.csv_data_list = [item["metric"] for item in cls.csv_data]

        # Determine which kpi metrics were collected and have a kpi threshold defined
        metrics_kpi_list = list(ECU_SPECIFIC_KPI[cls.target_name][branch].keys())
        cls.metric_list = list(set(metrics_kpi_list).intersection(cls.csv_data_list))

    def get_metric_and_threshold_value(self, metric):
        """Retrieve metric value and threshold value from csv data
        This will read data from csv file, search for a specific
        metric on it and return the metric_value and the kpi_threshold.
        If metric is not found raises an RuntimeError.

        :param str metric: name of metric to search
        """
        for row in self.csv_data:
            if row["metric"] == metric:
                return float(row["metric_value"]), float(row["kpi_threshold"])

        raise RuntimeError(f"Couldn't find '{metric}' from {METRICS_FILE_NAME}")
