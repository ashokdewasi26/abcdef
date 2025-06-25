# Copyright (C) 2024. BMW Car IT. All rights reserved.
"""Test that fetches rendered frames' statistics in main menu swiping"""
import logging
import re
import time

from unittest import skipIf
from mtee.testing.tools import metadata

import si_test_idcevo.si_test_helpers.test_helpers as utils

from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.pages.idcevo.allapps_page import AllAppsPage
from si_test_idcevo.si_test_helpers.performance_helpers import (
    process_and_store_gfx_metrics,
    reboot_into_fresh_lifecycle,
)
from si_test_idcevo.si_test_helpers.test_helpers import skip_unsupported_ecus

logger = logging.getLogger(__name__)


HISTOGRAM_THRESHOLD = 25
# Command structuring: adb shell input swipe "${x1}" "${y1}" "${x2}" "${y2}" "${duration}"
left_to_right_swipe = 'input swipe "1000" "720" "2000" "720" "500"'
right_to_left_swipe = 'input swipe "2000" "720" "1000" "720" "500"'
reset_gfx_stats = "dumpsys gfxinfo com.bmwgroup.idnext.launcher reset"
read_gfx_stats = "dumpsys gfxinfo com.bmwgroup.idnext.launcher"

regex_patterns = {
    "total_frames": r"Total frames rendered: (\d+)",
    "janky_frames": r"Janky frames: (\d+)",
    "janky_frames_legacy": r"Janky frames \(legacy\): (\d+)",
    "percentile_50": r"50th percentile: (\d+)ms",
    "percentile_90": r"90th percentile: (\d+)ms",
    "percentile_95": r"95th percentile: (\d+)ms",
    "percentile_99": r"99th percentile: (\d+)ms",
}

page_capture_regex = re.compile(
    r'android\.widget\.TextView\s+index="1"\s+package="com\.bmwgroup\.idnext\.launcher"'
    r'\s+class="android\.widget\.TextView"\s+text="([^"]*)"\s+resource-id="TextAtom:dynamic_string'
)


class TestFrameTime:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(root=True)
        cls.all_apps = AllAppsPage()
        cls.pages_content = []

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    @classmethod
    def perform_swipes(cls, cmd, count):
        """Perform swipe actions on the application menu"""
        for _ in range(count):
            time.sleep(1)
            cls.all_apps.start_activity(cmd=cmd)

    @classmethod
    def get_page_content(cls):
        """Obtains the current window dump and returns the name of the first app in the current page"""
        time.sleep(2)  # Wait for page to stabilize
        page_dump = cls.test.driver.page_source
        if not page_dump:
            time.sleep(5)
            page_dump = cls.test.driver.page_source
            if not page_dump:
                raise RuntimeError("Could not obtain page dump even after a second try.")

        # Capture part of the dump that contains the name of the first app in the current page
        if match := page_capture_regex.search(page_dump):
            captured_text = match.group(1)
        else:
            raise RuntimeError("Could not match regex in the page dump.")

        return captured_text

    @classmethod
    def map_all_apps_menu_pages(cls):
        """Populates the pages_content list with the name of the first app in the application menu"""
        consecutive_retries = 0
        while consecutive_retries < 10:
            page_dump = cls.get_page_content()

            if not cls.pages_content:
                cls.pages_content.append(page_dump)
                cls.test.take_apinext_target_screenshot(cls.test.results_dir, "first_page_added")
                logger.debug(f"First page added: {cls.pages_content[0]}")
            elif cls.pages_content[-1] == page_dump:
                # Current page is equal to page before swipe,
                # which means a swipe failed, or that we reached the last page
                consecutive_retries += 1
            else:
                cls.pages_content.append(page_dump)
                cls.test.take_apinext_target_screenshot(cls.test.results_dir, "page_added")
                logger.debug(f"Page {len(cls.pages_content)} added: {cls.pages_content[-1]}")
                consecutive_retries = 0

            cls.perform_swipes(right_to_left_swipe, 1)

        # Return to first page for test execution
        cls.go_back_to_first_page()

    @classmethod
    def go_back_to_first_page(cls):
        """Return to the first page of the application menu"""
        max_retries = 20
        page_content = cls.get_page_content()
        retries = 0
        while page_content != cls.pages_content[0] and retries < max_retries:
            cls.perform_swipes(left_to_right_swipe, 1)
            page_content = cls.get_page_content()
            retries += 1
            if retries >= max_retries:
                logger.debug(
                    f"Couldnt return to page 1. Current content:{page_content} Expected content:{cls.pages_content[0]}"
                )
                raise RuntimeError("Could not return to first page after 20 tries. Error should be investigated.")

    @classmethod
    def execute_performance_routine(cls):
        """Executes the performance routine and guarantees that it is executed correctly, retrying if necessary"""
        max_retries = 10
        for retries in range(max_retries):
            gfx_stats_output = cls._performance_routine()
            cls.go_back_to_first_page()
            if gfx_stats_output != -1:
                return gfx_stats_output

            if retries + 1 >= max_retries:
                raise RuntimeError(
                    "Couldnt execute performance test after 10 tries, check performance_swipe_test_failed screenshots"
                )

    @classmethod
    def _performance_routine(cls):
        """Performs two swipes to the left and reads GFX statistics; returns "-1" if page 3 is not reached"""
        cls.all_apps.start_activity(cmd=reset_gfx_stats)
        cls.perform_swipes(right_to_left_swipe, 2)
        gfx_stats_output = str(cls.all_apps.start_activity(cmd=read_gfx_stats))

        current_page = cls.get_page_content()
        if current_page != cls.pages_content[2]:
            cls.test.take_apinext_target_screenshot(cls.test.results_dir, "performance_swipe_test_failed")
            return -1

        logger.debug(f"GFX statistics: {gfx_stats_output}")
        cls.test.take_apinext_target_screenshot(cls.test.results_dir, "performance_swipe_test_success")
        return gfx_stats_output

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI", "SI-performance", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Performance",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-129350",
    )
    @skipIf(skip_unsupported_ecus(["rse26", "cde"]), "This test isn't supported by this ECU!")
    def test_001_measure_frame_time(self):
        """
        [SIT_Automated] Measure frame times of application menu swipe

        Steps:
        1 - Perform a reboot so the test begins in a sanitized state.
        2 - Wait 60 seconds for stabilization. Certify target is in application mode.
        3 - Open application menu.
        4 - Create a map of the pages in the application menu.
        5 - Execute the performance test:
            5.1 - Reset GFX statistics.
            5.2 - Execute 2 swipes to the left.
            5.3 - Read GFX statistics.
            5.4 - Check if the page after the swipes is the expected one. Repeat if not.
        6 - Create an histogram to store in test folder.
        7 - Process data and put into a json for the metric collector to read.
        """

        reboot_into_fresh_lifecycle(self.test)
        self.test.apinext_target.root()
        self.test.setup_driver()
        time.sleep(3)

        self.all_apps.start_activity()
        time.sleep(3)
        self.test.take_apinext_target_screenshot(self.test.results_dir, "after_opening_all_apps_menu")

        self.map_all_apps_menu_pages()

        gfx_statistics = self.execute_performance_routine()

        process_and_store_gfx_metrics(
            self.test, gfx_statistics=gfx_statistics, output_file_name="all_apps_frame_times.json"
        )
