import logging
import re
import time

from appium.webdriver.common.appiumby import AppiumBy
from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import assert_true
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage, Element

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

MYMODES_TIMEOUT = 10  # Timeout for every mode to load


class ModesPage(BasePage):
    COMMON_NAME = "Modes"
    PACKAGE_NAME = "com.bmwgroup.apinext.modesandmoments"
    MODES_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".ui.activities.ModesAndMomentsActivity.Default"
    MODE_NAME_ELEM_PREFIX = "TextAtom"
    MODE_SECTION_PREFIX = "ExperienceCardNarrow-"
    ANDROID_SELECTION_BAR = Element(By.CLASS_NAME, "android.widget.ProgressBar")
    CHANGE_MODE_BUTTON_PREFIX = "TextAtom:dynamic_string/"
    CONFIGURE_TAB = Element(By.ID, "TextAtom:string/modes_and_moments_configure_bt")
    GENERAL_TAB = Element(By.ID, "TextAtom:string/modes_and_moments_config_page_general_htb")
    START_MODE_BTN = Element(By.ID, "TextAtom:string/modes_and_moments_general_tab_start_mode_bt")
    RESET_MODE_BTN = Element(
        By.XPATH,
        "//*[contains(@text, 'Reset Personal') or @text='Reset Sport' or "
        "@text='Reset Efficient' or @text='Reset Silent']",
    )
    LAST_USED_BTN = Element(By.ID, "TextAtom:string/modes_and_moments_general_tab_lum_info_prv")
    DISPLAY_STYLE = Element(By.ID, "TextAtom:string/modes_and_moments_design_tab_display_style_bt")
    AUTO_TAB = Element(By.ID, "TextAtom:string/modes_and_moments_design_tab_display_style_color_ui_mode_auto_bt")
    BRIGHT_TAB = Element(By.ID, "TextAtom:string/modes_and_moments_design_tab_display_style_color_ui_mode_bright_bt")
    DARK_TAB = Element(By.ID, "TextAtom:string/modes_and_moments_design_tab_display_style_color_ui_mode_dark_bt")
    MODE_CHANGE_DLT_MSG = re.compile(r"Slot successfully changed to MyMode (\d+)")
    MODES_DICT = {
        "PERSONAL": "1000",
        "EFFICIENT": "1001",
        "SPORT": "1002",
        "SILENT": "1003",
    }
    BACK_BTN = Element(By.XPATH, "//android.view.View[@resource-id='back_button']")
    MYMODES_PAGE_HEADER = Element(
        By.XPATH, "//android.widget.TextView[@resource-id='TextAtom:string/modes_and_moments_landing_page_hdr']"
    )
    MYMODES_BTN = Element(By.XPATH, "//*[contains(@resource-id, 'IconicBar.Det.Modes')]")
    MODE_SECTION_ELEM_GENERIC_ID = Element(
        AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceIdMatches("{MODE_SECTION_PREFIX}.*")'
    )
    MODE_NAME_ELEM_GENERIC_ID = Element(
        By.XPATH, f"//*[contains(@resource-id, '{MODE_NAME_ELEM_PREFIX}') and @package='{PACKAGE_NAME}']"
    )
    CONFIGURE_BTN = Element(By.ID, "TextAtom:string/modes_and_moments_configure_bt")
    DESIGN_TAB = Element(By.ID, "TextAtom:string/modes_and_moments_config_page_design_htb")
    AMBIENT_LIGHT_BTN = Element(By.ID, "TextAtom:string/modes_and_moments_design_tab_ambient_light_color_bt")
    MULTI_COLOR_BTN = Element(
        By.ID, "TextAtom:string/modes_and_moments_design_tab_ambient_light_color_multicolor_color_bt"
    )
    DISPLAY_STYLE_TOGGLE_BTN = Element(
        By.ID, "TextAtom:string/modes_and_moments_design_tab_ambient_light_sync_to_display_style_bt"
    )
    DISPLAY_STYLE = Element(By.ID, "TextAtom:string/modes_and_moments_design_tab_display_style_bt")
    BACK_ARROW = Element(By.ID, "IconAtom:drawable/idx_icon_back_arrow_simple")

    @classmethod
    def check_android_mymodes(cls):
        """Check if MyModesAndMoments activity is in list of activities"""
        time.sleep(2)
        list_activities = [cls.get_activity_name()]

        modes_available = cls.validate_activity(list_activities=list_activities)
        if modes_available:
            logger.info("Modes activity started successfully")
        else:
            logger.warning("Failed on starting Launcher activity")
        return modes_available

    @classmethod
    def get_current_mode(cls):
        """Get the currently selected mode name

        The strategy is:
        - Wait until a selection bar is shown (blue bar under currently selected mode name)
        - Use a generic ID which matches any mode to collect them all
        - From the collected check which has a selection bar
        - Return the name of the mode containing the selection bar
        """
        selected_mode = ""
        selection_bar = None
        # Wait to have a selection bar visible
        cls.check_visibility_of_element(cls.ANDROID_SELECTION_BAR, MYMODES_TIMEOUT)
        # Collect all modes section elements
        mode_section_elems = cls.driver.find_elements(*cls.MODE_SECTION_ELEM_GENERIC_ID)
        if not mode_section_elems:
            raise RuntimeError("Could not find any modes on UI")
        else:
            logger.info("Going to check which mode has the selection bar")
            for mode_elem in mode_section_elems:
                selection_bar = mode_elem.find_elements(*cls.ANDROID_SELECTION_BAR)
                if selection_bar:
                    mode_elem_name = mode_elem.find_elements(*cls.MODE_NAME_ELEM_GENERIC_ID)
                    assert mode_elem_name, (
                        "Failed to get current selected mode. "
                        f"Selection bar was found, but not the element with mode name: '{mode_elem_name[0].text}'"
                    )
                    selected_mode = mode_elem_name[0].text
                    logger.info(f"Found selection bar in '{selected_mode}', returning as selected mode")
        assert selected_mode, "Failed to get current selected mode"
        return selected_mode

    @classmethod
    def set_mode_and_validate(cls, test, mode_name):
        """Change mode to 'mode_name' and check if the mode was successfully changed."""
        if mode_name not in cls.MODES_DICT:
            raise ValueError(f"Mode {mode_name} does not exist in the modes dictionary.")

        mode_id = cls.MODES_DICT[mode_name]
        requested_mode_resource_id = f'new UiSelector().resourceId("{cls.MODE_SECTION_PREFIX + mode_id}")'
        requested_mode_elem = Element(AppiumBy.ANDROID_UIAUTOMATOR, requested_mode_resource_id)

        wait_dlt_timeout = 15
        try:
            with DLTContext(test.mtee_target.connectors.dlt.broker, filters=[("IXMA", "EXPC")]) as trace:
                cls.click(requested_mode_elem)
                mode_changed_msg = trace.wait_for(
                    attrs={"payload_decoded": cls.MODE_CHANGE_DLT_MSG},
                    drop=True,
                    count=1,
                    timeout=wait_dlt_timeout,
                )
        except NoSuchElementException as exc:
            raise RuntimeError(f"Could not find '{mode_name}' mode button.") from exc
        except TimeoutException as exc:
            raise RuntimeError(f"Timed out waiting for DLT message confirming mode changed to '{mode_name}'.") from exc
        # to allow the transition to occur
        time.sleep(11)
        cls.ensure_page_loaded(test)
        # Validate mode ID from DLT
        captured_mode_id = cls.MODE_CHANGE_DLT_MSG.search(mode_changed_msg[0].payload_decoded).group(1)
        assert_true(
            mode_id == captured_mode_id,
            f"Mode switch failed to validate in DLT. Expected mode id '{mode_id}', but got {captured_mode_id}.",
        )
        # Validate mode name from UI
        current_mode = cls.get_current_mode()
        assert_true(
            mode_name.upper() in current_mode.upper(),
            f"Mode switch failed to validate in UI. Expected mode {mode_name.upper()}, got {current_mode.upper()}.",
        )
        return test.take_apinext_target_screenshot(test.results_dir, "switched_mode_to_" + mode_name)

    @classmethod
    def ensure_page_loaded(cls, test):
        """
        Ensure that the page is loaded by checking if all modes are visible.

        Returns the list of modes expected but not found, or raises an error
        if the My Modes page cannot be accessed.
        """
        cls.start_activity()
        time.sleep(2)  # Wait for the activity to start
        test.take_apinext_target_screenshot(test.results_dir, "before_check_android_mymodes")

        if not cls.check_if_in_mymodes_page():
            logger.info("Attempting to navigate to My Modes...")
            test.apinext_target.send_tap_event(2237, 1332)
            test.take_apinext_target_screenshot(test.results_dir, "after_tapping")

            if not cls.check_android_mymodes() and not cls.check_if_in_mymodes_page():
                logger.error("Failed to access My Modes and Moments after navigation attempts.")
                raise RuntimeError("Could not access My Modes and Moments")

    @classmethod
    def navigate_to_ambient_lighting_page(cls):
        """
        Navigate to Ambient light and ensure 'Synchronize with display style' button is visible.
        """
        cls.click(cls.CONFIGURE_BTN)
        cls.click(cls.DESIGN_TAB)
        cls.click(cls.AMBIENT_LIGHT_BTN)
        display_style_toggle_btn_availability_status = cls.wait_to_check_visible_element(cls.DISPLAY_STYLE_TOGGLE_BTN)
        assert_true(
            display_style_toggle_btn_availability_status,
            "'Synchronize with display style' button is not visible after clicking on ambient light button",
        )

    @classmethod
    def find_missing_modes(cls):
        """
        Finds missing modes on the current screen

        Return AssertionError if no mode is found, else
        return the list of modes expected but not found
        """
        missing_modes = []
        # get all modes elements
        mode_elem_name = cls.driver.find_elements(*cls.MODE_NAME_ELEM_GENERIC_ID)
        assert (
            mode_elem_name
        ), "Failed to get any mode.\
                        Tried a generic ID to get all modes showing but failed"
        present_modes = [current_mode.text.upper() for current_mode in mode_elem_name]
        logger.info(f"Modes found on UI: '{present_modes}'")

        for mode_name in cls.MODES_DICT.keys():
            if not any(mode_name.upper() in found_mode.upper() for found_mode in present_modes):
                missing_modes.append(mode_name)

        return missing_modes

    @classmethod
    def check_if_in_mymodes_page(cls):
        """
        Checks if it's in the my modes page.
        """
        # Check for the My Modes Page header
        if cls.driver.find_elements(*cls.MYMODES_PAGE_HEADER):
            return True

        # If not found, click the back button (if it exists)
        back_btn = cls.driver.find_elements(*cls.BACK_BTN)
        if back_btn:
            logger.info("Clicking back button")
            cls.click(cls.BACK_BTN)

        return cls.driver.find_elements(*cls.MYMODES_PAGE_HEADER)
