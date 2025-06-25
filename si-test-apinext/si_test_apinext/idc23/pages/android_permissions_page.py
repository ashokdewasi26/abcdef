import logging
import time

from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class AndroidPermissionsPage(BasePage):

    PACKAGE_NAME = "com.android.permissioncontroller"
    ANDROID_PERMISSIONS_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    # Elements resource ID / locators
    UI_LIST_ITEM_ID = Element(By.ID, ANDROID_PERMISSIONS_RESOURCE_ID_PREFIX + "car_ui_list_item_title")
    UI_LIST_ITEM_TOUCH_ID = Element(
        By.ID, ANDROID_PERMISSIONS_RESOURCE_ID_PREFIX + "car_ui_list_item_touch_interceptor"
    )
    UI_TOOLBAR_ICON_ID = Element(By.ID, ANDROID_PERMISSIONS_RESOURCE_ID_PREFIX + "car_ui_toolbar_nav_icon_container")
    BACK_BUTTON_ID = Element(By.ID, ANDROID_PERMISSIONS_RESOURCE_ID_PREFIX + "permissionAppsFragment_backBtn")

    ALLOW_WHILE_USING_APP_ID = Element(By.XPATH, "//*[@text='While using the app']")
    ALLOW_ID = Element(By.XPATH, "//*[@text='Allow']")
    DONT_ALLOW_ID = Element(By.XPATH, "//*[@text='Don’t allow & don’t ask again']")

    @classmethod
    def click_allow_return(cls):
        """In case an Android dialog box appears, click on allow and return"""
        allow_button = cls.driver.find_elements(*AndroidPermissionsPage.ALLOW_ID)
        if allow_button:
            allow_button[0].click()
            time.sleep(0.5)
        back_button = cls.driver.find_elements(*AndroidPermissionsPage.UI_TOOLBAR_ICON_ID)
        if back_button:
            back_button[0].click()
        back_button = cls.driver.find_elements(*AndroidPermissionsPage.BACK_BUTTON_ID)
        if back_button:
            back_button[0].click()
        return

    @classmethod
    def click_allow_while_using_app(cls):
        """In case an Android dialog box appears, click on allow while using app"""
        ui_pop_up = cls.driver.find_elements(*AndroidPermissionsPage.UI_LIST_ITEM_ID)
        if ui_pop_up:
            allow_option = cls.check_visibility_of_element(AndroidPermissionsPage.ALLOW_WHILE_USING_APP_ID)
            allow_option.click()
        return

    @classmethod
    def click_first_item(cls):
        """Locate dialog box and click on first answer (usually 'Allow')"""
        allow_button_elem = cls.check_presence_of_element_located(AndroidPermissionsPage.UI_LIST_ITEM_TOUCH_ID)
        allow_button_elem.click()
        time.sleep(1)
        return
