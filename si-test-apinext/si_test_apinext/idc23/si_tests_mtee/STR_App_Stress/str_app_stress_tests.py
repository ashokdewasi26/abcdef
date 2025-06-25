# Copyright (C) 2023. BMW CTW PT. All rights reserved.

import csv
import logging
import os
import re
import time
import sh
from unittest import SkipTest
from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import require_environment, require_environment_setup, TEST_ENVIRONMENT
from mtee.testing.tools import (
    assert_false,
    assert_equal,
    assert_less_equal,
    assert_true,
    nottest,
)

try:
    from validation_utils.utils import TimeoutError
except ModuleNotFoundError:
    from node0_ssh_client.tools import TimeoutError
from tee.target_common import VehicleCondition
from tee.tools.lifecycle import LifecycleFunctions
from tee.tools.dlt_helper import get_udp_broadcast_buffer_storage_time
from tee.tools.node0_tools import remount_exec_container

from si_test_apinext.idc23 import STR_LIMIT
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.metric_extractor import ExtractMetrics
from si_test_apinext.util.global_steps import GlobalSteps
from mtee_apinext.enablers.support.android_generic_hid_mapping import AndroidGenericKeyCodes

required_target_packages = [
    "system-functions-mgu22-systemtests-targetfiles",
    "lifecycle-components-systemtests-targetfiles",
]

lf = LifecycleFunctions()
logger = logging.getLogger(__name__)
target = TargetShare().target
USE_DLT_RECEIVE_TARGET = True
USE_DLT_RECEIVE_HOST = False
USE_DLT_BROKER_HOST = False

# Dict with default state of STR flag {TARGET_NAME(str): FLAG(bool), ...}
TARGET_STR_FLAG_DEFAULT_VALUE = {
    "mgu22": True,
    "idc23": True,
    "bcpj": False,
    "bmt": False,
    "mgu-high": False,
    "rse22": False,
}

REQUIREMENTS = (TEST_ENVIRONMENT.target.hardware.gen22, TEST_ENVIRONMENT.test_bench.farm)
MESSAGES_TO_CHECK_DURING_STR = {
    "NSM entering STR": [r"Going to suspend to ram.*SUSPEND_TO_RAM.*"],
    "NSC entering STR": [r"StartUnit.*suspend.target"],
    "NSM leaving STR": [r"resumedFromRAM"],
    "NSC leaving STR": [r"suspend.target.*done", r"Resuming from suspend-to-RAM", r"resumed from suspend-to-RAM"],
}
JOUR_ERROR_MESSAGE = {
    "Kernerl PM Error": [r"kernel: Error: PM.*failed"],
}
SYSTEMD_MESSAGES = {
    "Systemd before STR": ["systemd-sleep.*Suspending system...", "kernel: PM: suspend entry"],
    "Systemd afer STR": ["systemd-sleep.*System resumed."],
}
DLT_MESSAGES = {
    "DLT closing socket": ["send DLT message failed, closing socket"],
    "DLT deactivate conn": ["Deactivate connection type: 2"],
}
STR_COUNTER_REGEX = re.compile(r"ResumeNo: (\d{1,3}).*")
MAX_TIME_SHUTDOWN = 60
TOLERANCE_TO_LC_TMSP_DEVIATION = 4
STR_RELIABILITY_NUMBER = 165
BOX_APP_TITLE = 149, 12, 573, 63
WAIT_PAGE_TRANSITION = 3

ALL_APPS = {
    "Navigation": "com.bmwgroup.idnext.navigation/.map.MainActivity",
    "MediaApp": "com.bmwgroup.apinext.mediaapp/.player.MediaActivity",
    "Launcher": "com.bmwgroup.idnext.launcher/.MainActivity",
    "Connectivity": "com.bmwgroup.idnext.connectivity/.nav.device_manager.NavDeviceManagerHostActivity",
    "Climate": "com.bmwgroup.apinext.climate/.ClimateMainActivity",
    "DoorsAndWindows": "com.bmwgroup.apinext.doorwindow/.DoorsWindowsActivity",
    "Seats": "com.bmwgroup.apinext.seats/.MainActivity",
    "Settings": "com.bmwgroup.idnext.settings/.SettingsActivity",
    "Parking": "com.bmwgroup.apinext.parking/com.bmwgroup.apinext.parking.MainActivity",
    "IBA": "com.bmwgroup.driversguide.row.idc/com.bmwgroup.driversguide.ui.home.HomeActivity",  # (User manual app)
}


