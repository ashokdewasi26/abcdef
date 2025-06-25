import time

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from si_test_apinext.common.pages.base_page import Element
from si_test_apinext.idc23.pages.settings_app_page import SettingsAppPage
from si_test_apinext.util.global_steps import GlobalSteps


class DateTimeSettingsAppPage(SettingsAppPage):

    # Date and time submenu
    DATE_TIME_ACTIVITY_TITLE_BAR_ID = Element(
        By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "activity_title_bar"
    )
    TIME_ZONE_ITEM_LABEL_SECONDARY_ID = Element(
        By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "item_label_secondary"
    )

    # Automatic related elements
    TIME_ZONE_AUTOMATIC_TOGGLE_ID = Element(
        By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "automaticTimeZoneToggle"
    )

    # Toggle elements
    MANUAL_SELECT_TOGGLE = Element(By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "manualSelectToggle")
    TWO_LINE_TOGGLE_TOGGLE_ID = Element(
        By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "twoLinesToggleToggle"
    )
    TWO_LINE_TOGGLE_SUBTITLE_ID = Element(
        By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "twoLinesToggleSubtitle"
    )

    # Item label elements
    ITEM_LABEL_ID = Element(By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "item_label")
    ITEM_LABEL_SECONDARY_ID = Element(By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "item_label_secondary")

    # Time zone display related elements
    TIME_ZONE_DISPLAY_ID = Element(By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "timeZoneDisplay")
    TIME_ZONE_DISPLAY_ITEM_LABEL_SECONDARY_XPATH = Element(
        By.XPATH,
        "//*[@resource-id='{}']/*[@resource-id='{}']".format(
            TIME_ZONE_DISPLAY_ID.selector, ITEM_LABEL_SECONDARY_ID.selector
        ),
    )

    # Date and time - Time zone submenu
    TIME_ZONE_REGION_ID = Element(By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "timeZoneRegion")
    TIME_ZONE_ZONE_ID = Element(By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "timeZoneZone")

    TIME_ZONE_REGION_SEARCH_ID = Element(By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "regionsSearch")
    TIME_ZONE_REGION_SEARCH_BOX_ID = Element(By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "search_box")
    TIME_ZONE_REGION_SEARCH_LIST_ID = Element(
        By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "regionSearchList"
    )
    TIME_ZONE_SEARCH_LIST_REGION_ID = Element(By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "region")
    TIME_ZONE_SELECT_TIME_ZONE_ZONES_ID = Element(
        By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "selectTimeZoneZones"
    )

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
        date_time_btn = cls.driver.find_element(*SettingsAppPage.DATE_TIME_GROUP_BY_UI_AUTOMATOR)
        if date_time_btn:
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
        elem = (
            cls.TIME_ZONE_ZONE_ID
            if cls.driver.find_elements(*cls.TIME_ZONE_ZONE_ID)
            else cls.TIME_ZONE_SELECT_TIME_ZONE_ZONES_ID
        )
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
        if time_format_subtitle.text.lower() == "1:00 pm":
            time_format_element.click()
            time.sleep(0.2)
            assert time_format_subtitle.text == "13:00"
        elif time_format_subtitle.text == "13:00":
            pass
        else:
            raise Exception(
                f"Unexpected time format, please adapt 'set_24_hour_format' method accordingly.\
            New time format found: {time_format_subtitle.text}"
            )
