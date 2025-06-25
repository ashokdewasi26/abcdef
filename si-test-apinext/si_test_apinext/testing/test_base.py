# import base64 # Temporary in case of need to record a video
import configparser
import inspect
import logging
import os
from pathlib import Path
import re

import sh
import si_test_apinext.util.driver_utils as utils
from appium.options.android import UiAutomator2Options
from mtee.testing.support.target_share import TargetShare as TargetShareMTEE
from mtee.testing.test_environment import TEST_ENVIRONMENT
from mtee_apinext.plugins.android_target import AndroidTarget
from mtee_apinext.targets import TargetShare
from selenium.webdriver.common.utils import is_url_connectable
from selenium.webdriver.support.ui import WebDriverWait
from si_test_apinext import DEFAULT_ADB_PORT, DEFAULT_PORT_SERVER, DEFAULT_SYSTEM_PORT
from si_test_apinext.common.pages.base_page import BasePage
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.padi.pages.ce_area_page import CEAreaPage
from si_test_apinext.padi.pages.padi_page import PadiPage as Padi
from tee.tools.diagnosis import DiagClient

logger = logging.getLogger(__name__)

APPIUM_OPEN_SESSION_ATTEMPTS = 3
APPIUM_CLOSE_SESSION_ATTEMPTS = 3
LOCATION_PERMISSIONS = ("android.permission.ACCESS_FINE_LOCATION", "android.permission.ACCESS_COARSE_LOCATION")


SERVER_LAUNCH_TIMEOUT = 600000
MTEE_HU_TRAAS_CFG = os.path.join("/ws/home", "mtee-hu.cfg")


