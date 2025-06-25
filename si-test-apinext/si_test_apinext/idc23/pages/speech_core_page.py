import logging
import time

import si_test_apinext.util.driver_utils as utils
from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class SpeechCorePage(BasePage):
    PACKAGE_NAME = "com.bmwgroup.idnext.speech.core"
    SPEECH_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".MainActivity"
    SETTINGS_ACTIVITY = ".ui.settings.SettingsSpeechActivity"

    PAGE_TITLE = Element(By.ID, SPEECH_RESOURCE_ID_PREFIX + "statusbar_title")

    DOWNLOADED_LANGUAGE_CONTAINER = Element(By.ID, SPEECH_RESOURCE_ID_PREFIX + "downloadedLanguageContainer")
    ITEM_LABEL = Element(By.ID, SPEECH_RESOURCE_ID_PREFIX + "item_label")
    BTN_DEBUG_MENU = Element(By.ID, SPEECH_RESOURCE_ID_PREFIX + "btnDebugMenu")
    CHECK_INTEGRITY_BUTTON = Element(By.ID, SPEECH_RESOURCE_ID_PREFIX + "check_integrity_button")
    VOICE_ASSISTANT_INITIALIZATION_STATUS = Element(
        By.ID, SPEECH_RESOURCE_ID_PREFIX + "voiceAssistantInitializationStatus"
    )
    voice_assis_status_expected_text = "Status of BMW Voice Assistant: Initialized"

    @classmethod
    def start_speech_settings(cls):
        """Call start activity-single-top on the target for the SettingsSpeechActivity to bring it to the foreground"""
        try:
            cls.apinext_target.execute_adb_command(
                ["shell", f"am start --activity-single-top {cls.PACKAGE_NAME}/{cls.SETTINGS_ACTIVITY}"]
            )
            time.sleep(0.5)
        except Exception as e:
            logger.debug(
                f"Got this error while trying to 'start --activity-single-top' in start_speech_settings(): '{e}'"
            )
        try:
            cls.start_activity()
            time.sleep(0.5)
        except Exception as e:
            logger.debug(f"Got this error while trying to start_activity in start_speech_settings() : '{e}'")

    @classmethod
    def check_assistant_status(cls):
        """Check BMW voice assistant integrity status"""
        voice_assist_status = cls.go_to_assistant_status_page()
        if voice_assist_status.text != cls.voice_assis_status_expected_text:
            logger.error(
                "Status of BMW Voice Assistant is not Initialized as expected."
                + f" Instead got: '{voice_assist_status.text}'"
            )
        utils.take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, "bmw_voice_assist_status")

    @classmethod
    def go_to_assistant_status_page(cls):
        """Go to BMW voice assistant integrity status page"""
        cls.start_speech_settings()
        voice_assist_status = cls.driver.find_elements(*cls.VOICE_ASSISTANT_INITIALIZATION_STATUS)
        if voice_assist_status:
            return voice_assist_status[0]
        else:
            debug_btn = cls.check_visibility_of_element(cls.BTN_DEBUG_MENU)
            debug_btn.click()
            check_integrity_btn = cls.check_visibility_of_element(cls.CHECK_INTEGRITY_BUTTON)
            check_integrity_btn.click()
            voice_assist_status = cls.check_visibility_of_element(cls.VOICE_ASSISTANT_INITIALIZATION_STATUS)
            return voice_assist_status
