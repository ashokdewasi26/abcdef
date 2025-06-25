import os
import time

import si_test_apinext.util.driver_utils as utils
from mtee.testing.tools import retry_on_except
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.common.pages.base_page import BasePage, Element
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.util.driver_utils import take_apinext_target_screenshot
from si_test_apinext.util.global_steps import GlobalSteps


class MediaPage(BasePage):
    PACKAGE_NAME = "com.bmwgroup.apinext.mediaapp"
    PACKAGE_ACTIVITY = ".player.MediaActivity"

    # Media app
    MEDIA_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    MEDIA_BAR_ID = Element(By.ID, MEDIA_RESOURCE_ID_PREFIX + "action_bar_root")
    AUDIO_RECONNECT_BUTTON_ID = Element(By.ID, MEDIA_RESOURCE_ID_PREFIX + "reconnect_button")
    MEDIA_SOURCE_LIST_ID = Element(By.ID, MEDIA_RESOURCE_ID_PREFIX + "sources_list")
    MEDIA_SOURCE_ITEM_ID = Element(By.ID, MEDIA_RESOURCE_ID_PREFIX + "focusable_item")
    MEDIA_BROWSE_LIST_ID = Element(By.ID, MEDIA_RESOURCE_ID_PREFIX + "browse_list")
    MEDIA_BROWSE_ITEM_ID = Element(By.ID, MEDIA_RESOURCE_ID_PREFIX + "item")
    MEDIA_BROWSE_ITEM_LABEL_ID = Element(By.ID, MEDIA_RESOURCE_ID_PREFIX + "item_label")
    MEDIA_PARTICLE_LABEL_ID = Element(By.ID, MEDIA_RESOURCE_ID_PREFIX + "line3_particle")
    MEDIA_SOURCE_NAME_ID = Element(By.ID, MEDIA_RESOURCE_ID_PREFIX + "source_name")
    MEDIA_USB_SOURCE_ID = Element(
        By.XPATH,
        "//*[contains(@text, 'TOSHIBA') or contains(@text, 'Toshiba') or contains(@text, 'INTENSO')"
        " or contains(@text, 'Intenso') or contains(@text, 'USB')]",
    )
    MEDIA_RADIO_SOURCE_ID = Element(By.XPATH, "//*[contains(@text, 'Radio')]")
    MEDIA_BLUETOOTH_SOURCE_ID = Element(By.XPATH, "//*[contains(@text, 'SITests') or contains(@text, 'SITESTS')]")
    MEDIA_SOURCE_SELECTOR_ID = Element(By.ID, MEDIA_RESOURCE_ID_PREFIX + "button_container")
    AUDIO_SETTINGS_BUTTON_ID = Element(By.XPATH, "//*[@text='Sound']")
    MEDIA_SUBMENU_BACK_ARROW = Element(By.ID, MEDIA_RESOURCE_ID_PREFIX + "back_arrow")
    MEDIA_RADIO_TUNER_WIDGET_ID = Element(By.ID, MEDIA_RESOURCE_ID_PREFIX + "line3_with_primary_icon")
    MEDIA_RADIO_TUNER_MANUAL_FREQ = Element(By.XPATH, "//android.widget.ImageView[@content-desc='Manual frequency']")
    MEDIA_RADIO_TUNER_CLOSE_SUBMENU = Element(By.ID, MEDIA_RESOURCE_ID_PREFIX + "side_navigation_back_arrow")

    RADIO_TUNER_RESOURCE_ID_PREFIX = "com.bmwgroup.apinext.tunermediaservice:id/"
    MEDIA_RADIO_TUNER_SEARCH_FREQ_BACK = Element(By.ID, RADIO_TUNER_RESOURCE_ID_PREFIX + "skip_back_button")
    MEDIA_RADIO_TUNER_GO_BACK_SUBMENU = Element(By.ID, RADIO_TUNER_RESOURCE_ID_PREFIX + "back_arrow_no_navigation")

    media_vhal_event_keycode = 1008

    @classmethod
    @retry_on_except(exception_class=TimeoutException, retry_count=4, backoff_time=2, silent_fail=False)
    def open_media(cls):
        """
        Open the media option on IDC and reconnect the media if reconnect option appears
        """
        # If media is already opened, then we dont need to re-open it
        media_bar = cls.driver.find_elements(*cls.MEDIA_BAR_ID)
        if media_bar:
            return

        try:
            GlobalSteps.inject_custom_vhal_input(cls.apinext_target, cls.media_vhal_event_keycode)
            cls.wb.until(
                ec.visibility_of_element_located(cls.MEDIA_BAR_ID),
                message=f"Unable to find media element:'{cls.MEDIA_BAR_ID.selector}' after tapping on MEDIA button",
            )
            if cls.driver.find_elements(*cls.AUDIO_RECONNECT_BUTTON_ID):
                reconnect_media = cls.wb.until(
                    ec.visibility_of_element_located(cls.AUDIO_RECONNECT_BUTTON_ID),
                    message=f"Unable to find {cls.AUDIO_RECONNECT_BUTTON_ID.selector} element on All Apps search",
                )
                GlobalSteps.click_button_and_not_expect_elem(cls.wb, reconnect_media, cls.AUDIO_RECONNECT_BUTTON_ID)
        except TimeoutException:
            # Most likely alert pop-up is shown up, it is worthwhile to try again after closing alerts
            utils.ensure_no_alert_popup(cls.results_dir, cls.driver, cls.apinext_target)
            utils.ensure_no_traffic_info(cls.results_dir, cls.driver, cls.apinext_target)
            raise

    @classmethod
    def reconnect_media(cls):
        """
        Reconnecting media if reconnect popup appears in media screen
        """
        Launcher.go_to_home()
        cls.open_media()
        Launcher.go_to_home()

    @classmethod
    def get_sources_list(cls):
        # TODO commented as workaround. To be uncommented in future updates.
        # sources_list = cls.wb.until(
        #     ec.visibility_of_element_located(cls.MEDIA_SOURCE_LIST_ID),
        #     f"Error while validating visibility of {cls.MEDIA_SOURCE_LIST_ID.selector}",
        # )
        # return sources_list.find_elements(*cls.MEDIA_SOURCE_ITEM_ID)

        # Workaround to manually get the media sources
        sources_list = []

        sources_list += cls.driver.find_elements(*cls.MEDIA_RADIO_SOURCE_ID)
        sources_list += cls.driver.find_elements(*cls.MEDIA_USB_SOURCE_ID)
        return sources_list

    @classmethod
    def get_browse_list(cls):
        browse_list = cls.wb.until(
            ec.visibility_of_element_located(cls.MEDIA_BROWSE_LIST_ID),
            f"Error while validating visibility of {cls.MEDIA_BROWSE_LIST_ID.selector}",
        )
        return browse_list.find_elements(*cls.MEDIA_BROWSE_ITEM_LABEL_ID)

    @classmethod
    def go_back_from_submenu(cls):
        """
        Try to click on back arrow button if it's present
        """
        back_arrow = cls.driver.find_elements(*cls.MEDIA_SUBMENU_BACK_ARROW)
        if back_arrow:
            back_arrow[0].click()
            time.sleep(1)

    @classmethod
    def get_current_media_source(cls):
        """
        Find the currently selected media source
        """
        source_name = cls.driver.find_elements(*cls.MEDIA_SOURCE_NAME_ID)
        if source_name:
            return source_name[0].get_attribute("text").strip()

    @classmethod
    @retry_on_except(exception_class=TimeoutException, retry_count=2, backoff_time=2, silent_fail=False)
    def select_audio_source(cls, source_id):
        """
        Select the expected source from the media source list
        :param source_id: MEDIA_USB_SOURCE_ID, MEDIA_RADIO_SOURCE_ID, or MEDIA_BLUETOOTH_SOURCE_ID
        """
        # Open source list
        media_source_button = cls.driver.find_element(*cls.MEDIA_SOURCE_SELECTOR_ID)
        GlobalSteps.click_button_and_expect_elem(cls.wb, media_source_button, cls.AUDIO_SETTINGS_BUTTON_ID)
        take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, "Open_audio_sources.png")
        # Select the given source
        source = cls.driver.find_elements(*source_id)
        if source:
            source[0].click()
            time.sleep(1)
            take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, "Select_audio_source.png")
        else:
            fail_source_screenshot = os.path.join(cls.results_dir, "No_expected_audio_source.png")
            take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, fail_source_screenshot)
            raise RuntimeError(f"Failed to find expected audio source in {fail_source_screenshot}")

    @classmethod
    def is_playing_source(cls, source_text):
        """Check if the expected source is played"""
        source = cls.driver.find_element(*cls.MEDIA_SOURCE_NAME_ID)
        if source:
            if source_text.lower() not in source.text.lower():
                cls.apinext_target.take_screenshot(os.path.join(cls.results_dir, f"Not_playing_{source_text}.png"))
                return False
            return True
        else:
            screenshot = os.path.join(cls.results_dir, "No_media_source.png")
            cls.apinext_target.take_screenshot(screenshot)
            raise RuntimeError(f"Failed to find media source in {screenshot}")

    @classmethod
    @retry_on_except(retry_count=2)
    def get_source_list_from_media(cls):
        """
        Navigates through the UI with appium to Media app and get list of sources

        :return: list with available sources
        :rtype: list of appium webdriver elements
        """
        Launcher.go_to_home()
        # Press media button
        cls.open_media()
        time.sleep(1)
        # Open the audio source selector
        media_source_button = cls.driver.find_elements(*cls.MEDIA_SOURCE_SELECTOR_ID)
        if media_source_button:
            GlobalSteps.click_button_and_expect_elem(cls.wb, media_source_button[0], cls.AUDIO_SETTINGS_BUTTON_ID)
        # Get all input sources available
        sources_list = cls.get_sources_list()
        return sources_list

    @classmethod
    def select_fm_tuner_source(cls):
        """Got to source list and select FM tuner as source
        :raises RuntimeError: if no Radio source is found
        """
        radio_source = []
        sources_list = cls.get_source_list_from_media()
        for source in sources_list:
            radio_source += source.find_elements(*cls.MEDIA_RADIO_SOURCE_ID)

        if len(radio_source) >= 1:
            for element in radio_source:
                if element.text.splitlines()[0].lower() == "radio":
                    radio_source = element
        else:
            raise RuntimeError("Unexpectedly found none Radio source")
        radio_source.click()
        time.sleep(1)

    @classmethod
    def validate_usb_source(cls):
        """
        Got to source list and check USB source is visible
        :raises RuntimeError: if no USB source is found
        """
        sources_list = cls.get_sources_list()
        usb_source = []
        for source in sources_list:
            usb_source += source.find_elements(*cls.MEDIA_USB_SOURCE_ID)

        if len(usb_source) >= 1:
            usb_source = usb_source[0]
        else:
            raise RuntimeError("Unexpectedly found none USB source")
        return usb_source
