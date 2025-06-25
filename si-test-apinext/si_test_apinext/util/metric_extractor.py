# Copyright (C) 2023. CTW PT. All rights reserved.
import csv
import logging
import os
import re
from collections import defaultdict
from collections.abc import Iterable

from mtee.testing.support.target_share import TargetShare

METRICS_FILE_NAME = "metrics.csv"

target = None

share = TargetShare()
if share and hasattr(share, "target"):
    target = share.target

logger = logging.getLogger(__name__)


class ExtractMetrics(object):
    """Extract metrics from log"""

    def __init__(self):
        self.result_dir = None
        self.log_file_path = None
        self.extract_file_dir = None

        if target:
            self.result_dir = target.options.result_dir

            self.log_file_path = target.options.log_file
            logger.info(f"Using log_file_path: {self.log_file_path}")

            self.extract_file_dir = os.path.join(self.result_dir, "extracted_files")

    def extract_metrics_and_log_to_csv(self):
        """Extract metrics from log"""

        pattern = re.compile(r"\[METRIC\] (name|key)='(?P<name>\S*)' (?P<data>.*)")

        metrics_dict = defaultdict(list)
        # Parse log file and store metric data
        with open(self.log_file_path) as file_handler:
            for file_line in file_handler.readlines():
                metric_data = pattern.search(file_line)
                if metric_data is not None:
                    name = metric_data.group("name")
                    data = metric_data.group("data")
                    metrics_dict[name].append(data)

        # Open CSV and call respective callback
        for name, data in metrics_dict.items():
            if hasattr(self, name):
                with open(os.path.join(self.extract_file_dir, "{}.csv".format(name)), "a", newline="") as csv_handler:
                    handler = getattr(self, name)
                    if callable(handler):
                        handler(data, csv_handler)
            else:
                self.metric_handler(name, data)

    def metric_handler(self, metric, data):
        header_names = ["metric", "data"]
        csv_filename = METRICS_FILE_NAME

        if not isinstance(data, Iterable):
            data = [data]

        with open(os.path.join(self.extract_file_dir, csv_filename), "a", newline="") as csv_handler:
            writer = csv.DictWriter(csv_handler, header_names)
            if not csv_handler.tell():
                writer.writeheader()
            for data_point in data:
                row = dict(zip(header_names, [metric, data_point]))
                writer.writerow(row)
