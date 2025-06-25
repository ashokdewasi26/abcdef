# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Application startup time (reference app)"""
import configparser
import logging
import os
import re
import time

from pathlib import Path
from mtee.metric import MetricLogger
from mtee.testing.tools import assert_true, metadata, run_command
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.linux_commands_handlers import LinuxCommandsHandler
from si_test_idcevo.si_test_helpers.pages.idcevo.connectivity_page import ConnectivityPage as Connectivity

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
metric_logger = MetricLogger()

apk_path = Path(os.sep) / "resources" / "perfo-ref-app-0_2_1.tar.gz"
DIFF_APP_TO_OPEN = {
    "Connectivity": Connectivity().get_activity_name(),
}
LAUNCH_STATE_PATTERN = re.compile(r"LaunchState: (?P<launch_state>COLD|WARM|HOT)")
PERFO_PACKAGE_NAME = "com.bmwgroup.apinext.perforefapp"
RETRY_OPEN_PERFO_APP = 3
SLEEP_TIME_IN_SEC = 5
TOTAL_TIME_PATTERN = re.compile(r"TotalTime: (?P<time_in_ms>\d+)")


class TestPerfoRefApp(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(root=True)
        cls.linux_helpers = LinuxCommandsHandler(cls.test.mtee_target, logger)
        cls._retry_counter = 0
        cls._stored_values = {}

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def _open_perfomance_ref_app(self):
        """Open the performance reference app"""
        start_perfo_app_cmd = [
            "am",
            "start",
            "-W",
            "com.bmwgroup.apinext.perforefapp/.MainActivity",
            "-c",
            "android.intent.category.LAUNCHER",
            "-a",
            "android.intent.action.MAIN",
        ]
        perfo_app_result = self.test.apinext_target.execute_command(start_perfo_app_cmd)
        logger.debug(f"perfo_app_result: {perfo_app_result}")
        time.sleep(SLEEP_TIME_IN_SEC)
        self.test.take_apinext_target_screenshot(self.test.results_dir, "Perfo_App")
        dumpsys_cmd = "dumpsys activity activities | grep -E 'mCurrentFocus|mFocusedApp'"
        launched_activities_result = self.test.apinext_target.execute_command(dumpsys_cmd)
        if PERFO_PACKAGE_NAME in launched_activities_result:
            logger.debug(f"Package: {PERFO_PACKAGE_NAME} validated")
        else:
            logger.info(f"Package: {PERFO_PACKAGE_NAME} didn't open or crashed")
            logger.info(f"The expected app was not found in: {launched_activities_result}")
        self._extract_info(perfo_app_result.stdout.decode("utf-8"))

    def _extract_info(self, info_to_extract):
        """Extract the information from the performance reference app"""
        launch_state_match = LAUNCH_STATE_PATTERN.search(info_to_extract)
        total_time_match = TOTAL_TIME_PATTERN.search(info_to_extract)

        if not launch_state_match or not total_time_match:
            self._retry_counter += 1

            if self._retry_counter <= RETRY_OPEN_PERFO_APP:
                logger.info(
                    f"The perfo app didn't open or crashed. Retrying {self._retry_counter} of {RETRY_OPEN_PERFO_APP}"
                )
                self._open_perfomance_ref_app()
            else:
                logger.error("The perfo app could not be opened")
                assert_true(False, f"The perfo app could not be opened in {RETRY_OPEN_PERFO_APP} retries")
        else:
            if int(total_time_match.group("time_in_ms")) > 3000:
                logger.error("The perfo app took more than 3s to execute")
                self._stored_values.update(
                    {launch_state_match.group("launch_state"): total_time_match.group("time_in_ms")}
                )

            metric_logger.publish(
                {
                    "name": "perfo_ref_app",
                    "kpi_name": f"launch_state_{launch_state_match.group('launch_state').lower()}",
                    "value": total_time_match.group("time_in_ms"),
                }
            )

    def _open_different_app(self, app_to_be_oppenned=DIFF_APP_TO_OPEN.get("Connectivity")):
        """Open the DIFF_APP_TO_OPEN"""
        start_diff_app_cmd = f"am start -n {app_to_be_oppenned}"
        diff_app_result = self.test.apinext_target.execute_command(start_diff_app_cmd)
        logger.debug(f"perfo_app_result: {diff_app_result}")
        time.sleep(SLEEP_TIME_IN_SEC)

        app_list = [
            app for app, package_activity in DIFF_APP_TO_OPEN.items() if package_activity == app_to_be_oppenned
        ]
        # Unpack the list into variables
        app, *_ = app_list

        self.test.take_apinext_target_screenshot(
            self.test.results_dir,
            app,
        )
        dumpsys_cmd = "dumpsys activity activities | grep -E 'mCurrentFocus|mFocusedApp'"
        launched_activities_result = self.test.apinext_target.execute_command(dumpsys_cmd)
        search_for_package = app_to_be_oppenned.split("/")[0]
        if search_for_package in launched_activities_result:
            logger.debug(f"Package: {search_for_package} validated")
        else:
            logger.info(f"Package: {search_for_package} didn't open or crashed")
            logger.info(f"The expected app was not found in: {launched_activities_result}")

    @metadata(
        testsuite=["SI", "SI-performance", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Performance",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-8980",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "APPLICATION_STARTUP_TIME"),
            },
        },
    )
    def test_001_launch_perfo_ref_app(self):
        """[SIT_Automated] [Perfo] Application startup time (reference app)

        **Steps**
            - Wait for the target to be completely initialized
            - Download and install the performance reference app (perfo-ref-app-0.2.1.apk)
            - Launch for the first time perfo-ref-app via adb
            - Launch a different app
            - Open again perfo-ref-app
            - Extract the information from the perfo-ref-app ('LaunchState' and 'TotalTime')
            - Publish the extracted information to grafana
            - Insure that the perfo-ref-app took less than 3s to execute in all the launch states
        """
        # Make sure the target is already initialized before installing the apk
        self.test.mtee_target.wait_for_reboot(timeout=180)
        self.test.mtee_target.wait_for_android_boot_completion()

        self.linux_helpers.extract_tar(apk_path)
        result = run_command(["ls", "-R", "/tmp"])
        logger.debug(f"Content of /tmp: \n{result.stdout}")

        result = self.test.apinext_target.install_apk("/tmp/perfo-ref-app-0.2.1.apk")
        logger.debug(f"Install apk result: {result}")

        assert_true("Success" in result.stdout.decode("utf-8"), "The apk was not installed successfully!")

        self._open_perfomance_ref_app()
        self._open_different_app()
        self._open_perfomance_ref_app()

        assert_true(
            len(self._stored_values) == 0,
            f"The perfo-ref-app toke more than 3s to execute in: {self._stored_values}",
        )
