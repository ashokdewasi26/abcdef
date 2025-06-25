# Copyright (C) 2025. BMW Car IT. All rights reserved.
import logging
import os
import subprocess
import time
from unittest import SkipTest, skipIf

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT
import sh
import si_test_idcevo.si_test_helpers.test_helpers as utils
from si_test_idcevo import REAL_PHONE_SYSTEM_PORT
from si_test_idcevo.si_test_helpers.android_testing.real_phone_appium_target import RealPhoneAppiumTarget
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.bluetooth_utils import BluetoothUtils
from si_test_idcevo.si_test_helpers.pages.idcevo.connectivity_page import ConnectivityPage as Connectivity
from si_test_idcevo.si_test_helpers.pages.idcevo.launcher_page import LauncherPage as Launcher
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target


logger = logging.getLogger(__name__)
target = TargetShare().target
ANDROID_HOME = os.environ.get("ANDROID_HOME")


@skipIf(
    not (target.has_capability(TEST_ENVIRONMENT.test_bench.rack)),
    "Test class only applicable for test racks",
)
class TestRealPhone:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(enable_appium=True, root=True)
        cls.bluetooth_utils = BluetoothUtils(cls.test)
        cls.real_phone_present = bool(cls.test.get_android_serial_id(config_var_name="ext-real-phone-android-serial"))
        cls.real_phone_target = None

        if cls.real_phone_present:
            cls.real_phone_target = RealPhoneAppiumTarget(
                adb=sh.adb,
                android_home=ANDROID_HOME,
                atest=None,
                serial_number=cls.test._real_phone_android_serial,
                system_port=REAL_PHONE_SYSTEM_PORT,
                results_dir=cls.test.results_dir,
            )
            cls.real_phone_target.restart_android(wait_for_boot_completion=True)
        else:
            raise SkipTest("No real phone connected to the test rack!")

        try:
            Connectivity.check_bluetooth_state_ui()
        except AssertionError as e:
            logger.info(f"Fail in setup_class: '{e}'\nGoing to reboot target")
            cls.test.teardown_base_class()
            cls.test.mtee_target.reboot(prefer_softreboot=False, check_target=True)
            cls.test.setup_base_class(enable_appium=True, root=True)
            cls.test.apinext_target.wait_for_boot_completed_flag()
            wait_for_application_target(cls.test.mtee_target)
            cls.bluetooth_utils = BluetoothUtils(cls.test)

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()
        cls.real_phone_target.close_appium_driver()

    def setup(self):
        if self.real_phone_target:
            self.real_phone_target.unlock_screen()
            self.real_phone_target.press_home()
            time.sleep(5)
            self.real_phone_target.start_recording()
        self.test.start_recording()

    def teardown(self):
        if self.real_phone_target:
            self.real_phone_target.take_real_phone_target_screenshot(
                results_dir=self.test.results_dir,
                file_name="screenshot_real_phone_target_teardown",
            )
            self.real_phone_target.stop_recording("real_phone")
            self.real_phone_target.lock_screen()
        video_name = "TestRealPhone"
        self.test.stop_recording(video_name)

    @utils.gather_info_on_fail
    def test_00_real_phone_devices_setup_precondition(self):
        """Test 00 Real Phone - Validate both android devices connections
        Steps:
            1. List all connected adb devices in current session
            2. Write IDCEvo and Real Phone appium driver capabilities to a text file

        Expected Outcome:
            1. Both IDCEvo and Real Phone appium sessions are correctly setup
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

        self.real_phone_target.setup_appium_driver()
        try:
            with open(f"{txt_name}.txt", "a") as f:
                f.write("Test Real Phone 00 Part 2")
                f.write(f"\n\nself.test.driver.capabilities::: {self.test.driver.capabilities}")
                f.write(
                    "\n\nself.real_phone_target.driver.capabilities::: "
                    f"{self.real_phone_target.real_phone_driver.capabilities}"
                )
        except Exception as e:
            logger.info(f"Failed to get driver capabilities info. Error: {e}")

    @utils.gather_info_on_fail
    def test_01_real_phone_bt_pairing(self):
        """Test 01 Real Phone - Basic BT Pairing
        Steps:
            1. Turn on IDCEvo bluetooth and remove all paired devices
            2. Turn on Real Phone bluetooth and get its name
            3. Select option to connect new device on IDCEvo
            4. Select IDCevo bluetooth device name on Real Phone
            5. Check if pairing codes match and accept pairing
            6. Ensure Real Phone device is paired and connected to IDCEvo

        Expected Outcome:
            1. Real Phone is paired and connected to IDCEvo
        """
        Connectivity.turn_on_bluetooth_ui()
        Connectivity.remove_all_paired_devices(self.test)

        self.real_phone_target.press_home()
        self.real_phone_target.turn_on_bt()
        time.sleep(1)
        real_phone_bt_name = self.real_phone_target.get_bt_name()

        self.bluetooth_utils.connect_new_device(self.real_phone_target)
        Launcher.go_to_home(self.test)
        assert Connectivity.validate_bt_paired_device(
            device=self.test.apinext_target, bt_device_name=real_phone_bt_name
        ), f"Failed to validate {real_phone_bt_name} bluetooth connection to IDCEvo"
