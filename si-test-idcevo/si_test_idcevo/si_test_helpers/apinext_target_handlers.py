# Copyright (C) 2023. BMW CTW PT. All rights reserved.

import configparser
import logging
import os

from mtee.testing.support.target_share import TargetShare as TargetShareMTEE
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee_apinext.enablers.support.android_generic_hid_mapping import AndroidGenericKeyCodes
from mtee_apinext.plugins.android_target import AndroidTarget
from mtee_apinext.targets import TargetShare
import sh
from si_test_idcevo.si_test_helpers.apinext_input_events import ApinextInputEvents
from si_test_idcevo.si_test_helpers.dmverity_helpers import adb_disable_verity
from si_test_idcevo.si_test_helpers.file_path_helpers import create_custom_results_dir, deconflict_file_path
from tee.tools.diagnosis import DiagClient

CHECK_LAUNCHER_ACTIVITY = "com.bmwgroup.idnext.launcher/.IdxMainActivity"
CHECK_ALL_APPS_ACTIVITY = "com.bmwgroup.idnext.launcher/.allapps.IdxAppOverviewActivity"
LOCATION_PERMISSIONS = ("android.permission.ACCESS_FINE_LOCATION", "android.permission.ACCESS_COARSE_LOCATION")
MTEE_HU_TRAAS_CFG = os.path.join("/ws/home", "mtee-hu.cfg")

logger = logging.getLogger(__name__)

KNOWN_TARGETS = ["idcevo", "rse26", "cde"]
LIST_MAIN_DISPLAY_ID = {
    "idcevo": "4633128631561747456",
    "rse26": "4633128631561747456",
    "cde": "4633128631561747456",
}
LIST_HUD_DISPLAY_ID = {
    "hud": "4633128631561747457",
    "phud_0": "4633128631561747460",
    "phud_1": "4633128631561747459",
    "phud_2": "4633128631561747458",
}


