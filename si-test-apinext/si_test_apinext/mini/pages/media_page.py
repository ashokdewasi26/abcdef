from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element


class MediaPage(BasePage):

    # Media app
    MEDIA_RESOURCE_ID_PREFIX = "com.bmwgroup.apinext.mediaapp:id/"
    MEDIA_BAR_ID = MEDIA_RESOURCE_ID_PREFIX + "action_bar_root"
    BACK_ARROW_ID = Element(By.ID, MEDIA_RESOURCE_ID_PREFIX + "back_arrow")
    RECONNECT_MEDIA = Element(By.ID, MEDIA_RESOURCE_ID_PREFIX + "reconnect_button")
    MEDIA_SOURCE_SELECTOR_ID = Element(By.ID, MEDIA_RESOURCE_ID_PREFIX + "mini_selector")
    OVERLAY_MEDIA_BUTTON = Element(By.ID, "com.bmwgroup.idnext.overlay:id/det_media")
    media_vhal_event_keycode = 1008

    @classmethod
    def get_media_element_id(cls):
        return Element(By.ID, cls.MEDIA_BAR_ID)
