from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage


class SpeechPage(BasePage):

    COMMON_NAME = "Speech"
    PACKAGE_NAME = "com.bmwgroup.apinext.ipaapp"
    SPEECH_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".feature.main.idx.MainComposeActivity"

    MAXIMUM_THRESHOLD_BOOT_TIME = 3000
