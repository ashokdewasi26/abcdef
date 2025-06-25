# Copyright (C) 2023. BMW Car IT. All rights reserved.
import configparser
import csv
import logging
import os
import re
import time
from pathlib import Path

from mtee.metric import MetricLogger
from mtee.testing.tools import assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.pages.idcevo.carhub_page import CarhubPage as Carhub
from si_test_idcevo.si_test_helpers.pages.idcevo.climate_page import ClimatePage as Climate
from si_test_idcevo.si_test_helpers.pages.idcevo.connectivity_page import ConnectivityPage as Connectivity
from si_test_idcevo.si_test_helpers.pages.idcevo.launcher_page import LauncherPage as Launcher
from si_test_idcevo.si_test_helpers.pages.idcevo.lights_page import LightsPage as Lights
from si_test_idcevo.si_test_helpers.pages.idcevo.media_page import MediaPage as Media
from si_test_idcevo.si_test_helpers.pages.idcevo.modes_page import ModesPage as Modes
from si_test_idcevo.si_test_helpers.pages.idcevo.navigation_page import NavigationPage as Navigation
from si_test_idcevo.si_test_helpers.pages.idcevo.settings_page import SettingsPage as Settings
from si_test_idcevo.si_test_helpers.pages.idcevo.speech_page import SpeechPage as Speech


# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
metric_logger = MetricLogger()
logger = logging.getLogger(__name__)

TOTAL_TIME_PATTERN = re.compile(r"TotalTime: (?P<time_in_ms>\d+)")
LAUNCH_STATE_PATTERN = re.compile(r"LaunchState: (?P<launch_state>COLD|WARM|HOT)")
NUM_ITERATIONS = 5
SLEEP_INTERVAL = 120
APPS_TO_MEASURE_STARTUP_TIME = [Climate(), Lights(), Modes(), Connectivity()]
APPS_TO_CHECK_STARTUP_TIME_BELOW_THRESHOLD = [Navigation(), Carhub(), Settings(), Media(), Speech()]
APPS_TO_VALIDATE = APPS_TO_MEASURE_STARTUP_TIME + APPS_TO_CHECK_STARTUP_TIME_BELOW_THRESHOLD

# List of applications to skip during validation because they are not fully enabled yet
APPS_WHITELIST = ["Navigation", "Speech", "Climate", "Media"]
CSV_FILE_NAME = "validate_apps_launching_info.csv"
SLEEP_TIME_IN_SEC = 5

logger = logging.getLogger(__name__)


