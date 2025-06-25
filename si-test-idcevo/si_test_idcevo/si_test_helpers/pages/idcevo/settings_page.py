from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage


class SettingsPage(BasePage):

    # https://cc-github.bmwgroup.net/apinext/settings-app/blob/master/app-idc25/src/main/AndroidManifest.xml
    COMMON_NAME = "Settings"
    PACKAGE_NAME = "com.bmwgroup.idnext.settings"
    SETTINGS_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".appidc25.ui.SettingsActivity"

    # Look for domain identifier in the AndroidManifest.xml file
    DOMAIN_IDENTIFIER = "settings_app"
    # Search for the action and category in the intent-filter
    ACTION_ACTIVITY = "com.bmwgroup.idnext.action.CAR_DOMAIN"

    MAXIMUM_THRESHOLD_BOOT_TIME = 3000
