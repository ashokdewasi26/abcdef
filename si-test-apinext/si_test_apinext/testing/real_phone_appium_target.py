import logging
import time

from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from si_test_apinext import DEFAULT_ADB_PORT, DEFAULT_PORT_SERVER, DEFAULT_SYSTEM_PORT
from si_test_apinext.real_phone.pages.android_pop_up_page import AndroidPopUp
from si_test_apinext.real_phone.pages.android_settings_page import AndroidSettings
from si_test_apinext.testing.real_phone_target import RealPhoneTarget

SERVER_LAUNCH_TIMEOUT = 600000
WEBDRIVERWAIT_TIMEOUT = 10

logger = logging.getLogger(__name__)


class RealPhoneAppiumTarget(RealPhoneTarget):
    url = f"http://localhost:{DEFAULT_PORT_SERVER}/wd/hub"
    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.new_command_timeout = 0  # means don't timeout
    options.uiautomator2_server_launch_timeout = SERVER_LAUNCH_TIMEOUT
    options.adb_port = DEFAULT_ADB_PORT
    # options.mjpeg_server_port = DEFAULT_MJPEG_SERVER_PORT # to clarify if this will be useful

    driver = None
    wb = None
    bt_name = ""

    def __init__(
        self,
        adb,
        android_home,
        atest,
        serial_number,
        system_port=DEFAULT_SYSTEM_PORT,
        tradefed_sh=None,
        _capture_adb_logcat=True,
        _clear_logcat_buffers=False,
        results_dir="",
    ):
        super(RealPhoneAppiumTarget, self).__init__(
            adb=adb,
            android_home=android_home,
            atest=atest,
            serial_number=serial_number,
            tradefed_sh=tradefed_sh,
            _capture_adb_logcat=_capture_adb_logcat,
            _clear_logcat_buffers=_clear_logcat_buffers,
        )
        self.options.udid = serial_number
        self.options.system_port = system_port
        self.results_dir = results_dir

    def setup(self):
        super(RealPhoneAppiumTarget, self).setup()

    def teardown(self):
        super(RealPhoneAppiumTarget, self).teardown()

    def from_config(self):
        super(RealPhoneAppiumTarget, self).from_config()

    @classmethod
    def setup_appium_driver(cls, number_of_tries=3):
        for i in range(number_of_tries):
            try:
                cls.driver = webdriver.Remote(cls.url, options=cls.options)
                cls.driver.update_settings({"enableMultiWindows": True, "waitForIdleTimeout": 500})
                cls.wb = WebDriverWait(cls.driver, WEBDRIVERWAIT_TIMEOUT)
                return
            except Exception as e:
                logger.warning(f"Failed to setup appium driver num {i}. Trying again. Msg: '{e}'")
        raise Exception(f"Failed to open Appium session after {number_of_tries} attempts")

    @classmethod
    def close_appium_driver(cls):
        if cls.driver:
            cls.driver.quit()
            cls.driver = None
            cls.wb = None

    def check_visibility_of_element(self, check_elem_visible):
        """Wait until visibility of check_elem_visible is found and return it

        An exception is raised by selenium if no element is found

        :param check_elem_visible: id of the element to check
        :type check_elem_visible: Element
        :return: visible element
        :rtype: Webdriver element
        """
        visible_element = self.wb.until(
            ec.visibility_of_element_located(check_elem_visible),
            message=f"Unable to find element:'{check_elem_visible.selector}'",
        )
        return visible_element

    def wait_to_check_visible_element(self, check_elem_visible):
        """Used for elements that take a while to show, but also might not show up at all"""
        try:
            visible_element = self.wb.until(
                ec.visibility_of_element_located(check_elem_visible),
                message=f"Unable to find element:'{check_elem_visible.selector}'",
            )
            return visible_element
        except TimeoutException:
            return None

    def turn_on_bt(self):
        """Turn on Bluetooth using adb"""
        self.execute_command(["am", "start", "-a", "android.bluetooth.adapter.action.REQUEST_ENABLE"])
        time.sleep(0.5)
        android_msg = self.driver.find_elements(*AndroidPopUp.MESSAGE_ID)
        if android_msg and android_msg[0].text == "Shell wants to turn on Bluetooth":
            allow_btn = self.driver.find_element(*AndroidPopUp.ALLOW_BUTTON)
            allow_btn.click()
            time.sleep(0.5)
        # This is required for pixel to show its bluetooth adapter
        self.bring_up_activity(activity=AndroidSettings.PACKAGE_NAME_ACTIVITY)
        time.sleep(0.5)
        connected_devices = self.check_visibility_of_element(AndroidSettings.CONNECTED_DEVICES)
        connected_devices.click()
        time.sleep(0.5)

    def turn_off_bt(self):
        """Turn off Bluetooth using adb"""
        self.execute_command(["am", "start", "-a", "android.bluetooth.adapter.action.REQUEST_DISABLE"])
        time.sleep(0.5)
        android_msg = self.driver.find_elements(*AndroidPopUp.MESSAGE_ID)
        if android_msg and android_msg[0].text == "Shell wants to turn off Bluetooth":
            allow_btn = self.driver.find_element(*AndroidPopUp.ALLOW_BUTTON)
            allow_btn.click()
            time.sleep(0.5)

    def get_bt_name(self):
        """Get the name of self bluetooth adapter

        :return: name
        :rtype: str
        """
        if not self.bt_name:
            self.bring_up_activity(activity=AndroidSettings.PACKAGE_NAME_ACTIVITY)
            time.sleep(1)
            connected_devices = self.check_visibility_of_element(AndroidSettings.CONNECTED_DEVICES)
            connected_devices.click()
            time.sleep(1)
            pair_new_device = self.check_visibility_of_element(AndroidSettings.PAIR_NEW_DEVICE)
            pair_new_device.click()
            time.sleep(1)
            device_name = self.check_visibility_of_element(AndroidSettings.DEVICE_NAME)
            device_name_summary = device_name.parent.find_element(*AndroidPopUp.SUMMARY)
            assert (
                device_name_summary.text
            ), f"Unable to get a valid name for real phone bluetooth, instead got: '{device_name_summary.text}'"
            self.bt_name = device_name_summary.text
        return self.bt_name
