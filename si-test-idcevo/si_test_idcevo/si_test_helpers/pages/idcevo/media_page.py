from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage


class MediaPage(BasePage):

    COMMON_NAME = "Media"
    PACKAGE_NAME = "com.bmwgroup.apinext.mediaapp"
    MEDIA_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".ui.MainActivity"

    MAXIMUM_THRESHOLD_BOOT_TIME = 3000
