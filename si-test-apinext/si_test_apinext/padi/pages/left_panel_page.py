import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.common.pages.base_page import Element
from si_test_apinext.padi.pages.side_panel_page import SidePanel

logger = logging.getLogger(__name__)


class LeftPanel(SidePanel):
    # Left Panel elements resource ID / locators
    PANEL_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "left_panel")

    PANEL_TXT_HOUR_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "txtHour")
    PANEL_TXT_MINUTE_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "txtMinute")
    PANEL_TXT_AMPM_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "txtAMPM")
    PANEL_TXT_DAYOFMONTH_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "txtDateField1")
    PANEL_TXT_DAYOFMONTH_ID_PU = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "txtDayOfMonth")
    PANEL_TXT_MONTH_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "txtDateField2")
    PANEL_TXT_MONTH_ID_PU = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "txtMonth")
    PANEL_SETTINGS_DETAILS_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "left_settings_detail")
    PANEL_CURRENT_TIME_ID = Element(By.ID, SidePanel.SIDE_PANEL_RESOURCE_ID_PREFIX + "currentTime")

    all_panel_elements = [
        PANEL_ID,
        PANEL_TXT_HOUR_ID,
        PANEL_TXT_MINUTE_ID,
        PANEL_TXT_AMPM_ID,
    ]
    ml_panel_elements = [PANEL_TXT_DAYOFMONTH_ID, PANEL_TXT_MONTH_ID]
    pu_panel_elements = [PANEL_TXT_DAYOFMONTH_ID_PU, PANEL_TXT_MONTH_ID_PU]

    side = "Left"
    side_locator = PANEL_ID
    side_center_coords = (960, 1080)

    child_lock_popup = (190, 990, 1340, 1120)

    @classmethod
    def validate_left_panel_elems(cls, branch, timeformat):
        """Validate presence of all LeftPanel elements"""
        cls.validate_side_panel_elems()
        if int(timeformat) == 2:  # Time is in 24h format
            cls.all_panel_elements.pop(cls.all_panel_elements.index(cls.PANEL_TXT_AMPM_ID))
        cls.all_panel_elements.extend(cls.pu_panel_elements) if branch == "pu2403" else cls.all_panel_elements.extend(
            cls.ml_panel_elements
        )
        for element in cls.all_panel_elements:
            cls.wb.until(
                ec.presence_of_element_located(element),
                f"Error while validating LeftPanel element presence: {element.selector}",
            )
        return True
