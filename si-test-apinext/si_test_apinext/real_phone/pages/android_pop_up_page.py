from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element


class AndroidPopUp(BasePage):

    PACKAGE_NAME = "android"
    ANDROID_POP_UP_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ""

    MESSAGE_ID = Element(By.ID, ANDROID_POP_UP_RESOURCE_ID_PREFIX + "message")
    SUMMARY = Element(By.ID, ANDROID_POP_UP_RESOURCE_ID_PREFIX + "summary")
    BUTTON1 = Element(By.ID, ANDROID_POP_UP_RESOURCE_ID_PREFIX + "button1")
    BUTTON2 = Element(By.ID, ANDROID_POP_UP_RESOURCE_ID_PREFIX + "button2")
    ALLOW_BUTTON = Element(By.XPATH, "//*[@text='Allow']")
    dont_allow_str = "Don/'t allow"
    DONT_ALLOW_BUTTON = Element(By.XPATH, f"//*[@text='{dont_allow_str}']")