@require_environment(*REQUIREMENTS)
class TestSTR:
    """Suspend to Ram testcase verification"""

    list_of_validated_apps = []

    @classmethod
    def log_to_csv(cls, str_cycle="setup_class", info=""):
        """
        Log relevant information to csv

        :param str_cycle[str]: STR cycle
        :param info[str]: Message

        Output: Expected that you will have a csv file (str_test_info.csv) with relevant information
        about failures during the STR cycles
        """
        csv_dir = os.path.join(target.options.result_dir, "extracted_files")
        csv_path = os.path.join(csv_dir, "str_test_info.csv")
        csv_header = ["STR_cycle", "info"]

        if not os.path.isdir(csv_dir):
            return

        with open(csv_path, mode="a") as csv_file:
            csv_writter = csv.DictWriter(csv_file, fieldnames=csv_header)
            if csv_file.tell() == 0:
                csv_writter.writeheader()
            csv_writter.writerow({csv_header[0]: str_cycle, csv_header[1]: info})

    @classmethod
    def _validate_apps(cls):
        """
        The purpose of this method is to validate all the applications defined
        in ALL_APPS before starting the STR cycles

        - Check that the intended apps opened correctly or didn't crash before starting the STR cycles
        and using this new list (list_of_validated_apps) to use before and after each STR cycle

        """
        for app, package_activity in ALL_APPS.items():
            cls.test.apinext_target.execute_adb_command(["shell", f"am start -n {package_activity}"])
            time.sleep(WAIT_PAGE_TRANSITION)
            screenshot_path = os.path.join(cls.test.results_dir, f"validated_app_{app}.png")
            cls.test.apinext_target.take_screenshot(screenshot_path)
            try:
                open_activity = cls.test.apinext_target.execute_adb_command(
                    ["shell", "dumpsys activity activities | grep ResumedActivity"]
                )
            except sh.ErrorReturnCode_1:
                logger.info("Retrying dumpsys for resumed activity")
                open_activity = cls.test.apinext_target.execute_adb_command(
                    ["shell", "dumpsys activity activities | grep ResumedActivity"]
                )
            search_for_package = package_activity.split("/")[0]
            if search_for_package in open_activity:
                logger.info(f"App: {app} validated. Adding this app to the new list")
                cls.list_of_validated_apps.append(package_activity)
            else:
                cls.log_to_csv(
                    str_cycle="setup_class",
                    info="App: {} didn't open or crashed. Excluding the app from the list".format(search_for_package),
                )
                logger.info(f"App: {app} didn't open or crashed. Excluding the app from the list")
                logger.debug(f"The expected app was not found in: {open_activity}")

        logger.debug(f"List of validated apps: {cls.list_of_validated_apps}")

        assert_true(
            len(cls.list_of_validated_apps) >= 1,
            "It was not possible to validate any of the applications defined in: ALL_APPS",
        )

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def setup_class(cls):
        """Get default value"""
        if target and not target.has_capability(TEST_ENVIRONMENT.feature.suspend_to_ram):
            raise SkipTest("Not applicable for this target!")
        remount_exec_container(target, partition="/var/data", container="node0")
        cls.default_udp_buffer_time = get_udp_broadcast_buffer_storage_time()
        cls.default_str_state = lf.get_str_state()
        # If STR isn't enable, enable it here
        if not cls.default_str_state:
            lf.set_str_state("0")
        target.reboot()
        target.wait_for_nsm_fully_operational()
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(appium=False)
        time.sleep(WAIT_PAGE_TRANSITION)
        screenshot_path = os.path.join(cls.test.results_dir, "setup_STR.png")
        cls.test.apinext_target.take_screenshot(screenshot_path)
        cls.lifecycle_tests_preconditions(cls)
        # Create an STR counter in Lifecycle class due to be using yield
        lf.str_counter = 0
        cls._validate_apps()

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def teardown_class(cls):
        """set defaults"""
        cls.test.teardown_base_class()
        remount_exec_container(target, partition="/var/data", container="node0")
        if lf.get_str_state() != cls.default_str_state:
            value_to_set = "0" if cls.default_str_state else "1"
            lf.set_str_state(value_to_set)
        target.reboot()
        target.wait_for_nsm_fully_operational()
        extractor = ExtractMetrics()
        extractor.extract_metrics_and_log_to_csv()

    def teardown(self):
        """Restores target into awake state and FAHREN if target ends the test asleep"""
        lf.set_default_vehicle_state()
        if not lf.is_alive():
            logger.debug("Sleeping after completed test, rebooting ...")
            # If STR is enable (STR FLAG is True): don't wait for reboot (not a cold boot)
            wait_for_serial_reboot = True if not TARGET_STR_FLAG_DEFAULT_VALUE[target.options.target] else False
            logger.debug(f"Target {target.options.target} will wait for reboot in wake up? {wait_for_serial_reboot}")
            lf.wakeup_target(wait_for_serial_reboot=wait_for_serial_reboot)
            target.wait_for_nsm_fully_operational()
            assert_true(
                lf.is_alive(),
                "Failing to restore initial state in PWF Living Driving tests - Target is not alive after test",
            )

    @nottest
    def lifecycle_tests_preconditions(self, set_vehicle_state=True, wait_for_serial_reboot=True):
        """Garantee the correct state before each lifecycle test:
        - make sure target is alive
        - set default vehicle state
        - check that nsm is fully operational
        : param bool set_vehicle_state: wheather or not to set default vehicle state
        : param bool wait_for_serial_reboot: disable serial reboot pattern so the wait_for_reboot doesn't check serial
        """
        if set_vehicle_state:
            lf.set_default_vehicle_state()
        if not lf.is_alive():
            # If STR is enabled (STR FLAG is True): don't wait for reboot (not a cold boot)
            wait_for_serial_reboot = True if not TARGET_STR_FLAG_DEFAULT_VALUE[target.options.target] else False
            logger.debug(f"Target {target.options.target} will wait for reboot in wake up ? {wait_for_serial_reboot}")
            lf.wakeup_target(wait_for_serial_reboot=wait_for_serial_reboot)
            # If not alive produce hard reboot:
            if not lf.is_alive():
                target.reboot(prefer_softreboot=False)

        target.wait_for_nsm_fully_operational()

    def read_systemd_messages(
        self,
        store_filename=None,
        last_minutes=2,
        grep=True,
        expression="mgu22 kernel|mgu22 systemd-sleep",
        verbose=True,
    ):
        """Check in journal the messages
        :param str(store_filename): Filename to store in extracted files
        :param last_minutes(int): period to collect journal messages (last minutes)
        :param grep(bool): If True capture in journal for given expression
        :param expression(str): expression to grep
        :param verbose(bool): To verbose the output into log file
        :return str: String with journal messages
        """
        cmd = 'journalctl --since "{} minute ago"'.format(last_minutes)
        if grep:
            cmd += ' | grep -E "{}"'.format(expression)
        result_messages = target.execute_command(cmd, timeout=10, shell=True)
        if verbose:
            logger.debug("journalctl messages:\n%s", result_messages.stdout)
        return result_messages.stdout

    def disable_firewall_for_current_lc(self):
        """Disable rules for firewall in current lifecycle"""
        cmd = "nft flush ruleset"
        result = target.execute_command(cmd, timeout=10, shell=True)
        logger.debug("%s result:\n%s", cmd, result.stdout)

    def verify_failures_in_log(self, failures_dict, log, should_exist=True):
        """Verifies in the given log if the failures_dict are present or not
        :param failures_dict(dict): Dict with messages to check
        :param log(str): Log to capture the given messages
        :param should_exist(bool): True if we should find them
        :return list: List with messages not found in case they should_exist, or messages found in case they
            not should_exist
        """
        msgs = []
        for item in failures_dict:
            for message in failures_dict[item]:
                if should_exist:
                    if not re.search(message, log):
                        msgs.append(" : ".join((item, message)))
                else:
                    if re.search(message, log):
                        msgs.append(" : ".join((item, message)))
        return msgs

    def try_get_str_counter_from_dlt(self):
        """Try to get str counter from DLT"""
        try:
            with DLTContext(
                self.test.mtee_target.connectors.dlt.broker, filters=[("NSM", "LCMG"), ("NSM", "SDMG")]
            ) as trace:
                filter_dlt_messages = trace.wait_for(
                    attrs=dict(payload_decoded=STR_COUNTER_REGEX),
                    timeout=10,
                    drop=True,
                    count=1,
                )
                for msg in filter_dlt_messages:
                    if STR_COUNTER_REGEX.search(msg.payload_decoded):
                        lf.str_counter = int(STR_COUNTER_REGEX.findall(msg.payload_decoded)[0])
                        logger.info(f"Suspend to RAM no: {lf.str_counter}")
                        return True
        except TimeoutError:
            logger.debug("Unable to find STR counter DLT message")
            return False

    def str_cold_boot_routine(self):
        """Due to stress testing of STR, there is a expected cold boot when the limit is reached
        Steps:
            - Set vehicle to PARKEN
            - Stop keep alive
            - Ensure target goes to sleep (expected shutdown)
            - Idle for a few seconds and then wake up target
            - Wait for Android boot complete flag
            - Ensure idc23 home page is set through DLT
            - Take screenshot
            - Set STR counter to 0
        """
        logger.info("Starting STR cold boot routine, expecting shutdown of ECU")
        target.switch_vehicle_to_state(VehicleCondition.PARKEN_BN_IO)
        lf.stop_keepalive()
        lf.nm3_stop_sending_all()

        lf.ecu_to_enter_sleep(timeout=MAX_TIME_SHUTDOWN)
        time.sleep(10)

        target.switch_vehicle_to_state(VehicleCondition.FAHREN)
        logger.info("Waking up target...")
        lf.wakeup_target()

        logger.info("Waiting for boot complete flag")
        self.test.apinext_target.wait_for_boot_completed_flag()
        logger.info(f"Target wakeup after cold boot routine, {STR_LIMIT}th Suspend to RAM")

        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as trace:
            utils.validate_idc23_home_availability(self.test.apinext_target, trace)

        screenshot_path = os.path.join(self.test.results_dir, "str_limit_wakeup.png")
        self.test.apinext_target.take_screenshot(screenshot_path)

        if not self.try_get_str_counter_from_dlt():
            lf.str_counter = 0
            logger.info(f"Suspend to RAM no: {lf.str_counter}")

    def perform_sysman_str_cycle(self):
        """Imported from SYSMAN STR cycle
        **Preconditions**
            #. ECU alive
            #. FAHREN state
            #. NM3 messages keep a PN, which the ECU is a member of, awake
        **Required Steps**
            * Set STR active (if not coded):
                * devcoding write COD_LIFECYCLE_SHUTDOWN_TARGET 0
                * Reboot the target
                    * nsm_control --r 7 (start only with mcast.py)
                * Wait until target is operational, check at startup for:
                    * "NSM NSMC 1680 log info verbose 19 NSMCImpl::loadCoding:.*shutdownTarget: 0.*"
            * Set target into PARKEN and stop keep alive - stop mcast keepalive
            * Wait until in sleep - Target should go to STR
            * Change vehicle state to FAHREN and setup keep alive
            * Trigger WUP line
            * Restore (if needed):
                * Call "devcoding write COD_LIFECYCLE_SHUTDOWN_TARGET 1"
                * Target reboot: nsm_control --r 7
        **Expected outcome**
            The initial setting shall place the target with STR active
            ECU enters in STR after setting PARKEN and stopping keep alive
            Verification is done in journal messages/lifecycle time still counting
        """
        store_filename = "str_bat_test"
        store_udp_log_filename = "/tmp/{}".format(store_filename)
        store_journal_filename = "{}_journal".format(store_filename)
        self.disable_firewall_for_current_lc()
        with DLTContext(
            self.test.mtee_target.connectors.dlt.broker, filters=[("NSM", "LCMG"), ("NSM", "SDMG")]
        ) as trace:
            sleep, reconnect, serial_stop, time_diff_host, time_diff_target = lf.perform_str(
                trace=trace,
                udp_log_file=store_udp_log_filename,
                default_udp_buffer_time=self.default_udp_buffer_time,
                messages_to_capture=[],
                wait_time_after_no_connection=60,
            )

        if abs(time_diff_host - time_diff_target) > TOLERANCE_TO_LC_TMSP_DEVIATION:
            if not self.try_get_str_counter_from_dlt():
                logger.error("Cold boot might have happened, resetting STR counter")
                lf.str_counter = 0

        journal_messages = self.read_systemd_messages(store_filename=store_journal_filename)

        missing_msgs_systemd = self.verify_failures_in_log(SYSTEMD_MESSAGES, journal_messages)
        error_messages_systemd = self.verify_failures_in_log(JOUR_ERROR_MESSAGE, journal_messages, should_exist=False)
        assert_false(
            missing_msgs_systemd and error_messages_systemd,
            "Some expected messages are missing during the STR:\n{}\nor unexpected:\n{}".format(
                missing_msgs_systemd,
                error_messages_systemd,
            ),
        )
        assert_true(sleep, "Failed to get target into STR")
        assert_true(serial_stop, "Failed to get serial stopped during STR")
        assert_false(reconnect, "Target went into STR but reconnection happened without any action in test!")
        sleep_after_str = lf.ecu_to_enter_sleep(timeout=30)
        assert_false(sleep_after_str, "Target went into shutdown after STR procedure!")
        target.wait_for_nsm_fully_operational()
        lf.debug_systemd_suspend()
        assert_less_equal(
            abs(time_diff_host - time_diff_target),
            TOLERANCE_TO_LC_TMSP_DEVIATION,
            "Failed to get timestamp of lifecycle after STR with expected time +tolerance - cold boot might happened!",
        )

        logger.info("STR cycle finished after {}s".format(time_diff_target))
        if not self.try_get_str_counter_from_dlt():
            lf.str_counter += 1
            logger.info(f"Suspend to RAM no: {lf.str_counter}")

    @utils.gather_info_on_fail
    def _str_cycle(self, iteration):
        """STR reliability Cycle
        **Required Steps**
            *Open IDC list_of_validated_apps
                - Check current Android activities
            *Verify the app's activities currently running/paused before STR
            *Perform STR active
                - use STR cycle imported from sysman
            *Verify the app's activities currently running/paused after STR
                - check Android activities remained the same
        **Expected outcome**
            Before and after STR the list of validated apps must be the same and usable

            IMPORTANT: Check the contents of the file: results/extracted_files/str_test_info.csv,
            to check if any application validated earlier, in setup_class, after a few cycles of
            STR stopped working or was not opened before or after STR
        """
        list_activities_before_str = []
        list_activities_after_str = []
        list_of_differences = []

        # Ensure boot complete flag everytime
        self.test.apinext_target.wait_for_boot_completed_flag()
        logger.info("Boot Complete Flag is set")

        # Ensure start from Home page
        GlobalSteps.inject_custom_vhal_input(self.test.apinext_target, AndroidGenericKeyCodes.KEYCODE_HOME)
        time.sleep(WAIT_PAGE_TRANSITION)

        for package_activity in self.list_of_validated_apps:
            self.test.apinext_target.execute_adb_command(["shell", f"am start -n {package_activity}"])
            time.sleep(WAIT_PAGE_TRANSITION)
            resumed_activity = self.test.apinext_target.execute_adb_command(
                ["shell", "dumpsys activity activities | grep ResumedActivity"]
            )
            search_for_package = package_activity.split("/")[0]
            if search_for_package not in resumed_activity:
                self.log_to_csv(
                    str_cycle=iteration,
                    info="Previously validated app: {} didn't open or crash before the STR cycle {}".format(
                        package_activity, iteration
                    ),
                )

        logger.info(f"Starting STR cycle {iteration}")
        # Get just the sixth word of the 'Hist #' command that only contains the package/activity
        activities_before_str = self.test.apinext_target.execute_adb_command(
            ["shell", "dumpsys activity activities | grep 'Hist #' | awk '{print $6}'"]
        )
        list_activities_before_str = activities_before_str.splitlines()
        logger.info(f"Before cycle {iteration} of STR found activities: {list_activities_before_str}")

        if lf.str_counter == (STR_LIMIT - 1):
            logger.info(f"Reached the LIMIT of Suspend to RAM {STR_LIMIT}")
            self.str_cold_boot_routine()
        else:
            self.perform_sysman_str_cycle()

            # After STR, check that the same apps are still open
            screenshot_path = os.path.join(self.test.results_dir, f"after_STR_final_state_{iteration}.png")
            self.test.apinext_target.take_screenshot(screenshot_path)
            # Get just the sixth word of the 'Hist #' command that only contains the package/activity
            activities_after_str = self.test.apinext_target.execute_adb_command(
                ["shell", "dumpsys activity activities | grep 'Hist #' | awk '{print $6}'"]
            )
            list_activities_after_str = activities_after_str.splitlines()
            logger.info(f"After STR {iteration} found activities {list_activities_after_str}")

            list_of_differences = list(set(list_activities_after_str) - set(list_activities_before_str))

            if len(list_of_differences) != 0:
                self.log_to_csv(
                    str_cycle=iteration,
                    info="Before STR cycle: {}, After the STR cycle, the following app did not appear: {}".format(
                        list_activities_before_str, list_of_differences
                    ),
                )

            assert_equal(
                len(list_of_differences),
                0,
                "Check the file at: results/extracted_files/str_test_info.csv for more info",
            )

    def test_000_str_reliability_ui_verification(self):
        for iteration in range(STR_RELIABILITY_NUMBER):
            # Run STR cycle
            yield (self._str_cycle, iteration)
