from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage


class ClimatePage(BasePage):

    COMMON_NAME = "Climate"
    # Climate activity doesn't have a domain identifier on the AndroidManifest.xml
    # https://cc-github.bmwgroup.net/apinext/climate-app/blob/master/app/src/main/AndroidManifest.xml
    PACKAGE_NAME = "com.bmwgroup.apinext.climate"
    CLIMATE_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".main.ClimateMainActivity"
