import time

from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import Element
from si_test_apinext.idc23.pages.settings_app_page import SettingsAppPage
from si_test_apinext.util.global_steps import GlobalSteps


class UnitsSettingsAppPage(SettingsAppPage):

    UNITS_DISTANCE_BUTTON_ID = Element(By.ID, SettingsAppPage.SETTINGS_APP_RESOURCE_ID_PREFIX + "unitsDistance")

    KM_RATIO_BUTTON = Element(By.XPATH, "//*[@text='km']")
    MI_RATIO_BUTTON = Element(By.XPATH, "//*[@text='mi']")

    @classmethod
    def enter_units_submenu(cls):
        """
        Enter Units submenu
        """
        units_button_id = cls.driver.find_elements(*cls.UNITS_BUTTON_ID)
        units_button = (
            cls.driver.find_element(*cls.UNITS_BUTTON_ID)
            if units_button_id
            else (cls.driver.find_element(*cls.UNITS_BUTTON_ID_BY_UI_AUTOMATOR))
        )

        distance_button = GlobalSteps.click_button_and_expect_elem(cls.wb, units_button, cls.UNITS_DISTANCE_BUTTON_ID)
        return distance_button

    @classmethod
    def set_distance_unit(cls, unit="km"):
        """
        Set distance unit of measurement

        :param unit: Unit to be selectd, defaults to "km"
        :type unit: str, optional
        :raises AssertionError: if not given one of the valid units: ["km", "mi"]
        """
        valid_units = ["km", "mi"]
        if unit == "km":
            select_unit = cls.KM_RATIO_BUTTON
        elif unit == "mi":
            select_unit = cls.MI_RATIO_BUTTON
        else:
            raise AssertionError(f"Given unit '{unit}' is not valid, valid units are: '{str(valid_units)}'")

        # Start Settings App
        cls.launch_settings_activity()
        time.sleep(1)
        distance_button = cls.enter_units_submenu()
        unit_btn = GlobalSteps.click_button_and_expect_elem(cls.wb, distance_button, select_unit)
        unit_btn.click()
