from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.common.pages.base_page import BasePage, Element
import si_test_apinext.util.driver_utils as utils


class SidePanelSettings(BasePage):
    SIDE_PANEL_PACKAGE_NAME = "com.bmwgroup.padi"
    SIDE_PANEL_RESOURCE_ID_PREFIX = SIDE_PANEL_PACKAGE_NAME + ":id/"
    # Side Panel elements resource ID / locators
    SIDE_PANEL_PANEL_BACKGROUND_LAYOUT_ID = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "settings_root")

    # Side Panel Menu buttons, only available after click on left panel
    SIDE_PANEL_CONTAINER_MENU_BUTTON_ID = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "menuButtonsContainer")
    SIDE_PANEL_AUDIO_MENU_BUTTON_ID = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "audioMenuButton")
    SIDE_PANEL_BLUETOOTH_MENU_BUTTON_ID = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "bluetoothMenuButton")
    SIDE_PANEL_DISPLAY_MENU_BUTTON_ID = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "displayMenuButton")
    SIDE_PANEL_INPUT_MENU_BUTTON_ID = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "inputMenuButton")

    # Display settings side panel
    SIDE_PANEL_DISPLAY_SETTINGS_LAYOUT_ID = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "displaySettingsLayout")
    SIDE_PANEL_CONTENT_AREA_CARRIAGE_ID = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "contentAreaCarriage")
    SIDE_PANEL_CONTENT_AREA_RECTANGLE_ID = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "contentAreaRectangle")
    SIDE_PANEL_ZOOM_TITLE_ID = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "zoomTitle")
    SIDE_PANEL_POSITION_TOUCH_ID = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "padiPositionTouch")
    SIDE_PANEL_POSITION_TOUCH_ID_PU = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "padi_position_touch")
    SIDE_PANEL_POSITION_CINEMATIC_ID = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "padiPositionCinematic")
    SIDE_PANEL_POSITION_CINEMATIC_ID_PU = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "padi_position_cinematic")
    SIDE_PANEL_ANGLE_NEXT_ID = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "padiAngleNext")
    SIDE_PANEL_ANGLE_NEXT_ID_PU = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "padi_angle_next")
    SIDE_PANEL_ANGLE_PREVIOUS_ID = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "padiAnglePrevious")
    SIDE_PANEL_ANGLE_PREVIOUS_ID_PU = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "padi_angle_previous")

    SIDE_PANEL_FOLD_UP_ID = Element(By.ID, SIDE_PANEL_RESOURCE_ID_PREFIX + "btnFoldDisplay")

    # Display settings ratio buttons
    SIDE_PANEL_RATIO_BUTTON_16_9 = Element(By.XPATH, "//*[@text='16:9']")
    SIDE_PANEL_RATIO_BUTTON_21_9 = Element(By.XPATH, "//*[@text='21:9']")
    SIDE_PANEL_RATIO_BUTTON_32_9 = Element(By.XPATH, "//*[@text='32:9']")

    ce_area_ratios_dict = {
        "16:9": SIDE_PANEL_RATIO_BUTTON_16_9,
        "21:9": SIDE_PANEL_RATIO_BUTTON_21_9,
        "32:9": SIDE_PANEL_RATIO_BUTTON_32_9,
    }

    # CE_AREA positions
    ce_area_left = "left"
    ce_area_center = "center"
    ce_area_right = "right"

    ce_area_positions_list = [ce_area_left, ce_area_center, ce_area_right]

    @classmethod
    def swipe_up_in_panel(cls):
        """
        Swipe up in Display Settings panel

        Find a ratio aspect button (the 21:9 by default) and swipe from
        that location until the top of the view.
        Return the ratio button element to be reused
        """
        zoom_title = cls.wb.until(
            ec.presence_of_element_located(cls.SIDE_PANEL_ZOOM_TITLE_ID),
            "Error while validating {cls.SIDE_PANEL_ZOOM_TITLE_ID.selector}",
        )
        zoom_title_location = zoom_title.location
        startx, starty = zoom_title_location["x"], zoom_title_location["y"]
        endy = 10
        cls.driver.swipe(startx, starty, startx, endy)

    @classmethod
    def change_aspect_ratio(cls, ratio_elem):
        """
        Change CE_AREA apect ratio to the given ratio
        """
        cls.swipe_up_in_panel()
        ratio_button = cls.wb.until(
            ec.presence_of_element_located(ratio_elem),
            f"Error while validating element presence: {ratio_elem.selector}",
        )
        ratio_button.click()

    @classmethod
    def change_ce_area_position(cls, pos="center"):
        pos_elem_id = cls.SIDE_PANEL_CONTENT_AREA_CARRIAGE_ID
        cls.swipe_up_in_panel()
        pos_elem = cls.wb.until(
            ec.presence_of_element_located(pos_elem_id),
            f"Error while validating element presence: {pos_elem_id.selector}",
        )
        pos_elem_bounds = utils.get_elem_bounds_detail(pos_elem)

        if pos == cls.ce_area_left:
            cls.driver.tap([((pos_elem_bounds["x_ini"] + 5), (pos_elem_bounds["y_ini"] + 5))])
        elif pos == cls.ce_area_center:
            pos_elem.click()
        elif pos == cls.ce_area_right:
            cls.driver.tap([((pos_elem_bounds["x_end"] - 1), (pos_elem_bounds["y_end"] - 1))])

    @classmethod
    def get_ce_area_expected_bounds(cls, pos, ratio):
        """
        Get the expected bounds values for the CE_AREA for the given
        position and ratio

        Args:
            pos - string : CE_AREA positions
            ratio - string : CE_AREA aspect ratios

        Returns:
            string : String with element bounds with the structure:
            '[x_start, y_start][x_end, y_end]'
        """
        ce_area_expected_bounds = {
            "16:9": {
                cls.ce_area_left: "[301,0][4141,2040]",
                cls.ce_area_center: "[1921,0][5761,2040]",
                cls.ce_area_right: "[3541,0][7381,2040]",
            },
            "21:9": {
                cls.ce_area_left: "[301,0][5341,2040]",
                cls.ce_area_center: "[1321,0][6361,2040]",
                cls.ce_area_right: "[2341,0][7381,2040]",
            },
            "32:9": {
                cls.ce_area_left: "[0,0][7680,2040]",
                cls.ce_area_center: "[0,0][7680,2040]",
                cls.ce_area_right: "[0,0][7680,2040]",
            },
        }
        return ce_area_expected_bounds[ratio][pos]
