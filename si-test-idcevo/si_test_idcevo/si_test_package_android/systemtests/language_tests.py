# Copyright (C) 2025. BMW CTW PT. All rights reserved.
import configparser
import logging
import time

from pathlib import Path
from mtee.testing.tools import metadata
import si_test_idcevo.si_test_helpers.test_helpers as utils
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)


@metadata(
    testsuite=["SI", "SI-android"],
    component="tee_idcevo",
    domain="IDCEvo Test",
    categorization="functional",
    priority="1",
    duplicates="IDCEVODEV-529521",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": config.get("FEATURES", "TEE_FEATURE"),
        },
    },
)
class TestLanguages:
    @classmethod
    def setup_class(cls):
        # TestBase is a singleton class to re-use appium driver and target vars
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(enable_appium=True)
        # cls.test.start_recording()

    @classmethod
    def teardown_class(cls):
        # video_name = "TestLanguages"
        # cls.test.stop_recording(video_name)
        cls.test.teardown_base_class()

    @utils.gather_info_on_fail
    def test_001_change_language_via_adb_local_change(self):
        """[SIT_Automated] Test changing the system language via ADB

        This test performs the following steps:
        1. Changes the device language to Portuguese ("pt"), waits for the change to take effect, and
         captures a screenshot of the launcher page.
        2. Changes the language to German ("de"), waits, and captures another screenshot.
        3. Changes the language to French ("fr"), waits, and captures another screenshot.
        4. Changes the language back to English ("en"), waits, and captures a final screenshot.

        Each screenshot is saved in the test results directory with a filename indicating the language.
        This test monitors that the launcher UI updates correctly for each language change.
        No assertions are made, test only fails if adb command raises an exception.
        """
        languages = [
            ("pt", "launcher_page_pt"),
            ("de", "launcher_page_de"),
            ("fr", "launcher_page_fr"),
            ("en", "launcher_page_en"),
        ]
        for lang, screenshot_name in languages:
            self.test.change_language(language=lang)
            time.sleep(3)
            utils.get_screenshot_and_dump(self.test, self.test.results_dir, screenshot_name)
