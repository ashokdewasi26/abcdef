import logging
from nose import SkipTest
import re
import time

from appium.webdriver.common.appiumby import AppiumBy
from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import metadata, TimeoutError
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.mini.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.mini.pages.settings_app_page import SettingsAppPage as Settings
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.mtee_utils import MteeUtils

logger = logging.getLogger(__name__)


@metadata(testsuite=["SI"])
class TestLanguageSettings:
    test = None
    failed_languages = set()
    validated_languages = []

    languages_id_dict = {
        "en-GB": "English UK",
        "cs": "Czech",
        "da": "Danish",
        "de": "Deutsch",
        "el": "Greek",
        "es": "Español",
        "fr": "Français",
        "it": "Italiano",
        "zh-CN": "Simple Chinese",
        "hu": "Hungarian",
        "nl": "Dutch",
        "nb": "Norwegian",
        "pl": "Polish",
        "pt": "Portuguese",
        "ro": "Română",
        "ru": "Русский",
        "sk": "Slovenian",
        "sl": "Slovakian",
        "fi": "Finnish",
        "sv": "Swedish",
        "tr": "Turkish",
        "uk": "Ukrainian",
    }

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.mtee_util = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        if not Launcher.validate_launcher():
            # Try to recover Launcher
            cls.test.teardown_base_class()
            cls.test.apinext_target.restart()
            cls.test.setup_base_class()
        # As the very fist language transition to be checked is English,
        # we are changing to German first to test the switch.
        cls.mtee_util.change_language("de")
        utils.start_recording(cls.test)

    @classmethod
    def teardown_class(cls):
        Launcher.go_to_home()
        cls.mtee_util.change_language("en_GB")
        utils.stop_recording(cls.test, "Language_test")
        cls.test.quit_driver()

    def __check_all_language(self, language_dict):
        """
        Go through the list of all the languages shown on the menu, and try each one,
        if success add to list of success, otherwise add to list of fail
        :param language_dict language dictionary with ID

        """
        found_lang = []

        # This is used to loop over the language and scroll through it N number of times
        for _ in range(4):
            language_buttons_list = self.get_language_list(Settings.LANGUAGE_ITEM)
            for each_lang in language_buttons_list[:-1]:
                if each_lang not in found_lang:
                    found_lang.append(each_lang)
                    self.__check_available_languages_list(each_lang, language_dict)

            # scrollForward (moves exactly one view)
            # TODO: implement a utility file for all possible actions by android_uiautomator - ABPI-225948
            self.test.driver.find_element(
                AppiumBy.ANDROID_UIAUTOMATOR, "new UiScrollable(new UiSelector().scrollable(true)).scrollForward()"
            )
        # Validate the last language after scrolling to the end
        last_language = self.get_language_list(Settings.LANGUAGE_ITEM)[-1]
        self.__check_available_languages_list(last_language, language_dict)

    def __check_available_languages_list(self, language_button, language_dict):
        """
        check all the available language are clickable from the list
        :param language_button radio button of language available in the page
        :param language_dict language dictionary with ID
        """
        if language_button.find_element(*Settings.RADIO_BUTTON_ITEM).get_attribute("checked") != "true":
            language_dlt = re.compile(r"LANGUAGE_JAVA_SERVICE\[\d+\]: Set vehicle's language to ?: ([a-z]*-?[A-Z]*),?")
            self.test.wb.until(ec.visibility_of(language_button))
            language_name = language_button.find_element(*Settings.ITEM_LABEL_ID).get_attribute("text")
            logger.info(f"Current language name: {language_name}")
            with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as dlt_detector:
                language_button.click()
                time.sleep(1)
                try:
                    messages = dlt_detector.wait_for(
                        {"apid": "ALD", "ctid": "LCAT", "payload_decoded": language_dlt}, regexp=True
                    )
                    for message in messages:
                        match = language_dlt.search(message.payload_decoded)
                        if match:
                            logger.info(f"Found Language id: {(match.group(1))}")
                            language_id = match.group(1)
                            if language_id in language_dict:
                                if language_dict[language_id] not in self.validated_languages:
                                    self.validated_languages.append(language_dict[language_id])
                            else:
                                self.failed_languages.add(
                                    f"Unknown language-id: {language_id}, language: {language_name}"
                                )
                except TimeoutError:
                    self.failed_languages.add(f"Unable to switch to {language_name}")
                    utils.get_screenshot_and_dump(
                        self.test, self.test.results_dir, f"Unable_to_switch_to_{language_name}"
                    )
                time.sleep(3)
                self.close_popup()
                return True

    def get_language_list(self, search_elem):
        """
        used to get all the language list (radiobutton list)
        """
        language_button_element = self.test.wb.until(
            ec.visibility_of_element_located(Settings.LANGUAGE_RADIO_BUTTON_GROUP_ID),
            f"Error while validating visibility of {Settings.LANGUAGE_RADIO_BUTTON_GROUP_ID.selector}",
        )
        language_list = language_button_element.find_elements(*search_elem)
        return language_list

    def close_popup(self):
        """
        Close popups to download language to enable speech
        """
        language_popup = self.test.driver.find_elements(*Launcher.LANGUAGE_POPUP_ID)
        if language_popup:
            close_popup = self.test.driver.find_element(*Launcher.LANGUAGE_POPUP_CLOSE_ID)
            close_popup.click()
            time.sleep(3)

    @utils.gather_info_on_fail
    def test_000_check_and_click_lngbtn(self):
        """
        Validate all languages through dlt messages

        * background info*
        This test scrolls the list of available languages and clicks on each of the languages
        validating the change through dlt messages

        *steps*
        1.Open settings select language settings
        2.Go through the list of all the languages shown on the menu, and try each one,
        3.Validate dlt pattern "LANGUAGE_JAVA_SERVICE[5212]: Set vehicle's language to: en-GB"
        4.If success add to list of success, otherwise add to list of fail

        """
        if self.test.branch_name in ("pu2311", "pu2403"):
            raise SkipTest("SW defect. Won't be fixed on PU2311 and PU2403 -- HU22DM-203600, HU22DM-205043.")
        Launcher.go_to_home()
        Settings.launch_settings_activity()
        Settings.check_presence_of_element_located(Settings.STATUSBAR_TITLE)
        # Scroll until Language menu is found
        language_button = self.test.driver.find_element(*Settings.LANGUAGE_BUTTON_ID)
        language_button.click()
        self.__check_all_language(self.languages_id_dict)
        logger.info(f"Successfully evaluated languages are: {self.validated_languages}")
        # Go back from submenu language
        Settings.try_back_arrow_click()
        assert not self.failed_languages, f"failed languages to check {self.failed_languages}"
