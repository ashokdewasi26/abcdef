# Copyright (C) 2023. BMW CTW PT. All rights reserved.

import logging
import os
import re
import time
from pathlib import Path

from mtee.testing.tools import TimeoutCondition, run_command

logger = logging.getLogger(__name__)


def deconflict_file_path(apath, extension=".mp4"):
    """Adds numbers to the end of path until the resulting path does not exist
    :param _type_ apath: _description_
    :param str extension: _description_, defaults to ".mp4"
    :return _type_: _description_
    """
    apath = os.path.abspath(apath)
    apath = str(apath).replace(extension, "")
    full_apath = str(apath + extension) if extension not in apath else apath
    if not os.path.exists(full_apath):
        return full_apath
    if len(apath) < 3 or not apath[-2:].isdigit():
        return deconflict_file_path(apath + "_01", extension=extension)
    return deconflict_file_path("{}{:02}".format(apath[:-2], int(apath[-2:]) + 1), extension=extension)


def get_calling_test(stack_inspect):
    """Get test that called the object given the stack_inspect

    :param List stack_inspect: Expected to be the return list from: inspect.stack()
    :return str: Name of the test that called the object passed on stack_inspect
    """
    frame_info = stack_inspect[1]
    filepath = frame_info[1]
    current_test_name = Path(filepath).stem
    logger.info(f"Calling test name: '{current_test_name}'")
    return current_test_name


def create_custom_results_dir(current_test_name, base_dir=None):
    """Create a custom test directory on specified path

    :param str current_test_name: Name of the directory to be created
    :param str base_dir: Directory where to create the new one, defaults to None
    """
    base_dir = os.getcwd() if not base_dir else base_dir
    if "results" not in base_dir:
        out_dir = os.path.join(base_dir, "results", current_test_name)
    else:
        out_dir = os.path.join(base_dir, current_test_name)
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    logger.info(f"Created results folder path: '{out_dir}'")
    return out_dir


def verify_file_in_target_with_timeout(mtee_target, folder_path, folder_name_regex, file_name_regex, timeout=60):
    """Based on folder and files details passed as argument, this function performs a file search on target
     and returns the coredump log file path and file_name.
    :param mtee_target: test mtee_target object
    :param folder_path:coredump folder root path
    :param folder_name_regex:coredump folder name pattern
    :param file_name_regex:coredump log file name pattern
    :param int timeout: timeout to check the file exists
    :return file_name: coredump log file name
    """
    timer = TimeoutCondition(timeout)
    while timer:
        for vmcore_log_dir in mtee_target.listdir(folder_path):
            folder_match = re.search(folder_name_regex, str(vmcore_log_dir))
            if folder_match:
                folder_name = folder_match.group(0)
                early_cluster_root_folder_path = os.path.abspath(os.path.join(folder_path, folder_name))
                for root_file_list in mtee_target.listdir(early_cluster_root_folder_path):
                    file_match = re.search(file_name_regex, str(root_file_list))
                    if file_match:
                        file_name = file_match.group(0)
                        log_file_on_target_full_path = os.path.abspath(
                            os.path.join(early_cluster_root_folder_path, file_name)
                        )
                        return log_file_on_target_full_path, file_name
    return None, None


def verify_file_in_host_with_timeout(filename, sleep_time=60, steps=2):
    """Check the file is inside host with TimeoutCondition
    :param str filename: filename to check in host
    :param int sleep_time: timeout to check the file exists
    :param float steps: delay between consecutive checks
    :return bool: True if exists, False otherwise
    """
    timer = TimeoutCondition(sleep_time)
    while timer:
        if os.path.isfile(filename):
            logger.info(f"Core dump present on host PC. File path- {filename}")
            return True
        if os.path.isfile(filename + ".gz"):
            run_command(["gzip", "-d", filename + ".gz"], check=True)
        time.sleep(steps)
    return False