class TestBase(object):
    # This class is a singleton
    # The purpose of this class is to be reused by all IDC tests, to avoid having more than one
    # appium session open and more than one target handler

    __instance__ = None

    _common_desired_caps = dict(
        platformName="Android",
        automationName="UiAutomator2",
        newCommandTimeout=0,  # means don't timeout
        uiautomator2ServerLaunchTimeout=600000,
        adbExecTimeout=60000,
        noReset=True,
    )

    _idc_desired_caps = dict(
        appPackage=Launcher.PACKAGE_NAME,
        appActivity=Launcher.PACKAGE_ACTIVITY,
    )
    _idc_desired_caps.update(_common_desired_caps)

    _padi_desired_caps = dict(
        appPackage=Padi.PACKAGE_NAME,
        appActivity=Padi.PACKAGE_ACTIVITY,
        clearSystemFiles=True,
    )
    _padi_desired_caps.update(_common_desired_caps)

    _padi_desired_caps_ml = dict(
        appPackage=Padi.PACKAGE_NAME,
        appActivity=Padi.PACKAGE_ACTIVITY_ML,
        clearSystemFiles=True,
    )
    _padi_desired_caps_ml.update(_common_desired_caps)

    def __init__(self) -> None:
        self.__apinext_target = None
        self.__driver = None
        self.__wb = None
        self._desired_caps = None
        self.opened_session = None
        self.__results_dir = None
        self.__mtee_target = None
        self.record_test = None
        self.bluetooth_on = False
        self._appium_options = None
        self._hu_android_serial = None
        self._real_phone_android_serial = None
        self.__diagnostic_client = None
        self.vcar_manager = None
        self.default_language = None
        self.__branch_name = None

    def __new__(cls):
        """Method to create singleton instance"""
        if not cls.__instance__:
            cls.__instance__ = super(TestBase, cls).__new__(cls)
        return cls.__instance__

    @staticmethod
    def get_instance():
        """Static method to fetch the current instance"""
        if not TestBase.__instance__:
            TestBase()
        return TestBase.__instance__

    @property
    def apinext_target(self):
        return self.__apinext_target

    @apinext_target.setter
    def apinext_target(self, value):
        self.__apinext_target = value
        BasePage.apinext_target = value

    @property
    def driver(self):
        return self.__driver

    @driver.setter
    def driver(self, value):
        self.__driver = value
        BasePage.driver = value

    @property
    def wb(self):
        return self.__wb

    @wb.setter
    def wb(self, value):
        self.__wb = value
        BasePage.wb = value

    @property
    def results_dir(self):
        return self.__results_dir

    @results_dir.setter
    def results_dir(self, value):
        self.__results_dir = value
        BasePage.results_dir = value

    @property
    def mtee_target(self):
        return self.__mtee_target

    @mtee_target.setter
    def mtee_target(self, value):
        self.__mtee_target = value
        BasePage.mtee_target = value

    @property
    def diagnostic_client(self):
        return self.__diagnostic_client

    @diagnostic_client.setter
    def diagnostic_client(self, value):
        self.__diagnostic_client = value
        BasePage.diagnostic_client = value

    @property
    def branch_name(self):
        return self.__branch_name

    @branch_name.setter
    def branch_name(self, value):
        self.__branch_name = value
        BasePage.branch_name = value

    @classmethod
    def get_android_serial_id(
        cls,
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

    def setup_android_serials_id(self):
        """If currently on a test rack get the HU and real phone android serial
        identifiers from the local config file"""
        if self._test_rack:
            self._hu_android_serial = self.get_android_serial_id(
                config_var_name="hu-android-serial", config_section="nosetests"
            )
            self._real_phone_android_serial = self.get_android_serial_id(
                config_var_name="ext-real-phone-android-serial", config_section="nosetests"
            )

    def setup_target(self):
        mtee_target = TargetShareMTEE().target
        # Define if currently in farm or rack env
        self._test_rack = mtee_target.has_capability(TEST_ENVIRONMENT.test_bench.rack)
        self.setup_android_serials_id()

        logger.info("Target name: %s", mtee_target.options.target)
        # The following code is necessary due to mismatch from dictionary on valid products and  options target name
        if "rse" in mtee_target.options.target:
            product_type = "padi22_b2"
        # The following code is necessary due to no C1 target exist in mtee-apinext
        elif "idc" in mtee_target.options.target:
            product_type = str(mtee_target.options.target) + "_b2"
        else:
            raise AssertionError(f"Unknown target: '{str(mtee_target.options.target)}'")
        target_plugin = AndroidTarget()
        target_class = target_plugin.valid_products[product_type]
        TargetShare().target = target_class(
            adb=sh.adb,
            android_home="/opt/android-sdk",
            atest=None,
            fastboot=sh.fastboot,
            serial_number=self._hu_android_serial,
            _capture_adb_logcat=False,
        )
        logger.info(
            "Configuring target class %s and setting TargetShare target",
            target_class.__name__,
        )

    def setup_base_class(self, root=False, appium=True):
        if not self.apinext_target:
            logger.info("Doing setup_class() because apinext_target not defined on " + str(self.__class__.__name__))
            self.setup_apinext_target()
            if root:
                self.apinext_target.root()

        # Get calling test name
        stack_inspect = inspect.stack()
        frame_info = stack_inspect[1]
        filepath = frame_info[1]
        current_test_name = Path(filepath).stem
        logger.debug(f"Calling test name: '{current_test_name}'")
        self.setup_results_dir(current_test_name)
        setup_screenshot = os.path.join(self.results_dir, "setup_target_ready_MainActivity.png")
        self.apinext_target.take_screenshot(setup_screenshot)

        if appium and (not self.driver or not is_url_connectable(DEFAULT_PORT_SERVER)):
            logger.info("Doing setup_class() because appium driver not defined on " + str(self.__class__.__name__))
            self.setup_driver()
        # Change language to default language set by target_manager if it is changed in previous test or actions.
        # If needed change the language in specific test file.
        current_language = self.vcar_manager.execute_remote_method("get_language")
        if self.default_language != current_language:
            logger.info(f"Changing language: {current_language} to default language: {self.default_language}")
            self.vcar_manager.execute_remote_method("set_language", self.default_language)

        # Makes sure that on the test class setup we have no streaming apps impeding us to take screenshots
        # Might need to be change in the future in case we want to validate content from cearea or hdmiapp
        # Check PURITY-112 that will allows to take screenshot even with cearea hdmiapp available
        self.stop_padi_video_streaming_apps()

    def teardown_base_class(self):
        # # Temporary in case of need to record a video
        # raw_data = self.driver.stop_recording_screen()
        # with open("test_launcher.mp4", "wb") as vd:
        #     vd.write(base64.b64decode(raw_data))

        self.quit_driver()

        self.apinext_target.root()
        self.apinext_target.wait_for_adb_device(wait_time=60)
        self.apinext_target.disable_heads_up_notifications()
        self.apinext_target.execute_adb_command(["shell", "am", "force-stop", utils.APPIUM_PACKAGES[1]])
        self.apinext_target.execute_adb_command(["shell", "am", "force-stop", utils.APPIUM_PACKAGES[2]])
        self.apinext_target.unroot()
        self.apinext_target.wait_for_adb_device(wait_time=60)

    def is_driver_connected(self):
        return is_url_connectable(DEFAULT_PORT_SERVER)

    def setup_apinext_target(self):
        # This condition is verified on MTEE execution, no Android Target is initialized, only MTEE Target.
        if not self.mtee_target:
            self.setup_target()
        self.mtee_target = TargetShareMTEE().target
        self.vcar_manager = TargetShareMTEE().vcar_manager
        self.apinext_target = TargetShare().target
        self.apinext_target.setup()
        self.apinext_target.wait_for_boot_completed_flag(wait_time=30)
        self.diagnostic_client = DiagClient(self.mtee_target.diagnostic_address, self.mtee_target.ecu_diagnostic_id)
        # Get default language after target setup. Set to ENGLISCH__UK if vcar returns KEINE_SPRACHE(no language set)
        default_language = self.vcar_manager.execute_remote_method("get_language")
        self.default_language = "ENGLISCH__UK" if default_language == "KEINE_SPRACHE" else default_language
        # Get current branch name
        self.branch_name = self.get_branch()
        # Trigger provisioning for IDC Racks as a mandatory precondition for the tests executed on Racks
        if self._test_rack and "idc" in self.apinext_target.product_type:
            if not self.apinext_target.check_internet_connectivity():
                self.setup_rack_provisioning()
                self.apinext_target.restart()
        self.apinext_target.disable_heads_up_notifications()
        self.force_stop_package()
        if "idc" in self.apinext_target.product_type:
            self.apinext_target.close_popups()
            self.vcar_manager.send('msg_emit("20.0000B034.0026.01")')  # TunerFmAmDab.stopTA request

    @utils.gather_info_on_fail
    def setup_driver(self, timeout=30):
        if not self._appium_options:
            self.setup_appium_options()

        # Retry mechanism to open appium driver
        for i in range(APPIUM_OPEN_SESSION_ATTEMPTS):
            logger.info(f"Opening Appium session. Attempt {i + 1}/{APPIUM_OPEN_SESSION_ATTEMPTS}")
            self.driver, self.opened_session, error_msg = utils.open_appium_session(
                self._appium_options, self.mtee_target, self.apinext_target
            )
            if self.driver and self.opened_session:
                self.wb = WebDriverWait(self.driver, timeout)
                if "idc" in self.apinext_target.product_type:
                    self.driver.update_settings(
                        {"enableMultiWindows": True, "allowInvisibleElements": True, "waitForIdleTimeout": 500}
                    )
                return
            elif self.driver and not self.opened_session:
                logger.info("Session started but not fully operational...")
                self.quit_driver()
                continue
        utils.remove_appium_apk(self.apinext_target)
        error_msgs = f"Couldn't set up appium driver, got WebDriverException with error_msg: '{error_msg}'"
        raise RuntimeError(error_msgs)

    def quit_driver(self):
        """Try to close appium driver if open"""
        if self.driver:
            # Retry mechanism to close appium driver
            for i in range(APPIUM_CLOSE_SESSION_ATTEMPTS):
                logger.info(f"Closing Appium session. Attempt {i + 1}/{APPIUM_CLOSE_SESSION_ATTEMPTS}")
                closed = utils.close_appium_session(self.driver, self.mtee_target, self.opened_session)
                if closed:
                    self.driver = None
                    self.wb = None
                    return

            raise RuntimeError(f"Couldn't close appium driver, with id: {self.opened_session}")

    def setup_desired_caps(self):
        """Define _desired_caps according ti the target type"""
        if not self.apinext_target:
            self.setup_apinext_target()

        if "padi" in self.apinext_target.product_type:
            self._desired_caps = (
                self._padi_desired_caps if self.branch_name == "pu2403" else self._padi_desired_caps_ml
            )
        elif "idc" in self.apinext_target.product_type:
            self._desired_caps = self._idc_desired_caps
        if not self._desired_caps:
            raise AssertionError(f"No desired caps available for this target: '{self.apinext_target.product_type}'")

    def setup_appium_options(self):
        """Define _appium_options since options were introduce on Appium-python-client >= 2.3.0
        We keep the desired capabilities approach from our side and then load them to the new options
        """
        if not self._desired_caps:
            self.setup_desired_caps()

        self._appium_options = UiAutomator2Options().load_capabilities(self._desired_caps)
        self._appium_options.system_port = DEFAULT_SYSTEM_PORT
        self._appium_options.adb_port = DEFAULT_ADB_PORT
        if self._test_rack:
            self._appium_options.udid = self._hu_android_serial
            os.environ["NO_PROXY"] = "*"  # Disables proxy server

    def stop_padi_video_streaming_apps(self):
        """Force stops padi streaming apps so that we are able to take screenshots - HU22DM-21385"""
        if not self.apinext_target:
            raise Exception("Unable to stop padi video streaming apps, apinext target is not setup")

        if "padi" in self.apinext_target.product_type:
            self.apinext_target.execute_adb_command(["shell", "am", "force-stop", "com.bmwgroup.padi.hdmiapp"])
            CEAreaPage.stop_cearea_package()
        else:
            logger.warning(
                "Unable to stop video streaming apps on product {}".format(self.apinext_target.product_type)
            )

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

        if "results" not in base_dir:
            out_dir = os.path.join(base_dir, "results", current_test_name)
        else:
            out_dir = os.path.join(base_dir, current_test_name)
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        logger.info(f"Created results folder path: '{out_dir}'")
        self.results_dir = out_dir

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

    def force_stop_package(self):
        """
        Force stop packages which popups in between test
        """
        packages = ["com.bmwgroup.apinext.festival"]
        user = self.apinext_target.get_current_user_id()
        for each_package in packages:
            grep_package = ["pm", "list", "packages", "--user", user, "-e", each_package]
            response = self.apinext_target.execute_command(grep_package)
            output = response.stdout.decode("utf-8").strip().replace(" ", "")
            if each_package in output:
                stop_package = ["am", "force-stop", each_package]
                self.apinext_target.execute_command(stop_package)

    def get_branch(self):
        """
        Extract the branch name from ro.build.id using ADB
        :return: Branch name as str.
        """
        branch_text = self.apinext_target.execute_adb_command(["shell", "getprop", "ro.build.id"])
        branch_regex = r"(?:padi22-|idc23-)(\w+)(?=-)"
        match = re.search(branch_regex, str(branch_text.stdout.decode("UTF-8")))
        logger.debug(f"branch found : '{match.group(1)}'")
        return match.group(1).lower()
