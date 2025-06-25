# Copyright (C) 2024-2025. BMW Group. All rights reserved.
import logging
import time

from appium.webdriver.common.appiumby import AppiumBy
from mtee.testing.connectors.connector_dlt import DLTContext
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.apinext_target_handlers import LIST_MAIN_DISPLAY_ID
from si_test_idcevo.si_test_helpers.dlt_helpers import check_dlt_trace
from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage, Element

DISPLAY_ID = LIST_MAIN_DISPLAY_ID["idcevo"]

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class AudioSettingsPage(BasePage):
    PACKAGE_NAME = "com.bmwgroup.apinext.audiosettingsapp"
    PERSO_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".ui.MainActivity"

    # DLT Payloads
    AUDIO_DLT_FILTERS = [("ALD", "LCAT")]

    # Elements on IDCEvo
    CLOSE_POPUP_BTN = Element(
        By.ID,
        "IconAtom:drawable/idx_icon_erase",
    )
    # Sound tab
    EQUALIZER_BTN = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        'new UiSelector().resourceId("TextAtom:string/equalizer_bt")',
    )

    BAL_FADER_BTN = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        'new UiSelector().resourceId("IconAtom:drawable/idx_icon_balance_fader")',
    )

    SPEED_VOL_BTN = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        'new UiSelector().resourceId("TextAtom:string/speed_volume_bt")',
    )

    NORMALIZED_VOL_BTN = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        'new UiSelector().resourceId("TextAtom:string/normalized_volume_bt")',
    )

    # Equalizer Pop-Up
    EQUALIZER_TEXT = Element(
        By.ID,
        "TextAtom:string/equalizer_popup_ti",
    )
    BASS_TEXT = Element(
        By.ID,
        "TextAtom:string/bass_band_popup_lb",
    )
    BASS_MINUS_BTN = Element(
        AppiumBy.XPATH,
        '(//android.view.View[@resource-id="UiLib:ListSliderComponent.ButtonDecrease"])[1]/android.view.View[1]',
    )
    BASS_PLUS_BTN = Element(
        AppiumBy.XPATH,
        '(//android.view.View[@resource-id="UiLib:ListSliderComponent.ButtonIncrease"])[1]/android.view.View[1]',
    )
    TREBLE_TEXT = Element(
        By.ID,
        "TextAtom:string/bass_band_popup_lb",
    )
    TREBLE_MINUS_BTN = Element(
        AppiumBy.XPATH,
        '(//android.view.View[@resource-id="UiLib:ListSliderComponent.ButtonDecrease"])[2]/android.view.View[1]',
    )
    TREBLE_PLUS_BTN = Element(
        AppiumBy.XPATH,
        '(//android.view.View[@resource-id="UiLib:ListSliderComponent.ButtonIncrease"])[2]/android.view.View[1]',
    )

    # Balance and Fader Pop-up
    BAL_FADER_TEXT = Element(
        By.ID,
        "TextAtom:string/balance_fader_popup_ti",
    )
    BALANCE_TEXT = Element(
        By.ID,
        "TextAtom:string/balance_popup_lb",
    )
    BAL_MINUS_BTN = Element(
        AppiumBy.XPATH,
        '(//android.view.View[@resource-id="UiLib:ListSliderComponent.ButtonDecrease"])[1]/android.widget.Button',
    )
    BAL_PLUS_BTN = Element(
        AppiumBy.XPATH,
        '(//android.view.View[@resource-id="UiLib:ListSliderComponent.ButtonIncrease"])[1]/android.widget.Button',
    )
    FADER_TEXT = Element(
        By.ID,
        "TextAtom:string/fader_popup_lb",
    )
    FAD_MINUS_BTN = Element(
        AppiumBy.XPATH,
        '(//android.view.View[@resource-id="UiLib:ListSliderComponent.ButtonDecrease"])[2]/android.widget.Button',
    )
    FAD_PLUS_BTN = Element(
        AppiumBy.XPATH,
        '(//android.view.View[@resource-id="UiLib:ListSliderComponent.ButtonIncrease"])[2]/android.widget.Button',
    )

    # Speed Volume Pop-Up
    SPEED_VOL_TEXT = Element(
        By.ID,
        "TextAtom:string/speed_volume_ti",
    )

    SPEED_VOL_HIGH_BTN = Element(
        AppiumBy.XPATH,
        '(//android.view.View[@resource-id="UiLib:ListComponent"])[3]',
    )

    @classmethod
    def close_popup(cls):
        try:
            close_element = cls.wait_to_check_visible_element(cls.CLOSE_POPUP_BTN)
            close_element.click()
            time.sleep(2)
            element_clicked = True
        except NoSuchElementException:
            logger.debug("'X' to close not found")
            element_clicked = False
        return element_clicked

    @classmethod
    def open_equalizer(cls):
        element_clicked = False
        try:
            equalizer_element = cls.wait_to_check_visible_element(cls.EQUALIZER_BTN)
            equalizer_element.click()
            time.sleep(2)
            # Confirm pop-up Text appears:
            cls.wait_to_check_visible_element(cls.EQUALIZER_TEXT)
            cls.wait_to_check_visible_element(cls.BASS_TEXT)
            cls.wait_to_check_visible_element(cls.TREBLE_TEXT)
            element_clicked = True
        except NoSuchElementException:
            logger.debug("equalizer_element not found")
        return element_clicked

    @classmethod
    def change_bass(cls):
        element_clicked = False
        try:
            bass_minus_element = cls.wait_to_check_visible_element(cls.BASS_MINUS_BTN)
            test = TestBase.get_instance()
            with DLTContext(test.mtee_target.connectors.dlt.broker, filters=cls.AUDIO_DLT_FILTERS) as trace:
                bass_minus_element.click()
                time.sleep(1)
                bass_change_msg = check_dlt_trace(trace, rgx=r"AudioControllerHal.*setParameters.*bass=-1")
                if not bass_change_msg:
                    logger.debug("Failed to find Bass Value Change in HAL")
                else:
                    element_clicked = True
        except NoSuchElementException:
            logger.debug("bass_minus_element not found")
        return element_clicked

    @classmethod
    def change_treble(cls):
        element_clicked = False
        try:
            test = TestBase.get_instance()
            with DLTContext(test.mtee_target.connectors.dlt.broker, filters=cls.AUDIO_DLT_FILTERS) as trace:
                cls.wait_to_check_visible_element(cls.TREBLE_PLUS_BTN).click()
                time.sleep(1)
                cls.wait_to_check_visible_element(cls.TREBLE_PLUS_BTN).click()
                time.sleep(1)
                cls.wait_to_check_visible_element(cls.TREBLE_PLUS_BTN).click()
                time.sleep(1)
                treble_change_msg = check_dlt_trace(trace, rgx=r"AudioControllerHal.*setParameters.*treble=3")
                if not treble_change_msg:
                    logger.debug("Failed to find Treble Value Change in HAL")
                else:
                    element_clicked = True
        except NoSuchElementException:
            logger.debug("treble_plus_element not found")
        return element_clicked

    @classmethod
    def open_balance_fader(cls):
        element_clicked = False
        try:
            time.sleep(1)
            bal_fader_element = cls.wait_to_check_visible_element(cls.BAL_FADER_BTN)
            bal_fader_element.click()
            time.sleep(2)
            # Confirm pop-up Text appears:
            if (
                cls.wait_to_check_visible_element(cls.BAL_FADER_TEXT)
                and cls.wait_to_check_visible_element(cls.BALANCE_TEXT)
                and cls.wait_to_check_visible_element(cls.FADER_TEXT)
            ):
                element_clicked = True
        except NoSuchElementException:
            logger.debug("bal_fader_element not found")
        return element_clicked

    @classmethod
    def change_balance(cls):
        element_clicked = False
        try:
            test = TestBase.get_instance()
            with DLTContext(test.mtee_target.connectors.dlt.broker, filters=cls.AUDIO_DLT_FILTERS) as trace:
                cls.wait_to_check_visible_element(cls.BAL_MINUS_BTN).click()
                time.sleep(1)
                cls.wait_to_check_visible_element(cls.BAL_MINUS_BTN).click()
                time.sleep(1)
                bass_change_msg = check_dlt_trace(trace, rgx=r"AudioControllerHal.*setParameters.*balance=-2")
                if not bass_change_msg:
                    logger.debug("Failed to find Balance Value Change in HAL")
                else:
                    element_clicked = True
        except NoSuchElementException:
            logger.debug("bal_minus_element not found")
        return element_clicked

    @classmethod
    def change_fader(cls):
        element_clicked = False
        try:
            test = TestBase.get_instance()
            with DLTContext(test.mtee_target.connectors.dlt.broker, filters=cls.AUDIO_DLT_FILTERS) as trace:
                cls.wait_to_check_visible_element(cls.FAD_PLUS_BTN).click()
                time.sleep(1)
                cls.wait_to_check_visible_element(cls.FAD_PLUS_BTN).click()
                time.sleep(1)
                treble_change_msg = check_dlt_trace(trace, rgx=r"AudioControllerHal.*setParameters.*fader=2")
                if not treble_change_msg:
                    logger.debug("Failed to find Fader Value Change in HAL")
                else:
                    element_clicked = True
        except NoSuchElementException:
            logger.debug("fader_plus_element not found")
        return element_clicked

    @classmethod
    def open_speed_volume(cls):
        element_clicked = False
        try:
            speed_volume_element = cls.wait_to_check_visible_element(cls.SPEED_VOL_BTN)
            speed_volume_element.click()
            time.sleep(2)
            # Confirm pop-up Text appears:
            cls.wait_to_check_visible_element(cls.SPEED_VOL_TEXT)
            element_clicked = True
        except NoSuchElementException:
            logger.debug("speed_volume_element not found")
        return element_clicked

    @classmethod
    def change_speed_volume(cls):
        element_clicked = False
        try:
            speed_high_element = cls.wait_to_check_visible_element(cls.SPEED_VOL_HIGH_BTN)
            test = TestBase.get_instance()
            with DLTContext(test.mtee_target.connectors.dlt.broker, filters=cls.AUDIO_DLT_FILTERS) as trace:
                speed_high_element.click()
                time.sleep(1)
                speed_change_msg = check_dlt_trace(trace, rgx=r"AudioControllerHal.*setParameters.*dfk_sensitivity=2")
                if not speed_change_msg:
                    logger.debug("Failed to find Speed Volume Value Change in HAL")
                else:
                    element_clicked = True
        except NoSuchElementException:
            logger.debug("speed_high_element not found")
        return element_clicked

    @classmethod
    def toggle_volume_normalization(cls):
        element_clicked = False
        try:
            normalization_element = cls.wait_to_check_visible_element(cls.NORMALIZED_VOL_BTN)
            test = TestBase.get_instance()
            with DLTContext(test.mtee_target.connectors.dlt.broker, filters=cls.AUDIO_DLT_FILTERS) as trace:
                normalization_element.click()
                time.sleep(1)
                normalization_change_msg = check_dlt_trace(
                    trace, rgx=r"AudioControllerHal.*setParameters.*dynamic_volume_adjust=false"
                )
                if not normalization_change_msg:
                    logger.debug("Failed to find Volume normalization Change in HAL")
                else:
                    element_clicked = True
        except NoSuchElementException:
            logger.debug("normalization_element not found")
        return element_clicked

    @property
    def activity_name(self):
        return self.get_activity_name()
