import logging
from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class ConnectivityPage(BasePage):

    # Connectivity app
    CONN_RESOURCE_ID_PREFIX = "com.bmwgroup.idnext.connectivity:id/"
    CONN_RESOURCE_ID_PREFIX_ML = "com.bmwgroup.idnext.wirelessservices:id/"
    CONN_BAR_ID = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "action_bar_root")
    CONN_DISC_FRAG_ID = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "view_id_bluetooth_device_discovery_fragment")
    CONN_DISC_FRAG_ID_ML = Element(By.ID, CONN_RESOURCE_ID_PREFIX_ML + "view_id_bluetooth_device_discovery_fragment")
    CONN_BACK_ARROW = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "back_arrow_no_navigation")
    CONN_CONTENT_CONTAINER = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "content_container")
    ACTIVATE_BLUETOOTH_ID = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "bluetooth_settings_disable_bluetooth")
    BT_NAME = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "bluetooth_settings_bt_friendly_name")
    CONN_DEVICE = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "view_id_bluetooth_overview_fragment")
    PAGE_TITLE_ID = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "mini_view_title")
    PAGE_TITLE_ID_ML = Element(By.ID, CONN_RESOURCE_ID_PREFIX_ML + "mini_view_title")
    OVERLAY_CONN_BUTTON = Element(By.ID, "com.bmwgroup.idnext.overlay:id/det_communication_call_phone")
    conn_vhal_event_keycode = 1006
