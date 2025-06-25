import logging
import time

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from si_test_apinext.common.pages.base_page import Element
from si_test_apinext.padi.pages.side_panel_settings_page import SidePanelSettings
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.global_steps import GlobalSteps

logger = logging.getLogger(__name__)


class SidePanel(SidePanelSettings):
    sett_prefix = SidePanelSettings.SIDE_PANEL_RESOURCE_ID_PREFIX
    # Side Panel mandatory elements
    SIDE_PANEL_MUTE_VOLUME_BUTTON_ID = Element(By.ID, sett_prefix + "muteVolumeButton")
    SIDE_PANEL_VOLUME_SLIDER_ID = Element(By.ID, sett_prefix + "volumeSlider")
    SIDE_PANEL_REDUCE_VOLUME_BUTTON_ID = Element(By.ID, sett_prefix + "reduceVolumeButton")
    SIDE_PANEL_INCREASE_VOLUME_BUTTON_ID = Element(By.ID, sett_prefix + "increaseVolumeButton")

    # Side Panel optional elements - Only available when Inactive
    SIDE_PANEL_INACTIVITY_OVERLAY_ID = Element(By.ID, sett_prefix + "inactivityOverlay")

    # Side Panel Menu buttons, optional elements -  - Only available when Active
    SIDE_PANEL_PAGE_INDICATOR_ID = Element(By.ID, sett_prefix + "pageIndicatorContainer")
    SIDE_PANEL_CONTAINER_MENU_BUTTON_ID = Element(By.ID, sett_prefix + "menuButtonsContainer")
    SIDE_PANEL_AUDIO_MENU_BUTTON_ID = Element(By.ID, sett_prefix + "audioMenuButton")
    SIDE_PANEL_LOUD_SPEAKER_BUTTON_ID = Element(By.ID, sett_prefix + "loudspeakerBigButton")
    SIDE_PANEL_HEAD_PHONE_BUTTON_ID = Element(By.ID, sett_prefix + "headphoneBigButton")
    SIDE_PANEL_BLUETOOTH_MENU_BUTTON_ID = Element(By.ID, sett_prefix + "bluetoothMenuButton")
    SIDE_PANEL_DISPLAY_MENU_BUTTON_ID = Element(By.ID, sett_prefix + "displayMenuButton")
    SIDE_PANEL_INPUT_MENU_BUTTON_ID = Element(By.ID, sett_prefix + "inputMenuButton")
    SIDE_PANEL_DISPLAY_LAYOUT_ID = Element(By.ID, sett_prefix + "padiDisplayLayout")
    SIDE_PANEL_DISPLAY_LAYOUT_ID_PU = Element(By.ID, sett_prefix + "padi_display_layout")
    SIDE_PANEL_DISPLAY_FOLD_BUTTON_ID = Element(By.ID, sett_prefix + "btnFoldDisplay")
    SIDE_INPUT_HDMI_BUTTON_ID = Element(By.ID, sett_prefix + "inputHDMI")
    SIDE_INPUT_EXTBOARD_BUTTON_ID = Element(By.ID, sett_prefix + "inputExtBoard")

    all_side_panel_elements = [
        SIDE_PANEL_MUTE_VOLUME_BUTTON_ID,
        SIDE_PANEL_VOLUME_SLIDER_ID,
        SIDE_PANEL_REDUCE_VOLUME_BUTTON_ID,
        SIDE_PANEL_INCREASE_VOLUME_BUTTON_ID,
    ]

    all_side_panel_menu_buttons = [
        SIDE_PANEL_PAGE_INDICATOR_ID,
        SIDE_PANEL_CONTAINER_MENU_BUTTON_ID,
        SIDE_PANEL_AUDIO_MENU_BUTTON_ID,
        SIDE_PANEL_BLUETOOTH_MENU_BUTTON_ID,
        SIDE_PANEL_DISPLAY_MENU_BUTTON_ID,
        SIDE_PANEL_INPUT_MENU_BUTTON_ID,
    ]

    side = None
    side_locator = None

    side_center_coords = None
    panel_center_coords = (960, 1080)
    delta_value_for_swipe = 400

    @classmethod
    def get_side_panel_elem(cls, timeout=1):
        """
        Return the element representing the Side Panel element
        """
        if cls.side in ["Left", "Right"] and cls.side_locator is not None:
            return WebDriverWait(cls.driver, timeout).until(ec.presence_of_element_located(cls.side_locator))
        else:
            raise Exception("Unrecognized side panel")

    @classmethod
    def activate_panel(cls):
        """
        Click on side panel

        The goal of this touch is to activate the panel, enabling
        side buttons and disable the inactivityOverlay

        Returns:
            True - If there is inactivityOverlay and the element was clicked
                in order to deactivate it
            False - If there is no inactivityOverlay element and no click
        """
        inactivity = cls.SIDE_PANEL_INACTIVITY_OVERLAY_ID
        activated = False
        for i in range(0, 10):
            try:
                # Look for an element that will show if activated
                WebDriverWait(cls.driver, 1).until(
                    ec.presence_of_element_located(cls.SIDE_PANEL_DISPLAY_MENU_BUTTON_ID)
                )
                activated = True
                break
            except TimeoutException:
                logger.debug("Unable to find display menu button.")
                pass

            try:
                inactivity_elem = cls.wb.until(
                    ec.presence_of_element_located(inactivity),
                    f"Error while validating SidePanel element presence: {inactivity.selector}",
                )
                inactivity_elem.click()
            except TimeoutException:
                logger.debug("Error getting inactivity element on side panel")

        if not activated:
            raise Exception("Unable to activate side panel")

    @classmethod
    def validate_side_panel_elems(cls):
        """Validate presence of common elements"""
        for element in cls.all_side_panel_elements:
            cls.wb.until(
                ec.presence_of_element_located(element),
                f"Error while validating SidePanel element presence: {element.selector}",
            )
        return True

    @classmethod
    def open_display_settings(cls):
        """
        Open Display Settings view

        Enable interactions in side panel and click in Display Settings
        button to open Display Settings view, if not already open
        """
        try:
            # Verify if Display Settings View is open
            WebDriverWait(cls.driver, 2).until(
                ec.presence_of_element_located(cls.SIDE_PANEL_DISPLAY_SETTINGS_LAYOUT_ID)
            )
        except TimeoutException:
            side_panel_elem = cls.get_side_panel_elem()
            # If Display Settings View is not open, click on button to open it
            cls.activate_panel()
            display_button = cls.SIDE_PANEL_DISPLAY_MENU_BUTTON_ID
            display_button_elem = side_panel_elem.find_element(*display_button)
            GlobalSteps.click_button_and_expect_elem(
                cls.wb, display_button_elem, cls.SIDE_PANEL_DISPLAY_SETTINGS_LAYOUT_ID
            )

    @classmethod
    def change_aspect_ratio(cls, ratio):
        """
        Change CE_AREA apect ratio to the given ratio
        """
        cls.open_display_settings()
        super(SidePanel, cls).change_aspect_ratio(ratio)
        cls.close_display_settings()

    @classmethod
    def change_ce_area_position(cls, pos="center"):
        """
        Change CE_AREA position to the given position, center by default
        """
        cls.open_display_settings()
        super(SidePanel, cls).change_ce_area_position(pos)
        cls.close_display_settings()

    @classmethod
    def close_display_settings(cls):
        """
        Close Display Settings view

        Enable interactions in side panel and click in Display Settings
        button to close Display Settings view, if not already closed
        """
        display_settings = cls.SIDE_PANEL_DISPLAY_SETTINGS_LAYOUT_ID
        try:
            # If Display Settings View is closed, OK, do nothing
            WebDriverWait(cls.driver, 1).until(ec.invisibility_of_element_located(display_settings))
        except TimeoutException:
            # Display is open, click on button to close it
            display_button = cls.SIDE_PANEL_DISPLAY_MENU_BUTTON_ID
            display_button_elem = cls.wb.until(
                ec.presence_of_element_located(display_button),
                f"Error while validating presence of the element: {display_button.selector}",
            )
            GlobalSteps.click_button_and_not_expect_elem(
                cls.wb, display_button_elem, cls.SIDE_PANEL_DISPLAY_SETTINGS_LAYOUT_ID
            )

    @classmethod
    def enable_interaction_panel(cls):
        """
        Enable interactions with SidePanel elements
        By tapping in the respective side panel, setting the focus making
        UI automator able to find SidePanel views and interact with it's elements
        """

        if cls.side not in ["Left", "Right"] or cls.side_center_coords is None:
            raise Exception("Unrecognized side panel when enabling interaction")

        cls.apinext_target.send_tap_event(*cls.side_center_coords)
        time.sleep(1)

    @classmethod
    def click_side_panel_menu_button(cls, test, panel, panel_menu_id):
        """
        enabling interaction to the padi and expect parameter elements send from upper method

        :param panel: indicates left and right side panel
        :param panel_menu_id: side panel menu element
        :param test: target object
        :return side panel settings elements
        """

        panel.enable_interaction_panel()
        side_panel = test.wb.until(
            ec.visibility_of_element_located(panel.PANEL_ID),
            f"Error while validating SidePanel element presence {panel.PANEL_ID.selector}",
        )
        # locating menu button ID and clicking on it
        return cls.click_on_child_element(test, side_panel, panel_menu_id, panel.PANEL_SETTINGS_DETAILS_ID)

    @classmethod
    def click_on_child_element(cls, test, parent_element, child_element, expect_element):
        """
        method used for finding first element out of multiple elements

        :param parent_element: parent_element used to find child_element
        :param child_element: find the from parent_element
        :param expect_element: except ID to check the element
        :param test: target object
        :return expected element
        """
        buttons_to_click = parent_element.find_element(*child_element)
        expected_element = GlobalSteps.click_button_and_expect_elem(test.wb, buttons_to_click, expect_element)
        time.sleep(0.5)
        return expected_element

    @classmethod
    def swipe_panel(cls):
        cls.driver.swipe(
            cls.panel_center_coords[0] - cls.delta_value_for_swipe,
            cls.panel_center_coords[1],
            cls.panel_center_coords[0] + cls.delta_value_for_swipe,
            cls.panel_center_coords[1],
        )

    @classmethod
    def get_display_settings_elem_bounds(cls, *elem):
        """
        Find element from display settings view and return its bounds

        Args:
            elem - Tuple of Element (namedtuple) objects.

        Returns:
            Tuple of bounds (x1, y1, x2, y2)
        """
        cls.open_display_settings()
        for each_elem in elem:
            found_elements = cls.driver.find_elements(*each_elem)
            if found_elements:
                elem_bounds = utils.get_elem_bounds_detail(found_elements[0], crop_region=True)
                return elem_bounds
        raise Exception(f"Unable to find following elements {elem} inside display settings")
