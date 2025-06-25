import glob
import logging
import os
from pathlib import Path
import time
from typing import Optional

from si_test_apinext.idc23 import HMI_BUTTONS_REF_IMG_PATH
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.screenshot_utils import capture_screenshot, compare_snapshot, match_template

logger = logging.getLogger(__name__)


class HMIhelper:
    def __init__(self, test_instance, ref_images_dir: Optional[Path] = HMI_BUTTONS_REF_IMG_PATH):
        self.test = test_instance
        self.results_dir_path = test_instance.results_dir

        if ref_images_dir:
            if Path(ref_images_dir).exists():
                self.ref_images_dir = ref_images_dir
            else:
                raise AssertionError(f"Given reference images path don't exist: '{str(ref_images_dir)}'")
        else:
            self.ref_images_dir = None

    def click_and_capture(self, button, test_name, sleep_time=1):
        """
        Click on the button element and capture the image
        Param button: button element to click
        Param test_name: screenshot name passed from the test
        Param sleep_time: Seconds to wait after clicking on an option.
        """
        button.click()
        time.sleep(sleep_time)
        return capture_screenshot(test=self.test, test_name=test_name, results_dir_path=self.results_dir_path)

    def find_current_button_status(self, button, test_name, image_pattern="*.png"):
        """
        Helper function to find an option in hmi is turned ON/OFF.

        TODO: Modify the function for radio buttons/ checkboxes for upcoming tests if needed.

        Param button: Button element to click.
        Param test_name: Screenshot name passed from the test.
        Param image_pattern: Regex for glob to search for files. By default, consider all *.png in ref_images_dir.
        """
        elem_bounds, ref_imgs_list = self.check_button_status_base(button, self.ref_images_dir, image_pattern)
        screenshot = capture_screenshot(test=self.test, test_name=test_name, results_dir_path=self.results_dir_path)
        for ref_img in ref_imgs_list:
            result, _ = match_template(
                image=screenshot,
                image_to_search=ref_img,
                region=elem_bounds,
                results_path=self.results_dir_path,
                acceptable_diff=6.0,
                save_diff=True,
            )
            if result:
                return "button_on" in Path(ref_img).stem
        return False

    def click_and_validate_button_status(self, button, status, test_name, sleep_time=2):
        """
        The Toggle button options doesn't provide the current status from the page source.
        Hence, identifying the current status of the button via image comparison.

        Param button: Button element to click.
        Param status: Current button status. We expect the button status to be toggled after clicking. ON->OFF/OFF->ON
        Param test_name: Screenshot name passed from the test.
        """
        screenshot = self.click_and_capture(button, test_name, sleep_time)
        button_reference = "button_on" if not status else "button_off"
        elem_bounds, files_data = self.check_button_status_base(
            button, self.ref_images_dir, button_reference + "*.png"
        )
        comparison_results = []
        for file_path in files_data:
            result, error = compare_snapshot(
                screenshot, file_path, test_name + "_compare", fuzz_percent=20, region=elem_bounds, unlink_files=True
            )
            comparison_results.append(result)
            if result:
                break
        assert any(comparison_results), f"Unable to find {button_reference} on {screenshot}, {error}"

    def ensure_button_status_on(self, button, test_name, sleep_time=3):
        """
        Turn on the option so the dependent options are enabled.

        Param button: Button element to click.
        Param test_name: Screenshot name passed from the test.
        """
        status = self.find_current_button_status(button, test_name, image_pattern="button_on*.png")
        if not status:
            self.click_and_validate_button_status(button, status, test_name, sleep_time=sleep_time)

    def ensure_button_status_off(self, button, test_name):
        """
        Turn off the option so the dependent options are enabled.

        Param button: Button element to click.
        Param test_name: Screenshot name passed from the test.
        """
        status = self.find_current_button_status(button, test_name, image_pattern="button_off*.png")
        if status:
            self.click_and_validate_button_status(button, status, test_name, sleep_time=3)

    @staticmethod
    def check_button_status_base(button, ref_images_dir, image_pattern):
        if ref_images_dir.exists():
            elem_bounds = utils.get_elem_bounds_detail(button, crop_region=True)
            files_data = glob.glob(os.path.join(ref_images_dir, image_pattern))
            logger.debug("Reference images %s", files_data)
            return elem_bounds, files_data
        else:
            raise RuntimeError(f"{ref_images_dir} does not exists. Check the folder structure and names.")
