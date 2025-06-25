import logging
from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class ConnectivitySettingsPage(BasePage):
    COMMON_NAME = "ConnectivitySettings"
    PACKAGE_NAME = "com.bmwgroup.idnext.wirelessservices"
    CONNECTIVITY_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".BTandWiFiAPConnectionSettings"
