import logging

from selenium.webdriver.common.by import By
from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage, Element

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class UpdateCenterPage(BasePage):
    COMMON_NAME = "UpdateCenter"
    PACKAGE_NAME = "com.bmwgroup.apinext.updatecenter"
    SPEECH_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = None  # ".MainActivity"  # to be confirmed

    # Look for domain identifier in the AndroidManifest.xml file
    DOMAIN_IDENTIFIER = "software"
    # Search for the action and category in the intent-filter
    ACTION_ACTIVITY = "com.bmwgroup.idnext.action.CAR_DOMAIN"

    RSU_TITLE = Element(
        By.XPATH,
        "//*[@resource-id='TextAtom:string/rsu_search_update_software_info_hdr' or \
        @text='BMW Operating System X']",
    )
    RSU_SUBTITLE = Element(
        By.XPATH,
        "//*[@resource-id='TextAtom:string/rsu_notify_search_idle_info_hdr' or \
        @text='We will inform you as soon as Software Updates are available.']",
    )
    RSU_BUTTON_TEXT = Element(
        By.XPATH,
        "//*[@resource-id='TextAtom:string/rsu_hmi_search_update_search_for_upgrade_bt' or \
        @text='Search for updates']",
    )
    RSU_INFO_TEXT = Element(
        By.XPATH,
        "//*[@resource-id='TextAtom:string/rsu_search_installed_software_info_hdr' or \
        @text='Installed software']",
    )
    RSU_UPDATE_SETTINGS_TEXT = Element(
        By.XPATH,
        "//*[@resource-id='TextAtom:string/rsu_search_update_settings_info_hdr' or \
        @text='Update settings']",
    )

    @property
    def activity_name(self):
        return self.get_activity_name()

    @classmethod
    def start_activity_via_cardomain(cls):
        """Start the activity"""
        cmd = (
            f"am start -a {cls.ACTION_ACTIVITY} -e "
            f"com.bmwgroup.idnext.launcher.car.domain.EXTRA_PLUGIN_ID {cls.DOMAIN_IDENTIFIER} -e "
            'com.bmwgroup.idnext.launcher.car.domain.EXTRA_INTENT_URI "updatecenter://"'
        )
        return_stdout = cls.apinext_target.execute_command(cmd)
        return return_stdout
