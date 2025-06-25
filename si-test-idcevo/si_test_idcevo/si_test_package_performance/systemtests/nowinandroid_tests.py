# Copyright (C) 2025. BMW Car IT. All rights reserved.
"""
Test for benchmarking the ECU's performance in a stable application (Now In Android).
This test always uses the same version of the app, so the performance can be directly compared between different builds
"""
import time

from unittest import skipIf
from mtee.testing.tools import metadata

import si_test_idcevo.si_test_helpers.test_helpers as utils

from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.pages.nowinandroid_page import NowInAndroidPage
from si_test_idcevo.si_test_helpers.performance_helpers import (
    process_and_store_gfx_metrics,
    reboot_into_fresh_lifecycle,
)
from si_test_idcevo.si_test_helpers.test_helpers import skip_unsupported_ecus

APP_STABILIZE_WAIT_TIME = 30


class TestNIAFrameTime:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(root=True)
        cls.nowinandroid = NowInAndroidPage()

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

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
        duplicates="IDCEVODEV-317429",
    )
    @skipIf(skip_unsupported_ecus(["rse26", "cde"]), "This test isn't supported by this ECU!")
    def test_001_benchmark_now_in_android(self):
        """Benchmark IDCevo performance in Now In Android android app

        Steps:
        1. Install NowInAndroid application and upload test data:
            1.1 - Fetch and install the app
            1.2 - Find owner of app data
            1.3 - Start application to generate relevant data
            1.4 - Upload test data to target
        2. Reboot target to guarantee a clean state. Wait 60 seconds
        3. Open the application, select preferences and close prompt
        4. Wait for the app to stabilize and load all article images
        5. Execute the performance test:
            5.1 - Reset GFX statistics
            5.2 - Perform two down scrolls
            5.3 - Perform two up scrolls
            5.4 - Read GFX statistics

        Expected result:
        1. NowInAndroid application is installed and test data is uploaded
        2. Performance test is executed and GFX statistics are collected
        """
        self.test.setup_driver()
        self.nowinandroid.install_apk_and_upload_data(self.test)
        self.test.teardown_appium()
        reboot_into_fresh_lifecycle(self.test)
        self.test.setup_driver()
        self.nowinandroid.open_app(self.test)
        self.nowinandroid.click_preferences_and_close_prompt(self.test)
        self.test.take_apinext_target_screenshot(self.test.results_dir, "Clicked_preferences")
        time.sleep(APP_STABILIZE_WAIT_TIME)
        gfx_statistics = self.nowinandroid.execute_performance_benchmark(self.test)
        process_and_store_gfx_metrics(
            self.test, gfx_statistics=gfx_statistics, output_file_name="nowinandroid_frame_times.json"
        )