class IDCEvoApinextTargetHandler(ApinextInputEvents):
    mtee_target = None
    apinext_target = None
    results_dir = None
    disabled_android_dm_verity = False

    def setup_apinext_target(self):
        """Setup apinext target instance"""
        if not self.mtee_target:
            self.setup_target()

        self.apinext_target = TargetShare().target
        self.apinext_target.setup()
        self.apinext_target.wait_for_boot_completed_flag(wait_time=30)
        self.change_language(language="en")

    def setup_target(self):
        """Setup mtee target instance"""
        self.mtee_target = TargetShareMTEE().target
        # Define if currently in farm or rack env
        self._test_rack = self.mtee_target.has_capability(TE.test_bench.rack)
        self.setup_android_serials_id()

        logger.info("Target name: %s", self.mtee_target.options.target)
        target_plugin = AndroidTarget()
        if self.mtee_target.options.target in KNOWN_TARGETS:
            product_type = self.mtee_target.options.target
        else:
            raise AssertionError(f"Unknown target: '{self.mtee_target.options.target}'")
        target_class = target_plugin.valid_products[product_type]
        TargetShare().target = target_class(
            adb=sh.adb,
            android_home="/opt/android-sdk",
            atest=None,
            fastboot=sh.fastboot,
            _capture_adb_logcat=False,
        )
        logger.info(f"Configuring target class {target_class.__name__} and setting TargetShare target")

        self.diagnostic_client = DiagClient(self.mtee_target.diagnostic_address, self.mtee_target.ecu_diagnostic_id)

    def setup_vcar_manager(self):
        """Setup vcar manager instance"""
        self.vcar_manager = TargetShareMTEE().vcar_manager

    def take_apinext_target_screenshot(self, results_dir, file_name, display_id=None):
        """Take a screenshot using adb
        :param results_dir: path to results folder
        :type results_dir: str
        :param file_name: name for created file
        :type file_name: str
        :return: file_path: path to created file
        """
        self.apinext_target.wait_for_boot_completed_flag()
        file_name = str(file_name + ".png") if ".png" not in file_name else file_name
        file_path = os.path.join(results_dir, file_name) if results_dir not in file_name else file_name
        file_path = deconflict_file_path(file_path, extension=".png")
        display_id = display_id if display_id else LIST_MAIN_DISPLAY_ID.get(self.mtee_target.options.target.lower())
        self.apinext_target.take_screenshot(file_path, display_id=display_id)
        return file_path

    def setup_android_serials_id(self):
        """If currently on a test rack get the HU and real phone android serial
        identifiers from the local config file"""
        if self._test_rack:
            self._real_phone_android_serial = self.get_android_serial_id(
                config_var_name="ext-real-phone-android-serial", config_section="nosetests"
            )

    def setup_rack_provisioning(self):
        """
        Trigger HU provisioning and grant permission for Network devtools app
        """
        self.diagnostic_client.steuern_provisioning()
        user = self.apinext_target.get_current_user_id()
        command = 'dumpsys package com.bmwgroup.apinext.networkdevtool | grep -A 10 "runtime permissions:"'
        result = self.apinext_target.execute_command(command, privileged=True)
        runtime_permissions = result.stdout.decode("utf-8")
        for permission in LOCATION_PERMISSIONS:
            if permission in runtime_permissions:
                command = f"pm grant --user {user} com.bmwgroup.apinext.networkdevtool {permission}"
                self.apinext_target.execute_command(command, privileged=True)

    def set_language_to_default(self):
        """Change language to default language set by target_manager if it is changed in previous test or actions.
        If needed change the language in specific test file.
        """

        current_language = self.vcar_manager.execute_remote_method("get_language")
        if self.default_language != current_language:
            logger.info(f"Changing language: {current_language} to default language: {self.default_language}")
            self.vcar_manager.execute_remote_method("set_language", self.default_language)

    def setup_results_dir(self, current_test_name="undefined_test"):
        """
        Create results folder for calling test inside results folder
        :param current_test_name: name of current test, defaults to "undefined_test"
        :type current_test_name: str, optional
        """
        base_dir = ""
        if self._test_rack:
            base_dir = self.mtee_target.options.result_dir
        else:
            base_dir = os.getcwd()
        out_dir = create_custom_results_dir(current_test_name, base_dir)
        self.results_dir = out_dir

    def change_language(self, language="en"):
        """Changes the system language on the Android target.

        This method sends a broadcast intent to change the device's language using the specified language code.

        Args:
            language (str, optional): The language and locale code to set (e.g., 'en', 'de-DE'). Defaults to 'en'.
                For supported languages, refer to:
                    - http://www.apps4android.org/?p=3695
                    - https://asc.bmwgroup.net/wiki/display/APINEXT/Cerence+Country+Language+Matrix

        Raises:
            AssertionError: If the command execution does not return the expected result.

        Expected Result:
            The command output should contain "result=0" indicating success.
        """
        command = (
            f"am broadcast -n com.bmwgroup.idnext.settings/.data.language.ChangeLocale "
            f"--receiver-permission android.permission.CHANGE_CONFIGURATION --es language {language}"
        )
        try:
            self.apinext_target.execute_command(command)
        except Exception as e:
            logger.info(f"Failed to change language: '{e}'")

    def connect_to_internet(self):
        """
        Connect the target to internet
        """
        if not self.mtee_target.has_capability(TE.test_bench.rack):
            logger.info("Connect to internet ...")
            if self.apinext_target.check_internet_connectivity():
                logger.info("Target is already connected to internet. Skipping connection setup")
                return
            self.apinext_target.turn_off_airplane_mode()
            self.apinext_target.bootstrap_wifi()
            self.mtee_target.reboot()
            self.apinext_target.wait_for_boot_completed_flag(wait_time=90)
            self.apinext_target.enable_wifi_service()
            self.apinext_target.connect_to_wifi()
            if not self.apinext_target.check_internet_connectivity():
                raise RuntimeError("Internet connection was not successful")
            logger.info("Connect to internet ... done")
        else:
            logger.info("TRAAS setup should have backend connectivity and provisioning by default")

    @classmethod
    def grant_permission(cls, package, permission):
        """
        Grant permission for a particular package

        :param package - Android package
        :param permission - requested permission for package
        """
        user = cls.apinext_target.get_current_user_id()
        command = f"pm grant --user {user} {package} {permission}"
        cls.apinext_target.execute_command(command, privileged=True)

    def get_android_serial_id(
        self,
        config_var_name,
        config_section="nosetests",
        config_file_path=MTEE_HU_TRAAS_CFG,
    ):
        """If currently on a test rack get the HU and real phone android serial
        identifiers from the local config file"""
        mtee_conf = configparser.ConfigParser()
        mtee_conf[config_section] = {}
        mtee_conf.read(config_file_path)
        return mtee_conf[config_section].get(config_var_name, None)

    def force_stop_package(self, list_of_packages=["com.bmwgroup.apinext.livevehicle"]):
        """
        Packages where you want to make a forced stop, to the packages that appear between tests

        :param list_of_packages: list of packages where you want to make a forced stop
        """
        user = self.apinext_target.get_current_user_id()
        for package in list_of_packages:
            grep_package = ["pm", "list", "packages", "--user", user, "-e", package]
            response = self.apinext_target.execute_command(grep_package)
            output = response.stdout.decode("utf-8").strip().replace(" ", "")
            if package in output:
                stop_package = ["am", "force-stop", package]
                self.apinext_target.execute_command(stop_package)

    def disable_dmverity_android(self):
        """
        Disable dmverity on the target
        """
        if not self.disabled_android_dm_verity:
            self.disabled_android_dm_verity = bool(adb_disable_verity())
            logger.info(f"Disabled dmverity on the android target: {self.disabled_android_dm_verity}")

    def check_service_command_execution(self, service, output) -> int:
        expected_output = f"Enabling {service}"
        if expected_output in output:
            return 1
        else:
            return 0

    def get_bluetooth_state_via_adb_command(self) -> int:
        """
        Gets the Bluetooth state via adb
        Returns:
        0 - Bluetooth disable, 1 - Bluetooth enable
        """
        command_output = self.apinext_target.execute_command("settings get global bluetooth_on")
        bluetooth_state = int(command_output.stdout.decode("utf-8").strip())
        return bluetooth_state

    def turn_on_bluetooth_via_adb_commands(self) -> int:
        """
        Executes the turn on bluetooth command via adb
        Returns:
        int: 0 if Bluetooth is disabled, 1 if Bluetooth enabled.
        """
        command_output = self.apinext_target.execute_command("su 0 settings put global bluetooth_on 1")
        bluetooth_state = command_output.stdout.decode("utf-8").strip()
        return self.check_service_command_execution("Bluetooth", bluetooth_state)

    def turn_off_bluetooth_via_adb_commands(self) -> int:
        """
        Executes the turn off bluetooth command via adb

        Returns:
        int: 0 if Bluetooth is disabled, 1 if Bluetooth enabled.
        """
        command_output = self.apinext_target.execute_command("settings put global bluetooth_on 0")
        bluetooth_state = command_output.stdout.decode("utf-8").strip()
        return self.check_service_command_execution("Bluetooth", bluetooth_state)

    def get_wifi_state_via_adb_commands(self) -> int:
        """
        Gets the Wifi state via adb
        Returns:
        0 - Wifi disable, 1 -Wifi enable
        """
        command_output = self.apinext_target.execute_command("settings get global wifi_on")
        wifi_state = int(command_output.stdout.decode("utf-8").strip())
        return wifi_state

    def turn_on_wifi_via_adb_commands(self) -> int:
        """
        Executes the turn on wifi command via adb

        Returns:
        int: 0 if Bluetooth is disabled, 1 if Bluetooth enabled.
        """
        command_output = self.apinext_target.execute_command("su 0 svc wifi enable")
        wifi_state = command_output.stdout.decode("utf-8").strip()
        return self.check_service_command_execution("Wifi", wifi_state)

    def turn_off_wifi_via_adb_commands(self) -> int:
        """
        Executes the turn off wifi command via adb
        Returns:
        int: 0 if Bluetooth is disabled, 1 if Bluetooth enabled.
        """
        command_output = self.apinext_target.execute_command("su 0 svc wifi disable")
        wifi_state = command_output.stdout.decode("utf-8").strip()
        return self.check_service_command_execution("Wifi", wifi_state)

    def go_back_android_keyevent(self):
        """
        Simulates the "Back" button press on an Android device by sending the corresponding keycode.

        This method utilizes the Android key event system to mimic the behavior of the "Back" button,
        which can be useful for navigation or automation tasks in Android applications.

        Returns:
            None
        """
        self.apinext_target.send_keycode(AndroidGenericKeyCodes.KEYCODE_BACK)

    def go_home_android_keyevent(self):
        """
        Simulates the "Home" button press on an Android device by sending the corresponding keycode.

        This method utilizes the Android key event system to mimic the behavior of the "Home" button,
        which can be useful for navigation or automation tasks in Android applications.

        Returns:
            None
        """
        self.apinext_target.send_keycode(AndroidGenericKeyCodes.KEYCODE_HOME)
