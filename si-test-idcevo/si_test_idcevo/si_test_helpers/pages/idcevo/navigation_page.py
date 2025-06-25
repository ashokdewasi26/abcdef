from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage


class NavigationPage(BasePage):

    COMMON_NAME = "Navigation"
    PACKAGE_NAME = "com.bmwgroup.idnext.navigation"
    NAVIGATION_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".map.MainActivity"

    MAXIMUM_THRESHOLD_BOOT_TIME = 3000
