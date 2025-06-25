import logging
import os
import time
from unittest import skip
from unittest.case import TestCase

import si_test_apinext.util.driver_utils as utils
from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import metadata
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from si_test_apinext.padi import LAUNCHER_REF_IMAGES_PATH
from si_test_apinext.padi.pages.ce_area_page import CEAreaPage as Launcher
from si_test_apinext.padi.pages.left_panel_page import LeftPanel
from si_test_apinext.padi.pages.padi_page import PadiPage as Padi
from si_test_apinext.padi.pages.right_panel_page import RightPanel
from si_test_apinext.testing.test_base import TestBase
from si_test_apinext.util.screenshot_utils import capture_screenshot, compare_snapshot

logger = logging.getLogger(__name__)


@metadata(testsuite=["SI"])
class TestLauncherPADI(TestCase):
    mtee_log_plugin = True
    resolution_8k = "7680x2160"
    # The element video is the placeholder for the CE area
    ce_area = Launcher.CE_AREA_VIDEO_ID
    launcher_ref_images_path = LAUNCHER_REF_IMAGES_PATH

    def __test_vcar_values(self):
        self.current_timeformat = float(
            self.vcar_manager.send("req_Vehicle.newCurrentUnitsConfigExt.operationUnitOfMeasurementTime")
        )

    @classmethod
    def setup_class(cls):
        # TestBase is a singleton class to re-use appium driver and target vars
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.vcar_manager = TargetShare().vcar_manager
        cls.__test_vcar_values(cls)
        time.sleep(30)
        package = Padi.PACKAGE_ACTIVITY.split(".")[-1]
        Launcher.stop_hdmi_animation()
        capture_screenshot(test=cls.test, test_name="setup_target_ready_" + package)
        utils.start_recording(cls.test)

    @classmethod
    def teardown_class(cls):
        utils.stop_recording(cls.test, "TestLauncherPADI")
        cls.test.quit_driver()

    def _get_ce_area_curr_expect_bounds(self, pos, ratio):
        """
        Find CE Area place holder element and return the expected and current bounds, and also return the element

        Args:
            pos - str, name of the position to be used to get expected bounds
            ratio - str, name of ratio to be used to get expected bounds

        Returns:
            curr_bounds - str, current values of bounds of CE Area
            expected_bounds - str, expected values of bounds of CE Area, for given position and ratio
            ce_area_elem - located WebDriver element of CE Area
        """
        ce_area_elem = WebDriverWait(self.test.driver, 2).until(
            ec.presence_of_element_located(self.ce_area), f"Error while validating {self.ce_area.selector}"
        )
        curr_bounds = ce_area_elem.get_attribute("bounds")
        expected_bounds = LeftPanel.get_ce_area_expected_bounds(pos=pos, ratio=ratio)
        return curr_bounds, expected_bounds, ce_area_elem

    def __toggle_headset_speaker(self, panel, toggle_upto=10):
        """
        open PADI display settings menu and toggle 10 times between headphone and speaker

         Args:
             :param  panel - class, LEFT or RIGHT side panel class object
             :param toggle_upto - max time toggle

         Note: first time ignoring NoSuchElementException because status can display be changed second time
          throwing exception
        """
        panel_settings = panel.click_side_panel_menu_button(self.test, panel, panel.SIDE_PANEL_AUDIO_MENU_BUTTON_ID)
        for i in range(toggle_upto):
            try:
                # locating speaker ID and clicking on it
                panel.click_on_child_element(
                    self.test,
                    panel_settings,
                    panel.SIDE_PANEL_LOUD_SPEAKER_BUTTON_ID,
                    panel.SIDE_PANEL_HEAD_PHONE_BUTTON_ID,
                )
                # locating headphone ID and clicking on it
                time.sleep(2)
                panel.click_on_child_element(
                    self.test,
                    panel_settings,
                    panel.SIDE_PANEL_HEAD_PHONE_BUTTON_ID,
                    panel.SIDE_PANEL_LOUD_SPEAKER_BUTTON_ID,
                )
                time.sleep(3)
            except (TimeoutException, StaleElementReferenceException):
                panel_settings = panel.click_side_panel_menu_button(
                    self.test, panel, panel.SIDE_PANEL_AUDIO_MENU_BUTTON_ID
                )

    @utils.gather_info_on_fail
    def test_000_check_launcher_available_and_capture_snapshot(self):
        """
        Check launcher is available and capture a screenshot

        *Background information*

        In this test we expect the launcher is available by checking the content and capture a screenshot as well.
        This test in named '00' because the Launcher availability should be validated on the startup of the target,
        so you want this test to be the first to run, to avoid a new restart of the target

        *Steps*
        1. Validate through adb the BMW Launcher activity is running
        2. Validate through UI the BMW launcher is present
        3. Take screenshot
        """

        expected_activity = Padi.PACKAGE_ACTIVITY if self.test.branch_name == "pu2403" else Padi.PACKAGE_ACTIVITY_ML
        self.assertEquals(
            expected_activity,
            self.test.driver.current_activity,
            f"Failure on validating Launcher, expected activity is not active: {expected_activity} . "
            f"Current activity:{self.test.driver.current_activity}",
        )

        self.test.wb.until(
            ec.presence_of_element_located(Launcher.CE_AREA_NOT_FOCUSED_ID),
            f"Error while validating {Launcher.CE_AREA_NOT_FOCUSED_ID} presence",
        )
        capture_screenshot(test=self.test, test_name="padi_launcher_available_screenshot")

    @utils.gather_info_on_fail
    def test_001_check_padi_launcher_and_panels(self):
        """
        Check padi launcher resolution and validate the presence of an element per each SidePanel (Left and Right)

        *Background information*

        In this test case we expect that PADI BMW Launcher starts with expected resolution(8k) and
        Panels (Left, Center Area(CE) and Right)

        *Steps*
        1. Go to Home
        2. Validate that PaDi android launcher starts with 8K resolution
        3. Validate that PaDi  displays 3 panels: (Left Panel, Center Area (CE Area), Right Panel)
        """

        resolution = self.test.apinext_target.execute_adb_command(["shell", "wm size"])
        assert resolution.stdout.decode("UTF-8") == f"Physical size: {self.resolution_8k}\n"

        # Verify Left Panel element
        LeftPanel.enable_interaction_panel()
        self.test.wb.until(
            ec.presence_of_element_located(LeftPanel.PANEL_ID), "Error while validating Left Panel presence"
        )

        # Verify Right Panel element
        RightPanel.enable_interaction_panel()
        self.test.wb.until(
            ec.presence_of_element_located(RightPanel.PANEL_ID), "Error while validating Right Panel presence"
        )

    @utils.gather_info_on_fail
    def test_002_check_padi_launcher_contents(self):
        """
        Check padi Panels elements presence and menu bar for SidePanels

        *Background information*

        In this test case we expect PaDi BMW Launcher contents
        Precondition: Target is running

        *Steps*
        1. Go to Home
        2. Validate that Left Panel contains widget panel and a right menu bar.
        3. Validate that Right Panel contains widget panel and a left menu bar.
        4. Validate that Central Area contains CE contents (for example apps).
        """

        # Validate CE Element when not focused
        self.test.wb.until(
            ec.presence_of_element_located(Launcher.CE_AREA_NOT_FOCUSED_ID),
            f"Error while validating {Launcher.CE_AREA_NOT_FOCUSED_ID} presence",
        )

        # Validate Left Panel
        LeftPanel.enable_interaction_panel()
        if not self.test.driver.find_elements(By.ID, "com.bmwgroup.padi:id/txtHour"):
            LeftPanel.swipe_panel()
        LeftPanel.validate_left_panel_elems(self.test.branch_name, self.current_timeformat)

        # Validate Right Panel
        RightPanel.enable_interaction_panel()
        # PaDi is ROW
        RightPanel.swipe_panel()
        RightPanel.validate_right_panel_elems()
        # TODO: If PaDi is CH
        # RightPanel.validate_right_panel_cn_elems(self.test.wb)

    @skip("Skipping test because of framework constraints on moving CE Area position")
    def test_003_check_all_panel_positions_and_ratios(self):
        """
        Move CE Area position with Panel UI for 16:9/21:9/32:9 aspect ratio

        *Background information*

        In this test case we check the capability of changing position of CE area.
        Precondition: Target is running

        *Steps*
        1. Go to Home
        2. Perform steps #3-12 with (SIDE PANEL-NEW POSITION) for each aspect ratio:
            * left-left
            * left-right
            * left-center
            * right-left
            * right-right
            * right-center
        3. Click on side panel 'SIDE PANEL'
        5. Click on "View" widget from panel side bar.
        6. Validate that "ASPec. RATIO AND IMAGE POSITION" windows is open.
        7. Select aspect ratio to 'RATIO'
        8. Select Picture position to 'NEW POSITION'
        9. Validate that CE area is located on the 'NEW POSITION'
        """
        transitions = ["left", "right", "center"]

        for panel in [LeftPanel, RightPanel]:
            for ratio, ratio_elem in panel.ce_area_ratios_dict.items():
                panel.change_aspect_ratio(ratio_elem)
                for pos in transitions:
                    logger.debug("Using %s to change to %s position and %s ratio", panel.__name__, pos, ratio)

                    panel.change_ce_area_position(pos)
                    for elem in self.test.driver.find_elements(By.XPATH, ("//*")):
                        if elem.get_attribute("resource-id"):
                            print(elem.get_attribute("resource-id"))

                    curr_bounds = Launcher.get_elem_bounds(self.ce_area)
                    expected_bounds = panel.get_ce_area_expected_bounds(pos=pos, ratio=ratio)
                    assert curr_bounds == expected_bounds, (
                        f"CE Area bounds mismatch on aspect {ratio} on position {pos}."
                        f"Expected: {expected_bounds} Got: {curr_bounds}"
                    )

    @skip("Skipping test because of framework constraints on moving CE Area position")
    def test_004_check_default_ratio(self):
        """
        Change CE Area to 21:9/32:9 aspect ratio click CE Area and expect default ratio 16:9

        *Background information*

        In this test case we check the capability CE area going to the default aspect ratio.
        Precondition: Target is running

        *Steps*
        1. Go to Home
        3. Set aspect ratio to 21:9
        4. Tap CE Area
        5. Validate aspect ratio of 16:9
        3. Set aspect ratio to 32:9
        4. Tap CE Area
        5. Validate aspect ratio of 16:9
        """
        pos = "center"
        default_ratio = "16:9"
        LeftPanel.change_ce_area_position(pos)

        for ratio, ratio_elem in LeftPanel.ce_area_ratios_dict.items():
            if ratio == default_ratio:
                continue
            LeftPanel.change_aspect_ratio(ratio_elem)
            curr_bounds, expected_bounds, ce_area_elem = self._get_ce_area_curr_expect_bounds(pos, ratio)
            assert curr_bounds == expected_bounds, (
                f"CE Area bounds mismatch on aspect {ratio} on position {pos}."
                f"Expected: {expected_bounds} Got: {curr_bounds}"
            )
            # Tap in the middle of the screen (in CE_area panel)
            ce_area_elem.click()
            time.sleep(1)
            curr_bounds, expected_bounds, _ = self._get_ce_area_curr_expect_bounds(pos, default_ratio)
            # Validate it's the default ratio
            assert expected_bounds == curr_bounds, (
                f"CE Area bounds mismatch after click. Expected: {expected_bounds} Got: {curr_bounds}."
                f"After a tap while on pos {pos} and ratio {ratio}"
            )

    @utils.gather_info_on_fail
    def test_005_check_padi_brightness(self):
        """
        Check different brightness levels from min to max

        *Background information*
        This test case is to check if padi response properly for change in brightness.
        Validation can be done via screenshot verification in comparison
        with reference screenshot.

        *Steps*
        1. Set brightness to min --> validate result
        2. Set brightness to max --> validate result
        3. Set brightness to random value btw 0-100 --> validate result


        Issue: ABPI-120734
        """
        image_list = [
            (
                0,
                ("brightness_reference_image_0_value.png", "brightness_reference_image_0_value_2.png"),
                "0_brightness",
            ),
            (
                255,
                ("brightness_reference_image_255_value.png", "brightness_reference_image_255_value_2.png"),
                "255_brightness",
            ),
            (
                43,
                ("brightness_reference_image_43_value.png", "brightness_reference_image_43_value_2.png"),
                "43_brightness",
            ),
        ]

        panels = [
            (LeftPanel, (395, 1742, 1225, 1892), "_left", (105, 1760, 105, 10)),
            (RightPanel, (6455, 1742, 7285, 1892), "_right", (7500, 1760, 7500, 10)),
        ]

        for panel, box, image_side, coord in panels:
            panel.enable_interaction_panel()
            for brightness_level, reference_image, test_name in image_list:
                panel.open_display_settings()
                self.test.apinext_target.execute_command(f"settings put system screen_brightness {brightness_level}")
                time.sleep(1)
                self.test.driver.swipe(*coord)
                screenshot_path = capture_screenshot(test=self.test, test_name=test_name + image_side)
                results = []
                for image_path in reference_image:
                    reference_path = os.path.join(self.launcher_ref_images_path, image_path)
                    test_result, message = compare_snapshot(
                        screenshot_path, reference_path, test_name + image_side, region=box
                    )
                    results.append(test_result)
                if not any(results):
                    raise AssertionError(message)

    @utils.gather_info_on_fail
    def test_007_audio_toggle(self):
        """
        Audio toggle between "Speakers" & "Headsets"

        *Background information*
        The aim of  this test is to verify that Basic Audio settings are be stable and functional all the time.

        *Steps*
        1.  Ensure PADI is up.
        2.  Go to Audio settings on Left Side of the Panel for PADI.
        3.  Try to select Audio output as "Speakers" and the switch back to "Headphones"
        4.  Go to Step 2 and follow the steps from 2-3 for Audio settings of the Right Panel.
        5.  Try the Toggle of audio output from "Headphone" to "Speakers" multiple times.

        Issue: ABPI-120735

        """
        self.__toggle_headset_speaker(LeftPanel)
        self.__toggle_headset_speaker(RightPanel)
