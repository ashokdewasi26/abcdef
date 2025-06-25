# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Tests for the Modes and Moments application."""
import configparser
import logging
import re
import time

from pathlib import Path
from unittest import skipIf

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT
from mtee.testing.tools import assert_false, assert_regexp_matches, assert_true, metadata
import si_test_idcevo.si_test_helpers.test_helpers as utils
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.pages.idcevo.launcher_page import LauncherPage as Launcher
from si_test_idcevo.si_test_helpers.pages.idcevo.modes_page import ModesPage
from si_test_idcevo.si_test_helpers.screenshot_utils import extract_text, match_template

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)  # pylint: disable=invalid-name
target = TargetShare().target


@skipIf(
    not (target.has_capability(TEST_ENVIRONMENT.test_bench.rack)),
    "Test class only applicable for test racks",
)
class TestModesAndMoments:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(enable_appium=True, root=True)
        cls.modes_page = ModesPage()
        cls.modes_page.start_activity()
        cls.test.start_recording()

    @classmethod
    def teardown_class(cls):
        try:
            cls.modes_page.ensure_page_loaded(test=cls.test)
            if cls.modes_page.get_current_mode() != "PERSONAL":
                cls.modes_page.set_mode_and_validate(cls.test, "PERSONAL")
            video_name = "TestModesAndMoments"
            cls.test.stop_recording(video_name)
        except Exception as e:
            raise RuntimeError(f"Exception occurred while running teardown_class: {str(e)}")
        finally:
            cls.test.teardown_base_class()

    def setup(self):
        self.missing_modes = self.modes_page.ensure_page_loaded(self.test)

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-android-traas"],
        component="tee_idcevo",
        domain="Experiences and Modes",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-29902",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "MODES_MOMENTS_ENABLE_BASIC_MODES"),
            },
        },
    )
    def test_001_open_mymodes_application(self):
        """
        [SIT_Automated] Open MyModes Application
        Steps:
            1. Ensure Modes and Moments application open and loaded
            2. Find if all expected modes are visible
        Note:
            Screenshot and dump will be taken in case of failure.
        """
        assert_false(
            self.missing_modes,
            "Modes and Moments app doesn't have expected modes visible. "
            f"Check screenshot and dump for more information. Missing modes: {self.missing_modes}",
        )

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-android-traas"],
        component="tee_idcevo",
        domain="Experiences and Modes",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-29892",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "EXPERIENCE_AND_MODES_ACTIVATE_MODE"),
                    config.get("FEATURES", "RG4_EXPERIENCE_AND_MODES_ACTIVATE_MODE"),
                ],
            },
        },
    )
    def test_002_change_mode_to_efficient(self):
        """
        [SIT_Automated] Activate "Efficient" Mode in MyModes
        Steps:
            1. Ensure Modes and Moments application open and loaded
            2. Guarantee current mode is not "Efficient"
            3. Change mode to "Efficient"
            4. Check if mode was changed successfully
            5. Validate that background image changed after mode change
        """
        mode_to_test = "EFFICIENT"

        if self.modes_page.get_current_mode() == mode_to_test:
            raise RuntimeError(mode_to_test + " mode is already active")

        screenshot_before = self.test.take_apinext_target_screenshot(
            self.test.results_dir, "before_switching_to_" + mode_to_test
        )

        screenshot_after = self.modes_page.set_mode_and_validate(self.test, mode_to_test)

        assert_true(
            self.modes_page.check_if_background_changed(screenshot_before, screenshot_after),
            "Failed in validating background image change when changing mode to " + mode_to_test,
        )

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-android-traas"],
        component="tee_idcevo",
        domain="Experiences and Modes",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-144084",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "EXPERIENCE_AND_MODES_ACTIVATE_MODE"),
                    config.get("FEATURES", "RG4_EXPERIENCE_AND_MODES_ACTIVATE_MODE"),
                    config.get("FEATURES", "EXPERIENCE_AND_MODES_ENABLE_SILENT_MODE"),
                ],
            },
        },
    )
    def test_003_change_mode_to_silent(self):
        """
        [SIT_Automated] Activate "Silent" Mode in MyModes
        Steps:
            1. Ensure Modes and Moments application open and loaded
            2. Guarantee current mode is not "Silent"
            3. Change mode to "Silent"
            4. Check if mode was changed successfully
            5. Validate that background image changed after mode change
        """
        mode_to_test = "SILENT"
        if self.modes_page.get_current_mode() == mode_to_test:
            raise RuntimeError(mode_to_test + " mode is already active")

        screenshot_before = self.test.take_apinext_target_screenshot(
            self.test.results_dir, "before_switching_to_" + mode_to_test
        )

        screenshot_after = self.modes_page.set_mode_and_validate(self.test, mode_to_test)

        assert_true(
            self.modes_page.check_if_background_changed(screenshot_before, screenshot_after),
            "Failed in validating background image change when changing mode to " + mode_to_test,
        )

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-android-traas"],
        component="tee_idcevo",
        domain="Experiences and Modes",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-29891",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "EXPERIENCE_AND_MODES_ACTIVATE_MODE"),
                    config.get("FEATURES", "RG4_EXPERIENCE_AND_MODES_ACTIVATE_MODE"),
                ],
            },
        },
    )
    def test_004_change_mode_to_personal(self):
        """
        [SIT_Automated] Activate "Personal" Mode in MyModes
        Steps:
            1. Ensure Modes and Moments application open and loaded
            2. Guarantee current mode is not "Personal"
            3. Change mode to "Personal"
            4. Check if mode was changed successfully
            5. Validate that background image changed after mode change
        """
        mode_to_test = "PERSONAL"
        if self.modes_page.get_current_mode() == mode_to_test:
            raise RuntimeError(mode_to_test + " mode is already active")

        screenshot_before = self.test.take_apinext_target_screenshot(
            self.test.results_dir, "before_switching_to_" + mode_to_test
        )

        screenshot_after = self.modes_page.set_mode_and_validate(self.test, mode_to_test)

        assert_true(
            self.modes_page.check_if_background_changed(screenshot_before, screenshot_after),
            "Failed in validating background image change when changing mode to " + mode_to_test,
        )

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-android-traas"],
        component="tee_idcevo",
        domain="Experiences and Modes",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-29905",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "EXPERIENCE_AND_MODES_ACTIVATE_MODE"),
                    config.get("FEATURES", "RG4_EXPERIENCE_AND_MODES_ACTIVATE_MODE"),
                ],
            },
        },
    )
    def test_005_change_to_already_selected_mode(self):
        """
        [SIT_Automated] Select already active Mode
        Steps:
            1. Ensure Modes and Moments application open and loaded
            2. Guarantee current mode is "Personal"
            3. Try to change mode to "Personal" again
            4. Verify background image is still the same
        """
        if self.modes_page.get_current_mode() != "PERSONAL":
            self.modes_page.set_mode_and_validate(self.test, "PERSONAL")

        time.sleep(5)
        screenshot_before = self.test.take_apinext_target_screenshot(
            self.test.results_dir, "before_switching_to_same_mode"
        )
        self.modes_page.set_mode_and_validate(self.test, "PERSONAL")
        time.sleep(5)
        screenshot_after = self.test.take_apinext_target_screenshot(
            self.test.results_dir, "after_switching_to_same_mode"
        )

        assert_false(
            self.modes_page.check_if_background_changed(screenshot_before, screenshot_after),
            "Before and after mode change image comparison threshold exceeded; background image changed unexpectedly.",
        )

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-android-traas"],
        component="tee_idcevo",
        domain="Experiences and Modes",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-29886",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "RG4_EXPERIENCE_AND_MODES_ACTIVATE_MODE"),
                    config.get("FEATURES", "EXPERIENCE_AND_MODES_ACTIVATE_MODE"),
                ],
            },
        },
    )
    def test_006_change_mode_to_sport(self):
        """
        [SIT_Automated] Activate "Sport" Mode in MyModes
        Steps:
            1. Ensure Modes and Moments application open and loaded
            2. Guarantee current mode is not "Sport", if current mode is sport, switch to default mode (Personal)
            3. Change mode to "Sport"
            4. Check if mode was changed successfully
            5. Validate that background image changed after mode change
        """
        mode_to_test = "SPORT"
        if self.modes_page.get_current_mode() == mode_to_test:
            raise RuntimeError(mode_to_test + " mode is already active")
        screenshot_before = self.test.take_apinext_target_screenshot(
            self.test.results_dir, "before_switching_to_" + mode_to_test
        )
        screenshot_after = self.modes_page.set_mode_and_validate(self.test, mode_to_test)
        assert_true(
            self.modes_page.check_if_background_changed(screenshot_before, screenshot_after),
            "Failed in validating background image change when changing mode to " + mode_to_test,
        )

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-android-traas"],
        component="tee_idcevo",
        domain="Experiences and Modes",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-148821",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "MY_MODES_GENERAL_SETTING"),
            },
        },
    )
    def test_007_mymodes_present_in_startup_menu(self):
        """
        [SIT_Automated] All MyModes present in StartUp Menu
        Steps:
            1. Ensure Modes and Moments application open and loaded
            2. Choose a MyMode and click the Configuration Button.
            3. Click on the general button and validate Start Mode button should be visible.
            4. Click on Start Mode and validate below modes must be visible on the page.
                ["Personal", "Efficient", "Sport", "Silent"]
        """
        last_used_info_regex = (
            r"The last-used My.*Mode is set automatically when the vehicle is started. Sport.*Mode"
            r" is excluded for legal reasons\."
        )
        self.modes_page.click(locator=self.modes_page.CONFIGURE_TAB)
        self.modes_page.click(locator=self.modes_page.GENERAL_TAB)
        assert_true(
            self.modes_page.check_visibility_of_element(self.modes_page.START_MODE_BTN),
            "Start Mode button is not visible in General tab of modes and moments app",
        )
        assert_true(
            self.modes_page.check_visibility_of_element(self.modes_page.RESET_MODE_BTN),
            f"Reset {self.modes_page.get_current_mode} button is not visible in General tab of modes and moments app",
        )
        self.modes_page.click(locator=self.modes_page.START_MODE_BTN)

        last_used_popup_element = self.modes_page.check_visibility_of_element(self.modes_page.LAST_USED_BTN)
        last_used_btn_info_text = last_used_popup_element.get_attribute("text")
        assert_regexp_matches(
            last_used_btn_info_text,
            last_used_info_regex,
            "'Last Used' option with the expected info message 'The last-used My Mode is set automatically "
            "when the vehicle is started. Sport Mode is excluded for legal reasons.' not visible on screen,"
            f"found text - {last_used_btn_info_text}, pop-up might have not launched after clicking on Start Mode",
        )
        self.modes_page.swipe_using_coordinates(coordinates=[1500, 1000, 1500, 630])
        utils.get_screenshot_and_dump(self.test, self.test.results_dir, "start_mode_popup_list_after_scroll")
        missing_modes = self.modes_page.find_missing_modes()
        assert_false(
            missing_modes,
            "Modes and Moments StartUp Menu doesn't have expected modes visible. "
            f"Check screenshot and dump for more information. Missing modes: {missing_modes}",
        )

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-android-traas"],
        component="tee_idcevo",
        domain="Experiences and Modes",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-212240",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "PERSONAL_MODE_AMBIENT_LIGHT_SETTING"),
                ],
            },
        },
    )
    def test_008_ambient_light_color_wheel_selecting_multicolor_tapping(self):
        """
        [SIT_Automated] Ambient Light Color Wheel selecting multi-color (tapping)
        Steps:
            1. Ensure that the current mode is "Personal"
            2. Navigate to Ambient lighting color by following
                Configure Button -> Design Tab -> Ambient lightning color
            3. Tap somewhere on Multi_color wheel to initialize previous color and capture screen
            4. Now, tap on different position on Multi_color wheel to select another color and capture screen
            5. Verify Ambient light switches to selected color.
        """
        multicolor_inner_wheel_region = (923, 561, 1151, 673)
        # Modes other than 'Personal' mode don't support changing of ambient color
        if self.modes_page.get_current_mode() != "PERSONAL":
            self.modes_page.set_mode_and_validate(self.test, "PERSONAL")
        self.modes_page.navigate_to_ambient_lighting_page()

        self.modes_page.click(self.modes_page.MULTI_COLOR_BTN)
        # Tap on color selection wheel to initialize the color
        self.test.apinext_target.send_tap_event(749, 605)
        screenshot_before_tap, _ = utils.get_screenshot_and_dump(self.test, self.test.results_dir, "initialize_color")
        # Tap on the color selection wheel to change the ambient color
        self.test.apinext_target.send_tap_event(1319, 605)
        screenshot_after_tap, _ = utils.get_screenshot_and_dump(self.test, self.test.results_dir, "selected_color")
        assert_true(
            self.modes_page.check_if_background_changed(
                screenshot_before_tap, screenshot_after_tap, multicolor_inner_wheel_region
            ),
            "Failed to verify Ambient light switches to selected color.",
        )

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-android-traas"],
        component="tee_idcevo",
        domain="Experiences and Modes",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-217405",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "PERSONAL_MODE_DISPLAY_STYLE_TAB"),
                ],
            },
        },
    )
    def test_009_display_style_color_availability(self):
        """
        [SIT_Automated] Display Style Color Availability
        Steps:
            1. Launch MyMode App and ensure MyMode Page is loaded
            2. Select any mode other than "Personal"
            3. Click on "Configure" button
            4. Click on "Design" tab
            5. Click on "Display Style" button
            6. Click on the back arrow to return to the previous screen (My Modes and My Moments launch screen).
            7. Repeat Steps from 2 to 6 for all modes other than Personal
        Expected results:
            for step 5:
                - Ensure that "Display style preset in this My Mode" flash msg appears.
                - Ensure that target remains on the same screen by clicking "Display style"
            for step 6:
                - Except "Personal" mode, ensure that "Display style preset in this My Mode" flash msg appears on
                    clicking Display style button and target remains on same page.
        """
        display_style_popup_region = (793, 1021, 1593, 1133)
        expected_display_style_popup_text = re.compile(r".*Display style preset.*My Mode")
        failed_modes_list = []
        for mode_name in self.modes_page.MODES_DICT.keys():
            if mode_name != "PERSONAL":
                self.modes_page.set_mode_and_validate(self.test, mode_name)
                self.modes_page.click(self.modes_page.CONFIGURE_BTN)
                self.modes_page.click(self.modes_page.DESIGN_TAB)
                self.modes_page.click(self.modes_page.DISPLAY_STYLE)
                popup_screenshot_path = self.test.take_apinext_target_screenshot(
                    self.test.results_dir, f"{mode_name}_display_style_popup.png"
                )
                actual_display_style_popup = extract_text(popup_screenshot_path, region=display_style_popup_region)
                display_style_button_status = self.test.driver.find_elements(*self.modes_page.DISPLAY_STYLE)
                display_style_popup_status = expected_display_style_popup_text.search(actual_display_style_popup)

                if not (display_style_button_status and display_style_popup_status):
                    failed_modes_list.append(
                        {
                            "mode": mode_name,
                            "expected_msg": expected_display_style_popup_text.pattern,
                            "actual_msg": actual_display_style_popup,
                        }
                    )
                time.sleep(1)  # Wait for the popup message window to disappear
                self.modes_page.click(self.modes_page.BACK_ARROW)
        assert_false(
            failed_modes_list,
            "Expected Pop-Up Message is not found in following MyModes. "
            f"Failed Modes List: {failed_modes_list} with failed mode, expected popup and actual popup",
        )

    @metadata(
        testsuite=["SI-android-traas"],
        component="tee_idcevo",
        domain="Experiences and Modes",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-217419",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "PERSONAL_MODE_AMBIENT_LIGHT_SETTING"),
            },
        },
    )
    def test_010_ambient_light_color_availability(self):
        """
        [SIT_Automated] Ambient Light Color Availability
        Steps:
            1. Ensure Modes and Moments application open and loaded
            2. Select any mode other than  "Personal"
            3. Click on "Configure" button
            4. Click on "Design" tab
            5. Click on "Ambient Lighting" button
            6. Click on the back arrow to return to the previous screen.
            7. Repeat steps 2 through 7 for next mode, until all modes are tested

        Expected results:
            for step 5:
                - Ensure that "ambient lighting preset on this My Mode" flash msg appears.
                - Ensure that target remains on same screen on clicking "Ambient Light"
            for step 6:
                - Except "Personal" mode, ensure that "ambient lighting preset on this My Mode" flash msg appears on
                    clicking Ambient Lights button and target remains on same page.
        """
        popup_screenshot_path = Path(self.test.results_dir, "ambient_light_popup.png")
        ambient_light_popup_region = (799, 1027, 1935, 1133)
        expected_ambient_light_popup_text = re.compile(r".*ambient lighting preset.*My Mode")
        failed_modes_list = []
        for mode_name in self.modes_page.MODES_DICT.keys():
            if mode_name != "PERSONAL":
                self.modes_page.set_mode_and_validate(self.test, mode_name)
                self.modes_page.click(self.modes_page.CONFIGURE_TAB)
                self.modes_page.click(self.modes_page.DESIGN_TAB)
                self.modes_page.click(self.modes_page.AMBIENT_LIGHT_BTN)

                utils.get_screenshot_and_dump(self.test, self.test.results_dir, "ambient_light_popup.png")
                actual_ambient_light_popup = extract_text(popup_screenshot_path, region=ambient_light_popup_region)

                ambient_light_button_status = self.test.driver.find_elements(*self.modes_page.AMBIENT_LIGHT_BTN)
                ambient_light_popup_status = expected_ambient_light_popup_text.search(actual_ambient_light_popup)

                if not (ambient_light_button_status and ambient_light_popup_status):
                    failed_modes_list.append({"mode": mode_name, "actual_msg": actual_ambient_light_popup})
                time.sleep(1)
                self.modes_page.click(self.modes_page.BACK_ARROW)
        assert_false(
            failed_modes_list,
            f"Expected popup message pattern: {expected_ambient_light_popup_text.pattern}. "
            f"Failed modes list : {failed_modes_list}",
        )

    @metadata(
        testsuite=["SI-android-traas"],
        component="tee_idcevo",
        domain="Experiences and Modes",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-212236",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "PERSONAL_MODE_AMBIENT_LIGHT_SETTING"),
                ],
            },
        },
    )
    def test_011_ambient_light_color_wheel_selecting_multicolor(self):
        """
        [SIT_Automated] Ambient Light Color Wheel selecting multicolor (dragging)
        Steps:
            1. Ensure Modes and Moments application open and loaded
            2. Ensure current mode is "Personal".
            3. Navigate to Ambient lighting color by following
                Configure Button -> Design Tab -> Ambient lightning color
            4. Select Multi-Color.
            5. Choose a color by dragging the Colorwheel.
        Expected:
            for step 5.
                - Colorwheel should change after dragging, it should be different than previous color.
        """
        try:
            self.test.start_recording()
            colorwheel_region = (956, 543, 1090, 678)
            # Modes other than 'Personal' mode don't support changing of ambient color
            if self.modes_page.get_current_mode() != "PERSONAL":
                self.modes_page.set_mode_and_validate(self.test, "PERSONAL")
            self.modes_page.navigate_to_ambient_lighting_page()

            self.modes_page.click(self.modes_page.MULTI_COLOR_BTN)

            # Tap on color selection wheel to initialize the color
            self.test.apinext_target.send_tap_event(1377, 681)
            screenshot_before_drag = self.test.take_apinext_target_screenshot(
                self.test.results_dir, "color_before_drag"
            )

            # Drag on color wheel to change the ambient color
            self.test.driver.swipe(726, 761, 726, 780, duration=2000)
            screenshot_after_drag = self.test.take_apinext_target_screenshot(self.test.results_dir, "color_after_drag")

            assert_true(
                self.modes_page.check_if_background_changed(
                    screenshot_before_drag, screenshot_after_drag, colorwheel_region
                ),
                "Failed to verify the color change on the color wheel after dragging it.",
            )
        finally:
            video_name = "selecting_multicolor_dragging"
            self.test.stop_recording(video_name)

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-android-traas"],
        component="tee_idcevo",
        domain="Experiences and Modes",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-217836",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "DARK_MODE_AND_BRIGHT_MODE_SWITCH"),
            },
        },
    )
    def test_012_dark_and_bright_set_to_dark(self):
        """
        [SIT_Automated] Dark&Bright set to dark
        Steps:
            1. Launch Modes and Moments application and Ensure MyMode Page is loaded
            2. Ensure Personal mode is active
            3. Click on the Configure button
            4. Click on the Display Style button
            5. Select Dark Style
            6. Set the Color of Color Wheel to one position and
               capture screenshot for dark theme Image Validation
            7. Go the home, launch all-apps Menu and check the current style
        Expected Results:
            For Step 4-
               Validate Auto, Dark and Bright Style Tab is visible on Display Style Screen
            For Step 5-
               Verify the Dark Style Tab is successfully selected
            For Step 6-
               Validate below options are in Dark Colour
                 - Dark Style Tab
                 - My Modes Screen
                 - Color Wheel
            For Step 7-
               Validate All Apps Menu background Style is in Dark Color
        """
        expected_data_not_found_list = []
        dark_tab_ref_image_path = "/tests/si-test-idcevo/si_test_data/ref_images/ref_dark_tab_img.png"
        colour_wheel_ref_image_path = (
            "/tests/si-test-idcevo/si_test_data/ref_images/ref_dark_style_colour_wheel_img.png"
        )
        display_style_dark_style_screen_image_path = (
            "/tests/si-test-idcevo/si_test_data/ref_images/ref_dark_style_theme_img.png"
        )
        all_apps_menu_dark_img_path = "/tests/si-test-idcevo/si_test_data/ref_images/ref_all_apps_menu_dark_img.png"
        dark_tab_region = (2107, 1023, 2307, 1133)
        colour_wheel_region = (920, 639, 1162, 821)
        display_style_dark_style_screen_image_region = (149, 547, 429, 749)
        all_apps_menu_dark_img_region = (300, 450, 660, 930)

        if self.modes_page.get_current_mode() != "PERSONAL":
            self.modes_page.set_mode_and_validate(self.test, "PERSONAL")
        self.modes_page.click(locator=self.modes_page.CONFIGURE_TAB)
        self.modes_page.click(locator=self.modes_page.DISPLAY_STYLE)

        auto_dark_bright_style_list = [self.modes_page.AUTO_TAB, self.modes_page.DARK_TAB, self.modes_page.BRIGHT_TAB]

        for style in auto_dark_bright_style_list:
            try:
                self.modes_page.check_presence_of_element_located(style)
            except Exception as e:
                logger.debug(f"Style with Element ID: {style} not found. Exception Occurred: {e}")
                utils.get_screenshot_and_dump(
                    self.test, self.test.results_dir, "my_modes_page_with_all_styles_button_present"
                )
                expected_data_not_found_list.append(f"Style with Element ID: {style} not found on My Mode screen")

        self.modes_page.click(locator=self.modes_page.DARK_TAB)
        time.sleep(3)  # Adding sleep for proper style change to Dark Style

        # Verifying Dark Style is successfully selected
        parent_element = self.test.driver.find_element(*self.modes_page.DARK_TAB)
        checked = parent_element.get_attribute("checked")
        if checked != "true":
            utils.get_screenshot_and_dump(self.test, self.test.results_dir, "my_modes_page_with_dark_style_selection")
            expected_data_not_found_list.append("Dark style button appears as unselected after clicking on it")

        # Setting the Color of Color Wheel to one position
        self.test.apinext_target.send_tap_event(1195, 917)

        dark_style_captured_image_path, _ = utils.get_screenshot_and_dump(
            self.test, self.test.results_dir, "my_modes_page_with_dark_style_selected"
        )

        expected_result_data = {
            "dark_tab": [dark_tab_ref_image_path, dark_tab_region],
            "colour_wheel": [colour_wheel_ref_image_path, colour_wheel_region],
            "display_style_screen": [
                display_style_dark_style_screen_image_path,
                display_style_dark_style_screen_image_region,
            ],
        }
        for image_areas, image_regions in expected_result_data.items():
            result, _ = match_template(
                image=dark_style_captured_image_path,
                image_to_search=image_regions[0],
                region=image_regions[1],
                results_path=self.test.results_dir,
            )
            if not result:
                expected_data_not_found_list.append(f"Image Areas: {image_areas} failed to change to dark style")

        # Launch and validate All Apps Menu is in Dark Style
        Launcher.open_all_apps_from_home(self.test)
        all_apps_menu_dark_screen_path, _ = utils.get_screenshot_and_dump(
            self.test, self.test.results_dir, "all_apps_page_with_dark_style_selected"
        )
        result, _ = match_template(
            image=all_apps_menu_dark_screen_path,
            image_to_search=all_apps_menu_dark_img_path,
            region=all_apps_menu_dark_img_region,
            results_path=self.test.results_dir,
        )
        if not result:
            expected_data_not_found_list.append("All-Apps failed to change to dark style")

        assert_false(
            expected_data_not_found_list,
            f"Failures found while testing Dark Style: {expected_data_not_found_list}",
        )
