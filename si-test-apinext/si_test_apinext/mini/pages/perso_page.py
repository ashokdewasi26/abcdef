import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.common.pages.base_page import BasePage, Element


class PersoPage(BasePage):

    # Perso
    PACKAGE_NAME = "com.bmwgroup.idnext.perso"
    PACKAGE_ACTIVITY = ".view.MainActivity"
    RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"

    # PERSO SWITCH
    PERSO_SWITCH_USER_ID = Element(By.ID, RESOURCE_ID_PREFIX + "switch_account_button")
    PERSO_SWITCH_USER_ID_PU = Element(By.ID, RESOURCE_ID_PREFIX + "secund_button")
    SWITCH_PROFILE_ID = Element(By.ID, RESOURCE_ID_PREFIX + "standardListItem")
    LIST_PROFILES_ID = Element(By.ID, RESOURCE_ID_PREFIX + "accountList")
    ACTIVATE_NEW_PROFILE_ID = Element(By.ID, RESOURCE_ID_PREFIX + "option_1")

    # PERSO DELETE
    SETTINGS_PROFILE_ID = Element(By.ID, RESOURCE_ID_PREFIX + "settingsButton")
    MANAGE_PROFILES_ID = Element(By.ID, RESOURCE_ID_PREFIX + "itemContainer")
    PANEL_PROFILE_ID = Element(By.ID, RESOURCE_ID_PREFIX + "settingsPanelLayout")
    NAME_LABEL_PROFILE_ID = Element(By.ID, RESOURCE_ID_PREFIX + "panelTitle")
    REMOVE_BUTTON_ID = Element(By.ID, RESOURCE_ID_PREFIX + "button_title")
    ACCEPT_REMOVE_BUTTON_ID = Element(By.ID, RESOURCE_ID_PREFIX + "option_1")

    # PERSO ADD USER
    ADD_PROFILE_ID = Element(By.ID, RESOURCE_ID_PREFIX + "addAccountButton")

    # PERSO USERS
    USER_PARENT = Element(By.ID, RESOURCE_ID_PREFIX + "standard_card_text_container")
    USER_CHILD = Element(By.ID, RESOURCE_ID_PREFIX + "standard_card_subHeader")
    USER = Element(By.ID, RESOURCE_ID_PREFIX + "standard_card_header")

    @classmethod
    def get_current_user_name(cls):
        echo_command = cls.apinext_target.execute_adb_command(["shell", "pm", "list users"])
        list_users = str(echo_command.stdout.decode("UTF-8")).split("\n")
        for user_str in list_users:
            if "running" in user_str:
                name = user_str.split(":")[1]
        return name

    @classmethod
    def launch_switch_user_screen(cls):
        cls.start_activity()
        try:
            switch_button = cls.wb.until(
                ec.visibility_of_element_located(cls.PERSO_SWITCH_USER_ID),
                message="Unable to find Switch Driver Profile Button",
            )
        except ():
            logging.info("Switch profile element not found. Checking another one...")
            switch_button = cls.wb.until(
                ec.visibility_of_element_located(cls.PERSO_SWITCH_USER_ID_PU),
                message="Unable to find Switch Driver Profile Button",
            )
        switch_button.click()

    @classmethod
    def get_current_active_user(cls):
        current_user = None
        parent_elements = cls.driver.find_elements(*cls.USER_PARENT)
        for parent_element in parent_elements:
            try:
                active_user = parent_element.find_elements(*cls.USER_CHILD)
                if active_user[0]:
                    element = parent_element.find_elements(*cls.USER)
                    current_user = element[0].get_attribute("text")
                    break
            except Exception as e:
                logging.error("No Active User Found : !! %s", e)
        logging.info("Current Active User: %s", current_user)
        return current_user

    @classmethod
    def check_user_present(cls, user_to_check):
        echo_command = cls.apinext_target.execute_adb_command(["shell", "pm", "list users"])
        list_users = str(echo_command.stdout.decode("UTF-8")).split("\n")
        return any(user_to_check in user_str for user_str in list_users)
