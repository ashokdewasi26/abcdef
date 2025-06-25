# Copyright (C) 2023. BMW CTW PT. All rights reserved.

import base64
import logging
import os
import re

from appium import webdriver
from appium.options.android import UiAutomator2Options
from mtee.testing.connectors.connector_dlt import DLTContext
from selenium.webdriver.common.utils import is_url_connectable
from selenium.webdriver.remote.remote_connection import LOGGER as seleniumLogger  # noqa: N811
from selenium.webdriver.support.ui import WebDriverWait
import si_test_idcevo.si_test_helpers.test_helpers as utils
from si_test_idcevo import APPIUM_ELEMENT_TIMEOUT
from si_test_idcevo.si_test_helpers.file_path_helpers import deconflict_file_path
from si_test_idcevo.si_test_helpers.pages.cde.launcher_page import LauncherPage as CDELauncher
from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage
from si_test_idcevo.si_test_helpers.pages.idcevo.launcher_page import LauncherPage as Launcher
from si_test_idcevo.si_test_helpers.pages.rse26.launcher_page import LauncherPage as RSE26Launcher

# Default variables for appium session
ABD_EXEC_TIMEOUT_IN_MS = 60000
APPIUM_CLOSE_SESSION_ATTEMPTS = 3
APPIUM_OPEN_SESSION_ATTEMPTS = 3
APPIUM_PACKAGES = ["io.appium.settings", "io.appium.uiautomator2.server", "io.appium.uiautomator2.server.test"]
DEFAULT_ADB_PORT = 5037
DEFAULT_PORT_SERVER = 4723
DEFAULT_SYSTEM_PORT = 8200
SERVER_LAUNCH_TIMEOUT_IN_MS = 600000
WAIT_FOR_APPIUM_DLT = 10
WAIT_FOR_IDLE_TIMEOUT_IN_MS = 500

seleniumLogger.setLevel(logging.INFO)
logger = logging.getLogger(__name__)


