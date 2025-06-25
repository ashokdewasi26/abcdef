import logging
import time

import si_test_apinext.util.driver_utils as utils
from appium.webdriver.common.appiumby import AppiumBy
from mtee.testing.tools import TimeoutCondition, TimeoutError, retry_on_except
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element
from si_test_apinext.idc23.pages.android_permissions_page import AndroidPermissionsPage
from si_test_apinext.idc23.pages.launcher_page import LauncherPage
from si_test_apinext.idc23.pages.speech_core_page import SpeechCorePage
from si_test_apinext.util.global_steps import GlobalSteps

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class PersonalAssistantPage(BasePage):
    PACKAGE_NAME = "com.bmwgroup.apinext.ipaapp"
    IPA_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".feature.main.MainActivity"

    PAGE_TITLE = Element(By.ID, IPA_RESOURCE_ID_PREFIX + "statusbar_title")
    DIALOGEXPLANATION = Element(By.ID, IPA_RESOURCE_ID_PREFIX + "dialogExplanation")
    BUTTON_TITLE = Element(By.ID, IPA_RESOURCE_ID_PREFIX + "button_title")
    BUTTON_ICON = Element(By.ID, IPA_RESOURCE_ID_PREFIX + "button_icon")
    OPTION_1 = Element(By.ID, IPA_RESOURCE_ID_PREFIX + "option_1")
    OPTION_2 = Element(By.ID, IPA_RESOURCE_ID_PREFIX + "option_2")
    BUTTON_CONTAINER_HORIZONTAL = Element(By.ID, IPA_RESOURCE_ID_PREFIX + "button_container_horizontal")
    SETTINGS_LANGUAGE = Element(By.ID, IPA_RESOURCE_ID_PREFIX + "settings_language")
    ACTIVATION_BY_VOICE_TOGGLE = Element(By.ID, IPA_RESOURCE_ID_PREFIX + "activation_by_voice_toggle")

    DOWNLOAD_BUTTON = Element(By.XPATH, "//*[contains(@text, 'Download')]")
    CANCEL_BUTTON = Element(By.XPATH, "//*[contains(@text, 'Cancel')]")
    SETTINGS_SUB_PAGE_ID = Element(
        By.XPATH,
        f"//*[contains(@text, 'Settings') and contains(@resource-id, '{IPA_RESOURCE_ID_PREFIX}')]",
    )
    DOWNLOAD_LANGUAGE_PACKAGE = Element(By.XPATH, "//*[@text='Download language package']")
    DOWNLOAD_AGAIN = Element(By.XPATH, "//*[@text='Download again']")
    DOWNLOAD_CANCEL = Element(By.XPATH, "//*[@text='Cancel']")

    PERSONAL_ASSISTANT_APP = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        "new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector()."
        + 'text("Personal Assistant"))',
    )

    dialog_box_to_download_text = (
        "Download a language for your assistant in order to use voice control"
        + " and receive spoken instructions and personalised suggestions in English."
    )

    @classmethod
    def open_personal_assistant(cls):
        """Open Personal Assistant app from all apps menu"""
        LauncherPage.open_all_apps_from_home()
        time.sleep(1)
        # Scroll until Personal Assistant is found
        personal_assist_app = cls.driver.find_element(*cls.PERSONAL_ASSISTANT_APP)
        try:
            GlobalSteps.click_button_and_expect_elem(cls.wb, personal_assist_app, cls.PAGE_TITLE)
        except TimeoutException:
            cls.start_activity()
            cls.check_visibility_of_element(cls.PAGE_TITLE)

    @classmethod
    def open_personal_assistant_settings_submenu(cls):
        """Open Personal Assistant Settings subpage"""
        settings_submenu = cls.check_visibility_of_element(cls.SETTINGS_SUB_PAGE_ID)
        settings_submenu.click()

    @classmethod
    @retry_on_except(retry_count=1)
    def ensure_language_package_installed(cls, total_time_for_setup=360):
        """Ensure Personal Assistant language package is installed

        :param total_time_for_setup: maximum time to wait for language to be downloaded, defaults to 360 seconds
        :type total_time_for_setup: int, optional
        :raises AssertionError: In case a language different than English is found active
        """
        wait_between_status_check = 5  # seconds

        downloaded_lang_active_text = "English (UK) (Active)"
        downloaded_lang_inactive_text = "English (UK) (Inactive)"
        cls.start_activity(validate_activity=False)
        cls.open_personal_assistant_settings_submenu()
        time.sleep(1)

        timeout_condition = TimeoutCondition(total_time_for_setup)
        try:
            while timeout_condition():
                time.sleep(int(wait_between_status_check / 2))
                # if download dialog box option appears click on it to start download
                dialog_box = cls.driver.find_elements(*cls.DIALOGEXPLANATION)
                if dialog_box and dialog_box[0].text == cls.dialog_box_to_download_text:
                    button_container = cls.driver.find_element(*cls.BUTTON_CONTAINER_HORIZONTAL)
                    option_download = button_container.find_element(*cls.OPTION_1)
                    option_download.find_element(*cls.DOWNLOAD_BUTTON)
                    option_download.click()
                    time.sleep(1)
                    continue
                # if download again option appears click on it
                download_again = cls.driver.find_elements(*cls.DOWNLOAD_AGAIN)
                if download_again:
                    download_cancel = cls.driver.find_elements(*cls.DOWNLOAD_CANCEL)
                    download_cancel[0].click()
                    time.sleep(1)
                    continue
                # go to downloaded languages
                ipa_languange_settings = cls.driver.find_elements(*cls.SETTINGS_LANGUAGE)
                if ipa_languange_settings:
                    ipa_languange_settings[0].click()
                    time.sleep(1)
                    continue
                # download language package
                download_languange = cls.driver.find_elements(*cls.DOWNLOAD_LANGUAGE_PACKAGE)
                if download_languange:
                    download_languange[0].click()
                    time.sleep(1)
                    continue
                # check if language is downloaded and assert it's English
                downloaded_languange_settings = cls.driver.find_elements(*SpeechCorePage.DOWNLOADED_LANGUAGE_CONTAINER)
                if downloaded_languange_settings:
                    download_lang_name = downloaded_languange_settings[0].find_elements(*SpeechCorePage.ITEM_LABEL)
                    if (
                        download_lang_name
                        and download_lang_name[0].get_attribute("text") == downloaded_lang_active_text
                    ):
                        logger.debug("English (UK) is the active language for personal assistant")
                        utils.take_apinext_target_screenshot(
                            cls.apinext_target, cls.results_dir, "ensure_language_package_installed"
                        )
                        return
                    elif (
                        download_lang_name
                        and download_lang_name[0].get_attribute("text") == downloaded_lang_inactive_text
                    ):
                        # Continue to next iteration to try to download the language package
                        continue
                    else:
                        raise AssertionError(f"Found an unexpected active language: '{download_lang_name[0].text}'")
                time.sleep(wait_between_status_check)
        except TimeoutError:
            raise TimeoutError(
                f"Unable to ensure the language package is installed in '{total_time_for_setup}'"
                + " seconds. Possibly download failed"
            )

    @classmethod
    @retry_on_except(retry_count=1)
    def ensure_voice_control_active(cls, hmi_helper):
        """Ensure Personal Assistant voice control option is active

        :param hmi_helper: HMIhelper module
        :type hmi_helper: HMIhelper instance
        :raises AssertionError: Raise to retry this method after having the language downloaded
        """
        cls.open_personal_assistant()
        cls.open_personal_assistant_settings_submenu()
        time.sleep(1)
        # if download dialog box option appears click on it to start download
        dialog_box = cls.driver.find_elements(*cls.DIALOGEXPLANATION)
        if dialog_box and dialog_box[0].text == cls.dialog_box_to_download_text:
            button_container = cls.driver.find_element(*cls.BUTTON_CONTAINER_HORIZONTAL)
            option_download = button_container.find_element(*cls.OPTION_2)
            option_download.find_element(*cls.CANCEL_BUTTON)
            option_download.click()
            time.sleep(1)
        active_voice_option = cls.check_visibility_of_element(cls.ACTIVATION_BY_VOICE_TOGGLE)
        if active_voice_option.get_attribute("enabled") != "true":
            cls.ensure_language_package_installed()
            raise AssertionError("Retrying after having language installed")
        active_voice_option.click()
        AndroidPermissionsPage.click_allow_return()
        icon_button = cls.check_visibility_of_element(cls.BUTTON_ICON)
        hmi_helper.ensure_button_status_on(icon_button, "turn_on_voice_activation_assistant")
