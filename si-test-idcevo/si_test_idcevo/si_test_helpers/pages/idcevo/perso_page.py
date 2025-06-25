# Copyright (C) 2024-2025. BMW Group. All rights reserved.
import logging
import re
import time

from appium.webdriver.common.appiumby import AppiumBy
from mtee.testing.tools import assert_true
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from si_test_idcevo import MetricsOutputName
from si_test_idcevo.si_test_helpers.apinext_target_handlers import LIST_MAIN_DISPLAY_ID
from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage, Element
from validation_utils.utils import TimeoutCondition

DISPLAY_ID = LIST_MAIN_DISPLAY_ID["idcevo"]

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class PersoBMWIDPage(BasePage):
    PACKAGE_NAME = "com.bmwgroup.idnext.perso"
    PERSO_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".app.ui.MainActivity"

    # resource-id="com.bmwgroup.idnext.perso:id/item_label"
    # class="android.widget.TextView" package="com.bmwgroup.idnext.perso"
    CHANGE_PROFILE = BasePage.get_element_by_text("Change profile")
    # resource-id="com.bmwgroup.idnext.perso:id/action_label"
    # class="android.widget.TextView" package="com.bmwgroup.idnext.perso"
    CONTINUE_AS_GUEST = BasePage.get_element_by_text("Continue as guest")
    # resource-id="com.bmwgroup.idnext.perso:id/button_title"
    # class="android.widget.TextView" package="com.bmwgroup.idnext.perso"
    OPEN = BasePage.get_element_by_text("Open")
    DRIVER = BasePage.get_element_by_text("Driver")

    LOADING_USER_ID = Element(By.ID, "com.android.systemui:id" + "user_loading")

    # Elements on IDCEvo
    ADD_PROFILE_BTN = 'new UiSelector().resourceId("ItemAddProfileOnList")'
    FOREGROUND_USER_AVATAR = 'new UiSelector().resourceId("AvatarLabelComponent")'
    SYNC_STATUS_TOGGLE = 'new UiSelector().resourceId("change_sync_status")'
    KEY_REC_TAB = 'new UiSelector().resourceId("TextAtom:string/perso_hero_settings_tab_key_recognition")'
    QR_CODE_URL = Element(By.XPATH, "//*[contains(@content-desc, 'https')]")
    KEY_FOB_ICON = 'new UiSelector().resourceId("IconAtom:drawable/idx_icon_id_transmitter")'
    KEY_FOB_SEARCH_SUCCESS = 'new UiSelector().resourceId("TextAtom:string/perso_success_search_key_fob")'
    # No key found.
    KEY_FOB_SEARCH_FAILED = 'new UiSelector().resourceId("TextAtom:string/perso_failed_search_key_fob")'
    # 1/2 key found and clickable=false
    KEY_FOB_SEARCH_LABEL = 'new UiSelector().resourceId("TextAtom:string/perso_subtitle_success_search_key_fob")'
    # 1/2 key linked (contains)
    KEY_FOB_LINKED_LABEL = (
        'new UiSelector().resourceId("TextAtom:string/perso_subtitle_success_search_key_fob_linked")'
    )
    DIGITAL_KEY_ICON = 'new UiSelector().resourceId("IconAtom:drawable/idx_icon_smartphone_smart_watch")'
    DIGITAL_KEY_FOUND = 'new UiSelector().resourceId("DIGITAL_KEY_SUCCESS")'
    PROFILE_GUIDE_TEXT = Element(By.ID, "TextAtom:string/perso_lt_profile_guide")

    # DLT Payloads
    USER_INFO_UPDATED_PAYLOAD_FILTER = re.compile(r"PERSO.*UserInfo.*updated")

    SITLION_USER = "SITLion"

    # KPI Metrics Keys
    ADD_PROTECTIONS_KPI_HAL_IN = "Account Protections Hal Add Key In"
    ADD_PROTECTIONS_KPI_HAL_OUT = "Account Protections Hal Add Key Out"
    ADD_PROTECTIONS_KPI_SRV_IN = "Account Protections Service Add Key In"
    ADD_PROTECTIONS_KPI_SRV_OUT = "Account Protections Service Add Key Out"
    ADD_PROTECTIONS_KPI_APP_IN = "Account Protections App Add Key In"
    ADD_PROTECTIONS_KPI_APP_OUT = "Account Protections App Add Key Out"

    ADD_PROTECTION_DLT_KPI = {
        ADD_PROTECTIONS_KPI_HAL_IN: {
            "pattern": re.compile(r".*#ACCOUNTPROTECTIONS #HAL\[[0-9]+\]\:addProtection"),
            "type": "msg_tmsp",
            "metric": MetricsOutputName.ACCOUNT_PROTECTIONS_ADD_KEY,
            "apid": "ALD",
            "ctid": "LCAT",
        },
        ADD_PROTECTIONS_KPI_HAL_OUT: {
            "pattern": re.compile(
                r".*#ACCOUNTPROTECTIONS #HAL #ACCOUNTPROTECTIONPROVIDER\[[0-9]+\]\:addProtection "
                "- callStatus: 0 statusCode: 255"
            ),
            "type": "msg_tmsp",
            "metric": MetricsOutputName.ACCOUNT_PROTECTIONS_ADD_KEY,
            "apid": "ALD",
            "ctid": "LCAT",
        },
        ADD_PROTECTIONS_KPI_SRV_IN: {
            "pattern": re.compile(
                r".*#ACCOUNTPROTECTIONS #SVC  #AccountProtectionsHalClient\[[0-9]+\]\:addProtection\(\),"
                " protectionType: 2"
            ),
            "type": "msg_tmsp",
            "metric": MetricsOutputName.ACCOUNT_PROTECTIONS_ADD_KEY,
            "apid": "ALD",
            "ctid": "LCAT",
        },
        ADD_PROTECTIONS_KPI_SRV_OUT: {
            "pattern": re.compile(
                r".*#ACCOUNTPROTECTIONS #SVC #AddRemoveProtectionsUseCase\[[0-9]+\]\:addProtection"
                " finished with result: 255"
            ),
            "type": "msg_tmsp",
            "metric": MetricsOutputName.ACCOUNT_PROTECTIONS_ADD_KEY,
            "apid": "ALD",
            "ctid": "LCAT",
        },
        ADD_PROTECTIONS_KPI_APP_IN: {
            "pattern": re.compile(
                r".*#PERSO #APP #EVO #HeroSettingsViewModel\[[0-9]+\]\:onEvent received: AddProtection"
            ),
            "type": "msg_tmsp",
            "metric": MetricsOutputName.ACCOUNT_PROTECTIONS_ADD_KEY,
            "apid": "ALD",
            "ctid": "LCAT",
        },
        ADD_PROTECTIONS_KPI_APP_OUT: {
            "pattern": re.compile(
                r".*#PERSO #APP #EVO #HeroSettingsViewModel\[[0-9]+\]\:toggleKeyFob "
                "executeToggleKeyfobProtectionUseCase Result: AddProtectionSuccessEvent"
            ),
            "type": "msg_tmsp",
            "metric": MetricsOutputName.ACCOUNT_PROTECTIONS_ADD_KEY,
            "apid": "ALD",
            "ctid": "LCAT",
        },
    }

    @classmethod
    def get_element(cls, driver, selector):
        try:
            element = driver.find_element(by=AppiumBy.ANDROID_UIAUTOMATOR, value=selector)
        except NoSuchElementException:
            element = None
        return element

    @property
    def activity_name(self):
        return self.get_activity_name()

    @classmethod
    def check_user(cls, test, account_id):
        """Check if Lion user profile was created"""
        test.setup_driver()
        cls.start_activity()
        time.sleep(5)
        error_msg = ""
        try:
            user_id = test.driver.find_element(
                By.XPATH,
                f"//*[contains(@text,'{cls.SITLION_USER}')]",
            )
            logger.info(f"New user added successfully: {user_id}")
        except NoSuchElementException:
            user_id = None
            try:
                test.driver.find_element(
                    By.XPATH,
                    f"//*[contains(@text,'{account_id}')]",
                )
                logger.info("New user added but without name")
                error_msg = "User created but the name is equal to account ID"
            except NoSuchElementException:
                error_msg = "User not created!"
                logger.info("User not found")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        test.take_apinext_target_screenshot(test.results_dir, f"{timestamp}_check_user")
        return user_id, error_msg

    @classmethod
    def open_settings(cls, test):
        cls.start_activity()
        perso_start = time.time()
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        time.sleep(2)
        test.take_apinext_target_screenshot(test.results_dir, f"{timestamp}_php", DISPLAY_ID)
        timeout_condition = TimeoutCondition(10)
        while timeout_condition:
            avatar_element = cls.get_element(test.driver, cls.FOREGROUND_USER_AVATAR)
            if avatar_element is not None:
                logger.debug(f"avatar_element visible after: '{time.time()-perso_start}' seconds from start activity")
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                test.take_apinext_target_screenshot(test.results_dir, f"{timestamp}_php_with_fg_avatar", DISPLAY_ID)
                break
            time.sleep(1)
        assert_true(avatar_element is not None, "Failed to get avatar_element")

        try:
            avatar_element.click()
            time.sleep(2)
            timestamp = time.strftime("%Y%m%d_%H%M%S")

            test.take_apinext_target_screenshot(test.results_dir, f"{timestamp}_settings_tab", DISPLAY_ID)
        except NoSuchElementException:
            logger.debug("avatar_element not found")

    @classmethod
    def open_key_rec_tab(cls, test):
        key_rec_tab_element = cls.get_element(test.driver, cls.KEY_REC_TAB)
        assert_true(key_rec_tab_element is not None, "Failed to get key_rec_tab")
        try:
            key_rec_tab_element.click()
            time.sleep(5)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            test.take_apinext_target_screenshot(test.results_dir, f"{timestamp}_key_rec_tab", DISPLAY_ID)
        except NoSuchElementException:
            logger.debug("key_rec_tab_element not found")