class IDCEvoAppiumHandler(object):
    _common_desired_caps = dict(
        platformName="Android",
        automationName="UiAutomator2",
        newCommandTimeout=0,  # means don't timeout
        uiautomator2ServerLaunchTimeout=SERVER_LAUNCH_TIMEOUT_IN_MS,
        adbExecTimeout=ABD_EXEC_TIMEOUT_IN_MS,
        noReset=True,
        enableMultiWindows=True,
        allowInvisibleElements=True,
        waitForIdleTimeout=WAIT_FOR_IDLE_TIMEOUT_IN_MS,
    )

    _idcevo_desired_caps = dict(
        appPackage=Launcher.PACKAGE_NAME,
        appActivity=Launcher.PACKAGE_ACTIVITY,
    )
    _idcevo_desired_caps.update(_common_desired_caps)

    _cde_desired_caps = dict(
        appPackage=CDELauncher.PACKAGE_NAME,
        appActivity=CDELauncher.PACKAGE_ACTIVITY,
    )
    _cde_desired_caps.update(_common_desired_caps)

    _rse26_desired_caps = dict(
        appPackage=RSE26Launcher.PACKAGE_NAME,
        appActivity=RSE26Launcher.PACKAGE_ACTIVITY,
    )
    _rse26_desired_caps.update(_common_desired_caps)

    _driver = None
    _web_driver_wait = None
    _desired_caps = None
    opened_session = None
    record_test = None
    _appium_options = None
    default_language = None

    @property
    def driver(self):
        return self._driver

    @driver.setter
    def driver(self, value):
        self._driver = value
        BasePage.driver = value

    @property
    def webdriverwait(self):
        return self._web_driver_wait

    @webdriverwait.setter
    def webdriverwait(self, value):
        self._web_driver_wait = value
        BasePage.web_driver_wait = value

    @utils.gather_info_on_fail
    def setup_driver(self, timeout=APPIUM_ELEMENT_TIMEOUT):
        if not self.driver or not is_url_connectable(DEFAULT_PORT_SERVER):
            logger.info(
                "Doing setup_appium_options() because appium driver is not defined on " + str(self.__class__.__name__)
            )
            self.setup_appium_options()

        for i in range(APPIUM_OPEN_SESSION_ATTEMPTS):
            logger.info(f"Opening Appium session. Attempt {i + 1}/{APPIUM_OPEN_SESSION_ATTEMPTS}")

            self.driver, self.opened_session, error_msg = self.open_appium_session()

            if self.driver and self.opened_session:
                self.webdriverwait = WebDriverWait(self.driver, timeout)
                return
            elif self.driver and not self.opened_session:
                logger.info("Appium driver started but couldn't find session ID.")
                self.teardown_appium()
            elif not self.driver and not self.opened_session:
                logger.info(f"Appium driver completely failed to start with error: {error_msg}")
                self.remove_appium_apk()

        raise RuntimeError(f"Couldn't set up appium driver (check info logs). Got the error message: '{error_msg}'")

    def teardown_appium(self):
        self.quit_driver()
        self.remove_appium_apk()
        self.apinext_target.wait_for_adb_device(wait_time=60)

    def quit_driver(self):
        """Try to close appium driver if open"""
        if self.driver:
            for i in range(APPIUM_CLOSE_SESSION_ATTEMPTS):
                logger.info(f"Closing Appium session. Attempt {i + 1}/{APPIUM_CLOSE_SESSION_ATTEMPTS}")
                closed = self.close_appium_session()
                if closed:
                    self.driver = None
                    self.webdriverwait = None
                    return

            raise RuntimeError(f"Couldn't close appium driver, with id: {self.opened_session}")

    def setup_desired_caps(self):
        """Define _desired_caps according to the target type"""

        if "idcevo" in self.apinext_target.product_type:
            udid_dict = dict(udid=self.apinext_target.get_android_serial_number())
            self._idcevo_desired_caps.update(udid_dict)
            self._desired_caps = self._idcevo_desired_caps
        elif "cde" in self.apinext_target.product_type:
            udid_dict = dict(udid=self.apinext_target.get_android_serial_number())
            self._cde_desired_caps.update(udid_dict)
            self._desired_caps = self._cde_desired_caps
        elif "rse26" in self.apinext_target.product_type:
            udid_dict = dict(udid=self.apinext_target.get_android_serial_number())
            self._rse26_desired_caps.update(udid_dict)
            self._desired_caps = self._rse26_desired_caps
        elif not self._desired_caps:
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

    def open_appium_session(self, url=f"http://localhost:{DEFAULT_PORT_SERVER}/wd/hub"):
        """Open appium session following up the DLT logs.
        param: options: appium options that include the session capabilities.
        param: url: (Optional) session url.
        return: driver, opened session ID and error message if any.
        """
        error_msg = ""
        with DLTContext(self.mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as dlt_detector:
            dlt_new_session_msg = re.compile(r"appium.*Created the new session")
            try:
                driver = webdriver.Remote(url, options=self._appium_options)
                appium_session_msg = dlt_detector.wait_for(
                    {"apid": "ALD", "ctid": "LCAT", "payload_decoded": dlt_new_session_msg},
                    timeout=WAIT_FOR_APPIUM_DLT,
                    drop=True,
                    raise_on_timeout=False,
                )
                if appium_session_msg:
                    logger.debug(f"Found appium_session_msg: '{appium_session_msg[0].payload_decoded}'")
                    session_id = re.match(r".*id ([\s\S]*?) and.*", appium_session_msg[0].payload_decoded).group(1)
                    logger.info(f"Session created with id {session_id}")
                else:
                    error_msg = f"Did not find Appium message for new session. Pattern: '{dlt_new_session_msg}'"
                    return driver, False, error_msg

            except Exception as error:
                error_msg = f"Appium session failed with '{error}'"
                logger.error(error_msg)
                return False, False, str(error)

            return driver, session_id, ""

    def close_appium_session(self):
        """Close appium session following up the DLT logs.
        Quit driver and wait for the messages for stopping uiautomator2
        and the appium response with session ID closed.

        :return: True if successfully closed. False if fails to close.
        """
        with DLTContext(self.mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as dlt_detector:
            dlt_stop_uiautomator_msg = re.compile(r"appium.*Stopping uiautomator2.*")
            dlt_close_session_msg = re.compile(r"appium.*AppiumResponse: {\"sessionId\":.*")
            try:
                self.driver.quit()
            except Exception as e:
                logger.debug(f"Found exception while trying to quit driver, error: '{e}'")
                return False

            stop_msgs = dlt_detector.wait_for(
                {"apid": "ALD", "ctid": "LCAT", "payload_decoded": re.compile(r"appium.*")},
                timeout=WAIT_FOR_APPIUM_DLT,
                count=0,
                drop=True,
                raise_on_timeout=False,
            )

        uiautomator_stop_msg = next(
            (msg for msg in stop_msgs if re.match(dlt_stop_uiautomator_msg, msg.payload_decoded)), None
        )
        if not uiautomator_stop_msg:
            logger.error(f"Couldn't find uiautomator stop message in DLT appium messages: '{stop_msgs}'")

        appium_response_msg = next(
            (msg for msg in stop_msgs if re.match(dlt_close_session_msg, msg.payload_decoded)), None
        )
        if appium_response_msg:
            logger.debug(f"Found appium_response_msg : '{appium_response_msg.payload_decoded}'")
            if self.opened_session is False:
                logger.info("Closing session that started correctly but couldn't find session ID.")

            session_id = re.match(r".*sessionId\":\"([\s\S]*?)\",.*", appium_response_msg.payload_decoded).group(1)
            if session_id == self.opened_session:
                logger.info(f"Session closed with id {session_id}")
            else:
                logger.error(f"Different session id found, expecting {self.opened_session}, got: {session_id}")
        else:
            logger.error(
                "Couldn't find appium response message with session ID in DLT. "
                "Message may be missing from the DLT log or wasn't caught in the DLTContext. "
                "Assuming session is correctly closed, but if problems arise, check the DLT logs."
            )

        self.opened_session = None
        return True

    def start_recording(self):
        try:
            self.driver.start_recording_screen()
            self.record_test = True
        except Exception as e:
            logger.error(f"Found exception while trying to start video recording on {self.results_dir}, error: '{e}'")

    def stop_recording(self, video_name):
        try:
            raw_data = self.driver.stop_recording_screen()
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

    def remove_appium_apk(self):
        android_packages = self.apinext_target.execute_command(["pm", "list packages", "-a"])
        for package in APPIUM_PACKAGES:
            if package in android_packages:
                logger.info(f"Uninstalling appium package: {package}")
                self.apinext_target.execute_adb_command(["uninstall", package])
