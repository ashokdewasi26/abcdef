# Copyright (C) 2022. BMW CTW. All rights reserved.
import logging
import sh
import time

import si_test_apinext.util.driver_utils as utils
from appium.webdriver.common.appiumby import AppiumBy
from mtee.testing.tools import assert_false, assert_true, retry_on_except
from mtee_apinext.enablers.support.android_generic_hid_mapping import AndroidGenericKeyCodes
from selenium.webdriver.common.by import By
from si_test_apinext.common.pages.base_page import Element
from si_test_apinext.idc23 import HMI_BUTTONS_REF_IMG_PATH
from si_test_apinext.idc23.pages.connectivity_page import ConnectivityPage as Connect
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.settings_app_page import SettingsAppPage
from si_test_apinext.real_phone.pages.android_bt_settings_page import AndroidBTSettings
from si_test_apinext.real_phone.pages.android_pop_up_page import AndroidPopUp
from si_test_apinext.real_phone.pages.android_settings_page import AndroidSettings
from si_test_apinext.util.global_steps import GlobalSteps
from si_test_apinext.util.hmi_helper import HMIhelper
from si_test_apinext.util.screenshot_utils import capture_screenshot

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class BluetoothUtils:
    def __init__(self, test):
        self.test = test
        self.hmihelper = HMIhelper(test, HMI_BUTTONS_REF_IMG_PATH)

    def ensure_bluetooth_services(self):
        """After bt pairing, ensure phone and audio services are supported"""
        self.ensure_service_on("phone", Connect.TELEPHONY_OPTION)
        self.ensure_service_on("media", Connect.MEDIA_OPTION)

    def ensure_service_on(self, name, option_element, sleep_time=5):
        """
        Validate if the named service is on or not, if not, then click to enable the service
        Param sleep_time: Seconds to wait after clicking on toggle ON/OFF.
        """
        service_option = self.test.driver.find_element(*option_element)
        service_toggle_button = service_option.find_element(*Connect.TOGGLE_BUTTON)

        service_status = self.hmihelper.find_current_button_status(
            service_toggle_button, f"bluetooth_{name}_status", image_pattern="button_on*.png"
        )
        # if the expected service is not on, then we click it on
        if not service_status:
            button = service_option.find_element(*Connect.TOGGLE_BUTTON)
            self.hmihelper.ensure_button_status_on(button, f"turn_on_bluetooth_{name}_service", sleep_time=sleep_time)

    def ensure_service_off(self, name, option_element):
        """Validate if the named service is off or not, if not, then click to click the service"""
        service_option = self.test.driver.find_element(*option_element)
        service_toggle_button = service_option.find_element(*Connect.TOGGLE_BUTTON)
        service_status = self.hmihelper.find_current_button_status(
            service_toggle_button, f"bluetooth_{name}_status", image_pattern="button_off*.png"
        )
        # if the expected service is on, then we click it off
        if service_status:
            button = service_option.find_element(*Connect.TOGGLE_BUTTON)
            self.hmihelper.ensure_button_status_off(button, f"turn_off_bluetooth_{name}_service")

    def go_to_bt_submenu(self):
        """Navigate to BT settings submenu"""
        # First try to use android activity
        AndroidBTSettings.start_action()
        time.sleep(1)
        bt_title_elem = self.test.driver.find_elements(*Connect.PAGE_TITLE_ID)
        if bt_title_elem and "BLUETOOTH" in bt_title_elem[0].text.upper():
            logger.info(f"Found bt title after Android settings start action '{bt_title_elem[0].text}'")
            return
        else:
            # Launching Settings App
            SettingsAppPage.launch_settings_activity()
            try:
                # Scroll until Bluetooth menu is found
                bluetooth_menu_btn = self.test.driver.find_element(*SettingsAppPage.BLUETOOTH_GROUP_BY_UI_AUTOMATOR)
                # Wait for the scroll animation to finish and reach the option.
                time.sleep(2)
                bluetooth_menu_btn.click()
                # Wait for the Bluetooth screen to load
                time.sleep(3)
                bt_title_elem = self.test.driver.find_elements(*Connect.PAGE_TITLE_ID)
                if bt_title_elem and "BLUETOOTH" in bt_title_elem[0].text:
                    logger.info(f"Found bt title after navigating through settings '{bt_title_elem[0].text}'")
                    return
                logger.error('Could not find "BLUETOOTH" in bt_title_elem on current page')
            except Exception as ex:  # pylint: disable=broad-except
                logger.error("Exception occurred while trying to go to bluetooth option: %s", ex)
                utils.get_screenshot_and_dump(self.test, self.test.results_dir, "bluetooth_settings_issue_dump")
                # Press back two times to deal with the scenario of the settings app being left on some other menu
                GlobalSteps.inject_key_input(self.test.apinext_target, SettingsAppPage.back_keycode)
                time.sleep(1)
                GlobalSteps.inject_key_input(self.test.apinext_target, SettingsAppPage.back_keycode)
                time.sleep(1)

    @utils.gather_info_on_fail
    @retry_on_except(retry_count=1, backoff_time=3)
    def turn_on_bluetooth(self):
        """Turn on Bluetooth on the Bluetooth settings menu

        Open settings app and navigate to the Bluetooth settings sub menu, click to enable
        Bluetooth and do a hmi verification of the button status to ensuro it's on

        :return: True if Bluetooth is already enabled or was successfully enabled
        :rtype: bool
        """
        if self.test.bluetooth_on is True:
            logger.debug("BT already ON, returning from turn_on_bluetooth")
            return True
        self.go_to_bt_submenu()
        time.sleep(1)
        self.ensure_service_on("bluetooth_setting", Connect.ACTIVATE_BT)
        self.test.bluetooth_on = True
        self.test.apinext_target.send_keycode(AndroidGenericKeyCodes.KEYCODE_BACK)
        time.sleep(1)
        return True

    @utils.gather_info_on_fail
    @retry_on_except(retry_count=1)
    def turn_on_bluetooth_via_adb_commands(self):
        """
        Turn on Bluetooth via adb commands
        If adb operation fails then turn on Bluetooth via UI from settings menu
        """
        status = self.check_the_status_of_bluetooth_via_adb_commands()
        if int(status):
            logger.info(f"Bluetooth is already ON: {status}")
            return
        self.go_to_bt_submenu()
        time.sleep(1)
        try:
            self.test.apinext_target.execute_command("cmd bluetooth_manager enable")
            logger.info("Bluetooth is turning on via adb command")
            capture_screenshot(test=self.test, test_name="taking_screenshot_after_turning_on_via_adb")
        except sh.ErrorReturnCode_255 as exception:
            logger.info("Exception occurred while turning on Bluetooth: {}".format(exception))
        status = self.check_the_status_of_bluetooth_via_adb_commands()
        if int(status):
            logger.info("Status of bluetooth is ON")
        else:
            logger.info("Bluetooth was not turned on via adb command")
            logger.info("turning on bluetooth via UI")
            self.turn_on_bluetooth()

    @utils.gather_info_on_fail
    @retry_on_except(retry_count=1)
    def check_the_status_of_bluetooth_via_adb_commands(self):
        """
        check Bluetooth status via adb commands
        """
        status = self.test.apinext_target.execute_command("settings get global bluetooth_on")
        logger.info(f"Bluetooth status as 0/1: {status}")
        return status

    @retry_on_except(retry_count=1)
    def get_bt_name(self):
        """Get IDC23 bluetooth adapter name"""
        SettingsAppPage.launch_settings_activity(validate_activity=False)
        # Scroll until Bluetooth menu is found
        bluetooth_menu_btn = self.test.driver.find_element(*SettingsAppPage.BLUETOOTH_GROUP_BY_UI_AUTOMATOR)
        bluetooth_menu_btn.click()
        time.sleep(1)

        bluetooth_name_elem = self.test.driver.find_element(*Connect.BT_NAME)
        label_elem = bluetooth_name_elem.find_element(*Connect.ITEM_LABEL)
        assert label_elem.text == "Bluetooth name"
        name_elem = bluetooth_name_elem.find_element(*Connect.ITEM_LABEL_SECONDARY)
        assert name_elem.text, f"Unable to get a valid name for IDC23 bluetooth, instead got: '{name_elem.text}'"
        return name_elem.text

    @retry_on_except(retry_count=1)
    def connect_new_device(self, real_phone, new_device_name=""):
        """Connect a real device to the IDC23 bluetooth

        Steps:
            - Go to connectivity menu and click on 'Add new device'
            - Search for the received name 'new_device_name' and click it
            - Make sure the pairing code generated by IDC is the same as the one showing on real phone
            - Accept pairing on real phone

        :param real_phone: real phone handler
        :type real_phone: RealPhoneAppiumTarget
        :param new_device_name: name of real phone bluetooth adapter, defaults to ""
        :type new_device_name: str, optional
        """
        Connect.open_connectivity()
        # Try to find 'new_device_name'
        new_bt_device = Element(By.XPATH, f"//*[@text='{new_device_name}']")
        new_device_elem = self.test.driver.find_elements(*new_bt_device)
        if new_device_elem:
            new_device_elem[0].click()
            time.sleep(1)
        else:
            # Try to scroll until 'new_device_name' is located and click it
            new_bt_device = Element(
                AppiumBy.ANDROID_UIAUTOMATOR,
                "new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector()."
                + f'text("{new_device_name}"))',
            )
            new_device_elem = self.test.driver.find_element(*new_bt_device)
            new_device_elem.click()
            time.sleep(1)
        # Make sure pairing codes match
        idc23_pair_code = Connect.check_visibility_of_element(Connect.PAIRING_CONFIRMATION_CODE_ID)
        # Click on "tap to pair with"
        tap_to_pair = real_phone.driver.find_elements(*AndroidSettings.TAP_TO_PAIR_WITH)
        if tap_to_pair:
            tap_to_pair[0].click()
            time.sleep(1)
        rp_pair_number = real_phone.check_visibility_of_element(AndroidSettings.PAIRING_SUBHEAD)
        assert (
            idc23_pair_code.text == rp_pair_number.text
        ), f"Pair code of IDC23: '{idc23_pair_code.text}' doesn't match real phone code: '{rp_pair_number.text}'"
        # Accept pairing on real phone
        pair_connect = real_phone.wait_to_check_visible_element(AndroidSettings.PAIR_CONNECT)
        if pair_connect:
            pair_connect.click()
            time.sleep(1)
        pair = real_phone.check_visibility_of_element(AndroidSettings.PAIR)
        pair.click()
        time.sleep(1)
        # If "Allow access to messages" shows up click "Don't allow"
        dont_allow = real_phone.wait_to_check_visible_element(AndroidPopUp.BUTTON2)
        if dont_allow:
            dont_allow.click()
            time.sleep(1)
        # If "Continue with BMW iDrive" shows up click it
        bmw_idrive = self.test.driver.find_elements(*Connect.CONTINUE_WITH_BMW_IDRIVE)
        if bmw_idrive:
            utils.take_apinext_target_screenshot(
                apinext_target=self.test.apinext_target,
                results_dir=self.test.results_dir,
                file_name="after_CONTINUE_WITH_BMW_IDRIVE",
            )
            bmw_idrive[0].click()
            time.sleep(1)

    def reconnect_device(self, device, bt_device_name, num_reconnect):
        """Perform iterations of BT reconnection between an external device and the IDC23

        This method assumes there has been a pairing between the devices before, leaving a bond between them
        Having a previous bond leaves the control of the connection/disconnection to the fact of having the BT
        adapters On or Off
        Assuming the IDC23 will have the BT adapter always on, we will turn On/Off the BT adapter of the external
        device to stress test the reconnection

        Steps:
            - Repeat the following steps 'num_reconnect' times:
                - Turn off external device BT adapter
                - Assert no external device connected
                - Turn on external device BT adapter
                - Wait some time ('big_sleep_after_bt_on')
                - Assert external device connected
            - Make sure the pairing code generated by IDC is the same as the one showing on real phone
            - Accept pairing on real phone

        :param AndroidTarget device: An Android target module with AndroidTarget class properties
        :param str bt_device_name: name of the BT adapter of the expected device
        :param int num_reconnect: number of reconnections to be performed
        """
        small_sleep = 3  # seconds
        big_sleep_after_bt_on = 10  # seconds
        for i in range(num_reconnect):
            Connect.open_connectivity()
            device.turn_off_bt()
            time.sleep(small_sleep)
            device.lock_screen()
            time.sleep(small_sleep)
            assert_false(
                Connect.has_device_connected(self.test.apinext_target),
                "Expected to have no device connected, instead got one",
            )
            device.unlock_screen()
            time.sleep(small_sleep)
            device.turn_on_bt()
            time.sleep(big_sleep_after_bt_on)
            Launcher.go_to_home()
            Connect.open_connectivity()
            time.sleep(small_sleep)
            assert_true(
                Connect.has_device_connected(self.test.apinext_target), f"Failed to have bt ON during iteration {i}"
            )
            assert_true(
                Connect.validate_bt_paired_device(device=self.test.apinext_target, bt_device_name=bt_device_name)
            )
            time.sleep(small_sleep)
