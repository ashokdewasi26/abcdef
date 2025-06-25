import logging
import time

import si_test_apinext.util.driver_utils as utils
from appium.webdriver.common.appiumby import AppiumBy
from mtee.testing.tools import TimeoutCondition, TimeoutError
from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import Element
from si_test_apinext.idc23.pages.android_permissions_page import AndroidPermissionsPage
from si_test_apinext.idc23.pages.personal_assistant_page import PersonalAssistantPage
from si_test_apinext.idc23.pages.settings_app_page import SettingsAppPage

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class VoiceControlSettingsPage(PersonalAssistantPage):
    PACKAGE_NAME = "com.bmwgroup.apinext.ipaapp"
    VOICE_CONTROL_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".feature.speechassistant.SpeechAssistantSettingsActivity"

    PAGE_TITLE = Element(By.ID, VOICE_CONTROL_ID_PREFIX + "statusbar_title")
    DIALOGEXPLANATION = Element(By.ID, VOICE_CONTROL_ID_PREFIX + "dialogExplanation")
    BUTTON_TITLE = Element(By.ID, VOICE_CONTROL_ID_PREFIX + "button_title")
    ITEM_LABEL = Element(By.ID, VOICE_CONTROL_ID_PREFIX + "item_label")
    ASSISTANTS_SETUP_RECYCLER_VIEW = Element(By.ID, VOICE_CONTROL_ID_PREFIX + "assistants_setup_recycler_view")
    BMW_TOP_HEADER = Element(By.ID, VOICE_CONTROL_ID_PREFIX + "bmw_top_header")
    BUTTON_START = Element(By.ID, VOICE_CONTROL_ID_PREFIX + "button_start")
    BUTTON_CENTER = Element(By.ID, VOICE_CONTROL_ID_PREFIX + "button_center")
    BUTTON_END = Element(By.ID, VOICE_CONTROL_ID_PREFIX + "button_end")
    SETUP_WIZARD_CONTAINER = Element(By.ID, VOICE_CONTROL_ID_PREFIX + "setup_wizard_container")
    TOGGLE_SWITCH_VIEW = Element(By.ID, VOICE_CONTROL_ID_PREFIX + "toggle_switch_view")
    FIRST_CARD = Element(By.ID, VOICE_CONTROL_ID_PREFIX + "first_card")
    ITEM_BUTTON = Element(By.ID, VOICE_CONTROL_ID_PREFIX + "item_button")

    SETTINGS_SUB_PAGE_ID = Element(
        By.XPATH,
        f"//*[contains(@text, 'Settings') and contains(@resource-id, '{VOICE_CONTROL_ID_PREFIX}')]",
    )
    BMW_PERSONAL_ASSISTANT = Element(By.XPATH, "//*[contains(@text, 'Personal Assistant (BMW)')]")
    CONTINUE_BUTTON = Element(By.XPATH, "//*[contains(@text, 'Continue')]")
    SKIP_BUTTON = Element(By.XPATH, "//*[contains(@text, 'Skip')]")
    CONTINUE_WITH_RESTRICTIONS_BUTTON = Element(By.XPATH, "//*[contains(@text, 'Continue with restrictions')]")
    ALLOW_BUTTON = Element(By.XPATH, "//*[@text='Allow')]")
    HARMONIOUS_BUTTON = Element(By.XPATH, "//*[contains(@text, 'Harmonious')]")
    FINISH_BUTTON = Element(By.XPATH, "//*[contains(@text, 'Finish')]")

    VOICE_CONTROL_OPTION = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        "new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector()."
        + 'text("Voice control"))',
    )

    setup_titles = {
        "01_hello": "Hello!",
        "02_down_lang": "Download language",
        "03_speech_proc": "Online speech processing",
        "04_talk_to_me": "Talk to me",
        "05_appearance": "Appearance",
        "06_data_analysis": "Allow data analysis",
        "07_setup_complete": "Setup completed",
    }

    @classmethod
    def open_voice_assistant(cls):
        """Open Voice assistant menu"""
        SettingsAppPage.launch_settings_activity(validate_activity=False)
        time.sleep(1)
        # Scroll until Voice Control option is found
        voice_control_btn = cls.driver.find_element(*cls.VOICE_CONTROL_OPTION)
        voice_control_btn.click()

    @classmethod
    def get_bmw_personal_assist_status(cls):
        """Get the status of setup regarding BMW voice assistant"""
        # Assert BMW assistant is available
        bmw_personal_assis_elem = cls.driver.find_element(*cls.BMW_PERSONAL_ASSISTANT)
        # Find if BMW assistant shows a setup button
        # if it doesn't means the setup is done
        bmw_personal_assis_elem_bounds = utils.get_elem_bounds_detail(bmw_personal_assis_elem)
        bmw_y_ini = bmw_personal_assis_elem_bounds["y_ini"]
        bmw_y_end = bmw_personal_assis_elem_bounds["y_end"]
        # Check all visible setup buttons
        bmw_assist_setup_button = None
        setup_elem_list = cls.driver.find_elements(*cls.ITEM_BUTTON)
        for setup_elem in setup_elem_list:
            # After several different approaches we defined the best way to check the setup button
            # is to make sure is alongside the bmw personnal assist option
            setup_elem_bounds = utils.get_elem_bounds_detail(setup_elem)
            setup_y_ini = setup_elem_bounds["y_ini"]
            setup_y_end = setup_elem_bounds["y_end"]
            setup_center = (setup_y_ini + setup_y_end) / 2
            if setup_center >= bmw_y_ini and setup_center <= bmw_y_end:
                logger.debug("Found a setup button alongside the bmw personnal assist")
                bmw_assist_setup_button = setup_elem
        # If BMW assistant has a setup button return it, else setup is done
        return bmw_assist_setup_button

    @classmethod
    def setup_voice_assistant(cls, activate_hello_bmw=False, total_time_for_setup=120):
        """Perform the several steps required to have the setup of voice assistant done

        :param activate_hello_bmw: flag to activate 'hello BMW' feature, defaults to False
        :type activate_hello_bmw: bool, optional
        :param total_time_for_setup: maximum to wait for setup to be complete, defaults to 120 seconds
        :type total_time_for_setup: int, optional
        :return: True if setup is correctly done, False otherwise
        :rtype: bool
        """

        cls.open_voice_assistant()
        setup_button = cls.get_bmw_personal_assist_status()
        if setup_button:
            setup_button.click()
        else:
            logger.debug("Setup is already done")
            return True

        timeout_condition = TimeoutCondition(total_time_for_setup)
        try:
            while timeout_condition():
                time.sleep(1)
                top_header_elem = cls.check_visibility_of_element(cls.BMW_TOP_HEADER)
                top_header_label = top_header_elem.find_element(*cls.ITEM_LABEL)
                if top_header_label.text in cls.setup_titles["01_hello"]:
                    button_continue = cls.driver.find_element(*cls.CONTINUE_BUTTON)
                    button_continue.click()
                    time.sleep(1)
                elif top_header_label.text in cls.setup_titles["02_down_lang"]:
                    button_continue = cls.driver.find_element(*cls.CONTINUE_BUTTON)
                    button_continue.click()
                    time.sleep(1)
                elif top_header_label.text in cls.setup_titles["03_speech_proc"]:
                    button_skip = cls.driver.find_element(*cls.SKIP_BUTTON)
                    button_skip.click()
                    time.sleep(2)
                    # click on pop up to continue
                    cls.check_visibility_of_element(cls.DIALOGEXPLANATION)
                    cls.driver.find_element(*cls.CONTINUE_WITH_RESTRICTIONS_BUTTON).click()
                    time.sleep(1)
                elif top_header_label.text in cls.setup_titles["04_talk_to_me"]:
                    if activate_hello_bmw:
                        button_center_elem = cls.driver.find_element(*cls.SETUP_WIZARD_CONTAINER)
                        toggle_switch_view = button_center_elem.find_element(*cls.TOGGLE_SWITCH_VIEW)
                        toggle_switch_view.click()
                        time.sleep(1)
                        AndroidPermissionsPage.click_first_item()
                    button_continue = cls.driver.find_element(*cls.CONTINUE_BUTTON)
                    button_continue.click()
                elif top_header_label.text in cls.setup_titles["05_appearance"]:
                    first_card_elem = cls.driver.find_element(*cls.FIRST_CARD)
                    first_card_elem.find_element(*cls.HARMONIOUS_BUTTON)
                    first_card_elem.click()
                    time.sleep(1)
                    button_continue = cls.driver.find_element(*cls.CONTINUE_BUTTON)
                    button_continue.click()
                    time.sleep(1)
                elif top_header_label.text in cls.setup_titles["06_data_analysis"]:
                    button_skip = cls.driver.find_element(*cls.SKIP_BUTTON)
                    button_skip.click()
                    time.sleep(1)
                elif top_header_label.text in cls.setup_titles["07_setup_complete"]:
                    button_finish = cls.driver.find_element(*cls.FINISH_BUTTON)
                    button_finish.click()
                    time.sleep(1)
                    setup_button = cls.get_bmw_personal_assist_status()
                    # assert no setup button is visible, meaning setup is done
                    assert setup_button is None
                    utils.take_apinext_target_screenshot(
                        cls.apinext_target, cls.results_dir, "setup_voice_assistant_success"
                    )
                    return True
                else:
                    logger.error(f"Found unexpected page title: '{top_header_label.text}'")
                    raise AssertionError("Stopping setup_voice_assistant() after getting into an unexpected page")
        except TimeoutError:
            logger.error("TimeoutError in setup_voice_assistant")
            return False
