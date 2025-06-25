# Copyright (C) 2025. CTW BMW PT. All rights reserved.
"""STR KPIS post processing tests"""
import configparser
import csv
import logging
import os

from collections import defaultdict
from pathlib import Path
from unittest import SkipTest

from mtee.metric import MetricLogger
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

metric_logger = MetricLogger()


class STRKPICSVPostProcessingPostTest(object):
    __test__ = True

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)

        cls.str_kpis_file_path = os.path.join(cls.test.mtee_target.options.result_dir, "str_kpis_results.csv")
        # log all files in the result directory for debugging
        logger.info("Result directory contents: %s", os.listdir(cls.test.mtee_target.options.result_dir))
        if not os.path.exists(cls.str_kpis_file_path):
            raise SkipTest("Unable to find csv file with KPI values, skipping")

        cls.kpis_values = cls.load_csv_kpi_data()

    @classmethod
    def load_csv_kpi_data(cls):
        """
        Load KPI data from the CSV file.
        Returns:
            dict: A dictionary where keys are KPI names and values are lists of results.
        """
        with open(cls.str_kpis_file_path, mode="r") as csvfile:
            csv_reader = csv.reader(csvfile)
            next(csv_reader)

            data = defaultdict(list)
            for row in csv_reader:
                kpi, value = row
                data[kpi].append(value)
            return dict(data)

    def test_000_str_cycles_performance_kpis(self):
        """
        STR KPI Post Processing

        Steps:
        1. Iterate over the KPIs and their corresponding values loaded from the CSV data.
        2. Log the processing steps for each KPI.
        3. Publish each KPI result using the metric_logger.
        4. Assert that the data is not empty to ensure the CSV file was loaded correctly.

        Outcome:
        - All KPI results from the CSV are published and logged.
        - The test fails with an AssertionError if no data is found in the CSV file.
        """
        logger.info("Kpis and values: %s", self.kpis_values)

        for kpi, values in self.kpis_values.items():
            logger.info(f"Processing results for KPI: {kpi}")
            for value in values:
                metric_logger.publish({"name": "generic_kpi_resumed", "kpi_name": f"{kpi}", "value": value})

        assert len(self.kpis_values) > 0, f"No data found in CSV file: {self.str_kpis_file_path}."
