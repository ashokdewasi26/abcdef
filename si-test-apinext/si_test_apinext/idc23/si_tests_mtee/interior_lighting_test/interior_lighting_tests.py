# Copyright (C) 2022. BMW Car IT. All rights reserved.
import logging
import time
from pathlib import Path
from unittest import skip

import si_test_apinext.util.driver_utils as utils
from mtee.testing.support.target_share import TargetShare
from si_test_apinext.idc23 import HMI_BUTTONS_REF_IMG_PATH, INTERIOR_LIGHT_REF_IMG_PATH
from si_test_apinext.idc23.pages.interior_lighting_page import InteriorLighting as Ilp
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.settings_app_page import SettingsAppPage as Settings
from si_test_apinext.testing.test_base import TestBase
from si_test_apinext.util.hmi_helper import HMIhelper
from si_test_apinext.util.screenshot_utils import capture_screenshot, compare_snapshot, crop_image, match_template
from si_test_apinext.util.mtee_utils import MteeUtils

logger = logging.getLogger(__name__)
target = TargetShare().target


COLORS = [Ilp.COLOR_02, Ilp.COLOR_12]


class TestInteriorLight:
    hmi_buttons_ref_img_path = HMI_BUTTONS_REF_IMG_PATH
    interior_light_ref_img_path = INTERIOR_LIGHT_REF_IMG_PATH

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.mtee_util = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        cls.hmihelper = HMIhelper(cls.test, cls.hmi_buttons_ref_img_path)
        Settings.language_change(language_name="English (UK)")
        utils.start_recording(cls.test)
        Launcher.go_to_home()
        Ilp.start_activity(validate_activity=False)

    @classmethod
    def teardown_class(cls):
        Launcher.go_to_home()
        utils.stop_recording(cls.test, "TestInteriorLight")
        cls.test.quit_driver()

    @utils.gather_info_on_fail
    def setup(self):
        utils.ensure_no_alert_popup(self.test.results_dir, self.test.driver, self.test.apinext_target)

    def check_inside_lighting_events(self):
        """
        Check if the current screen is already inside lighting events option
        """
        menu_title = self.test.driver.find_elements(*Ilp.DISPLAY_SUBMENU_TITLE_ID)
        if menu_title[0].text in Ilp.LIGHTING_EVENTS_TITLE:
            return True
        return False

    def crop_colour(self, colour, screenshot, image_name):
        """
        Crop the colour region and return the image for comparison
        """
        colour_image = colour.find_element(*Ilp.COLOR_IMAGE)
        elem_bounds = utils.get_elem_bounds_detail(colour_image, crop_region=True)
        cropped_image = Path(self.test.results_dir, image_name + ".png")
        crop_image(screenshot, elem_bounds, output=cropped_image)
        return cropped_image

    @utils.gather_info_on_fail
    def test_01_toggle_light_when_opening_door(self):
        """
        Toggle status of light when opening door

        Steps:
        1. Go to Interior lighting app.
        2. Select Reading light sub menu.
        3. Capture snapshot & find current button status of light when opening door option using match template.
        4. Click on light when opening door option.
        5. Capture snapshot & validate the button status of light when opening door is toggled.

        Traceability: ABPI-178256
        """

        Launcher.go_to_submenu(Ilp.READING_LIGHT, Ilp.DISPLAY_SUBMENU_TITLE_ID, Ilp.READING_LIGHT_TITLE)
        capture_screenshot(test=self.test, test_name="test_01_toggle_light_when_opening_door_start")
        tyre_popup = self.test.driver.find_elements(*Ilp.TYRE_ID)
        if tyre_popup:
            # Adding 3 secs sleep to wait for pressure monitor pop-up to disappear
            time.sleep(3)
        button = Ilp.get_option_button(Ilp.LIGHTWHENOPENDOOR)
        # Finding current button status
        status = self.hmihelper.find_current_button_status(
            button, "test_01_toggle_light_when_opening_door_start", image_pattern="button_*.png"
        )
        logger.debug(f"Button status of light when opening door: {status}")
        self.hmihelper.click_and_validate_button_status(
            button, status, "test_01_toggle_light_when_opening_door_final_state"
        )

    @utils.gather_info_on_fail
    def test_02_toggle_light_at_different_position(self):
        """
        Toggle the light at different position
        precondition: light_when_opening_door should be ON

        Steps:
        1. Go to Interior lighting app.
        2. Select Reading light sub menu.
        3. Turn on light when opening door option
        4. Toggle the different lights.
        5. Capture snapshot & validate the light status is toggled via checking the android id available on screen

        Traceability: ABPI-178256
        """

        Launcher.go_to_submenu(Ilp.READING_LIGHT, Ilp.DISPLAY_SUBMENU_TITLE_ID, Ilp.READING_LIGHT_TITLE)
        button = Ilp.get_option_button(Ilp.LIGHTWHENOPENDOOR)
        self.hmihelper.ensure_button_status_on(button, "test_02_turn_on_light_when_opening_door")
        light_button = self.test.driver.find_element(*Ilp.MAINLIGHT)
        light_on = light_button.find_elements(*Ilp.SPOTLIGHT_ON)
        self.hmihelper.click_and_capture(
            light_button, "test_02_toggle_light_at_" + Ilp.MAINLIGHT.selector.split("/")[1]
        )
        expected_status = (
            light_button.find_elements(*Ilp.SPOTLIGHT_OFF)
            if light_on
            else light_button.find_elements(*Ilp.SPOTLIGHT_ON)
        )
        assert any(expected_status), (
            f"Unable to find {Ilp.SPOTLIGHT_OFF.selector if light_on else Ilp.SPOTLIGHT_ON.selector} "
            f"after clicking on {Ilp.MAINLIGHT.selector}"
        )

    @utils.gather_info_on_fail
    def test_03_toggle_ambient_lighting(self):
        """
        ON/OFF Ambient Lighting

        Steps:
        1. Go to Interior lighting app.
        2. Select Ambient lighting sub menu.
        3. Capture snapshot & find current button status of Ambient lighting option using match template.
        4. Click on Ambient lighting option.
        5. Capture snapshot & validate the button status of Ambient lighting is toggled.

        Traceability: ABPI-178256
        """
        Launcher.go_to_submenu(Ilp.AMBIENT_LIGHTING, Ilp.DISPLAY_SUBMENU_TITLE_ID, Ilp.AMBIENT_LIGHTING_TITLE)
        capture_screenshot(test=self.test, test_name="test_03_toggle_ambient_light_option_start")
        button = Ilp.get_option_button(Ilp.AMBIENT_LIGHT_TOGGLE)
        # Finding current button status
        status = self.hmihelper.find_current_button_status(
            button, "test_03_toggle_ambient_lighting_start", image_pattern="button_*.png"
        )
        logger.debug(f"Button status of Ambient Lighting: {status}")
        self.hmihelper.click_and_validate_button_status(button, status, "test_03_toggle_ambient_lighting_final_state")

    @utils.gather_info_on_fail
    def test_04_change_ambient_colour(self):
        """
        Change ambient colour

        Steps:
        1. Go to Interior lighting app.
        2. Select Ambient lighting sub menu.
        3. Go to colour option and select a colour.
        4. Capture snapshot & validate the selected colour is reflected under Ambient lighting.

        Traceability: ABPI-178256
        """
        Launcher.go_to_submenu(Ilp.AMBIENT_LIGHTING, Ilp.DISPLAY_SUBMENU_TITLE_ID, Ilp.AMBIENT_LIGHTING_TITLE)
        button = Ilp.get_option_button(Ilp.AMBIENT_LIGHT_TOGGLE)
        self.hmihelper.ensure_button_status_on(button, "test_04_ensure_ambient_light_on")
        colour_option = self.test.driver.find_element(*Ilp.AMBIENT_LIGHT_COLOR)
        screenshot = capture_screenshot(test=self.test, test_name="test_04_initial_ambient_colour")
        initial_color = self.crop_colour(colour_option, screenshot, "initial_color")
        self.hmihelper.click_and_capture(colour_option, "test_04_change_ambient_colour_click")
        for each_color in COLORS:
            colour = self.test.driver.find_element(*each_color)
            colour_name = colour.find_elements(*Ilp.COLOR_TEXT)
            # If colour name is not found means that is not the selected colour.
            if not colour_name:
                self.hmihelper.click_and_capture(colour, "test_04_selected_ambient_colour")
                colour_name = colour.find_element(*Ilp.COLOR_TEXT).get_attribute("text")
                logger.info(f"Selected colour is: {colour_name}")
                break
            else:
                self.hmihelper.click_and_capture(colour, "test_04_selected_ambient_colours")

        Launcher.return_from_submenu(Ilp.DISPLAY_SUBMENU_TITLE_ID, Ilp.AMBIENT_LIGHTING_TITLE)
        screenshot = capture_screenshot(test=self.test, test_name="test_04_selected_ambient_colour_final")
        colour_option = self.test.driver.find_element(*Ilp.AMBIENT_LIGHT_COLOR)
        final_color = self.crop_colour(colour_option, screenshot, "final_color")
        result, _ = compare_snapshot(final_color, initial_color, "colour_ckeck")
        if result:
            raise AssertionError(
                f"Color didn't change as expected, initial color:'{initial_color}' "
                f"is same as final colour: '{final_color}'"
            )

    @utils.gather_info_on_fail
    def test_05_change_background_light(self):
        """
        Check background light option slider value can be set to min, 50% and max.

        Steps:
        1. Go to Interior lighting app.
        2. Select Ambient lighting sub menu.
        3. Go to Background light option.
        4. Tap on the min, 50% and max values and validate the slider values are changed using reference images.

        Traceability: ABPI-178256
        """
        Launcher.go_to_submenu(Ilp.AMBIENT_LIGHTING, Ilp.DISPLAY_SUBMENU_TITLE_ID, Ilp.AMBIENT_LIGHTING_TITLE)
        button = Ilp.get_option_button(Ilp.AMBIENT_LIGHT_TOGGLE)
        self.hmihelper.ensure_button_status_on(button, "test_05_ensure_ambient_light_on")
        bg_light_option = self.test.driver.find_element(*Ilp.BACKGROUND_LIGHT_SEEKBAR)
        elem_bounds = utils.get_elem_bounds_detail(bg_light_option, crop_region=True)
        self.hmihelper.click_and_capture(bg_light_option, "test_05_change_background_light_start")
        for each_pos in Ilp.bg_light_coords.keys():
            for _ in range(Ilp.bg_light_coords[each_pos]["steps"]):
                self.test.apinext_target.send_tap_event(*Ilp.bg_light_coords[each_pos]["coords"])
                time.sleep(0.5)
            time.sleep(1)
            screenshot = capture_screenshot(test=self.test, test_name=f"test_05_{each_pos}")
            reference_image = Path(self.interior_light_ref_img_path / f"slider_short_{each_pos}.png")
            result, _ = match_template(screenshot, reference_image, elem_bounds, self.test.results_dir)
            if not result:
                raise AssertionError(
                    f"Error on checking {each_pos} position. "
                    f"reference {reference_image} template cannot be found on actual image {screenshot}"
                )

    @utils.gather_info_on_fail
    def test_06_change_accent_light(self):
        """
        Check accent light option slider value can be set to min, 50% and max.

        Steps:
        1. Go to Interior lighting app.
        2. Select Ambient lighting sub menu.
        3. Go to Accent light option.
        4. Tap on the min, 50% and max values and validate the slider values are changed using reference images.

        Traceability: ABPI-178256
        """
        Launcher.go_to_submenu(Ilp.AMBIENT_LIGHTING, Ilp.DISPLAY_SUBMENU_TITLE_ID, Ilp.AMBIENT_LIGHTING_TITLE)
        button = Ilp.get_option_button(Ilp.AMBIENT_LIGHT_TOGGLE)
        self.hmihelper.ensure_button_status_on(button, "test_06_ensure_ambient_light_on")
        acc_light_option = self.test.driver.find_element(*Ilp.ACCENT_LIGHTING_SEEKBAR)
        elem_bounds = utils.get_elem_bounds_detail(acc_light_option, crop_region=True)
        self.hmihelper.click_and_capture(acc_light_option, "test_06_change_accent_light_start")
        for each_pos in Ilp.acc_light_coords.keys():
            for _ in range(Ilp.acc_light_coords[each_pos]["steps"]):
                self.test.apinext_target.send_tap_event(*Ilp.acc_light_coords[each_pos]["coords"])
                time.sleep(0.5)
            time.sleep(1)
            screenshot = capture_screenshot(test=self.test, test_name=f"test_06_{each_pos}")
            reference_image = Path(self.interior_light_ref_img_path / f"slider_short_{each_pos}.png")
            result, _ = match_template(
                screenshot, reference_image, elem_bounds, self.test.results_dir, acceptable_diff=3
            )
            if not result:
                raise AssertionError(
                    f"Error on checking {each_pos} position. "
                    f"reference {reference_image} template cannot be found on actual image {screenshot}"
                )

    @utils.gather_info_on_fail
    def test_07_toggle_reduced_for_night_driving(self):
        """
        ON/OFF Reduced for night driving

        Steps:
        1. Go to Interior lighting app.
        2. Select Ambient lighting sub menu.
        3. Capture snapshot & find current button status of Reduced for night driving option using match template.
        4. Click on Reduced for night driving option.
        5. Capture snapshot & validate the button status of Reduced for night driving is toggled.

        Traceability: ABPI-178256
        """
        Launcher.go_to_submenu(Ilp.AMBIENT_LIGHTING, Ilp.DISPLAY_SUBMENU_TITLE_ID, Ilp.AMBIENT_LIGHTING_TITLE)
        button = Ilp.get_option_button(Ilp.AMBIENT_LIGHT_TOGGLE)
        self.hmihelper.ensure_button_status_on(button, "test_07_ensure_ambient_light_on")
        self.test.driver.swipe(*Ilp.swipe_to_end, duration=1000)
        button = Ilp.get_option_button(Ilp.REDUCED_FOR_NIGHT_DRIVING_TOGGLE)
        # Finding current button status
        status = self.hmihelper.find_current_button_status(
            button, "test_07_toggle_reduced_for_night_driving_start", image_pattern="button_*.png"
        )
        logger.debug(f"Button status of Reduced for night driving: {status}")
        self.hmihelper.click_and_validate_button_status(
            button, status, "test_07_toggle_reduced_for_night_driving_final_state"
        )

    @utils.gather_info_on_fail
    def test_08_toggle_welcome_option(self):
        """
        ON/OFF Welcome

        Steps:
        1. Go to Interior lighting app.
        2. Select Ambient lighting sub menu.
        3. Go to Lighting events.
        3. Capture snapshot & find current button status of Welcome option using match template.
        4. Click on Welcome option.
        5. Capture snapshot & validate the button status of Welcome is toggled.

        Traceability: ABPI-178256
        """
        Launcher.go_to_submenu(Ilp.AMBIENT_LIGHTING, Ilp.DISPLAY_SUBMENU_TITLE_ID, Ilp.AMBIENT_LIGHTING_TITLE)
        self.test.driver.swipe(*Ilp.swipe_to_end, duration=1000)
        time.sleep(1)
        lighting_events_option = self.test.driver.find_element(*Ilp.LIGHTING_EVENTS)
        self.hmihelper.click_and_capture(lighting_events_option, "test_08_inside_lighting_events")
        button = Ilp.get_option_button(Ilp.WELCOME_OPTION)
        # Finding current button status
        status = self.hmihelper.find_current_button_status(
            button, "test_08_toggle_welcome_option_start", image_pattern="button_*.png"
        )
        logger.debug(f"Button status of welcome option: {status}")
        self.hmihelper.click_and_validate_button_status(button, status, "test_08_toggle_welcome_option_final_state")

    @skip("Option not available on latest IDC builds. Enable back if the option is available. Refer: ABPI-349340")
    @utils.gather_info_on_fail
    def test_09_toggle_safety_warnings_option(self):
        """
        ON/OFF Safety and warnings

        Steps:
        1. Go to Interior lighting app.
        2. Select Ambient lighting sub menu.
        3. Go to Lighting events.
        3. Capture snapshot & find current button status of Safety and warnings option using match template.
        4. Click on Safety and warnings option.
        5. Capture snapshot & validate the button status of Safety and warnings is toggled.

        Traceability: ABPI-178256
        """
        if not self.check_inside_lighting_events():
            Launcher.go_to_submenu(Ilp.AMBIENT_LIGHTING, Ilp.DISPLAY_SUBMENU_TITLE_ID, Ilp.AMBIENT_LIGHTING_TITLE)
            self.test.driver.swipe(*Ilp.swipe_to_end, duration=1000)
            lighting_events_option = self.test.driver.find_element(*Ilp.LIGHTING_EVENTS)
            self.hmihelper.click_and_capture(lighting_events_option, "test_09_inside_lighting_events")
        button = Ilp.get_option_button(Ilp.ALERT_OPTION)
        # Finding current button status
        status = self.hmihelper.find_current_button_status(
            button, "test_09_toggle_safety_warnings_option_start", image_pattern="button_*.png"
        )
        logger.debug(f"Button status of Safety and warnings option: {status}")
        self.hmihelper.click_and_validate_button_status(
            button, status, "test_09_toggle_safety_warnings_option_final_state"
        )

    @utils.gather_info_on_fail
    def test_10_toggle_locking_unlocking_option(self):
        """
        ON/OFF Locking and unlocking

        Steps:
        1. Go to Interior lighting app.
        2. Select Ambient lighting sub menu.
        3. Go to Lighting events.
        3. Capture snapshot & find current button status of Locking and unlocking option using match template.
        4. Click on Locking and unlocking option.
        5. Capture snapshot & validate the button status of Locking and unlocking is toggled.

        Traceability: ABPI-178256
        """
        if not self.check_inside_lighting_events():
            Launcher.go_to_submenu(Ilp.AMBIENT_LIGHTING, Ilp.DISPLAY_SUBMENU_TITLE_ID, Ilp.AMBIENT_LIGHTING_TITLE)
            self.test.driver.swipe(*Ilp.swipe_to_end, duration=1000)
            time.sleep(1)
            lighting_events_option = self.test.driver.find_element(*Ilp.LIGHTING_EVENTS)
            self.hmihelper.click_and_capture(lighting_events_option, "test_10_inside_lighting_events")
        button = Ilp.get_option_button(Ilp.LOCK_OPTION)
        # Finding current button status
        status = self.hmihelper.find_current_button_status(
            button, "test_10_toggle_locking_unlocking_option_start", image_pattern="button_*.png"
        )
        logger.debug(f"Button status of Locking and unlocking option: {status}")
        self.hmihelper.click_and_validate_button_status(
            button, status, "test_10_toggle_locking_unlocking_option_final_state"
        )

    @utils.gather_info_on_fail
    def test_11_toggle_incoming_calls_option(self):
        """
        ON/OFF Incoming calls

        Steps:
        1. Go to Interior lighting app.
        2. Select Ambient lighting sub menu.
        3. Go to Lighting events.
        3. Capture snapshot & find current button status of Incoming calls option using match template.
        4. Click on Incoming calls option.
        5. Capture snapshot & validate the button status of Incoming calls is toggled.

        Traceability: ABPI-178256
        """
        if not self.check_inside_lighting_events():
            Launcher.go_to_submenu(Ilp.AMBIENT_LIGHTING, Ilp.DISPLAY_SUBMENU_TITLE_ID, Ilp.AMBIENT_LIGHTING_TITLE)
            self.test.driver.swipe(*Ilp.swipe_to_end, duration=1000)
            time.sleep(1)
            lighting_events_option = self.test.driver.find_element(*Ilp.LIGHTING_EVENTS)
            self.hmihelper.click_and_capture(lighting_events_option, "test_11_inside_lighting_events")
        self.test.driver.swipe(*Ilp.swipe_to_end, duration=1000)
        button = Ilp.get_option_button(Ilp.CALL_OPTION)
        # Finding current button status
        status = self.hmihelper.find_current_button_status(
            button, "test_11_toggle_incoming_calls_option_start", image_pattern="button_*.png"
        )
        logger.debug(f"Button status of Incoming calls option: {status}")
        self.hmihelper.click_and_validate_button_status(
            button, status, "test_11_toggle_incoming_calls_option_final_state"
        )
        back_option = self.test.driver.find_element(*Ilp.SIDE_NAVIGATION_BACK_ARROW)
        back_option.click()

    @utils.gather_info_on_fail
    def test_12_change_cockpit_brightness(self):
        """
        Check cockpit brightness option slider value can be set to min, 50% and max.

        Steps:
        1. Go to Interior lighting app.
        2. Select Vehicle cockpit brightness sub menu.
        3. Tap on the min, 50% and max values and validate the slider values are changed using reference images.

        Traceability: ABPI-178256
        """
        if self.check_inside_lighting_events():
            Launcher.return_from_submenu(Ilp.DISPLAY_SUBMENU_TITLE_ID, Ilp.AMBIENT_LIGHTING_TITLE)
        Launcher.go_to_submenu(
            Ilp.VEHICLE_DASHBOARD_BRIGHTNESS, Ilp.DISPLAY_SUBMENU_TITLE_ID, Ilp.DASHBOARD_BRIGHTNESS_TITLE
        )
        cockpit_option = self.test.driver.find_element(*Ilp.COCKPIT_BRIGHTNESS_SEEKBAR)
        elem_bounds = utils.get_elem_bounds_detail(cockpit_option, crop_region=True)
        self.hmihelper.click_and_capture(cockpit_option, "test_12_change_cockpit_brightness_start")
        for each_pos in Ilp.cockpit_brightness_coords.keys():
            for _ in range(Ilp.cockpit_brightness_coords[each_pos]["steps"]):
                self.test.apinext_target.send_tap_event(*Ilp.cockpit_brightness_coords[each_pos]["coords"])
                time.sleep(0.5)
            time.sleep(1)
            screenshot = capture_screenshot(test=self.test, test_name=f"test_12_{each_pos}")
            reference_image = Path(self.interior_light_ref_img_path / f"slider_long_{each_pos}.png")
            result, _ = match_template(screenshot, reference_image, elem_bounds, self.test.results_dir)
            if not result:
                raise AssertionError(
                    f"Error on checking {each_pos} position. "
                    f"reference {reference_image} template cannot be found on actual image {screenshot}"
                )