class TestValidateAppsLaunching:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(root=True)
        cls.test.set_activities_list()
        cls.list_of_invalid_apps = []
        cls.booting_times_greater_than_threshold = {}
        cls.check_threshold_is_published = []

    @classmethod
    def teardown_class(cls):
        """Test case teardown"""
        cls.test.mtee_target.resume_after_reboot(skip_ready_checks=False)
        cls.test.teardown_base_class()

    def _log_to_csv(self, app="", info=""):
        """
        Log relevant information to csv

        :param app[str]: Application that could not be validated
        :param info[str]: Message

        Output: Expected that you will have a csv file (validate_apps_launching_info.csv) with
        relevant information about the failure
        """
        csv_path = os.path.join(self.test.results_dir, CSV_FILE_NAME)
        csv_header = ["Application", "info"]

        if not os.path.isdir(self.test.results_dir):
            return

        with open(csv_path, mode="a") as csv_file:
            csv_writter = csv.DictWriter(csv_file, fieldnames=csv_header)
            if csv_file.tell() == 0:
                csv_writter.writeheader()
            csv_writter.writerow({csv_header[0]: app, csv_header[1]: info})

    def _validate_apps(self):
        """
        The purpose of this method is to validate all the applications defined
        in APPS_TO_VALIDATE before starting the test

        - Check that the intended apps opened correctly or didn't crash before starting the test
        and
        """
        for i in range(len(APPS_TO_VALIDATE) - 1, -1, -1):
            application = APPS_TO_VALIDATE[i]

            if any(
                (application.PACKAGE_NAME in package and application.PACKAGE_ACTIVITY in str(activity))
                for package, activity in self.test.activities_list.items()
            ) or hasattr(application, "DOMAIN_IDENTIFIER"):
                logger.info(f"App: {application.COMMON_NAME} is in activities_list")
            else:
                logger.info(f"App: {application.COMMON_NAME} isn't in activities_list")
                message_to_csv = (
                    f"Package/activity: {application.get_activity_name()} not found. "
                    " Package name or activity name may have changed."
                )
                new_package_activity = self.test.get_most_similar_activity(application.get_activity_name())
                if new_package_activity:
                    message_to_csv += f" It will be used the most similar package/activity: {new_package_activity}."
                    logger.debug(message_to_csv)
                    application.set_activity_name(new_package_activity)
                else:
                    logger.error(
                        f"Package/activity: {application.get_activity_name()} not found."
                        f" Check these files: '{CSV_FILE_NAME}' and "
                        f" {self.test.activities_file} for more information"
                    )
                    app_to_remove = APPS_TO_VALIDATE.pop(i).COMMON_NAME
                    for app in APPS_TO_MEASURE_STARTUP_TIME:
                        if app.COMMON_NAME == app_to_remove:
                            APPS_TO_MEASURE_STARTUP_TIME.remove(app)
                            break
                    for app in APPS_TO_CHECK_STARTUP_TIME_BELOW_THRESHOLD:
                        if app.COMMON_NAME == app_to_remove:
                            APPS_TO_CHECK_STARTUP_TIME_BELOW_THRESHOLD.remove(app)
                            break
                self._log_to_csv(
                    app=application.COMMON_NAME,
                    info=message_to_csv,
                )

    def launch_activity(self, app, launch_cmd):
        """
        Executing command to launch activity and taking a screenshot

        :param app: App page to validate
        :type app: class instance
        :param launch_cmd: Command to launch the activity
        :type launch_cmd: string
        :return: Decoded output of the command of launching the activity
        :rtype: string
        """
        res_app_start_cmd = app.start_activity(cmd=launch_cmd)
        res_app_start_decoded = res_app_start_cmd.stdout.decode("utf-8")
        logger.debug(f"Result execute command: {res_app_start_decoded}")
        time.sleep(SLEEP_TIME_IN_SEC)
        self.test.take_apinext_target_screenshot(self.test.results_dir, f"{app.COMMON_NAME}_App")

        return res_app_start_decoded

    def check_invalid_apps(self, app):
        """
        Check if any application failed to open or crashed with dumpsys command
        If so, add the application to the list of invalid apps

        :param app: App page to validate
        :type app: class instance
        """
        dumpsys_cmd = "dumpsys activity activities | grep -E 'mCurrentFocus|mFocusedApp'"
        res_dumpsys_cmd = self.test.apinext_target.execute_command(dumpsys_cmd)
        logger.debug(f"Result dumpsys command: {res_dumpsys_cmd}")

        if app.COMMON_NAME not in APPS_WHITELIST:
            if app.PACKAGE_NAME in res_dumpsys_cmd:
                logger.debug(f"App: {app.COMMON_NAME} validated")
            else:
                logger.info(f"App: {app.COMMON_NAME} didn't open or crashed")
                logger.info(f"The expected app was not found in: {res_dumpsys_cmd}")
                self.list_of_invalid_apps.append(app.COMMON_NAME)
        else:
            logger.info(f"{app.COMMON_NAME} in application whitelist")

    def publish_activity_metrics(self, app, res_app_start_decoded):
        """
        Publish the metric with the time value and the type of boot

        :param app: App page to validate
        :type app: class instance
        :param res_app_start_decoded: Output of the command of launching the activity
        :type res_app_start_decoded: string
        """
        total_time_match = TOTAL_TIME_PATTERN.search(res_app_start_decoded)
        total_time = int(total_time_match.group(1)) if total_time_match else 0
        launch_state_match = LAUNCH_STATE_PATTERN.search(res_app_start_decoded)

        launch_state = launch_state_match.group("launch_state") if launch_state_match else "UNKNOWN"
        logger.info(f"{app.COMMON_NAME} in application with total_time: {total_time} and launch_state: {launch_state}")

        metrics_to_publish = {
            "name": "app_start",
            "app": app.COMMON_NAME,
            "time_value": total_time,
            "type_of_boot": launch_state,
        }

        if (
            app in APPS_TO_CHECK_STARTUP_TIME_BELOW_THRESHOLD
            and app.COMMON_NAME not in self.check_threshold_is_published
        ):
            self.check_threshold_is_published.append(app.COMMON_NAME)
            metrics_to_publish["metric_threshold"] = str(app.MAXIMUM_THRESHOLD_BOOT_TIME)

        metric_logger.publish(metrics_to_publish)

        if app in APPS_TO_CHECK_STARTUP_TIME_BELOW_THRESHOLD and total_time > app.MAXIMUM_THRESHOLD_BOOT_TIME:
            if app.COMMON_NAME not in self.booting_times_greater_than_threshold:
                self.booting_times_greater_than_threshold[app.COMMON_NAME] = [total_time]
            else:
                self.booting_times_greater_than_threshold[app.COMMON_NAME].append(total_time)

    def return_to_home_screen(self):
        Launcher.go_to_home(self.test)
        time.sleep(2)

    def measure_and_validate_app_launch_time(self, type_of_start="", publish_metric=False):
        """
        This function validates the application and, depending on the value of publish_metric,
        it may publish the startup times of the applications.

        Parameters:
        type_of_start (str): Specifies the type of start for the application.
        publish_metric (bool): Determines whether to publish the startup time and launch state as a metric.
        """
        for app in APPS_TO_VALIDATE:
            if app.COMMON_NAME in self.list_of_invalid_apps:
                continue

            if type_of_start.lower() == "cold":
                app_start_cmd = app.get_command_cold_start()
            else:
                app_start_cmd = app.get_command_warm_hot_start()

            res_app_start_decoded = self.launch_activity(app, app_start_cmd)
            self.check_invalid_apps(app)

            if publish_metric:
                self.publish_activity_metrics(app, res_app_start_decoded)

            if app.COMMON_NAME in APPS_WHITELIST:
                app_stop_cmd = f"am force-stop {app.PACKAGE_NAME}"
                self.test.apinext_target.execute_command(app_stop_cmd, privileged=True)

            # Returning to home screen to have more stable results. Not returning to home could lead to
            # UNKNOWN states when launching apps
            self.return_to_home_screen()

    def target_uptime(self):
        """
        Returns the target uptime in seconds.
        """
        return_stdout, _, _ = self.test.mtee_target.execute_command("cat /proc/uptime")
        return_stdout_list = return_stdout.split()
        uptime_seconds = float(return_stdout_list[0])

        return uptime_seconds

    @metadata(
        testsuite=["BAT", "SI", "SI-android", "SI-performance"],
    )
    def test_001_validate_apps_launching(self):
        """
        [SIT_Automated] Validate Apps launching

        The purpose of this test is to validate all the applications defined
        in APPS_TO_VALIDATE: Climate, Lights, Navigation, Modes, Connectivity, Carhub, Settings, Media and Speech

        Steps:
            1. Launch the application via adb
            2. Take a screenshot
            3. Validate that the application was run using dumpsys to validate that the application
            is the application on mCurrentFocus or mFocusedApp. If not, the test will fail at the end
            showing all the applications that failed this validation
            4. Stop the current app before starting the next
            5. Repeat the previous steps until you validate all applications in APPS_TO_VALIDATE
        IMPORTANT: The navigation app has been added to the list of apps to whitelist during
        validation because it depends on connectivity (with the Internet or with the BMW backend)
        and is not yet activated. Speech app was also added to this list, as is not yet fully enabled.
        """

        self._validate_apps()
        self.measure_and_validate_app_launch_time()
        assert_true(
            len(self.list_of_invalid_apps) == 0,
            f"It was not possible to validate the following application(s): {self.list_of_invalid_apps}."
            f" Check the following file: {CSV_FILE_NAME} for more information, as the package name "
            f"or package activity name may have changed",
        )

    @metadata(
        testsuite=["BAT", "SI", "SI-android", "SI-performance", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Android Platform",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-57760",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "NAVIGATION_STARTUP_TIME"),
            },
        },
    )
    def test_002_apps_launch_time(self):
        """
        [SIT_Automated] Validate applications startup times

        The objective of this test is to verify the startup time of this apps: Navigation, Carhub, Settings,
        Media and Speech, while also publishing startup time metrics of other applications.

        Steps:
            1. Launch the application via adb
            2. Take a screenshot
            3. Validate that the application was run using dumpsys to validate that the application
            is the application on mCurrentFocus or mFocusedApp. If not, the test will fail at the end
            showing all the applications that failed this validation
            4. Stop the current app before starting the next
            5. Repeat the previous steps until you validate all applications in APPS_TO_VALIDATE
            6. Publish the metric with the time value and the type of boot
            7. Check if the navigation boot times are less than 3 seconds
        IMPORTANT: The navigation app has been added to the list of apps to whitelist during
        validation because it depends on connectivity (with the Internet or with the BMW backend)
        and is not yet activated. Speech app was also added to this list, as is not yet fully enabled.
        """

        current_uptime = self.target_uptime()
        if current_uptime < SLEEP_INTERVAL:
            wait_time = abs(SLEEP_INTERVAL - current_uptime)
            time.sleep(wait_time)
        self._validate_apps()

        for i in range(NUM_ITERATIONS):
            self.measure_and_validate_app_launch_time(publish_metric=True)
            self.measure_and_validate_app_launch_time(type_of_start="cold", publish_metric=True)

        assert_true(
            len(self.booting_times_greater_than_threshold) == 0,
            f"The following apps had startup times greater than the defined threshold (milliseconds), for some "
            f"iterations: {self.booting_times_greater_than_threshold}."
            f" Check the following file: {CSV_FILE_NAME} for more information.",
        )
