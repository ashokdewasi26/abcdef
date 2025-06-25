from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element


class NavigationPage(BasePage):

    # Navigation App
    NAV_RESOURCE_ID_PREFIX = "com.bmwgroup.idnext.navigation:id/"
    NAV_MAIN_MAP_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "main_map")
    NAV_MAIN_INFO_VIEW = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "information_text_view")
    OVERLAY_NAV_BUTTON = Element(By.ID, "com.bmwgroup.idnext.overlay:id/det_navigation")
    WAITING_PROVISIONING = Element(By.XPATH, "//*[contains(@text, 'PROVISIONING')]")
    nav_vhal_event_keycode = 10010
