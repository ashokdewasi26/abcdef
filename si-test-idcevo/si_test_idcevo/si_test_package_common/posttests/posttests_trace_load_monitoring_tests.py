# Copyright (C) 2024. BMW Car IT. All rights reserved.
"""Trace Load Monitoring Test"""
import csv
import logging
import os
from unittest import skipIf

from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import metadata


logger = logging.getLogger(__name__)

OUTPUT_FOLDER = "extracted_files"
ANALYSIS_METADATA = "traffic_load_analysis_metadata.csv"
THRESHOLD_TRACE_LOAD = 4000


@metadata(testsuite=["BAT", "SI", "IDCEVO-SP21"])
class TraceLoadMonitoringPostTest(object):
    target = TargetShare().target

    __test__ = True

    @skipIf(not target, "Test requires target.")
    def test_read_average_trace_load(self):
        """Reads the trace metadata from the csv files and returns average trace load."""
        total_load = 0
        extract_file_dir = os.path.join(self.target.options.result_dir, OUTPUT_FOLDER)
        metadata_path = os.path.join(extract_file_dir, ANALYSIS_METADATA)
        assert os.path.exists(metadata_path)

        with open(metadata_path, "r") as csvfile:
            reader = csv.DictReader(csvfile, delimiter=";")
            for row in reader:
                if row["average trace load (MBph)"]:
                    total_load = int(row["average trace load (MBph)"])
            assert (
                total_load < THRESHOLD_TRACE_LOAD
            ), f"The average trace load value {total_load} passed the threshold trace load value"
