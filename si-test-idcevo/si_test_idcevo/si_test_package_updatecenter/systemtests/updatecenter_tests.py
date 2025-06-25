# Copyright (C) 2024-2025. BMW Group. All rights reserved.
import configparser
import logging
import time
from pathlib import Path
from unittest import skipIf

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT
from mtee.testing.tools import metadata
from si_test_idcevo.si_test_helpers import test_helpers as utils
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.apinext_target_handlers import LIST_MAIN_DISPLAY_ID
from si_test_idcevo.si_test_helpers.pages.idcevo.updatecenter_page import UpdateCenterPage as UpdateCenter
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
target = TargetShare().target

DISPLAY_ID = LIST_MAIN_DISPLAY_ID["idcevo"]


@skipIf(
    not (target.has_capability(TEST_ENVIRONMENT.test_bench.rack)),
    "Test class only applicable for test racks",
)
class TestOneUpdateIdleAndSearch:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(enable_appium=True, root=True)
        cls.test.apinext_target.wait_for_boot_completed_flag()
        wait_for_application_target(cls.test.mtee_target)

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-android-traas"],
        component="None",
        domain="Performance",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "IDLE_SEARCH"),
            },
        },
    )
    def test_001_idle_search(self):
        """
        [SIT_Automated] Check IDLE screen

        Steps:
            1. Open OneUpdate app
            2. Check that expected information is displayed to screen

        Expected outcome:
            1. Information from idle screen is visible in screen
        """

        UpdateCenter.start_activity_via_cardomain()
        time.sleep(2)
        UpdateCenter.validate_activity()

        UpdateCenter.check_visibility_of_element(UpdateCenter.RSU_TITLE, 3)
        UpdateCenter.check_visibility_of_element(UpdateCenter.RSU_BUTTON_TEXT, 3)
        UpdateCenter.check_visibility_of_element(UpdateCenter.RSU_INFO_TEXT, 3)
        UpdateCenter.check_visibility_of_element(UpdateCenter.RSU_UPDATE_SETTINGS_TEXT, 3)
        UpdateCenter.check_visibility_of_element(UpdateCenter.RSU_SUBTITLE, 3)

        self.test.take_apinext_target_screenshot(self.test.results_dir, "final_check_idle_screen.png")
