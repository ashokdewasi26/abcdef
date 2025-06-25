# Copyright (C) 2025. BMW CTW PT. All rights reserved.
"""Helpers for benchmarking and performance tests."""

import json
import logging
import re
import time

from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np

from si_test_idcevo.si_test_helpers.android_helpers import ensure_launcher_page
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target

logger = logging.getLogger(__name__)


def process_and_store_gfx_metrics(test, gfx_statistics, output_file_name):
    """Use the GFX statistics data to create a histogram and save the metrics to a json file

    Steps:
    1. Search for metrics in output data and add to metrics dictionary
    2. Find histogram line in output data which contains the frame times
    3. Extract frame times from the histogram line
    4. Create a bar chart with the frame times
    5. Add frame time values and the mean to the metrics dictionary
    6. Export metrics dictionary to a json file
    """
    gfx_statistics_patterns = {
        "total_frames": r"Total frames rendered: (\d+)",
        "janky_frames": r"Janky frames: (\d+)",
        "janky_frames_legacy": r"Janky frames \(legacy\): (\d+)",
        "percentile_50": r"50th percentile: (\d+)ms",
        "percentile_90": r"90th percentile: (\d+)ms",
        "percentile_95": r"95th percentile: (\d+)ms",
        "percentile_99": r"99th percentile: (\d+)ms",
    }
    frame_time_pattern = r"(\d+)ms=(\d+)"  # Extracts the frame times and respective amount of frames

    if not isinstance(gfx_statistics, str):
        raise TypeError(f"gfx_statistics must be a string, got {type(gfx_statistics)}")
    if gfx_statistics is None:
        raise RuntimeError("GFX statistics data is empty or None.")
    if output_file_name is None:
        raise RuntimeError("Output file name must be configured.")

    metrics = defaultdict(int)
    for metric_name, regex_pattern in gfx_statistics_patterns.items():
        if match := re.search(regex_pattern, gfx_statistics):
            metrics[metric_name] = int(match.group(1))
        else:
            logger.error(f"Could not find metric '{metric_name}' in GFX statistics")

    histogram_line = next(
        (line for line in gfx_statistics.split("\n") if "HISTOGRAM" in line and "GPU HISTOGRAM" not in line), None
    )
    if not histogram_line:
        raise RuntimeError(f"Could not find frame time values in GFX statistics: {gfx_statistics}")

    matches = re.findall(frame_time_pattern, histogram_line)
    times_list = [int(time) for time, count in matches for _ in range(int(count))]

    if times_list:
        create_histogram(test.results_dir, times_list)

    mean = sum(times_list) / len(times_list)
    metrics["mean"] = mean

    for number, value in enumerate(times_list):
        if value <= 50:
            key = f"value_below_50_{number}"
        else:
            key = f"value_above_50_{number}"
        metrics[key] = value

    # Export to json
    file_path_json = test.results_dir + "/" + output_file_name
    with open(file_path_json, "w") as file:
        json.dump(metrics, file, indent=4)


def create_histogram(results_dir, data, histogram_threshold=25):
    """Create a histogram with the frame times data, Separated in 2 plots for better visibility"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(20, 8))

    avg = sum(data) / len(data)

    # Plot first histogram (values <= histogram_threshold)
    values_under_threshold = [x for x in data if x <= histogram_threshold]
    if len(values_under_threshold) > 0:
        ax1.hist(
            values_under_threshold,
            bins=np.arange(min(values_under_threshold), max(values_under_threshold) + 1.5, 1),
            edgecolor="black",
        )
        ax1.set_xticks(np.arange(min(values_under_threshold), max(values_under_threshold) + 1, 1))
        ax1.set_yticks(np.arange(0, int(ax1.get_ylim()[1]) + 1, 1))  # Set whole values on y-axis
    else:
        ax1.text(0.5, 0.5, f"No data <= {histogram_threshold}", transform=ax1.transAxes, ha="center", va="center")
    ax1.set_title(f"Values <= {histogram_threshold}, Average: {avg:.2f}")
    ax1.set_xlabel("Value")
    ax1.set_ylabel("Count")

    # Plot second histogram (values > histogram_threshold)
    values_above_threshold = [x for x in data if x > histogram_threshold]
    if len(values_above_threshold) > 0:
        unique_values_above_threshold = sorted(set(values_above_threshold))
        ax2.hist(
            values_above_threshold,
            bins=np.arange(min(unique_values_above_threshold), max(unique_values_above_threshold) + 1.5, 1),
            edgecolor="black",
        )
        ax2.set_xticks(unique_values_above_threshold)
        ax2.set_yticks(np.arange(0, int(ax2.get_ylim()[1]) + 1, 1))  # Set whole values on y-axis
    else:
        ax2.text(0.5, 0.5, f"No data > {histogram_threshold}", transform=ax2.transAxes, ha="center", va="center")
    ax2.set_title(f"Values > {histogram_threshold}, Average: {avg:.2f}")
    ax2.set_xlabel("Value")
    ax2.set_ylabel("Count")

    # Adjust spacing between subplots
    plt.subplots_adjust(hspace=0.5)

    plt.savefig(results_dir + "/frame_time_histogram.png")


def reboot_into_fresh_lifecycle(test):
    """Perform a reboot so the test begins in a sanitized state."""
    test.mtee_target.reboot(prefer_softreboot=True)
    if not wait_for_application_target(test.mtee_target):
        test.mtee_target.reboot(prefer_softreboot=False)
        if not wait_for_application_target(test.mtee_target):
            raise RuntimeError("Could not boot target into application mode after two reboots.")
    time.sleep(120)  # Give the target some time to stabilize
    ensure_launcher_page(test)
