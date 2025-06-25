import logging
import sh
import time

from appium.webdriver.common.appiumby import AppiumBy
from mtee.testing.tools import retry_on_except
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from si_test_apinext.common.pages.base_page import BasePage, Element
from si_test_apinext.util.global_steps import GlobalSteps


logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class SettingsAppPage(BasePage):

    PACKAGE_NAME = "com.bmwgroup.idnext.settings"
    SETTINGS_APP_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".SettingsActivity"
    PACKAGE_ACTIVITY_ML = ".appidc23.SettingsActivity"

    # Page title
    SETTINGS_MENU_TITLE = ["SYSTEM SETTINGS", "SETTINGS"]

    # language settings
    LANGUAGE_BUTTON_ID = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        "new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector()."
        + f'resourceId("{SETTINGS_APP_RESOURCE_ID_PREFIX}btnLanguage"))',
    )
    LANGUAGE_RADIO_BUTTON_GROUP_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "languageRadioButtonGroup")
    LANGUAGE_ITEM = Element(By.CLASS_NAME, "android.view.ViewGroup")
    RADIO_BUTTON_ITEM = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "item_radioButton")
    STATUSBAR_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "miniHeader")
    # START_RSU_BUTTON = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "btnRSU")
    START_RSU_BUTTON = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        "new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector()."
        + f'resourceId("{SETTINGS_APP_RESOURCE_ID_PREFIX}btnRSU"))',
    )
    # SettingsApp main menu elements resource ID / locators
    DATE_TIME_BUTTON_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "btnDateTime")

    # Date and time submenu
    DATE_TIME_ACTIVITY_TITLE_BAR_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "activity_title_bar")
    TIME_ZONE_ITEM_LABEL_SECONDARY_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "item_label_secondary")

    # Automatic related elements
    TIME_ZONE_AUTOMATIC_TOGGLE_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "automaticTimeZoneToggle")

    # Toggle elements
    MANUAL_SELECT_TOGGLE = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "manualSelectToggle")
    TWO_LINE_TOGGLE_TOGGLE_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "twoLinesToggleToggle")
    TWO_LINE_TOGGLE_SUBTITLE_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "twoLinesToggleSubtitle")

    # Item label elements
    ITEM_LABEL_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "item_label")
    ITEM_LABEL_SECONDARY_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "item_label_secondary")

    # Time zone display related elements
    TIME_ZONE_DISPLAY_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "timeZoneDisplay")
    TIME_ZONE_DISPLAY_ITEM_LABEL_SECONDARY_XPATH = Element(
        By.XPATH,
        "//*[@resource-id='{}']/*[@resource-id='{}']".format(
            TIME_ZONE_DISPLAY_ID.selector, ITEM_LABEL_SECONDARY_ID.selector
        ),
    )

    STATUSBAR_TITLE = Element(
        By.XPATH,
        "//*[@resource-id='{}']//*[@resource-id='{}']".format(STATUSBAR_ID.selector, ITEM_LABEL_ID.selector),
    )

    # Date and time - Time zone submenu
    TIME_ZONE_REGION_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "timeZoneRegion")
    TIME_ZONE_ZONE_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "timeZoneZone")

    TIME_ZONE_REGION_SEARCH_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "regionsSearch")
    TIME_ZONE_REGION_SEARCH_BOX_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "search_box")
    TIME_ZONE_REGION_SEARCH_LIST_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "regionSearchList")
    TIME_ZONE_SEARCH_LIST_REGION_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "region")
    TIME_ZONE_SELECT_TIME_ZONE_ZONES_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "selectTimeZoneZones")

    # Present on all submenus
    BACK_ARROW_NO_NAVIGATION_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "back_arrow_no_navigation")

    # Swipe
    RSU_SWIPE = (1100, 768, 1100, 480)

    @classmethod
    def get_current_default_time_zone(cls):
        """
        Return the timezone text from the auto timezone element

            Returns:
                str with timezone found
        """
        cls.enter_date_time_submenu()
        time_zone_text = cls.get_current_time_zone()
        return time_zone_text

    @classmethod
    def set_time_zone(cls, wanted_region="Portugal"):
        """
        Set new timezone by searching for country/region and selecting the first possible timezone

            Args:
                wanted_region - str with the name of the country/region to be selected

            Returns:
                str with timezone found
        """
        cls.enter_date_time_submenu()
        # If "Time Zone" option not visible, deactivate "Automatic time zone setting toogle"
        time_zone_elem_list = cls.driver.find_elements(*cls.TIME_ZONE_DISPLAY_ID)
        if not time_zone_elem_list:
            time_zone_toogle_elem = cls.driver.find_element(*cls.TIME_ZONE_AUTOMATIC_TOGGLE_ID)
            time_zone_elem = GlobalSteps.click_button_and_expect_elem(
                cls.wb, time_zone_toogle_elem, cls.TIME_ZONE_DISPLAY_ID
            )
        else:
            time_zone_elem = time_zone_elem_list[0]

        # Find and click "Region" on Time Zone submenu
        time_zone_region_elem = GlobalSteps.click_button_and_expect_elem(
            cls.wb, time_zone_elem, cls.TIME_ZONE_REGION_ID
        )
        # Find and click the search bar to select the Region
        time_zone_region_search_elem = GlobalSteps.click_button_and_expect_elem(
            cls.wb, time_zone_region_elem, cls.TIME_ZONE_REGION_SEARCH_ID
        )
        # Find and introduce the wanted region text on the box
        time_zone_region_search_box_elem = GlobalSteps.click_button_and_expect_elem(
            cls.wb, time_zone_region_search_elem, cls.TIME_ZONE_REGION_SEARCH_BOX_ID
        )
        time_zone_region_search_box_elem.send_keys(wanted_region)
        # Get list of results
        time_zone_search_list_elem = cls.wb.until(
            ec.visibility_of_element_located(cls.TIME_ZONE_SEARCH_LIST_REGION_ID),
            f"Error while validating visibility of {cls.TIME_ZONE_SEARCH_LIST_REGION_ID.selector}",
        )
        region_result_list = time_zone_search_list_elem.find_element(By.XPATH, ("//*[@text!='']"))
        # No two countries have the same name
        assert (
            region_result_list.text == wanted_region
        ), f"Error while trying to select {wanted_region}, instead found: {str(region_result_list)}"
        region_result_list.click()
        # Some countries have multiple time zones, for now select the first on the list
        try:
            region_time_zone = WebDriverWait(cls.driver, 1).until(
                ec.visibility_of_element_located(cls.TIME_ZONE_SELECT_TIME_ZONE_ZONES_ID),
                f"Error while validating visibility of {cls.TIME_ZONE_SELECT_TIME_ZONE_ZONES_ID.selector}",
            )
            region_time_zone_list = region_time_zone.find_element(By.XPATH, ("//*[@text!='']"))
            # Default: Click on the first of the list
            region_time_zone_list.click()
        except TimeoutException:
            pass

    @classmethod
    def enter_date_time_submenu(cls):
        """
        Enter Date Time submenu
        """
        date_time_button = cls.wb.until(
            ec.visibility_of_element_located(cls.DATE_TIME_BUTTON_ID),
            f"Error while validating visibility of {cls.DATE_TIME_BUTTON_ID.selector}",
        )
        GlobalSteps.click_button_and_expect_elem(cls.wb, date_time_button, cls.TIME_ZONE_AUTOMATIC_TOGGLE_ID)

    @classmethod
    def get_current_time_zone(cls):
        """
        Return the timezone text from the automatic timezone element

        In case automatic timezone element is not toggled, get timezone from timezone display elem

            Returns:
                str with timezone found

            Raises:
                AssertionError - If text found doesn't have GMT on it
        """
        time_zone_elem_list = cls.driver.find_elements(*cls.TIME_ZONE_DISPLAY_ID)
        if time_zone_elem_list:
            time_zone_elem_list = cls.driver.find_element(*cls.TIME_ZONE_DISPLAY_ID)
            time_zone_text = time_zone_elem_list.find_element(*cls.ITEM_LABEL_SECONDARY_ID).text
        else:
            time_zone_toogle_elem = cls.driver.find_element(*cls.TIME_ZONE_AUTOMATIC_TOGGLE_ID)
            time_zone_text = time_zone_toogle_elem.find_element(*cls.ITEM_LABEL_SECONDARY_ID).text
        assert "GMT" in time_zone_text, f"GMT not in {time_zone_text}"
        return time_zone_text

    @classmethod
    def get_current_manual_time_zone(cls):
        """
        Return the timezone text from the manual timezone element

            Returns:
                str with timezone found

            Raises:
                AssertionError - If text found doesn't have GMT on it
        """
        elem = cls.TIME_ZONE_ZONE_ID
        sub_elem = cls.TIME_ZONE_ITEM_LABEL_SECONDARY_ID
        time_zone_elem = cls.wb.until(
            ec.visibility_of_element_located(elem),
            f"Error while validating visibility of {elem.selector}",
        )
        time_zone_elem_subtext = time_zone_elem.find_element(*sub_elem)
        assert "GMT" in time_zone_elem_subtext.text, f"GMT not in {time_zone_elem_subtext.text}"

        return time_zone_elem_subtext.text

    @classmethod
    def set_24_hour_format(cls):
        """
        Set to 24H format the time displayed on HU Android UI

            Returns:
                None

            Raises:
                Exception - If time format is not recognized
        """
        cls.enter_date_time_submenu()
        manual_select = cls.wb.until(
            ec.visibility_of_element_located(cls.MANUAL_SELECT_TOGGLE),
            f"Error while validating visibility of {cls.MANUAL_SELECT_TOGGLE.selector}",
        )
        elem_text = "24-hour format"
        time_format_element = manual_select.find_element(By.XPATH, (f"//*[@text='{elem_text}']"))
        time_format_element_parent = time_format_element.parent
        time_format_subtitle = time_format_element_parent.find_element(*cls.ITEM_LABEL_SECONDARY_ID)
        time_format_subtitle_text = time_format_subtitle.text.strip().lower()
        if "pm" in time_format_subtitle_text or time_format_subtitle_text == "1:00 pm":
            time_format_element.click()
            time.sleep(0.2)
            updated_subtitle_text = time_format_element_parent.find_element(*cls.ITEM_LABEL_SECONDARY_ID).text.strip()
            assert updated_subtitle_text == "13:00"
        elif time_format_subtitle_text == "13:00":
            pass
        else:
            raise Exception(
                f"Unexpected time format, please adapt 'set_24_hour_format' method accordingly.\
            New time format found: {time_format_subtitle_text}"
            )

    @classmethod
    def return_from_submenus(cls):
        """
        Click on back arrow button to return from submenus until reaches General settings menu

        Time settings submenus have the back arrow button, this method recursively clicks
        on this button in order to return to the settings main menu

            Returns:
                None

            Raises:
                Exception - If some unexpected page is reached
        """
        while cls.try_back_arrow_click():
            general_settings_element = cls.driver.find_elements(By.XPATH, ("//*[@text='System settings']"))
            if general_settings_element:
                return
        raise Exception("Reached unexpected page, please make sure this method is used in a settings submenu")

    @classmethod
    def launch_settings_activity(cls, validate_activity=True):
        """Launches setting activity page on target

        :param validate_activity: Validation check whether activity has launched successfully.
        """
        logger.info(f"Branch name: {cls.branch_name}")
        if cls.branch_name == "pu2403":
            settings_activity = f"{cls.PACKAGE_NAME}/{cls.PACKAGE_ACTIVITY}"
        else:
            settings_activity = f"{cls.PACKAGE_NAME}/{cls.PACKAGE_ACTIVITY_ML}"
        logger.info(f"Launching Setting Activity: {settings_activity}")
        command = f"am start -n {settings_activity}"
        cls.apinext_target.execute_command(command)
        time.sleep(1)
        # Press back two times to deal with the scenario of the settings app being left on some
        # sub settings menu
        GlobalSteps.inject_key_input(cls.apinext_target, cls.back_keycode)
        time.sleep(1)
        GlobalSteps.inject_key_input(cls.apinext_target, cls.back_keycode)
        time.sleep(1)
        cls.apinext_target.execute_command(command)
        if validate_activity:
            activity_found = cls.validate_resumed_activities_on_screen(settings_activity)
            if not activity_found:
                raise RuntimeError(f"Runtime error occurred while launching activities {settings_activity}/")

    @classmethod
    @retry_on_except(retry_count=2, backoff_time=2)
    def validate_resumed_activities_on_screen(cls, activities):
        """
        Validates whether activity name passed as an argument is present on Foreground on target.

        Note:
            In case if argument type is list,
            this function will return True if any one item of the list appears on Foreground

            Returns:
                True OR False

        :param activities: (str/list) activity name OR list with multiple activity names
        """
        activity_found = None
        try:
            resumed_act = cls.apinext_target.execute_command("dumpsys activity activities | grep ResumedActivity")
        except sh.ErrorReturnCode_1 as err:
            logger.info("Unable to find current activities using adb dumpsys")
            raise err
        if isinstance(activities, str):
            activities = [activities]
        for each_act in activities:
            logger.info(f"Finding activity: {each_act} in Resumed Activity list: {resumed_act}")
            if each_act in resumed_act:
                activity_found = True
                logger.info(f"Found activity: {each_act}")
                break
            else:
                activity_found = False
        return activity_found

    @classmethod
    def language_change(cls, language_name):
        """
        Wait for set time and click on element

        Args:
            language_name - Language to be changed
        """
        try:
            lang_name = By.XPATH, f"//*[@text='{language_name}']"
            logger.info(f"Language Changing to {language_name}")
            cls.launch_settings_activity()
            cls.wait_and_click_on_element(element=cls.LANGUAGE_BUTTON_ID)
            cls.wait_and_click_on_element(element=lang_name)
            logger.info(f"Language Changed to {language_name}")
        except Exception as e:
            raise Exception(f"Unable to Change the Language : {e}")
