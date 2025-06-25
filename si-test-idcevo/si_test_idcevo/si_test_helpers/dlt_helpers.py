# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""DLT component related helpers"""
import csv
import logging
import os
import re

from collections import defaultdict
from mtee.testing.tools import assert_equal, assert_false, assert_true

logger = logging.getLogger(__name__)


def seek_android_dlt_msg_with_conditions(
    apid, ctid, payload_regex_list, dlt_log_extract_file_paths, verification=True
):
    """Assert an android message with the desired parameters is present on the messages of interest log after
    verifying the conditions for having that message are met, like:
    - the lifecycle reached late.target done "NSC,COCO,,.*<unit.result>: late.target . done.*" and
    - the PWF state before late.target expects android messages
    - the lifecycle is long enough for android messages to be registered
    :param str apid: Apid to be present on the message
    :param str ctid: Ctid to be present on the message
    :param list payload_regex_list: List of regex to be analyzed
    :param list dlt_log_extract_file_paths: List of file paths with messages of interest to be analyzed
    :param bool verification: If True verification is made, else it will return fails and number of lifecycles
    """
    error_dict = defaultdict(list)
    failing_lifecycles, late_lifecycles = [], []
    pwf_states_with_android_msgs = ["FAHREN", "DIAGNOSE", "WOHNEN"]  # 0-FAHREN 1-DIAGNOSE 2-WOHNEN
    minimum_lyfecycle_duration = 30  # seconds
    for dlt_log_extract_file_path in dlt_log_extract_file_paths:
        lifecycle_no = os.path.basename(os.path.dirname(dlt_log_extract_file_path))
        with open(dlt_log_extract_file_path, "r") as dlt_log_extract:
            csv_data = csv.DictReader(dlt_log_extract)
            read_data = [entry for entry in csv_data]
        match = []
        if not read_data:
            logger.warning(f"In LC '{lifecycle_no}' there where no messages of interest captured")
            continue

        # Skip it for 1st Lifecycle or if lifecycle duration is less than minimum duration. IDCEVODEV-7948
        last_tmsp = float(read_data[-1]["timestamp"])
        if int(lifecycle_no) < 2 or last_tmsp < minimum_lyfecycle_duration:
            continue
        last_pwf_state_before_late_target, late_target_reached = find_pwf_state_before_late_target(
            read_data, lifecycle_no
        )

        # If the desired conditions exist, search for desired messages
        if late_target_reached:
            late_lifecycles.append(lifecycle_no)
            if last_pwf_state_before_late_target in pwf_states_with_android_msgs:
                for payload_regex in payload_regex_list:
                    payload_regex_compiled = re.compile(payload_regex)
                    match = any(
                        payload_regex_compiled.search(entry["payload"])
                        for entry in read_data
                        if (entry["apid"], entry["ctid"]) == (apid, ctid)
                    )
                    if not match:
                        failing_lifecycles.append(lifecycle_no)
                        error_dict[payload_regex].append(lifecycle_no)

    logger.debug("late.target reached in lifecycles: {}".format(late_lifecycles))
    assert_true(late_lifecycles, "No lifecycle found with late.target reached")
    if verification:
        error_list = [
            'Expected DLT message "{}" not found on lifecycles: "{}"'.format(message, ", ".join(lifecycle_list))
            for message, lifecycle_list in error_dict.items()
        ]
        assert_false(error_list, "\n".join(error_list))
    return failing_lifecycles, error_list, len(dlt_log_extract_file_paths)


def find_pwf_state_before_late_target(read_data, lifecycle_no):
    """
    Find if LC reached Late Target (Boot completed), and return the last pwf state before reaching late_target
    :param list read_data: list with dlt messages of one LC
    :param str lifecycle_no: Number of current LC
    """
    late_target = "unitResult <unit,result>: late.target , done"
    last_pwf_state_before_late_target = "4"  # PARKEN - Default PWF state
    last_pwf_state = []
    late_target_reached = False
    for entry in read_data:
        # Find pwf state before late.target
        pwf_state = re.findall(r"(?<=pwf is: )\w+", entry["payload"])
        last_pwf_state = pwf_state or last_pwf_state
        if late_target in entry["payload"]:
            late_target_reached = late_target_reached or (entry["apid"] == "NSC" and entry["ctid"] == "COCO")
            assert_equal(
                len(last_pwf_state),
                1,
                f"On lifecycle {lifecycle_no} last_pwf_state was not correctly found,\
                        instead found:{str(last_pwf_state)}",
            )
            # If late_target reached and last PWF state found save last PWF state and go
            last_pwf_state_before_late_target = last_pwf_state[0]
            break
    return last_pwf_state_before_late_target, late_target_reached


def check_dlt_trace(trace, rgx, timeout=30):
    """Searches the given regex on the provided DLTContext
    :param DLTContext trace: Trace in which the regex need to be searched
    :param str rgx: Regex to be searched on the DLTContext
    :param int timeout: Timeout for message receiving. Defaults to 30s
    :returns: a payload(str) which matches the given regex from DLTcontext else None
    """
    return trace.wait_for(
        attrs=dict(payload_decoded=re.compile(rgx)),
        count=1,
        drop=True,
        timeout=timeout,
        raise_on_timeout=False,
    )
