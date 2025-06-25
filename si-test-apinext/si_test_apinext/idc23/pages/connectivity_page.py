import logging
import os
import time

import si_test_apinext.util.driver_utils as utils
from appium.webdriver.common.appiumby import AppiumBy
from mtee.testing.tools import assert_true
from mtee.testing.tools import retry_on_except
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import BasePage, Element
from si_test_apinext.util.global_steps import GlobalSteps

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class ConnectivityPage(BasePage):
    # Connectivity app
    PACKAGE_NAME = "com.bmwgroup.idnext.connectivity"
    PACKAGE_NAME_ML = "com.bmwgroup.idnext.wirelessservices"
    CONN_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    CONN_RESOURCE_ID_PREFIX_ML = PACKAGE_NAME_ML + ":id/"
    PACKAGE_ACTIVITY = ".nav.device_manager.NavDeviceManagerHostActivity"

    CONN_BAR_ID = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "action_bar_root")
    ACTIVATE_BT = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "bluetooth_settings_disable_bluetooth")
    BT_NAME = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "bluetooth_settings_bt_friendly_name")
    ADD_DEVICE = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "add_device_button")

    CONN_DISC_FRAG_ID = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "view_id_bluetooth_device_discovery_fragment")
    CONN_DISC_FRAG_ID_ML = Element(By.ID, CONN_RESOURCE_ID_PREFIX_ML + "view_id_bluetooth_device_discovery_fragment")
    SELECT_DEVICE = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "device_name")
    CONN_DEVICE = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "view_id_bluetooth_overview_fragment")
    CONN_BACK_ARROW = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "back_arrow_no_navigation")
    CONFIRM_BT = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "pairing_code_confirm_button")
    RETRY_BT = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "pairing_code_retry_button")
    TELEPHONY_OPTION = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "option_toggle_phone")
    MEDIA_OPTION = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "option_toggle_media")
    MESSAGE_NOTIFICATION_OPTION = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "message_notifications")
    RELOAD_CONTACTS_OPTION = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "option_reload_contacts")
    REMOVE_OPTION = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "option_delete_device")
    SIDE_NAVIGATION_BACK_ARROW_ID = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "side_navigation_back_arrow")
    WIFI_SETTINGS_BUTTON_ID = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "wifi_settings_button")
    BLUETOOTH_SETTINGS_DEVICES_MAINTENANCE_ID = Element(
        By.ID, CONN_RESOURCE_ID_PREFIX + "bluetooth_settings_devices_maintenance"
    )
    ITEM_LABEL = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "item_label")
    ITEM_LABEL_SECONDARY = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "item_label_secondary")
    PAIRING_CONFIRMATION_CODE_ID = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "pairing_confirmation_code")

    CONNECT_NEW_DEVICE_ID = Element(By.XPATH, "//*[@text='Connect new device']")
    NO_DEVICE_CONNECTED_ID = Element(By.XPATH, "//*[@text='No device connected.']")
    CONNECTING = Element(By.XPATH, "//*[@text='Connecting…']")
    TRY_AGAIN = Element(By.XPATH, "//*[@text='Try again']")
    CANCEL = Element(By.XPATH, "//*[@text='Cancel']")
    BLUETOOTH_NAME = Element(By.XPATH, "//*[@text='Bluetooth name']")
    CONTINUE_WITH_BMW_IDRIVE = Element(By.XPATH, "//*[contains(@text, 'Continue with BMW iDrive')]")

    TOGGLE_BUTTON = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "button_icon")

    PAGE_TITLE_ID = Element(By.ID, CONN_RESOURCE_ID_PREFIX + "statusbar_title")
    PAGE_TITLE_ID_ML = Element(By.ID, CONN_RESOURCE_ID_PREFIX_ML + "statusbar_title")
    page_title_bluetooth_on = "CONNECT NEW DEVICE"
    page_title_bluetooth_off = "BLUETOOTH"
    page_title_bluetooth_paired = "MOBILE DEVICES"
    active_call = "ACTIVE CALL"

    DEVICES_ON_LEFT = Element(By.XPATH, "//*[@text='Devices']")

    SCROLL_U_REMOVE_BUTTON_ID = Element(
        AppiumBy.ANDROID_UIAUTOMATOR,
        "new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector()." + 'text("Remove"))',
    )

    conn_vhal_event_keycode = 1006

    @classmethod
    def confirm_pairing(cls):
        """Confirm the passkey from the other party

        The next validation of this action is much complex and uses dlt log also.
        Please take a look at ConnectorBluetoothIDC23::confirm_pairing_from_target()
        """
        confirm_bt = cls.driver.find_elements(*cls.CONFIRM_BT)
        if confirm_bt:
            confirm_bt[0].click()
            time.sleep(5)

    @classmethod
    def remove_pairing(cls):
        """Remove the paired device from IDC23"""
        # Scroll down until "Remove" is visible
        remove_bt = cls.driver.find_element(*cls.SCROLL_U_REMOVE_BUTTON_ID)
        if remove_bt:
            utils.take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, "find_remove_button.png")
            remove_bt.click()
        else:
            utils.take_apinext_target_screenshot(
                cls.apinext_target, cls.results_dir, "Failed_to_find_remove_button.png"
            )
            raise RuntimeError('Could not find "Remove" in Failed_to_find_remove_button.png')

    @classmethod
    def remove_all_paired_devices(cls):
        """Remove all paired devices."""
        cls.open_connectivity()
        while cls.has_paired_device():
            logger.info("Found paired devices, going to remove them")
            cls.remove_pairing()
            cls.open_connectivity()
        logger.info("Removed all paired devices")
        utils.take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, "all_devices_removed.png")

    @classmethod
    @retry_on_except(exception_class=TimeoutException, retry_count=3, backoff_time=2, silent_fail=False)
    def open_connectivity(cls):
        """
        Open connectivity main widget if it is not present.
        """
        if not cls.driver.find_elements(*cls.PAGE_TITLE_ID):
            # Open "Connect phone"
            GlobalSteps.inject_custom_vhal_input(cls.apinext_target, cls.conn_vhal_event_keycode)

            # Using the connectivity device_manager start activity we can end up in different pages
            # depending on previous steps
            no_devices = cls.driver.find_elements(*cls.NO_DEVICE_CONNECTED_ID)
            conn_back_arrow = cls.driver.find_elements(*cls.SIDE_NAVIGATION_BACK_ARROW_ID)
            # If the message 'No device connected.' is present it means we are at the device manager page
            # and need to go back
            if no_devices and conn_back_arrow:
                conn_back_arrow[0].click()

            # On the device manager page we have a Wi-fi button and also a 'Connect new device'
            # button. So if we have a 'Connect new device' but not a Wi-fi button it means we are at
            # the initial connect new device page
            wi_fi_button = cls.driver.find_elements(*cls.WIFI_SETTINGS_BUTTON_ID)
            new_device_button = cls.driver.find_elements(*cls.CONNECT_NEW_DEVICE_ID)
            if not wi_fi_button and new_device_button:
                new_device_button[0].click()

            try:
                connetivity_app_status = cls.check_visibility_of_first_and_second_elements(
                    cls.PAGE_TITLE_ID, cls.PAGE_TITLE_ID_ML
                )
                assert_true(
                    connetivity_app_status,
                    "Failed to open connectivity app after telephone button press/release. "
                    f"Either element {cls.PAGE_TITLE_ID} or element "
                    f"{cls.PAGE_TITLE_ID_ML} were expected to be present after telephone operation ",
                )
            except TimeoutException as exp:
                screenshot = os.path.join(
                    cls.results_dir, f'No_connectivity_title_{time.strftime("%Y-%h-%d_%H-%M-%S")}.png'
                )
                cls.apinext_target.take_screenshot(screenshot)

                # Most likely alert pop-up is shown up, it is worthwhile to try again after closing alerts
                utils.ensure_no_alert_popup(cls.results_dir, cls.driver, cls.apinext_target)
                utils.ensure_no_traffic_info(cls.results_dir, cls.driver, cls.apinext_target)

                raise exp

    @classmethod
    def has_paired_device(cls):
        """Check if there is already paired bluetooth devices.

        "telephone" is an implication for bluetooth connection. Only paired device widget could display this item.
        returns: True if any device is paired, False otherwise
        """
        telephony = cls.driver.find_elements(*cls.TELEPHONY_OPTION)
        if len(telephony) == 0:
            devices = cls.driver.find_elements(*cls.DEVICES_ON_LEFT)
            if len(devices) != 0:
                devices[0].click()
                cls.apinext_target.take_screenshot(
                    os.path.join(cls.results_dir, f'Open_devices_{time.strftime("%Y-%h-%d_%H-%M-%S")}.png')
                )
                time.sleep(2)
                telephony = cls.driver.find_elements(*cls.TELEPHONY_OPTION)
        return len(telephony) != 0

    @classmethod
    @retry_on_except(
        exception_class=(NoSuchElementException, StaleElementReferenceException),
        retry_count=2,
        backoff_time=2,
        silent_fail=False,
    )
    def is_active_call(cls):
        """
        Check if there is an active call.
        If there is active call, then the page title is "ACTIVE CALL"

        returns: True if active call, False otherwise

        Raises:
            NoSuchElementException - If it was not able to find an element of 'PAGE_TITLE_ID' on displayed widgets
            StaleElementReferenceException - If title was there befor but disappears at the moment at usage
        """
        try:
            page_title = cls.driver.find_element(*cls.PAGE_TITLE_ID)
            return page_title and (page_title.text == cls.active_call)
        except NoSuchElementException:
            screenshot = os.path.join(
                cls.results_dir,
                f'No_active_call_because_of_NoSuchElementException_{time.strftime("%Y-%h-%d_%H-%M-%S")}.png',
            )
            cls.apinext_target.take_screenshot(screenshot)
            # Two reasons for no PAGE_TITLE_ID
            # 1. alert pop-up, then we can retry after closing it
            # 2. really no active call at all, then we should return false
            if utils.is_alert_popup(cls.driver):
                utils.ensure_no_alert_popup(cls.results_dir, cls.driver, cls.apinext_target)
                raise
            return False
        except StaleElementReferenceException:
            # Only one reasons for StaleElementReferenceException: the element is covered by alert
            # So, we need to retry again
            screenshot = os.path.join(
                cls.results_dir,
                f'No_active_call_because_of_StaleElementReferenceException_{time.strftime("%Y-%h-%d_%H-%M-%S")}.png',
            )
            cls.apinext_target.take_screenshot(screenshot)
            utils.ensure_no_alert_popup(cls.results_dir, cls.driver, cls.apinext_target)
            raise

    @classmethod
    def validate_bt_paired_device(cls, device, bt_device_name):
        """Verify if the 'device' has a BT bond with a device named 'bt_device_name'

        :param AndroidTarget device: An Android target module with AndroidTarget class properties
        :param str bt_device_name: name of the BT adapter of the expected device
        :return bool: True if expected device is paired with current device, False if not
        """
        bonded_device = device.execute_command(
            "dumpsys bluetooth_manager | grep -A 15 AdapterProperties | grep -A 2 Bonded"
        )
        bonded_device_str = str(bonded_device.stdout, "utf-8")
        if bt_device_name in bonded_device_str:
            return True
        else:
            return False

    @classmethod
    def get_connection_state(cls, device):
        """Get the BT connection state of current 'device'

        :param AndroidTarget device: An Android target module with AndroidTarget class properties
        :return str: Current connection state
        """
        connection_state = device.execute_command(
            "dumpsys bluetooth_manager | grep -A 18 AdapterProperties | grep ConnectionState"
        )
        return str(connection_state.stdout, "utf-8")

    @classmethod
    def has_device_connected(cls, device):
        """Verify if current device BT adapter state is Connected

        :param AndroidTarget device: An Android target module with AndroidTarget class properties
        :raises Exception: In case an unexpected state is found
        :return bool: True if state is connected, False if disconnected
        """
        state_connected = "STATE_CONNECTED"
        state_disconnected = "STATE_DISCONNECTED"
        state_connecting = "STATE_CONNECTING"
        state_disconnecting = "STATE_DISCONNECTING"

        connection_state = cls.get_connection_state(device)

        while (state_connecting in connection_state) or (state_disconnecting in connection_state):
            time.sleep(2)
            connection_state = cls.get_connection_state(device)

        if state_connected in connection_state:
            return True
        elif state_disconnected in connection_state:
            return False
        else:
            raise Exception(f"Found an unexpected Bluetooth state: '{connection_state}'")
