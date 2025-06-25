# Copyright (C) 2023. BMW CTW PT. All rights reserved.

import logging
import os
from functools import wraps
from re import split
from unittest import SkipTest
from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT
from mtee.testing.tools import assert_is_not_none
from si_test_idcevo.si_test_helpers.file_path_helpers import deconflict_file_path

# TRAAS environment defines this env
RESULTS_DIR = os.getenv("RESULT_DIR", os.path.join(os.getcwd(), "results"))
logger = logging.getLogger(__name__)


def gather_info_on_fail(fn):
    @wraps(fn)
    def with_screen_shot(self, *args, **kwargs):
        """Take a screenshot of the drive page, when a function fails"""
        try:
            return fn(self, *args, **kwargs)
        except Exception:
            # This will only be reached if the test fails
            func_name = fn.__name__

            if hasattr(self, "test"):
                current_module = self.test
                # current_module.stop_padi_video_streaming_apps()
            else:
                # In case gather_info_on_fail is called during a Page method
                current_module = self

            output_results = current_module.results_dir if current_module.results_dir else RESULTS_DIR
            current_module.take_apinext_target_screenshot(output_results, f"{func_name}_fail.png")

            if current_module.driver:
                get_xml_dump(current_module.driver, output_results, f"{func_name}_dump_fail.xml")
            else:
                logger.debug(f"Unable to UI dump. Context: {func_name}")
            # In case real phone is present get screenshot and UI element dump
            if hasattr(self, "real_phone_present") and self.real_phone_present:
                current_module = self.real_phone_target

                output_results = current_module.results_dir if current_module.results_dir else RESULTS_DIR
                current_module.take_real_phone_target_screenshot(output_results, f"{func_name}_REAL_PHONE_fail.png")

                if current_module.real_phone_driver:
                    get_xml_dump(
                        current_module.real_phone_driver, output_results, f"{func_name}_REAL_PHONE_dump_fail.xml"
                    )
                else:
                    logger.debug(f"Unable to UI dump. Context: {func_name}")
            raise

    return with_screen_shot


def get_xml_dump(driver, results_dir, file_name):
    """Take a dump of the elements on the UI into an xml file

    :param driver: WebDriver object
    :param results_dir: path to results folder
    :type results_dir: str
    :param file_name: name for created file
    :type file_name: str
    """
    page_source = driver.page_source
    file_name = os.path.join(results_dir, file_name) if results_dir not in file_name else file_name
    file_name = str(file_name + ".xml") if ".xml" not in file_name else file_name
    file_name = deconflict_file_path(file_name, extension=".xml")
    with open(file_name, "w") as f:
        f.write(page_source)
        f.close()
    return page_source


def get_screenshot_and_dump(test, results_dir, file_name):
    """Take a screenshot and a UI dump

    :param test: TestBase singleton object
    :param results_dir: path to results folder
    :type results_dir: str
    :param file_name: name for created file
    :type file_name: str
    :return: page dump xml str
    """
    screenshot_path = test.take_apinext_target_screenshot(results_dir, file_name)
    full_page_source = get_xml_dump(test.driver, results_dir, file_name)
    return screenshot_path, full_page_source


def skip_unsupported_ecus(supported_ecus=["idcevo", "rse26", "cde"]):
    """Skip test if target isn't a supported ECU"""
    target = TargetShare().target
    return target.options.target.lower() in supported_ecus


def check_ipk_installed(required_ipks):
    """Check if the necessary IPK's are installed correctly"""
    mtee_target = TargetShare().target
    ipk_found = []
    for ipk in required_ipks:
        # Check if package is installed with opkg list
        list_cmd = f"opkg list | grep {ipk}"
        return_stdout, _, _ = mtee_target.execute_command(list_cmd)
        if ipk in return_stdout:
            ipk_found.append(ipk)
            continue

        # Check if the package contains any cache file, if so the package was installed correctly
        cache_cmd = f"ls -l /var/data/opkg/opkg-cache/ | grep {ipk}"
        return_stdout, _, _ = mtee_target.execute_command(cache_cmd)
        logger.info(f"Cache output: {return_stdout}")
        if return_stdout:
            ipk_found.append(ipk)

    missing_ipks = list(set(required_ipks) - set(ipk_found))
    if missing_ipks:
        return_stdout, _, _ = mtee_target.execute_command("opkg list")
        logger.info(f"{missing_ipks} not installed.\n List of installed packages: {return_stdout}")
        return False
    return True


def validate_output_list(obtained_output_string, expected_output_list):
    """
    Validates output with a expected output list, will fail even if one expected item is not present
    :param string obtained_output_string: output from the target
    :param list expected_output_list: list of expected logs
    :return bool, list failed_output_list: list of expected logs not present in the output
    """
    failed_output_logs = []
    for expected in expected_output_list:
        if expected not in obtained_output_string:
            failed_output_logs.append(expected)
    if len(failed_output_logs) == 0:
        return True, failed_output_logs
    else:
        return False, failed_output_logs


def set_service_pack_value():
    """
    - This function sets the service_pack value based on the target's capabilities("SP21" or "SP25")
    """
    service_pack = None
    mtee_target = TargetShare().target
    if mtee_target.has_capability(TEST_ENVIRONMENT.service_pack.SP21):
        service_pack = "SP21"
        return service_pack
    elif mtee_target.has_capability(TEST_ENVIRONMENT.service_pack.SP25):
        service_pack = "SP25"
        return service_pack
    else:
        assert_is_not_none(service_pack, "Service Pack is different from SP21 or SP25")


def get_elem_bounds_detail(elem_from_driver, crop_region=False):
    """_summary_

    :param _type_ elem_from_driver: _description_
    :param bool crop_region: _description_, defaults to False
    :return _type_: _description_
    """
    assert hasattr(
        elem_from_driver, "get_attribute"
    ), "Given element seems to not be given by appium\
        webdriver as it doesn't have the method get_attribute"

    bounds = elem_from_driver.get_attribute("bounds")
    bounds_list = split(r"[\[\],]", bounds)
    bounds_list = list(filter(None, bounds_list))
    bounds_list = list(map(float, bounds_list))
    if crop_region:
        return bounds_list[0], bounds_list[1], bounds_list[2], bounds_list[3]
    else:
        return {
            "x_ini": bounds_list[0],
            "y_ini": bounds_list[1],
            "x_end": bounds_list[2],
            "y_end": bounds_list[3],
            "x_width": bounds_list[2] - bounds_list[0],
            "y_height": bounds_list[3] - bounds_list[1],
            "ratio": (bounds_list[2] - bounds_list[0]) / (bounds_list[3] - bounds_list[1]),
        }


def check_use_case(available_use_cases, use_case, error_msg):
    """Helper function to check specific use cases

    None->Test does not run so, SkipTest will be raised
    False->Test failed
    True->Test success

    :param available_use_cases: dict of available use cases
    Example: {"use_case": <None(test did not run), False(test failed), True(test pass)>}
    :param use_case: specific use case to check
    :param error_msg: error message in case of test fail
    """
    state = available_use_cases.get(use_case, None)
    if state is None:
        raise SkipTest("Skipped since use case was not tested")

    assert state, error_msg
