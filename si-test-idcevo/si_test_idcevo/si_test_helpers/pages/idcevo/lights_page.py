from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage


class LightsPage(BasePage):
    # https://cc-github.bmwgroup.net/apinext/light-app/blob/master/app/src/main/AndroidManifest.xml
    COMMON_NAME = "Lights"
    PACKAGE_NAME = "com.bmwgroup.apinext.light"
    LIGHTS_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".MainActivity"

    # Look for domain identifier in the AndroidManifest.xml file
    DOMAIN_IDENTIFIER = "light_app"
    # Search for the action and category in the intent-filter
    ACTION_ACTIVITY = "com.bmwgroup.idnext.action.CAR_DOMAIN"
