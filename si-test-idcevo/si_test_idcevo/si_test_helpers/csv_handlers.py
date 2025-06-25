# Copyright (C) 2023. BMW CTW PT. All rights reserved.

import csv
import logging
import os
import re

logger = logging.getLogger(__name__)


class CSVHandler(object):
    def __init__(self, csv_file_name, csv_file_dir="") -> None:
        self.csv_file_name = csv_file_name
        self.csv_file_path = os.path.join(csv_file_dir, csv_file_name)
        self.csv_file_dir = csv_file_dir

    def _verify_dir(self):
        """
        Creates new directory 'csv_file_dir' in case it does not exists.
        """

        if self.csv_file_dir and not os.path.exists(self.csv_file_dir):
            os.makedirs(self.csv_file_dir)

    def csv_metric_logger(self, metric, metric_value, kpi_threshold_value=0):
        """Write metric data to a CSV file

        Writes in a csv file the following data:
          metric name, metric value, metric threshold, difference between metric value and threshold

        :param metric: metric name
        :param metric_value: value associated with the metric
        :param kpi_threshold_value: metric kpi threshold
        """

        header_names = ["metric", "metric_value", "kpi_threshold", "diff"]
        row_values = [metric, metric_value]
        row_values.append(kpi_threshold_value)
        row_values.append(metric_value - kpi_threshold_value)

        with open(self.csv_file_path, "a", newline="") as csv_handler:
            writer = csv.writer(csv_handler, header_names)
            if not csv_handler.tell():
                writer.writerow(header_names)
            writer.writerow(row_values)

    def exports_list_to_csv(self, file_to_write):
        """
        Exports a python list to a csv file.
        :param file_to_write: list which will be exported to a csv file.
        """

        self._verify_dir()
        with open(self.csv_file_path, mode="w", newline="") as file:
            writer = csv.writer(file)
            for item in file_to_write:
                writer.writerow([item])

    def get_csv_files_path(self, dir, dir_children_to_ignore=[]):
        """Returns list containing all csv files' path (with the same name of 'csv_file_name')
        available inside of a specified directory ('dir')
        :param dir: path of the parent directory (csv files could be found on this directory
        or in children directories)
        :param dir_children_to_ignore: list of children directories to ignore during the search
        :return: list containing all matching csv files present in the specified directory tree.
        """

        files_path = []
        dir_children_filtered = False
        for dir, dir_children, dir_files in os.walk(dir):
            if dir_children_to_ignore and not dir_children_filtered:
                for expression in dir_children_to_ignore:
                    for child in dir_children:
                        if expression in child:
                            dir_children.remove(child)
                dir_children_filtered = True
            for file in dir_files:
                if file == self.csv_file_name:
                    file_path_aux = os.path.join(dir, file)
                    files_path.append(file_path_aux)
                    logger.info(f"The following csv file was found: {file_path_aux}")

        files_path = sorted(files_path)

        logger.info(f"A total of {len(files_path)} '{self.csv_file_name}' files were found.")

        return files_path

    def get_csv_files_after_given_string(self, csv_files_path, string_to_search):
        """
        Get ordered list containing all csv files' path available inside of a specified directory.
        Remove CSV files that come before the file containing the "string_to_search".
        The first instance of "string_to_search" is the only one taken into account.
        If "string_to_search" can't be found, all files will be returned.
        """
        files_path = self.get_csv_files_path(dir=csv_files_path)

        string_to_search_regex = re.compile(string_to_search)
        setup_done_file_index = None
        for index, csv_file in enumerate(files_path):
            with open(csv_file) as file:
                for row in file:
                    if string_to_search_regex.search(row):
                        setup_done_file_index = index
                        break
            if setup_done_file_index is not None:
                break

        # If the 'string_to_search' was found, remove all files before the file containing it
        if setup_done_file_index is not None:
            files_path = files_path[setup_done_file_index:]

        return files_path
