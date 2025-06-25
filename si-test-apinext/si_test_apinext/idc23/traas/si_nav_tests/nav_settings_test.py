#  Copyright (C) 2023. BMW Car IT. All rights reserved.
import logging
from nose import SkipTest

from appium.webdriver.common.appiumby import AppiumBy
from mtee.testing.test_environment import require_environment, require_environment_setup, TEST_ENVIRONMENT as TE
from si_test_apinext.idc23 import HMI_BUTTONS_REF_IMG_PATH
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.navigation_page import NavigationPage as Navi
from si_test_apinext.idc23.pages.personal_assistant_page import PersonalAssistantPage
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.global_steps import GlobalSteps
from si_test_apinext.util.hmi_helper import HMIhelper

logger = logging.getLogger(__name__)
REQUIREMENTS = TE.target_type.hu, TE.test_bench.rack


@require_environment(*REQUIREMENTS)
class TestNaviSettings:
    hmi_buttons_ref_img_path = HMI_BUTTONS_REF_IMG_PATH

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        if not cls.test.apinext_target:
            cls.test.setup_apinext_target()
        cls.hmihelper = HMIhelper(cls.test, cls.hmi_buttons_ref_img_path)
        utils.start_recording(cls.test)

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def teardown_class(cls):
        Navi.stop_route_guidance()
        Launcher.go_to_home()
        utils.stop_recording(cls.test, "TestNaviSettings")
        cls.test.quit_driver()

    @utils.gather_info_on_fail
    def test_00_toggle_spoken_instructions(self):
        """
        Toggle the Spoken instructions option

        Steps:
        1. Open Navigation and go to navigation settings.
        2. Validate navigation settings is open.
        3. Capture snapshot & find current button status of spoken instructions option using match template.
        4. Click on spoken instructions option.
        5. Capture snapshot & validate the button status of spoken instructions is toggled.

        Traceability: ABPI-361224
        """
        PersonalAssistantPage.ensure_language_package_installed()
        Navi.go_to_navigation()
        settings_bt = self.test.driver.find_element(*Navi.SETTINGS_BUTTON_ID)
        GlobalSteps.click_button_and_expect_elem(self.test.wb, settings_bt, Navi.SETTINGS_AREA_ID)
        self.test.driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR, "new UiScrollable(new UiSelector().scrollable(true)).flingToBeginning(1)"
        )
        Navi.toggle_nav_settings(self.hmihelper, "test_00_toggle_spoken_instructions", Navi.SPOKEN_INSTRUCTIONS_ID)

    @utils.gather_info_on_fail
    def test_01_toggle_auto_zoom(self):
        """
        Toggle the Auto zoom option

        Steps:
        1. Open Navigation and go to navigation settings.
        2. Validate navigation settings is open.
        3. Capture snapshot & find current button status of Auto zoom option using match template.
        4. Click on Auto zoom option.
        5. Capture snapshot & validate the button status of Auto zoom is toggled.

        Traceability: ABPI-361224
        """
        Navi.toggle_nav_settings(self.hmihelper, "test_01_toggle_auto_zoom", Navi.AUTO_ZOOM_ID)

    @utils.gather_info_on_fail
    def test_02_toggle_map_views(self):
        """
        Toggle the Map view option

        Steps:
        1. Open Navigation and go to navigation settings.
        2. Validate navigation settings is open.
        3. Click on Map view option.
        4. Select a Map view option other than the current one selected.
        5. Validate the selected map view is reflect in the navigation settings.

        Traceability: ABPI-361224
        """
        # After pu2403, map view button not present on nav settings as mentioned here HU22DM-205927
        if self.test.branch_name != "pu2311":
            raise SkipTest("Test not applicable for pu2403 and further after UX changes.")
        self.test.driver.find_element(*Navi.SETTINGS_AREA_ID)
        for each_view in Navi.MAP_VIEWS:
            map_view = self.test.driver.find_element(*Navi.POP_UP_LIST)
            self.hmihelper.click_and_capture(map_view, "test_02_toggle_map_view_before.png")
            new_view = self.test.driver.find_element(*each_view)
            self.hmihelper.click_and_capture(new_view, "test_02_toggle_map_view_after.png")
            map_view = self.test.driver.find_element(*Navi.POP_UP_LIST)
            map_view.find_element(*each_view)

    @utils.gather_info_on_fail
    def test_03_toggle_avoid_motorways(self):
        """
        Toggle the Avoid motorways option

        Steps:
        1. Open Navigation and go to navigation settings.
        2. Validate navigation settings is open.
        3. Capture snapshot & find current button status of Avoid motorways option using match template.
        4. Click on Avoid motorways option.
        5. Capture snapshot & validate the button status of Avoid motorways is toggled.

        Traceability: ABPI-361224
        """
        self.test.driver.swipe(*Navi.ROUTE_OPTION_SWIPE, duration=1000)
        Navi.toggle_nav_settings(self.hmihelper, "test_03_toggle_avoid_motorways", Navi.AVOID_MOTORWAYS)

    @utils.gather_info_on_fail
    def test_04_toggle_avoid_toll_roads(self):
        """
        Toggle the Avoid toll roads option

        Steps:
        1. Open Navigation and go to navigation settings.
        2. Validate navigation settings is open.
        3. Capture snapshot & find current button status of Avoid toll roads option using match template.
        4. Click on Avoid toll roads option.
        5. Capture snapshot & validate the button status of Avoid toll roads is toggled.

        Traceability: ABPI-361224
        """
        self.test.driver.swipe(*Navi.ROUTE_OPTION_SWIPE, duration=1000)
        Navi.toggle_nav_settings(self.hmihelper, "test_04_toggle_avoid_toll_roads", Navi.AVOID_TOLL)

    @utils.gather_info_on_fail
    def test_05_toggle_avoid_ferries(self):
        """
        Toggle the Avoid ferries option

        Steps:
        1. Open Navigation and go to navigation settings.
        2. Validate navigation settings is open.
        3. Capture snapshot & find current button status of Avoid ferries option using match template.
        4. Click on Avoid ferries option.
        5. Capture snapshot & validate the button status of Avoid ferries is toggled.

        Traceability: ABPI-361224
        """
        self.test.driver.swipe(*Navi.ROUTE_OPTION_SWIPE, duration=1000)
        Navi.toggle_nav_settings(self.hmihelper, "test_05_toggle_avoid_ferries", Navi.AVOID_FERRIES)

    @utils.gather_info_on_fail
    def test_06_toggle_demo_mode(self):
        """
        Toggle the Demo mode option

        Steps:
        1. Open Navigation and go to navigation settings.
        2. Validate navigation settings is open.
        3. Capture snapshot & find current button status of Demo mode option using match template.
        4. Click on Demo mode option.
        5. Capture snapshot & validate the button status of Demo mode is toggled.

        Traceability: ABPI-361224
        """
        self.test.driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR, "new UiScrollable(new UiSelector().scrollable(true)).flingToEnd(2)"
        )
        Navi.toggle_nav_settings(self.hmihelper, "test_06_toggle_demo_mode", Navi.DEMO_MODE)

    @utils.gather_info_on_fail
    def test_07_validate_release_notes(self):
        """
        Validate Release note data is present

        Steps:
        1. Open Navigation and go to navigation settings.
        2. Validate navigation settings is open.
        3. Validate all release note elements are present.

        Traceability: ABPI-361224
        """
        self.test.driver.find_element(*Navi.SETTINGS_AREA_ID)
        self.test.driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR, "new UiScrollable(new UiSelector().scrollable(true)).flingToEnd(2)"
        )
        utils.take_apinext_target_screenshot(self.test.apinext_target, self.test.results_dir, "Nav_release_notes.png")
        self.test.driver.find_element(*Navi.BUILD_VERSION)
        self.test.driver.find_element(*Navi.BUILD_DATE)
        self.test.driver.find_element(*Navi.MAP_ATTRIBUTION)
        self.test.driver.find_element(*Navi.MAPBOX_ATTRIBUTION)
