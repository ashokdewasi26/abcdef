import logging
import os
import time
from mtee.testing.tools import assert_true, retry_on_except
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from si_test_idcevo.si_test_helpers.android_helpers import ensure_launcher_page
from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage, Element
from si_test_idcevo.si_test_helpers.pages.idcevo.connectivity_settings_page import ConnectivitySettingsPage


logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class ConnectivityPage(BasePage):
    # https://cc-github.bmwgroup.net/apinext/wireless-services-app/blob/0d6db8664c719033c08c10d9d984a07e7261c0f0/wirelessservices/src/idcevo/AndroidManifest.xml
    # https://cc-github.bmwgroup.net/apinext/wireless-services-app/blob/2f0fb2a6e0f2e5018f44aa707f89320c3edc8203/wirelessservices/src/main/res/values/strings-idc23.xml
    COMMON_NAME = "Connectivity"
    PACKAGE_NAME = "com.bmwgroup.idnext.wirelessservices"
    CONNECTIVITY_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".ConnectivityActivity"
    DOMAIN_IDENTIFIER = "wsa_connectivity"
    ACTION_ACTIVITY = "com.bmwgroup.idnext.action.CAR_DOMAIN"

    BLUETOOTH_ACTIVE = Element(By.ID, "TextAtom:string/wiserv_settings_bt_on_info_lb")
    BLUETOOTH_DEACTIVE = Element(By.ID, "TextAtom:string/wiserv_settings_bt_off_info_lb")
    BLUETOOTH_DEACTIVATE_CONFIRMATION = Element(By.XPATH, "//*[contains(@text,'Yes')]")

    MORE_OPTIONS_RID = "IconAtom:drawable/idx_icon_more"
    MORE_OPTIONS = Element(By.XPATH, f"//*[@resource-id='{MORE_OPTIONS_RID}' and @package='{PACKAGE_NAME}']")

    ACCEPT_BLUETOOTH_CONNECTION = Element(By.ID, "TextAtom:string/wiserv_dip_accept_bt")
    CONNECTED_DEVICE_SETTINGS_RID = "IconAtom:drawable/idx_icon_settings"
    CONNECTED_DEVICE_SETTINGS = Element(
        By.XPATH, f"//*[@resource-id='{CONNECTED_DEVICE_SETTINGS_RID}' and @package='{PACKAGE_NAME}']"
    )
    CONTINUE_WITHOUT_ANDROID_AUTO = Element(By.XPATH, "//*[@text='Connect telephone without Apple CarPlay']")
    PAIRING_CONFIRMATION_CODE_ID = Element(By.XPATH, "//*[contains(@text, 'Passkey')]")
    REMOVE_DEVICE = Element(By.ID, "TextAtom:string/wiserv_settings_device_details_remove_device_bt")
    SMARTPHONES = Element(By.ID, "TextAtom:string/wiserv_landing_page_device_smartphone_bt")
    START_ANDROID_AUTO = Element(By.XPATH, "//*[@text='Start Android Auto']")

    WIFI_ACTIVATE = Element(By.XPATH, "//*[contains(@text,'Activate to use')]")
    WIFI_DEACTIVATE = Element(By.XPATH, "//*[contains(@text,'Local network')]")
    WIFI_DEACTIVATE_CONFIRMATION = Element(By.XPATH, "//*[@text='Deactivate']")
    # currently the cancel button for the pop-up window to deactivate wifi does not have a uid
    WIFI_DEACTIVATE_CANCELATION = Element(By.XPATH, "//*[@text='Cancel']")
    WI_FI_CONNECTION_OPTION = Element(By.ID, "TextAtom:string/wiserv_settings_wifi_settings_bt")

    IDCEVO_BT_ID = Element(By.XPATH, "//*[contains(@text,'BMW-') or contains(@text,'s-BMW')]")

    @classmethod
    @retry_on_except(retry_count=1)
    def open_connectivity_settings(cls):
        """
        Runs the ADB command to access the "More options" in the Connections page.
        Raises:
        - `AssertionError` if it's not possible to validate Connectivity settings activity
        """
        warm_start_cmd = cls.get_command_warm_hot_start()
        cls.start_activity(warm_start_cmd)
        time.sleep(5)
        try:
            cls.click(cls.MORE_OPTIONS)
            logger.info("Just clicked on more options to open Connectivity settings")
        except (NoSuchElementException, TimeoutException):
            logger.error("Did not find the 'More Options' button on Connectivity Settings page. Is it correctly open?")
        time.sleep(1)
        connectivity_activity = ConnectivitySettingsPage.validate_activity()
        assert_true(connectivity_activity, "Failed to validate Connectivity Settings service")

    @classmethod
    def check_bluetooth_state_ui(cls):
        """
        Checks the current Bluetooth state in the Cardomain UI, by calling the functions responsible for
        assessing the state of the service.
        Requirements:
        - The device must be on the Connections page of the Cardomain menu.
        Returns:
        - False if the Bluetooth is offline.
        - True if the Bluetooth is online.
        Raises:
        - `AssertionError` if it's not possible to assess the Bluetooth state.
        """
        cls.open_connectivity_settings()
        try:
            cls.check_visibility_of_element(cls.BLUETOOTH_ACTIVE)
            logger.info("Found BT button element activated")

            return True
        except TimeoutException:
            logger.info(
                f"Tried to find the element '{cls.BLUETOOTH_ACTIVE}' in the UI without success"
                "that means it's probably not active"
            )
            pass

        try:
            cls.check_visibility_of_element(cls.BLUETOOTH_DEACTIVE)
            logger.info("Found BT button element deactivated")
            return False
        except TimeoutException:
            logger.info(f"Tried to find the element '{cls.BLUETOOTH_DEACTIVE}' in the UI without success")
            raise AssertionError("It was not possible to assess the state of Bluetooth")

    @classmethod
    @retry_on_except(retry_count=1)
    def turn_on_bluetooth_ui(cls):
        """
        Turns on the Bluetooth via the Cardomain UI.
        This method first checks the current Bluetooth state using the `check_bluetooth_state_ui()`
        method.
        Returns:
        - True if Bluetooth is already active or if it was successfully activated.
        Raises:
        - `AssertionError` if it's not possible to interact with BLUETOOTH_DEACTIVE
        """
        if cls.check_bluetooth_state_ui():
            logger.info("Doing no action in terms of activating BT because it's already activated")
            return True
        try:
            logger.info("BT button is not enabled, going to click on it to activate")
            cls.click(cls.BLUETOOTH_DEACTIVE)
            time.sleep(1)
            return True
        except NoSuchElementException as error:
            raise AssertionError("Turn_on_bluetooth_ui, raised an error while turning on the bluetooth ") from error

    @classmethod
    @retry_on_except(retry_count=1)
    def bluetooth_pop_up_confirmation_deactivation_via_ui(cls):
        """
        Interacts with the pop-up window for the confirmation of the deactivation of Bluetooth
        Returns:
        - True - Bluetooth was put offline
        - False - Bluetooth continues to be online
        """
        element = cls.check_visibility_of_element(cls.BLUETOOTH_DEACTIVATE_CONFIRMATION)
        element.click()

    @classmethod
    def turn_off_bluetooth_ui(cls):
        """
        Turns off the Bluetooth via the Cardomain UI.
        This method first checks the current Bluetooth state using the `check_bluetooth_state_ui()` method.
        Returns:
        -True if Bluetooth is already deactive or if it was successfully deactivated
        Raises:
        - `AssertionError` if it's not possible to interact with
            BLUETOOTH_ACTIVE
        """

        if not cls.check_bluetooth_state_ui():
            return True

        try:
            cls.click(cls.BLUETOOTH_ACTIVE)
        except Exception as error:
            raise AssertionError("Turn_off_bluetooth_ui, raised an error while turning off the bluetooth ") from error
        # The popup is not showing every time, so this is not critical
        try:
            cls.bluetooth_pop_up_confirmation_deactivation_via_ui()
        except Exception as error:
            logger.info(f"Expected a confirmation pop-up to deactivate BT but it didn't show: '{error}'")

    @classmethod
    def wifi_pop_up_cancel_to_deactivate_wifi_via_ui(cls):
        """
        Interacts with the pop-up window to cancel the deactivation of WiFi.
        Returns:
        - True: The cancellation pop-up was successfully handled; WiFi remains online.
        - False: The cancellation pop-up did not appear.
        """
        try:
            cls.click(cls.WIFI_DEACTIVATE_CANCELATION)
            logger.info("Deactivating confirmation popup!")
            time.sleep(1)
            return True
        except TimeoutException:
            logger.info("Didn't find the pop-up window to deactivate the wifi")
            return False

    @classmethod
    def wifi_pop_up_confirmation_deactivation_via_ui(cls):
        """
        Interacts with the pop-up window to confirm the deactivation of WiFi.
        Returns:
        - True: WiFi was successfully deactivated.
        - False: The confirmation pop-up did not appear.
        """
        time.sleep(3)
        try:
            logger.info("Trying to deactivate the wifi on the pop-up")
            cls.click(cls.WIFI_DEACTIVATE_CONFIRMATION)
            return True
        except TimeoutException:
            return False

    @classmethod
    def turn_on_wifi_ui(cls):
        """
        Turns on the Wifi via the Cardomain UI.
        This method first checks the current Wifi state using the `check_wifi_state_ui()`
        method.
        Returns:
        - True if Wifi is already active or if it was successfully activated.
        Raises:
        - `AssertionError` if it's not possible to interact with WIFI_ACTIVATE
        """
        if cls.check_wifi_state_ui():
            logger.info("Wifi already turn on")
            return True
        try:
            cls.click(cls.WIFI_ACTIVATE)
            time.sleep(1)
            return True
        except Exception as error:
            raise AssertionError("Turn_on_wifi_ui, raised an error while turning on the wifi ") from error

    @classmethod
    def turn_off_wifi_ui(cls):
        """
        Turns off the Wifi via the Cardomain UI.
        This method first checks the current Wifi state using the `check_wifi_state_ui()` method.
        Returns:
        -True if Wifi is already deactive or if it was successfully deactivated
        Raises:
        - `AssertionError` if it's not possible to interact with
            WIFI_DEACTIVATE
        """
        if not cls.check_wifi_state_ui():
            logger.info("Wifi already turn off")
            return False

        try:
            cls.click(cls.WIFI_DEACTIVATE)
        except Exception as error:
            raise AssertionError("Method turn_off_wifi_ui, raised an error while turning off the wifi") from error
        # The popup is not showing every time, so this is not critical/mandatory
        try:
            cls.wifi_pop_up_confirmation_deactivation_via_ui()
        except Exception as error:
            logger.info(f"Expected a confirmation pop-up to deactivate WIFI but it didn't show: '{error}'")

    @classmethod
    def check_for_confirmation_menu_to_deactivate_wifi(cls):
        """
        Checks if the confirmation menu to deactivate WiFi is present.
        Returns:
        - True: If the confirmation menu is present.
        - False: If the confirmation menu is not present.
        """
        try:
            cls.check_visibility_of_element(cls.WIFI_DEACTIVATE_CONFIRMATION)
            logger.info("confirmation menu to deactivate wifi is appearing")
            return True
        except TimeoutException:
            logger.info("Didn't find the pop-up window to deactivate wifi")
            return False

    @classmethod
    def check_wifi_state_ui(cls):
        """
        Checks the current Wifi state in the Cardomain UI, by calling the functions responsible for
        assessing the state of the service.
        Requirements:
        - The device must be on the Connections page of the Cardomain menu.
        Returns:
        - False if the Wifi is offline.
        - True if the Wifi is online.
        Raises:
        - `AssertionError` if it's not possible to assess the Wifi state.
        """
        cls.select_wifi_page()
        try:
            cls.check_visibility_of_element(cls.WIFI_ACTIVATE)
            logger.info("Found Wifi button, element activated")
            return False

        except TimeoutException:
            logger.info(f"Tried to find the element of wifi '{cls.WIFI_ACTIVATE}' in the UI without success")

        try:
            cls.check_visibility_of_element(cls.WIFI_DEACTIVATE)
            logger.info("Found Wifi button, element deactivated")

            return True
        except TimeoutException:
            raise AssertionError("It was not possible to assess the state of Wifi")

    @classmethod
    def select_wifi_page(cls):
        try:
            cls.open_connectivity_settings()
            time.sleep(1)
            cls.click(cls.WI_FI_CONNECTION_OPTION)
            logger.info("Found wifi option button")
            # The pop-up window to deactivate wifi can be up
            if cls.check_for_confirmation_menu_to_deactivate_wifi():
                cls.wifi_pop_up_cancel_to_deactivate_wifi_via_ui()
                time.sleep(1)
                cls.select_wifi_page()
        except Exception as error:
            logger.info("Can't find the wifi option button: %s", error)

    @classmethod
    def turn_on_bt_and_validate_the_status(cls, test):
        """
        Turns on the Bluetooth and validate the status via the Cardomain UI.
        This method first checks the current Bluetooth state using the `check_bluetooth_state_ui()`
        method.
        If Bluetooth state is off, it tries to turn it On.
        Later it again checks the Bluetooth state using the `validate_bt_is_on_via_ui()` and validates that it's On.
        :param test: test instance object
        :returns: True if Bluetooth is active or if it was successfully activated.
        :Raises: AssertionError if Bluetooth didn't turned On via the Cardomain UI.
        """
        if cls.check_bluetooth_state_ui():
            logger.info("Doing no action in terms of activating BT because it's already activated")
            ensure_launcher_page(test)
            return True
        try:
            logger.info("BT button is not enabled, going to click on it to activate")
            cls.click(cls.BLUETOOTH_DEACTIVE)
            time.sleep(1)
            ensure_launcher_page(test)
        except NoSuchElementException as error:
            ensure_launcher_page(test)
            raise AssertionError(
                "turn_on_bt_and_validate_the_status, raised an error while turning on the Bluetooth ",
            ) from error
        cls.validate_bt_is_on_via_ui(test)

    @classmethod
    def turn_on_wifi_and_validate_the_status(cls, test):
        """
        Turns on the Wifi via the Cardomain UI.
        This method first checks the current Wifi state using the `check_wifi_state_ui()`
        method.
        If Wifi is off, it tries to turn it On.
        Later it again checks the Wifi state using the `validate_wifi_is_on_via_ui()` and validates that it's On.
        :param test: test instance object
        :returns: True if Wifi is active or if it was successfully activated.
        :Raises: AssertionError if Wifi didn't turned On via the Cardomain UI.
        """
        if cls.check_wifi_state_ui():
            logger.info("Doing no action in terms of activating Wifi because it's already activated")
            ensure_launcher_page(test)
            return True
        try:
            logger.info("Wifi button is not enabled, going to click on it to activate")
            cls.click(cls.WIFI_ACTIVATE)
            time.sleep(1)
            ensure_launcher_page(test)
        except Exception as error:
            ensure_launcher_page(test)
            raise AssertionError(
                "turn_on_wifi_and_validate_the_status, raised an error while turning on the Wifi ",
            ) from error
        cls.validate_wifi_is_on_via_ui(test)

    @classmethod
    def validate_bt_is_on_via_ui(cls, test):
        """
        This function validates Bluetooth should be On via Cardomain UI.
        :returns: True if Bluetooth is active.
        :Raises: AssertionError if Bluetooth state is Off
        """
        if not cls.check_bluetooth_state_ui():
            ensure_launcher_page(test)
            raise AssertionError(
                "validate_bt_is_off_via_ui, raised an error since Bluetooth state was expected to be On",
            )
        return True

    @classmethod
    def validate_wifi_is_on_via_ui(cls, test):
        """
        This function validates Wifi should be On via Cardomain UI.
        :returns: True if Wifi is active.
        :Raises: AssertionError if Wifi state is Off
        """
        if not cls.check_wifi_state_ui():
            ensure_launcher_page(test)
            raise AssertionError(
                "validate_wifi_is_off_via_ui, raised an error since Wifi state was expected to be On",
            )
        return True

    @classmethod
    def has_paired_device(cls, test):
        """Check if there are paired bluetooth devices.

        returns: True if any device is paired, False otherwise
        """
        connected_device_settings = cls.driver.find_elements(*cls.CONNECTED_DEVICE_SETTINGS)
        test.apinext_target.take_screenshot(
            os.path.join(test.results_dir, f'Paired_bt_devices_{time.strftime("%Y-%h-%d_%H-%M-%S")}.png')
        )
        return len(connected_device_settings) != 0

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
    def open_connected_device_settings(cls, test):
        """Click on connected device settings."""
        device_settings = cls.driver.find_elements(*cls.CONNECTED_DEVICE_SETTINGS)
        if device_settings:
            test.take_apinext_target_screenshot(test.results_dir, "find_connected_device_settings_button.png")
            device_settings[0].click()
        else:
            test.take_apinext_target_screenshot(
                test.results_dir, "Failed_to_find_connected_device_settings_button.png"
            )
            raise RuntimeError(
                "Could not find connected device settings in Failed_to_find_connected_device_settings_button.png"
            )

    @classmethod
    def remove_pairing(cls, test):
        """Remove the paired device from IDCEvo"""
        # Check if "Remove device" is visible
        remove_device = cls.driver.find_element(*cls.REMOVE_DEVICE)
        if remove_device:
            test.take_apinext_target_screenshot(test.results_dir, "find_remove_device_button.png")
            remove_device.click()
            time.sleep(1)
        else:
            test.take_apinext_target_screenshot(test.results_dir, "Failed_to_find_remove_device_button.png")
            raise RuntimeError("Could not find remove device button in Failed_to_find_remove_device_button.png")

    @classmethod
    def remove_all_paired_devices(cls, test):
        """Remove all paired devices."""
        # Open Connections Menu
        warm_start_cmd = cls.get_command_warm_hot_start()
        cls.start_activity(warm_start_cmd)

        # Click on "Smartphones" to see paired devices
        smartphones_button = cls.check_visibility_of_element(cls.SMARTPHONES)
        smartphones_button.click()
        time.sleep(1)

        # Check if there are paired devices, if yes remove one by one
        while cls.has_paired_device(test):
            logger.info("Found paired devices, going to remove them")
            cls.open_connected_device_settings(test)
            cls.remove_pairing(test)
            time.sleep(5)

        logger.info("Removed all paired devices")
        test.take_apinext_target_screenshot(test.results_dir, "all_devices_removed.png")
