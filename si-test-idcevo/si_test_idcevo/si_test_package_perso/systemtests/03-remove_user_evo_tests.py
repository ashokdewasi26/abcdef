# Copyright (C) 2024-2025. BMW Group. All rights reserved.
import configparser
import logging
import time
from pathlib import Path
from unittest import SkipTest

from appium.webdriver.common.appiumby import AppiumBy
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import assert_true, metadata
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from si_test_idcevo.si_test_helpers import test_helpers as utils
from si_test_idcevo.si_test_helpers.android_helpers import ensure_launcher_page
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.apinext_target_handlers import LIST_MAIN_DISPLAY_ID
from si_test_idcevo.si_test_helpers.pages.idcevo.perso_page import PersoBMWIDPage as Perso
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target
from validation_utils.utils import TimeoutCondition

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

DISPLAY_ID = LIST_MAIN_DISPLAY_ID["idcevo"]
# Use cases for perso tests to be displayed on reporting
# {"use_case": <None(test did not run), False(test failed), True(test pass)>}
USE_CASES = {
    "remove_user": None,
}


class TestPersoSwitchUserEvo:
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
        testsuite=["BAT", "SI", "SI-android", "SI-performance", "SI-perso-traas"],
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
                "FEATURE": config.get("FEATURES", "PERSO_USER_SWITCH"),
            },
        },
    )
    def test_001_add_user(self):
        """
        001 - [SIT_Automated] Check user creation button

        Steps:
            1. Open Perso app
            2. Wait for Add Profile button to appear
            3. Click on Add Profile button

        Expected outcome:
            1. Add Profile button is available and accessible
        """

        if not self.test.mtee_target.has_capability(TE.test_bench.rack):
            SkipTest("Skipping test as it is not running on rack")

        ensure_launcher_page(self.test)
        Perso.start_activity()
        time.sleep(2)
        self.test.take_apinext_target_screenshot(self.test.results_dir, "001_perso_app", DISPLAY_ID)

        timeout_condition = TimeoutCondition(10)
        while timeout_condition:
            add_user_element = Perso.get_element(self.test.driver, Perso.ADD_PROFILE_BTN)
            if add_user_element is not None:
                break
            time.sleep(1)
        assert_true(add_user_element is not None, "Failed to get add_user_element")

        try:
            add_user_element.click()
            time.sleep(2)
            self.test.take_apinext_target_screenshot(self.test.results_dir, "001_add_user_element_click", DISPLAY_ID)
        except NoSuchElementException:
            logger.debug("add_user_element not found")

    # THIS NEEDS TO BE THE LAST TEST
    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-perso-traas"],
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
                "FEATURE": config.get("FEATURES", "PERSO_USER_SWITCH"),
            },
        },
    )
    def test_002_remove_user_profile(self):
        """002 - [SIT_Automated] Remove user profile

        Steps:
            1. Open Perso app
            2. Click on "User Settings"
            3. Swipe up to see "Remove User" button
            4. Remove user profile
            5. Check if user is removed

        Expected outcome:
            SITLion user is removed
        """

        USE_CASES["remove_user"] = False
        Perso.start_activity()
        time.sleep(3)

        try:
            user_id = self.test.driver.find_element(
                By.XPATH,
                f"//*[contains(@text,'{Perso.SITLION_USER}')]",
            )
            logger.info(f"{Perso.SITLION_USER} found. Going to remove it...")
        except NoSuchElementException:
            logger.info(f"{Perso.SITLION_USER} not found. Terminating test...")
            user_id = None
        self.test.take_apinext_target_screenshot(self.test.results_dir, "user_homepage")
        assert_true(user_id is not None, f"Error on finding {Perso.SITLION_USER} user")

        self.test.apinext_target.execute_adb_command(["shell", "input", "touchscreen", "tap", "2350", "455"])
        time.sleep(2)
        self.test.take_apinext_target_screenshot(self.test.results_dir, "user_settings")
        self.test.apinext_target.execute_adb_command(
            ["shell", "input", "touchscreen", "swipe", "1350", "1000", "1350", "650"]
        )
        self.test.take_apinext_target_screenshot(self.test.results_dir, "user_settings_swipe")
        time.sleep(2)
        remove_button = self.test.driver.find_element(
            by=AppiumBy.ANDROID_UIAUTOMATOR, value='new UiSelector().resourceId("delete_current_user_button")'
        )
        remove_button.click()
        time.sleep(2)
        self.test.take_apinext_target_screenshot(self.test.results_dir, "removing_confirmation")

        user_id = self.test.driver.find_element(
            By.XPATH,
            "//*[contains(@text,'Yes, remove')]",
        )
        user_id.click()

        # close appium because changing user will break the session
        self.test.teardown_appium()
        time.sleep(5)
        self.test.setup_driver()

        time.sleep(2)
        Perso.start_activity()
        time.sleep(5)

        try:
            user_id = self.test.driver.find_element(
                By.XPATH,
                f"//*[contains(@text,'{Perso.SITLION_USER}')]",
            )
            user_removed = False
            logger.info(f"User still exists: {user_id}")
        except NoSuchElementException:
            logger.info("User not found after removing it")
            user_removed = True

        Perso.start_activity()
        time.sleep(3)
        self.test.take_apinext_target_screenshot(self.test.results_dir, "user_removed")
        if user_removed:
            USE_CASES["remove_user"] = True
        else:
            raise AssertionError("Error removing user")

    def test_003_remove_user(self):
        """003 - [PERSO_USE_CASE] Remover user"""
        utils.check_use_case(
            USE_CASES,
            "remove_user",
            "User cannot be removed. " "Please check 'Remove user profile' test for more details",
        )
