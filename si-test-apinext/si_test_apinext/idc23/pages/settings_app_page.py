import logging
import sh
import time

from appium.webdriver.common.appiumby import AppiumBy
from mtee.testing.tools import retry_on_except
from mtee.testing.tools import TimeoutCondition
from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.global_steps import GlobalSteps

logger = logging.getLogger(__name__)


class SettingsAppPage(BasePage):

    PACKAGE_NAME = "com.bmwgroup.idnext.settings"
    SETTINGS_APP_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".SettingsActivity"
    PACKAGE_ACTIVITY_ML = ".appidc23.SettingsActivity"

    # Page title
    SETTINGS_MENU_TITLE = ["SYSTEM SETTINGS", "SETTINGS"]

    # language settings
    LANGUAGE_BUTTON_ID = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        "new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector()."
        + f'resourceId("{SETTINGS_APP_RESOURCE_ID_PREFIX}btnLanguage"))',
    )
    LANGUAGE_RADIO_BUTTON_GROUP_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "languageRadioButtonGroup")
    LANGUAGE_ITEM = Element(By.CLASS_NAME, "android.view.ViewGroup")
    RADIO_BUTTON_ITEM = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "item_radioButton")
    STATUSBAR_TITLE = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "statusbar_title")
    ACTIVATE_RSU_BUTTON = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        "new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector()." + 'text("Activate"))',
    )
    START_RSU_BUTTON = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        "new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector()."
        + 'text("Remote Software Upgrade"))',
    )
    START_SEARCH_FOR_UPGRADE = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        "new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector()."
        + 'text("Search for upgrade"))',
    )
    # SettingsApp main menu elements resource ID / locators
    DATE_TIME_BUTTON_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "btnDateTime")
    DATE_TIME_GROUP_BY_UI_AUTOMATOR = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        "new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector()."
        + f'resourceId("{SETTINGS_APP_RESOURCE_ID_PREFIX}btnDateTime"))',
    )
    UNITS_BUTTON_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "btnUnits")
    UNITS_BUTTON_ID_BY_UI_AUTOMATOR = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        "new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector()."
        + f'resourceId("{SETTINGS_APP_RESOURCE_ID_PREFIX}btnUnits"))',
    )

    BLUETOOTH_GROUP_BY_UI_AUTOMATOR = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        "new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector()."
        + f'resourceId("{SETTINGS_APP_RESOURCE_ID_PREFIX}btnBluetoothStandard"))',
    )

    # Item label elements
    ITEM_LABEL_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "item_label")
    ITEM_LABEL_SECONDARY_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "item_label_secondary")

    # Present on all submenus
    BACK_ARROW_NO_NAVIGATION_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "back_arrow_no_navigation")

    # General settings
    GENERAL_SETTING_NAVIGATION_ID = Element(By.ID, SETTINGS_APP_RESOURCE_ID_PREFIX + "main_navigation")

    @classmethod
    @utils.gather_info_on_fail
    def return_from_submenus(cls):
        """
        Click on back arrow button to return from submenus until reaches General settings menu

        Time settings submenus have the back arrow button, this method recursively clicks
        on this button in order to return to the settings main menu

            Returns:
                None

            Raises:
                Exception - If some unexpected page is reached
        """
        max_wait_time_to_return = 5
        timer = TimeoutCondition(max_wait_time_to_return)
        while timer:
            while cls.try_back_arrow_click():
                logger.info("Finding status bar in setting")
                status_bar_settings = cls.driver.find_elements(*cls.STATUSBAR_TITLE)
                if status_bar_settings:
                    logger.info("Found status bar title")
                    for elem in status_bar_settings:
                        if elem.get_attribute("text") == "SYSTEM SETTINGS":
                            logger.info("Found SYSTEM SETTINGS -- Returned from submenus")
                            return
        raise Exception("Reached unexpected page, please make sure this method is used in a settings submenu")

    @classmethod
    def launch_settings_activity(cls, validate_activity=True):
        """Launches setting activity page on target

        :param validate_activity: Validation check whether activity has launched successfully.
        """
        logger.info(f"Branch name: {cls.branch_name}")
        if cls.branch_name == "pu2403":
            settings_activity = f"{cls.PACKAGE_NAME}/{cls.PACKAGE_ACTIVITY}"
        else:
            settings_activity = f"{cls.PACKAGE_NAME}/{cls.PACKAGE_ACTIVITY_ML}"
        logger.info(f"Launching Setting Activity: {settings_activity}")
        command = f"am start -n {settings_activity}"
        cls.apinext_target.execute_command(command)
        time.sleep(1)
        # Press back two times to deal with the scenario of the settings app being left on some
        # sub settings menu
        GlobalSteps.inject_key_input(cls.apinext_target, cls.back_keycode)
        time.sleep(1)
        GlobalSteps.inject_key_input(cls.apinext_target, cls.back_keycode)
        time.sleep(1)
        cls.apinext_target.execute_command(command)
        if validate_activity:
            activity_found = cls.validate_resumed_activities_on_screen(settings_activity)
            if not activity_found:
                raise RuntimeError(f"Runtime error occurred while launching activities {settings_activity}/")

    @classmethod
    @retry_on_except(retry_count=2, backoff_time=2)
    def validate_resumed_activities_on_screen(cls, activities):
        """
        Validates whether activity name passed as an argument is present on Foreground on target.

        Note:
            In case if argument type is list,
            this function will return True if any one item of the list appears on Foreground

            Returns:
                True OR False

        :param activities: (str/list) activity name OR list with multiple activity names
        """
        activity_found = None
        try:
            resumed_act = cls.apinext_target.execute_command("dumpsys activity activities | grep ResumedActivity")
        except sh.ErrorReturnCode_1 as err:
            logger.info("Unable to find current activities using adb dumpsys")
            raise err
        if isinstance(activities, str):
            activities = [activities]
        for each_act in activities:
            logger.info(f"Finding activity: {each_act} in Resumed Activity list: {resumed_act}")
            if each_act in resumed_act:
                activity_found = True
                logger.info(f"Found activity: {each_act}")
                break
            else:
                activity_found = False
        return activity_found

    @classmethod
    def language_change(cls, language_name):
        """
        This Method will Change the System Language
        param langauge_name: Language to be changed on the system
        """
        try:
            lang_name = By.XPATH, f"//*[@text='{language_name}']"
            logger.info(f"Changing Language to {language_name}")
            cls.launch_settings_activity()
            cls.wait_and_click_on_element(element=cls.LANGUAGE_BUTTON_ID)
            cls.wait_and_click_on_element(element=lang_name)
            logger.info(f"Language Changed to {language_name}")
        except Exception as e:
            raise Exception(f"Unable to Change the Language : {e}")
