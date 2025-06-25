from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.by import By
from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage, Element


class AndroidSettings(BasePage):
    PACKAGE_NAME = "com.android.settings"
    ANDROID_SETTINGS_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".Settings$ConnectedDeviceDashboardActivity"

    PACKAGE_NAME_ACTIVITY = PACKAGE_NAME + "/" + PACKAGE_ACTIVITY

    PAIR_NEW_DEVICE = Element(By.XPATH, "//*[@text='Pair new device']")
    DEVICE_NAME = Element(By.XPATH, "//*[@text='Device name']")
    PAIR_CONNECT = Element(By.XPATH, "//*[@text='Pair & connect']")
    PAIR = Element(By.XPATH, "//*[@text='Pair']")
    TAP_TO_PAIR_WITH = Element(By.XPATH, "//*[contains(@text, 'Tap to pair with')]")
    PAIRING_SUBHEAD = Element(By.ID, ANDROID_SETTINGS_RESOURCE_ID_PREFIX + "pairing_subhead")

    CONNECTED_DEVICES = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        "new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector()."
        + 'text("Connected devices"))',
    )
