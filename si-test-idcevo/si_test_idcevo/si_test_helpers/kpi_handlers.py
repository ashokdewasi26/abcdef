# Copyright (C) 2023. CTW PT. All rights reserved.

import logging

from mtee.metric import MetricLogger
from mtee.testing.support.target_share import TargetShare

target = TargetShare().target
metric_logger = MetricLogger()
logger = logging.getLogger(__name__)


def get_target_branches_and_thresholds(desired_kpi_name, kpi_thresholds):
    """Get all branches configured in the respective kpi thresholds

    :param desired_kpi_name: name of the KPI we want to use
    :param kpi_thresholds: Config Dict with the respective ECU thresholds. Check kpi_threshold_config.py
    :return branch_and_threshold_value: returns a dictionary with respective branches and thresholds
    """
    branch_and_threshold_value = {}

    for branch in kpi_thresholds.keys():
        if desired_kpi_name in kpi_thresholds[branch].keys():
            branch_and_threshold_value.update({branch: kpi_thresholds[branch][desired_kpi_name]})

    return branch_and_threshold_value


def get_specific_kpi_threshold(desired_kpi_name, kpi_thresholds, desired_branch="master"):
    """Get the specific threshold for the desired KPI

    :param desired_kpi_name: name of the KPI we want to use
    :param kpi_thresholds: Config Dict with the respective ECU thresholds. Check kpi_threshold_config.py
    :param desired_branch: name of the branch we are currently validating
    :return kpi_threshold: returns the threshold value of the specified KPI (desired_kpi)
    """

    if desired_branch not in kpi_thresholds or desired_kpi_name not in kpi_thresholds[desired_branch]:
        logger.debug(f"{desired_branch}.{desired_kpi_name} is not present in the configuration file.")
        desired_branch = "default_branch"
        desired_kpi_name = "default_kpi_threshold"
        logger.debug(f"Using the default threshold: {kpi_thresholds[desired_branch][desired_kpi_name]}")

    return kpi_thresholds[desired_branch][desired_kpi_name]


def process_kpi_value(kpi_value, config, csv_hanlder, kpi_thresholds):
    """Process each KPI, logging it to ECU log and to a CSV file
    inputs: KPI value, KPI name, KPI configuration parameters
    """
    # Add threshold in case it exists
    kpi_threshold_value = get_specific_kpi_threshold(config["metric"], kpi_thresholds)

    metric_threshold = {}
    if kpi_threshold_value != 0:
        # At this point, if a kpi_threshold_value exists, we need to check that this KPI threshold
        # is also configured for other branches of the target
        target.options.target,
        branches_and_threshold = get_target_branches_and_thresholds(config["metric"], kpi_thresholds)
        logger.debug(
            f"KPI threshold values ('{config['metric']}') for each '{target.options.target}'"
            f" branch: '{branches_and_threshold}'"
        )
        if len(branches_and_threshold) != 0:
            for branch, threshold_value in branches_and_threshold.items():
                metric_threshold[f"metric_threshold_{branch}"] = str(threshold_value)

    metric_logger.publish(
        {
            "name": "generic_kpi",
            "kpi_name": config["metric"],
            "time_value": kpi_value,
            **metric_threshold,
        }
    )

    csv_hanlder.csv_metric_logger(f"{config['metric']}", kpi_value, kpi_threshold_value)
