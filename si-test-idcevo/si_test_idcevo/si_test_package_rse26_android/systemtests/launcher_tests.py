# Copyright (C) 2025. BMW Car IT. All rights reserved.
import logging
import time

from mtee.testing.tools import assert_true, metadata
import si_test_idcevo.si_test_helpers.test_helpers as utils
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.pages.rse26.launcher_page import LauncherPage as Launcher

logger = logging.getLogger(__name__)


@metadata(testsuite=["SI", "SI-android"])
class TestLauncher:
    @classmethod
    def setup_class(cls):
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
        launcher_available = Launcher.validate_activity()
        assert_true(launcher_available, "Failed to validate Launcher service")

        self.test.take_apinext_target_screenshot(self.test.results_dir, "launcher_available_screenshot")

    @utils.gather_info_on_fail
    def test_002_check_go_back_to_home(self):
        """
        [SIT_Automated] Check that after going to menu we can go back to home
        """
        Launcher.press_all_apps_button()
        utils.get_screenshot_and_dump(self.test, self.test.results_dir, "AllAppsMenu")
        assert_true(
            Launcher.validate_activity(
                list_activities=["com.bmwgroup.idnext.launcher.allapps.IdxAppOverviewActivity"]
            ),
            "Failed to validate All Apps menu activity",
        )

        Launcher.go_to_home()
        utils.get_screenshot_and_dump(self.test, self.test.results_dir, "launcher_home")
        assert_true(
            Launcher.validate_activity(list_activities=["com.bmwgroup.apinext.rselauncherapp/.MainActivity"]),
            "Failed to validate Launcher activity",
        )
