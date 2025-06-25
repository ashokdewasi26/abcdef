# Copyright (C) 2023. BMW Car IT. All rights reserved.
import logging
import time

from mtee.testing.tools import assert_true, metadata

import si_test_idcevo.si_test_helpers.test_helpers as utils
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.pages.idcevo.launcher_page import LauncherPage as Launcher

logger = logging.getLogger(__name__)


@metadata(testsuite=["SI", "SI-android"])
class TestLauncher:
    @classmethod
    def setup_class(cls):
        # TestBase is a singleton class to re-use appium driver and target vars
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(enable_appium=True)
        cls.test.start_recording()

    @classmethod
    def teardown_class(cls):
        video_name = "TestLauncher"
        cls.test.stop_recording(video_name)
        cls.test.teardown_base_class()

    @utils.gather_info_on_fail
    def test_001_check_launcher_available_and_capture_snapshot(self):
        """
        [SIT_Automated] Check launcher is available and capture a screenshot
        """
        time.sleep(1)
        launcher_available = Launcher().validate_activity()
        assert_true(launcher_available, "Failed to validate Launcher service")

        self.test.take_apinext_target_screenshot(self.test.results_dir, "launcher_available_screenshot")

    @utils.gather_info_on_fail
    def test_002_check_go_back_to_home(self):
        """
        [SIT_Automated] Check that after going to menu we can go back to home
        """
        result_all_apps = Launcher().press_all_apps_button(self.test)
        time.sleep(2)
        utils.get_screenshot_and_dump(self.test, self.test.results_dir, "launcher_all_apps_menu")
        assert_true(result_all_apps > 0, "Failed to press all apps button")

        Launcher.go_to_home(self.test)
        time.sleep(2)
        utils.get_screenshot_and_dump(self.test, self.test.results_dir, "launcher_home")
