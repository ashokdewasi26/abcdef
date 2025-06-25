from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.common.pages.base_page import Element
from si_test_apinext.padi.pages.side_panel_page import SidePanel


class RightPanel(SidePanel):
    # Right Panel elements resource ID / locators
    PANEL_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "right_panel")

    PANEL_TXT_TEMPERATURE_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "txtTemperature")
    PANEL_TXT_TEMPERATURE_UNIT = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "txtTemperatureUnit")
    PANEL_ICON_WEATHER_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "weatherIcon")
    PANEL_TXT_CITY_NAME_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "txtCityName")
    PANEL_DIVIDER_CITY_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "cityDivider")
    PANEL_TXT_WEATHER_STATUS_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "txtWeatherStatus")
    PANEL_TXT_AQI_LABEL_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "txtAQI_label")
    PANEL_DIVIDER_AQI_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "aqiDivider")
    PANEL_TXT_AQI_VALUE_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "txtAQI_value")
    PANEL_SETTINGS_DETAILS_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "right_settings_detail")
    # Excluding weather icon as it will only be available if target connected to internet
    all_panel_elements = [
        PANEL_ID,
    ]

    all_panel_cn_elements = [
        PANEL_ID,
        PANEL_TXT_AQI_LABEL_ID,
        PANEL_DIVIDER_AQI_ID,
        PANEL_TXT_AQI_VALUE_ID,
    ]
    side = "Right"
    side_locator = PANEL_ID
    side_center_coords = (6720, 1080)

    @classmethod
    def validate_right_panel_elems(cls):
        """Validate presence of all RightPanel elements"""
        cls.validate_side_panel_elems()
        for element in cls.all_panel_elements:
            cls.wb.until(
                ec.presence_of_element_located(element),
                f"Error while validating RightPanel element presence: {element.selector}",
            )
        return True

    @classmethod
    def validate_panel_cn_elems(cls):
        """Validate presence of all RightPanel elements in China variant"""
        cls.validate_side_panel_elems()
        for element in cls.all_panel_cn_elements:
            cls.wb.until(
                ec.presence_of_element_located(element),
                f"Error while validating RightPanel element presence: {element.selector}",
            )
        return True
