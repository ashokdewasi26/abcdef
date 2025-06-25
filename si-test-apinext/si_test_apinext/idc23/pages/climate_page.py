from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element
from si_test_apinext.util.global_steps import GlobalSteps
from mtee.testing.tools import retry_on_except


class ClimatePage(BasePage):

    # Climate app
    PACKAGE_NAME = "com.bmwgroup.apinext.climate"
    CLIMATE_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".ClimateMainActivity"

    PAGE_TITLE = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "statusbar_title")
    CLIMATE_ICON = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "climateIcon")
    CLIMATE_ON_OFF = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "climateMainSystemButton")
    CLIMATE_OFF = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "climateMainClimateOffTextView")
    CLIMATE_AC = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "climateMainACButton")
    CLIMATE_OPT_ACTIVE = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "overlayToggleBarActiveGlow")
    CLIMATE_MAX_AC = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "climateMainMaxACButton")
    CLIMATE_AIR_FLOW = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "climateMainAirRecirculationButton")
    CLIMATE_AUTO_ID = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "climateMainAutoButton")
    CLIMATE_AUTO_ID_ML = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "climatAutoManualButtonGroup")
    CLIMATE_SYNC_TEMP = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "climateMainSyncButton")
    AUTO_BLOWER_TEXT = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "autoBlowerTextView")
    AUTO_BLOWER_PLUS = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "autoBlowerPlusButton")
    AUTO_BLOWER_MINUS = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "autoBlowerMinusButton")
    MANUAL_BLOWER_TEXT = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "manualBlowerTextView")
    MANUAL_BLOWER_PLUS = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "manualBlowerPlusButton")
    MANUAL_BLOWER_MINUS = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "manualBlowerMinusButton")
    AIR_RECIRCULATION_MODE = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "air_recirculation_tile")
    AUTO_AIR_RECIRCULATION_MODE = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "automatic_air_recirculation_tile")
    FRESH_AIR_MODE = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "fresh_air_tile")

    # Bottom bar elements
    TEMP_PLUS_BUTTON = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "plusLayout")
    OVERLAY_TIME_PLUS_BUTTON = Element(By.ID, "com.bmwgroup.idnext.overlay:id/plusLayout")
    TEMP_MINUS_BUTTON = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "minusLayout")
    OVERLAY_TIME_MINUS_BUTTON = Element(By.ID, "com.bmwgroup.idnext.overlay:id/minusLayout")
    TEMP_VALUE = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "textViewNumDegrees")
    OVERLAY_TEMP_VALUE = Element(By.ID, "com.bmwgroup.idnext.overlay:id/textViewNumDegrees")
    MODE_TEXT = Element(By.ID, CLIMATE_RESOURCE_ID_PREFIX + "modeText")
    OVERLAY_MODE_TEXT = Element(By.ID, "com.bmwgroup.idnext.overlay:id/modeText")

    # Regions
    fan_popup = (365, 617, 1553, 787)

    @classmethod
    @retry_on_except(retry_count=2)
    def open_climate(cls):
        """Open climate app by pressing climate button
        *Press climate icon
        *Check title of page has "CLIMATE" in it
        :return: True, if page is open
        :raises: RuntimeError, in case the app title isn't found
        """
        climate_page_title = cls.driver.find_elements(*cls.PAGE_TITLE)
        if climate_page_title:
            if "CLIMATE" in climate_page_title[0].text:
                return True
        climate_icon = cls.driver.find_element(*cls.CLIMATE_ICON)
        climate_title = GlobalSteps.click_button_and_expect_elem(cls.wb, climate_icon, cls.PAGE_TITLE)
        if "CLIMATE" in climate_title.text:
            return True

        raise RuntimeError("Climate app could not open after clicking on Climate Icon")
