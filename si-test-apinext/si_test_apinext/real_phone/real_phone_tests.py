import logging
import os
import subprocess
from unittest import skipIf

import sh
import si_test_apinext.util.driver_utils as utils
from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT
from si_test_apinext import REAL_PHONE_SYSTEM_PORT
from si_test_apinext.idc23.pages.connectivity_page import ConnectivityPage
from si_test_apinext.idc23.pages.launcher_page import LauncherPage
from si_test_apinext.idc23.traas.bluetooth.helpers.bluetooth_utils import BluetoothUtils
from si_test_apinext.testing.real_phone_appium_target import RealPhoneAppiumTarget
from si_test_apinext.testing.test_base import TestBase
from si_test_apinext.util.mtee_utils import MteeUtils

real_phone_present = bool(TestBase.get_android_serial_id(config_var_name="ext-real-phone-android-serial"))
logger = logging.getLogger(__name__)
target = TargetShare().target
android_home = os.environ.get("ANDROID_HOME")


@skipIf(
    not (target.has_capability(TEST_ENVIRONMENT.test_bench.rack) and real_phone_present),
    "Test only applicable for test racks with Real Phone present",
)
class TestRealPhone:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.bluetooth_utils = BluetoothUtils(cls.test)
        cls.pixel5 = None
        cls.mtee_utils = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)

        if real_phone_present:
            cls.pixel5 = RealPhoneAppiumTarget(
                adb=sh.adb,
                android_home=android_home,
                atest=None,
                serial_number=cls.test._real_phone_android_serial,
                system_port=REAL_PHONE_SYSTEM_PORT,
                results_dir=cls.test.results_dir,
            )
            cls.pixel5.restart_android(wait_for_boot_completion=True)

    @classmethod
    def teardown_class(cls):
        if cls.pixel5:
            cls.pixel5.close_appium_driver()
        cls.test.quit_driver()

    def setup(self):
        utils.pop_up_check(self.test)
        utils.ensure_no_alert_popup(self.test.results_dir, self.test.driver, self.test.apinext_target)
        if self.pixel5:
            self.pixel5.unlock_screen()
            self.pixel5.press_home()
            utils.start_recording(self.pixel5)
        utils.start_recording(self.test)

    def teardown(self):
        utils.pop_up_check(self.test)
        utils.ensure_no_alert_popup(self.test.results_dir, self.test.driver, self.test.apinext_target)
        if self.pixel5:
            utils.take_apinext_target_screenshot(
                apinext_target=self.pixel5,
                results_dir=self.test.results_dir,
                file_name="screenshot_pixel5_teardown",
            )
            utils.stop_recording(self.pixel5, "pixel5")
            self.pixel5.lock_screen()
        video_name = "TestRealPhone"
        utils.stop_recording(self.test, video_name)

    @skipIf(
        not (target.has_capability(TEST_ENVIRONMENT.test_bench.rack) and real_phone_present),
        "Test only applicable for test racks with Real Phone present",
    )
    @utils.gather_info_on_fail
    def test_00_real_phone_devices_setup_precondition(self):
        """Test 00 Real Phone - Validate both android devices connections

        Validate both android devices (IDC23 and real phone) are correctly setup and register the output
        Start Real Phone appium session
        """
        txt_name = self.test.results_dir + "/test_real_phone_00"
        all_devices = subprocess.run(
            ["adb", "devices", "-l"],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        with open(f"{txt_name}.txt", "a") as f:
            f.write("Test Real Phone 00")
            f.write(f"\n\ntest_real_phone adb devices {all_devices.stdout.decode()}")

        self.pixel5.setup_appium_driver()
        with open(f"{txt_name}.txt", "a") as f:
            f.write("Test Real Phone 00 Part 2")
            f.write(f"\n\nself.test.driver.session::: {self.test.driver.session}")
            f.write(f"\n\nself.pixel5.driver.session::: {self.pixel5.driver.session}")

    @skipIf(
        not (target.has_capability(TEST_ENVIRONMENT.test_bench.rack) and real_phone_present),
        "Test only applicable for test racks with Real Phone present",
    )
    @utils.gather_info_on_fail
    def test_01_real_phone_bt_pairing(self):
        """Test 01 Real Phone - Basic BT Pairing"""
        # Turn on IDC23 bluetooth and remove all paired devices
        self.bluetooth_utils.turn_on_bluetooth()
        ConnectivityPage.remove_all_paired_devices()
        LauncherPage.go_to_home()
        self.pixel5.press_home()
        # Turn on real phone bluetooth and get it's name
        self.pixel5.turn_on_bt()
        # Wait for Bluetooth name to display on UI
        self.pixel5.time.sleep(1)
        pixel5_bt_name = self.pixel5.get_bt_name()

        self.bluetooth_utils.connect_new_device(real_phone=self.pixel5, new_device_name=pixel5_bt_name)
        LauncherPage.go_to_home()
        # Validate the real device is paired and connected by making sure IDC23 has a connected device
        #  and this device has real phone name
        ConnectivityPage.validate_bt_paired_device(device=self.test.apinext_target, bt_device_name=pixel5_bt_name)

    @skipIf(
        not (target.has_capability(TEST_ENVIRONMENT.test_bench.rack) and real_phone_present),
        "Test only applicable for test racks with Real Phone present",
    )
    @utils.gather_info_on_fail
    def test_02_real_phone_bluetooth_reboot(self):
        """Test 02 Real Phone - Resume pairing after IDC23 reboot

        *Steps*
        1. Pair external device Bluetooth with IDC
        2. Reboot IDC23
        3. Validate BT host pairing resumed
        """

        pixel5_bt_name = self.pixel5.get_bt_name()
        if not ConnectivityPage.validate_bt_paired_device(
            device=self.test.apinext_target, bt_device_name=pixel5_bt_name
        ):
            self.bluetooth_utils.connect_new_device(real_phone=self.pixel5, new_device_name=pixel5_bt_name)

        # Reboot IDC23
        self.mtee_utils.restart_target_and_driver(self.test)
        utils.pop_up_check(self.test)
        utils.ensure_no_alert_popup(self.test.results_dir, self.test.driver, self.test.apinext_target)
        ConnectivityPage.validate_bt_paired_device(device=self.test.apinext_target, bt_device_name=pixel5_bt_name)

    @skipIf(
        not (target.has_capability(TEST_ENVIRONMENT.test_bench.rack) and real_phone_present),
        "Test only applicable for test racks with Real Phone present",
    )
    @utils.gather_info_on_fail
    def test_03_real_phone_bluetooth_reconnect_stress(self):
        """Test 03 Real Phone - Stress test reconnection

        Like simulating an out of range device and then returning to range
        *Steps*
        1. Pair external device Bluetooth with IDC
        2. Validate pairing
        3. Repeat for 10 times:
            4. Disconnect Real Phone (Turn off BT adapter)
            5. Connect Real Phone (Turn on BT adapter)
            6. Validate pairing
        """
        number_reconnect = 10
        self.pixel5.turn_on_bt()
        pixel5_bt_name = self.pixel5.get_bt_name()
        if not ConnectivityPage.validate_bt_paired_device(
            device=self.test.apinext_target, bt_device_name=pixel5_bt_name
        ):
            self.bluetooth_utils.connect_new_device(real_phone=self.pixel5, new_device_name=pixel5_bt_name)

        ConnectivityPage.validate_bt_paired_device(device=self.test.apinext_target, bt_device_name=pixel5_bt_name)

        self.bluetooth_utils.reconnect_device(self.pixel5, pixel5_bt_name, number_reconnect)
