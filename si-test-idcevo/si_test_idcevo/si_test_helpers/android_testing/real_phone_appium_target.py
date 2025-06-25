import base64
import logging
import os
import time

from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from si_test_idcevo import APPIUM_ELEMENT_TIMEOUT, DEFAULT_ADB_PORT, DEFAULT_PORT_SERVER, DEFAULT_SYSTEM_PORT
from si_test_idcevo.si_test_helpers.android_testing.real_phone_target import RealPhoneTarget
from si_test_idcevo.si_test_helpers.file_path_helpers import deconflict_file_path
from si_test_idcevo.si_test_helpers.pages.real_phone.android_pop_up_page import AndroidPopUp
from si_test_idcevo.si_test_helpers.pages.real_phone.android_settings_page import AndroidSettings

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
    options.allow_invisible_elements = True
    options.enable_multi_windows = True

    real_phone_driver = None
    web_driver_wait = None
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
                cls.real_phone_driver = webdriver.Remote(cls.url, options=cls.options)
                cls.real_phone_driver.update_settings({"enableMultiWindows": True, "waitForIdleTimeout": 500})
                cls.web_driver_wait = WebDriverWait(cls.real_phone_driver, WEBDRIVERWAIT_TIMEOUT)
                return
            except Exception as e:
                logger.warning(f"Failed attempt number {i} to setup appium driver. Trying again. Msg: '{e}'")
        raise Exception(f"Failed to open Appium session after {number_of_tries} attempts")

    @classmethod
    def close_appium_driver(cls):
        if cls.real_phone_driver:
            cls.real_phone_driver.quit()
            cls.real_phone_driver = None
            cls.web_driver_wait = None

    @classmethod
    def check_visibility_of_element(cls, check_element_visible, web_driver_timeout=APPIUM_ELEMENT_TIMEOUT):
        """Wait until visibility of check_element_visible is found and return it

        An exception is raised by selenium if no element is found

        :param check_element_visible: id of the element to check
        :type check_element_visible: Element
        :param web_driver_timeout: WebDriverWait timeout, default is APPIUM_ELEMENT_TIMEOUT
        :type web_driver_timeout: int
        :return: visible element
        :rtype: Webdriver element
        """

        visible_element = WebDriverWait(cls.real_phone_driver, web_driver_timeout).until(
            ec.visibility_of_element_located(check_element_visible),
            message=f"Unable to find element:'{check_element_visible.selector}' "
            + f"after waiting {web_driver_timeout} seconds",
        )

        return visible_element

    @classmethod
    def wait_to_check_visible_element(cls, check_elem_visible, web_driver_timeout=APPIUM_ELEMENT_TIMEOUT):
        """Used for elements that take a while to show, but also might not show up at all"""
        try:
            visible_element = WebDriverWait(cls.real_phone_driver, web_driver_timeout).until(
                ec.visibility_of_element_located(check_elem_visible),
                message=f"Unable to find element:'{check_elem_visible.selector}' "
                + f"after waiting {web_driver_timeout} seconds",
            )
            return visible_element
        except TimeoutException:
            return None

    def turn_on_bt(self):
        """Turn on Bluetooth using adb"""
        self.execute_command(["am", "start", "-a", "android.bluetooth.adapter.action.REQUEST_ENABLE"])
        time.sleep(0.5)
        android_msg = self.real_phone_driver.find_elements(*AndroidPopUp.MESSAGE_ID)
        time.sleep(3)
        self.take_real_phone_target_screenshot(self.results_dir, "After find element AndroidPopUp.MESSAGE_ID")
        if android_msg and android_msg[0].text == "Shell wants to turn on Bluetooth":
            allow_btn = self.real_phone_driver.find_element(*AndroidPopUp.ALLOW_BUTTON)
            allow_btn.click()
            time.sleep(0.5)

    def turn_off_bt(self):
        """Turn off Bluetooth using adb"""
        self.execute_command(["am", "start", "-a", "android.bluetooth.adapter.action.REQUEST_DISABLE"])
        time.sleep(0.5)
        android_msg = self.real_phone_driver.find_elements(*AndroidPopUp.MESSAGE_ID)
        if android_msg and android_msg[0].text == "Shell wants to turn off Bluetooth":
            allow_btn = self.real_phone_driver.find_element(*AndroidPopUp.ALLOW_BUTTON)
            allow_btn.click()
            time.sleep(0.5)

    def get_bt_name(self):
        """Get the name of self bluetooth adapter

        :return: name
        :rtype: str
        """
        if not self.bt_name:
            self.bring_up_activity(activity=AndroidSettings.PACKAGE_NAME_ACTIVITY)
            time.sleep(0.5)
            self.take_real_phone_target_screenshot(self.results_dir, "SETTINGS")
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

    def take_real_phone_target_screenshot(self, results_dir, file_name):
        """Take a screenshot using adb
        :param results_dir: path to results folder
        :type results_dir: str
        :param file_name: name for created file
        :type file_name: str
        """
        file_name = os.path.join(results_dir, file_name) if results_dir not in file_name else file_name
        file_name = str(file_name + ".png") if ".png" not in file_name else file_name
        file_name = deconflict_file_path(file_name, extension=".png")
        self.take_screenshot(file_name)

    def start_recording(self):
        try:
            self.real_phone_driver.start_recording_screen()
            self.record_test = True
        except Exception as e:
            logger.error(f"Found exception while trying to start video recording on {self.results_dir}, error: '{e}'")

    def stop_recording(self, video_name):
        try:
            raw_data = self.real_phone_driver.stop_recording_screen()
            # If video_name is a results path ok, if not make it be
            if self.results_dir not in video_name:
                video_path = os.path.join(self.results_dir, video_name)
            else:
                video_path = video_name
            video_path = f"{video_path}.mp4"
            final_video_path = deconflict_file_path(video_path)

            with open(final_video_path, "wb") as vd:
                vd.write(base64.b64decode(raw_data))
        except Exception as e:
            logger.error(f"Found exception while trying to save video recording on {self.results_dir}, error: '{e}'")
