from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element


class PersoPage(BasePage):

    # Perso
    PACKAGE_NAME = "com.bmwgroup.idnext.perso"
    PACKAGE_ACTIVITY = ".view.MainActivity"
    PERSO_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"

    # PERSO SWITCH
    PERSO_SWITCH_USER_ID = Element(By.ID, PERSO_RESOURCE_ID_PREFIX + "switch_account_button")
    SWITCH_PROFILE_ID = Element(By.ID, PERSO_RESOURCE_ID_PREFIX + "standardListItem")
    LIST_PROFILES_ID = Element(By.ID, PERSO_RESOURCE_ID_PREFIX + "accountList")
    ACTIVATE_NEW_PROFILE_ID = Element(By.ID, PERSO_RESOURCE_ID_PREFIX + "option_1")
    GUEST_PROFILE_ID = Element(
        By.XPATH, "//*[@resource-id='" + PERSO_RESOURCE_ID_PREFIX + "accountList']//*[@text='Guest']"
    )
    GUEST_PROFILE_TEXT = Element(By.XPATH, "//*[@text='Continue as guest']")

    # PERSO DELETE
    SETTINGS_PROFILE_ID = Element(By.ID, PERSO_RESOURCE_ID_PREFIX + "settingsButton")
    MANAGE_PROFILES_ID = Element(By.ID, PERSO_RESOURCE_ID_PREFIX + "itemContainer")
    PANEL_PROFILE_ID = Element(By.ID, PERSO_RESOURCE_ID_PREFIX + "settingsPanelLayout")
    NAME_LABEL_PROFILE_ID = Element(By.ID, PERSO_RESOURCE_ID_PREFIX + "panelTitle")
    REMOVE_BUTTON_ID = Element(By.ID, PERSO_RESOURCE_ID_PREFIX + "button_title")
    ACCEPT_REMOVE_BUTTON_ID = Element(By.ID, PERSO_RESOURCE_ID_PREFIX + "option_1")

    # PERSO ADD USER
    ADD_PROFILE_ID = Element(By.ID, PERSO_RESOURCE_ID_PREFIX + "addAccountButton")
    ADD_PROFILE_TEXT = Element(By.XPATH, "//*[@text='Add profile']")
    ADD_BMW_ID = Element(By.ID, PERSO_RESOURCE_ID_PREFIX + "link_bmw_id_button")
    DIALOG_EXPLANATION_ID = Element(By.ID, PERSO_RESOURCE_ID_PREFIX + "dialogExplanation")

    @classmethod
    def get_current_user_name(cls):
        echo_command = cls.apinext_target.execute_adb_command(["shell", "pm", "list users"])
        list_users = str(echo_command.stdout.decode("UTF-8")).split("\n")
        for user_str in list_users:
            if "running" in user_str:
                name = user_str.split(":")[1]
        return name

    @classmethod
    def check_user_present(cls, user_to_check):
        echo_command = cls.apinext_target.execute_adb_command(["shell", "pm", "list users"])
        list_users = str(echo_command.stdout.decode("UTF-8")).split("\n")
        return any(user_to_check in user_str for user_str in list_users)
