# Copyright (C) 2024. BMW Car IT GmbH. All rights reserved.
"""Intensive-reboot test cases"""
import inspect
import json
import logging
import subprocess
import time
import traceback
from collections import defaultdict
from pathlib import Path
from unittest import skip

from diagnose.hsfz import HsfzError
from mtee.metric import MetricLogger
from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import (
    assert_false,
    assert_greater_equal,
    assert_less_equal,
    assert_true,
    metadata,
)
from mtee.tools.utils import StopWatch
from tee.tools.diagnosis import DiagClient
from validation_utils.utils import TimeoutCondition

target = TargetShare().target
diagnostic_client = DiagClient(target.diagnostic_address, target.ecu_diagnostic_id)
metric_logger = MetricLogger()
logger = logging.getLogger(__name__)

RESPONSE_PAYLOAD = 0
RESPONSE_TIMESTAMP = 1
RESPONSE_EXCEPTION_TRACEBACK = 2
SSH_BOOT_TIMEOUT = 240
REBOOT_CYCLES = 50


class IntensiveRebootReporter:
    """Generate report for IntensiveRebootRunner"""

    INTENSIVE_REBOOT_REPORT_DIR = Path(target.options.result_dir) / "intensive_reboot"
    SUMMARY_KEY_HUMMAN_STRS = {
        "is_passed": "Test case passed",
        "reboot_times": "Reboot times",
        "total_execution_time": "Total execution time (unit: sec)",
        "total_reboot_time": "Total reboot time (unit: sec)",
        "total_reboot_check_time": "Total reboot-checking time (unit: sec)",
        "reboot_failed": "Fail reboot times",
        "reboot_check_failed": "Fail reboot-check times",
    }

    def __init__(self, test_name, reboot_times, report_filename=None, expected_boot_mode=None, description=""):
        """
        Init the reporter

        :param str test_name: for logging
        :param int reboot_times: the times of running the test
        :param Optional[str] report_filename: the report filename.
            The default value is "{test_name}_intensive_reboot_report.json"
        """
        self.test_name = test_name
        self.description = description
        self.reboot_times = reboot_times
        self.expected_boot_mode = expected_boot_mode
        self.report_path = self.INTENSIVE_REBOOT_REPORT_DIR / (
            report_filename or f"{self.test_name}_intensive_reboot_report.json"
        )

        # Example:
        #
        # self._report = {
        #     "test_name": "ecu_reset",
        #     "expected_boot_mode": "APP",       # None means any of boot mode
        #     "summary": {
        #         "reboot_times": 50,
        #         "total_execution_time": 1000,      # unit: sec(s)
        #         "total_reboot_time": 900,          # unit: sec(s)
        #         "total_reboot_check_time": 100,    # unit: sec(s)
        #         "reboot_failed": 2,                # The number of exceptions happen during reboot function
        #         "reboot_check_failed": 3,          # The number of fails for checking functions
        #         "reboot_failed_stats: {
        #             "ecu_reset_and_uds_check": 0,  # The number of rebooting fails
        #             "install_coding_esys": 0,
        #         },
        #         "reboot_check_failed_stats": {
        #             "boot_mode_failure": 0,        # The number of checking fails
        #             "ssh_not_ready": 2,
        #         },
        #     },
        #     "reboot_failed_stats": {
        #         "ecu_reset_and_uds_check": [2, 5],  # the value presents the error boot_cycle
        #         "install_coding_esys": [],
        #     },
        #     "reboot_check_failed_stats": {
        #         "boot_mode_failure": [],            # the value presents the error boot_cycle
        #         "ssh_not_ready": [2, 5],
        #         "hmi_not_ready": [2],
        #         "found_unexpected_dtc": [5],
        #     },
        #     "boot_cycle_summary": {
        #         # the key presents the boot_cycle
        #         1: {
        #             "reboot": True,
        #             "reboot_check": True,
        #             "total": 100.0,                       # "reboot_time" + "reboot_check_time"
        #             "reboot_time": 90.0,                  # sum of "reboot_time_items", unit: sec
        #             "reboot_check_time": 10.0,            # sum of "reboot_check_time_items", unit: sec
        #             "reboot_time_items": {
        #                 "ecu_reset_and_uds_check": 34.0,  # unit: sec
        #                 "install_coding_esys": 42.0,
        #             },
        #             "reboot_check_time_items": {
        #                 "bood_mode_failure": 34.0,        # unit: sec
        #                 "ssh_not_ready": 42.0,
        #             },
        #         },
        #     },
        #     "reboot_failed_error_logs": {
        #         "ecu_reset_and_uds_check": {
        #             2: "example error message 1",   # the key presents the error boot_cycle
        #             5: "example error message 2",
        #         },
        #         "install_coding_esys": {
        #             5: "some error messages...",
        #         },
        #     },
        #     "reboot_check_failed_error_logs": {
        #         "ssh_not_ready": {
        #             2: "example error message 1",    # the key presents the error boot_cycle
        #             5: "example error message 2",
        #         },
        #         "found_unexpected_dtc": {
        #             5: "some error messages...",
        #         },
        #     },
        # }
        self._report = {
            "test_name": self.test_name,
            "description": self.description,
            "expected_boot_mode": self.expected_boot_mode,
            "summary": {},
            "boot_cycle_summary": {
                boot_cycle: {"reboot_time_items": {}, "reboot_check_time_items": {}}
                for boot_cycle in range(1, self.reboot_times + 1)
            },
            "reboot_failed_stats": defaultdict(list),
            "reboot_failed_error_logs": defaultdict(dict),
            "reboot_check_failed_stats": defaultdict(list),
            "reboot_check_failed_error_logs": defaultdict(dict),
        }

        self.total_reboot_time = 0
        self.total_reboot_check_time = 0

        self.num_reboot_failed = 0
        self.num_reboot_check_failed = 0

    @property
    def total_execution_time(self):
        return self.total_reboot_time + self.total_reboot_check_time

    def _add_log(self, key, boot_cycle, name, is_passed, error_log, duration):
        stats_key = f"{key}_failed_stats"
        error_logs_key = f"{key}_failed_error_logs"
        item_time_key = f"{key}_time_items"

        # Add boot_cycle to statistics
        if not is_passed:
            self._report[stats_key][name].append(boot_cycle)

        # Record error logs by name for each boot_cycle
        if error_log:
            logger.error("%s - %d %s error - %s - %s", self.test_name, boot_cycle, key, name, error_log)
            self._report[error_logs_key][name][boot_cycle] = error_log

        # Record executing time by name for each boot_cycle
        self._report["boot_cycle_summary"][boot_cycle][item_time_key][name] = duration

    def add_reboot_item_log(self, boot_cycle, name, is_passed, error_log, duration):
        self._add_log("reboot", boot_cycle, name, is_passed, error_log, duration)

    def add_reboot_check_item_log(self, boot_cycle, name, is_passed, error_log, duration):
        self._add_log("reboot_check", boot_cycle, name, is_passed, error_log, duration)

    def add_boot_cycle_summary(
        self, boot_cycle, is_reboot, is_reboot_check, reboot_time, reboot_check_time, cool_down_time_after_reboot
    ):
        self._report["boot_cycle_summary"][boot_cycle].update(
            {
                "reboot": is_reboot,
                "reboot_check": is_reboot_check,
                "total": reboot_time + reboot_check_time,
                "reboot_time": reboot_time,
                "reboot_check_time": reboot_check_time,
                "cool_down_time_after_reboot": cool_down_time_after_reboot,
            }
        )

        self.total_reboot_time += reboot_time
        self.total_reboot_check_time += reboot_check_time

        self.num_reboot_failed += not is_reboot
        self.num_reboot_check_failed += not is_reboot_check

    def _generate_summary(self):
        self._report["summary"] = {
            "is_passed": not self.num_reboot_failed and not self.num_reboot_check_failed,
            "reboot_times": self.reboot_times,
            "total_execution_time": self.total_execution_time,
            "total_reboot_time": self.total_reboot_time,
            "total_reboot_check_time": self.total_reboot_check_time,
            "reboot_failed": self.num_reboot_failed,
            "reboot_check_failed": self.num_reboot_check_failed,
            "reboot_failed_stats": {
                err_name: len(err_boot_cycles)
                for err_name, err_boot_cycles in self._report["reboot_failed_stats"].items()
            },
            "reboot_check_failed_stats": {
                err_name: len(err_boot_cycles)
                for err_name, err_boot_cycles in self._report["reboot_check_failed_stats"].items()
            },
        }

    def _print_summary(self):
        """Print summary to stderr for showing the summary in result.html"""
        summary = {
            self.SUMMARY_KEY_HUMMAN_STRS[key] if key in self.SUMMARY_KEY_HUMMAN_STRS else key: value
            for key, value in self._report["summary"].items()
        }

        logger.info(summary)

    def report(self):
        self.INTENSIVE_REBOOT_REPORT_DIR.mkdir(parents=True, exist_ok=True)

        self._generate_summary()
        self._print_summary()

        # Write the report with json format
        with self.report_path.open("w") as report_out:
            json.dump(self._report, report_out, indent=4)


class IntensiveRebootRunner:
    """A test case runner to run target reboot several times"""

    # BOOT_MODE_CHECKS: Dict[str, Callable[[self, BootCycle], (IsPassed, Optional[ErrorMessage)]]
    # BootCycle = int
    # IsPassed = bool
    # ErrorMessage = str
    BOOT_CHECK_FUNCS = {
        "boot_mode_failure": "_check_boot_mode",
        "found_unexpected_dtc": "_check_unexpected_dtcs",
        "ssh_not_ready": "_check_ssh_ready",
        "detected_crash_state": "_check_crash_state",
        "wait_for_android_device": "_wait_for_android_device",
    }

    BOOT_MODE_CHECKS = {
        "APP": (
            "boot_mode_failure",
            "found_unexpected_dtc",
            "wait_for_android_device",
            "ssh_not_ready",
            "detected_crash_state",
        ),
        "BOL": ("boot_mode_failure", "detected_crash_state"),
        "RSU": ("boot_mode_failure", "detected_crash_state"),
    }

    def __init__(
        self,
        test_name,
        reboot_times,
        description="",
        report_filename=None,
        reboot_fun=None,
        reboot_fun_name="reboot_func",
        pass_reboot_fun_boot_cycle=False,
        expected_boot_mode=None,
        custom_target=None,
        serial=False,
        custom_diagnostic_client=None,
        resume_before_reboot=False,
        cool_down_time_after_reboot=0,
    ):
        """
        Init the runner

        :param str test_name: for logging and report
        :param str description: describe the test, for report
        :param int reboot_times: the times of running the test
        :param Optional[str] report_filename: the report filename.
            The default value is "{test_name}_intensive_reboot_report.json"
        :param Union[Callable[[int],], Callable[,]] reboot_fun: the target reboot function. If the
            function has argument, the argument is boot cycle.
        :param bool pass_reboot_fun_boot_cycle: Pass boot_cycle to reboot_fun if True
        :param str reboot_fun_name: Present the name of the function. It's used for report.
        :param Optional[str] expected_boot_mode: Possible expected_boot_mode value: "APP", "BOL", "RSU" or None
            None presents to check that the boot_mode has value (one of three).
            Otherwise, check that the boot_mode is the same or not
        :param bool serial: If test verifications should be done using serial connection only.
        """
        self._target = custom_target or TargetShare().target
        self._diagnostic_client = custom_diagnostic_client or diagnostic_client

        self.test_name = test_name
        self.description = description
        self.reboot_times = reboot_times
        self.resume_before_reboot = resume_before_reboot
        self.reboot_fun = reboot_fun or self._target.reboot
        self.reboot_fun_name = reboot_fun_name
        self.pass_reboot_fun_boot_cycle = pass_reboot_fun_boot_cycle
        self.expected_boot_mode = expected_boot_mode
        self.serial = serial
        self.cool_down_time_after_reboot = cool_down_time_after_reboot
        self.already_raised_dtcs = []
        self.reporter = IntensiveRebootReporter(
            self.test_name,
            reboot_times=self.reboot_times,
            report_filename=report_filename,
            expected_boot_mode=self.expected_boot_mode,
            description=self.description,
        )

        self.boot_mode_check_names = self._get_boot_mode_check_names()

    def _get_boot_mode_check_names(self):
        name = self.expected_boot_mode
        return self.BOOT_MODE_CHECKS.get(name, ())

    def reset_target_dlt_flags(self):
        # Reset the state of DLTMonitor
        self._target.reset_connector_dlt_state()

    def reboot(self, boot_cycle, is_log=True):
        with StopWatch() as reboot_func_watch:
            is_reboot = True
            reboot_error_log = ""

            if self.resume_before_reboot:
                self.prepare()
            try:
                if self.pass_reboot_fun_boot_cycle:
                    self.reboot_fun(boot_cycle)
                else:
                    self.reboot_fun()
            except Exception as err:
                is_reboot = False
                reboot_error_log = f"""{self.reboot_fun_name}: Unexpected exception happen - {str(err)}
traceback: {traceback.format_exc()}"""

        if is_log:
            self.reporter.add_reboot_item_log(
                boot_cycle, self.reboot_fun_name, is_reboot, reboot_error_log, reboot_func_watch.duration
            )
        elif not is_reboot:
            logger.error(
                "%s - %d'th reboot error - %s - %s", self.test_name, boot_cycle, self.reboot_fun_name, reboot_error_log
            )

        return is_reboot

    def reboot_check(self, boot_cycle, is_log=True):
        is_passed_all = True

        for check_name in self.boot_mode_check_names:
            is_passed = True
            error_log = ""

            with StopWatch() as check_watch:
                try:
                    is_passed, error_log = getattr(self, f"{self.BOOT_CHECK_FUNCS[check_name]}")(boot_cycle)
                except Exception as err:
                    is_passed = False
                    error_log = str(err)

            if is_log:
                self.reporter.add_reboot_check_item_log(
                    boot_cycle, check_name, is_passed, error_log, check_watch.duration
                )
            else:
                if not is_passed:
                    logger.error(
                        "%s - %d'th reboot check error - %s - %s", self.test_name, boot_cycle, check_name, error_log
                    )

            logger.info(
                "%s - %d's boot cycle - %s check - %s in %f sec(s)",
                self.test_name,
                boot_cycle if boot_cycle else -1,
                check_name,
                "pass" if is_passed else "fail",
                check_watch.duration,
            )

            is_passed_all &= is_passed

        return is_passed_all

    def prepare(self):
        """Preparation before run the test case"""
        pass

    def run(self):
        """
        Run the test

        :return bool: True if the test is success
        """
        logger.info("Start the intensive-reboot test for %s.", self.test_name)

        try:
            self.prepare()
        except Exception as err:
            logger.error("%s - prepare error - %s", self.test_name, err)
            return False

        for boot_cycle in range(1, self.reboot_times + 1):
            logger.info("%s starts to %d/%d boot", self.test_name, boot_cycle, self.reboot_times)

            self.reset_target_dlt_flags()

            with StopWatch() as reboot_exec_watch:
                is_reboot_success = self.reboot(boot_cycle)

            is_reboot_check_success = False
            if is_reboot_success:
                with StopWatch() as reboot_check_watch:
                    is_reboot_check_success = self.reboot_check(boot_cycle)

            reboot_time = reboot_exec_watch.duration
            reboot_check_time = reboot_check_watch.duration if is_reboot_success else 0

            if is_reboot_success and self.cool_down_time_after_reboot:
                logger.info(f"Cooldown phase of {self.cool_down_time_after_reboot}s")
                time.sleep(self.cool_down_time_after_reboot)

            # Record to report
            self.reporter.add_boot_cycle_summary(
                boot_cycle,
                is_reboot_success,
                is_reboot_check_success,
                reboot_time,
                reboot_check_time,
                self.cool_down_time_after_reboot,
            )

            # Write to log
            boot_cycle_exec_time = reboot_time + reboot_check_time
            msg_prefix = f"{self.test_name} - {boot_cycle}/{self.reboot_times} boot cycle"
            if is_reboot_success and is_reboot_check_success:
                logger.info("%s - success after %f secs", msg_prefix, boot_cycle_exec_time)
            else:
                if not is_reboot_success:
                    logger.error("%s - fail to reboot after %f secs", msg_prefix, reboot_time)
                else:
                    logger.error("%s - fail to reboot check after %f secs", msg_prefix, boot_cycle_exec_time)

        # Generate summary and write report to file
        self.reporter.report()

        # Log the test summary
        logger.info(
            "%s has %d times for reboot error(s) in %d reboot(s)",
            self.test_name,
            self.reporter.num_reboot_failed,
            self.reboot_times,
        )
        logger.info(
            "%s has %d reboot check error(s) in %d reboot(s) ",
            self.test_name,
            self.reporter.num_reboot_check_failed,
            self.reboot_times,
        )
        logger.info("%s saves the report in %s", self.test_name, self.reporter.report_path)
        logger.info("%s execute in %f sec(s)", self.test_name, self.reporter.total_execution_time)

        # Reboot to the original state
        try:
            self.clean()
        except Exception as err:
            logger.error("%s - clean error - %s", self.test_name, err)
            return False

        return not self.reporter.num_reboot_failed and not self.reporter.num_reboot_check_failed

    def clean(self):
        if self.expected_boot_mode in ("APP", "RSU"):
            self._target.resume_after_reboot(skip_ready_checks=False)
            return

        self._target.reboot()
        self._target.wait_for_boot_mode()

        boot_mode = self._target.connectors.dlt.monitor.boot_mode
        if boot_mode != "APP":
            raise RuntimeError(f"{self.test_name} - reboot at the clean state error, the reboot mode is {boot_mode}")

    def _check_boot_mode(self, _):
        self._target.wait_for_boot_mode()
        boot_mode = self._target.connectors.dlt.monitor.boot_mode

        logger.info("%s - Get the boot mode: %s", self.test_name, boot_mode)

        if not self.expected_boot_mode:
            is_passed = bool(boot_mode)
            error_msg = "boot_mode is an empty string"
        else:
            is_passed = boot_mode == self.expected_boot_mode
            error_msg = f"Expected: {self.expected_boot_mode}, Actual: {boot_mode}"

        return is_passed, error_msg if not is_passed else None

    def _check_ssh_ready(self, boot_cycle):
        try:
            self._target.ssh.wait_for_ssh(target.get_address(), SSH_BOOT_TIMEOUT)
        except RuntimeError as err:
            return False, str(err)

        return True, None

    def _check_crash_state(self, _):
        is_passed = not self._target.connectors.dlt.monitor.crash_detected
        error_msg = None

        if not is_passed:
            error_msg = f"Crash detected: {self._target.connectors.dlt.monitor.crash_detected}"
            logger.info(error_msg)

        return is_passed, error_msg

    def _check_unexpected_dtcs(self, boot_cycle):
        unexpected_dtcs, _ = self._diagnostic_client.get_unexpected_dtcs(
            mem="BOTH", whitelisted_dtc=self._target.whitelisted_dtc + self.already_raised_dtcs
        )

        if unexpected_dtcs:
            error_msg = f"Found unexpected DTCs: {unexpected_dtcs} "
            self.already_raised_dtcs += unexpected_dtcs
            return False, error_msg

        return True, None

    def _wait_for_android_device(self, boot_cycle):
        timeout = 90
        try:
            subprocess.check_call(["adb", "wait-for-device", "devices"], timeout=timeout)
            return True, None
        except subprocess.CalledProcessError:
            return False, "ADB devices command returned an error. Check the logs"
        except subprocess.TimeoutExpired:
            return False, f"ADB wait-for-device timed out. No ADB devices detected in {timeout} seconds."
        except Exception:
            return False, f"Unknown exception was raised during ADB wait-for-device on cycle {boot_cycle}"


class ECUReset:
    """Perform ECU reset and checks"""

    def __init__(self, test_name):
        self.test_name = test_name
        self.target_key = target.options.target
        self.countdown_uds_request = None
        self.countdown_target_connected = None
        self.timeout_value_uds_request = {"idcevo": 35, "rse26": 35, "cde": 35}
        self.timeout_value_target_connected = {"idcevo": 25, "rse26": 25, "cde": 25}
        self.responses_log = []
        self.minimum_time = 3
        self.poll_interval = 1

    def perform_ecu_reset(self):
        """Trigger diagnosis ECU-Reset
        :return Tuple[bool, str]: to presents uds_request_error and exception_trace_ecu_reset
        """
        try:
            diagnostic_client.ecu_reset()
        except (EOFError, HsfzError, OSError, RuntimeError):
            return True, traceback.format_exc()

        return False, None

    def polling_uds_ping_session_state(self):
        """Perform RDBI_PING_SESSION_STATE (0x22 f1 00) every 1000ms until request is accepted"""
        # Start timeout mechanism
        self.countdown_uds_request = TimeoutCondition(self.timeout_value_uds_request[self.target_key])
        self.countdown_target_connected = TimeoutCondition(self.timeout_value_target_connected[self.target_key])
        self.responses_log = []
        while self.countdown_uds_request:
            ecu_response = None
            event_timestamp = None
            exception_trace_ping_session_state = None

            # Ignore the check in the first 2 seconds
            if self.minimum_time - self.countdown_uds_request.time_elapsed > 0:
                continue

            # After the first 2 seconds following ecu_reset, perform RDBI_PING_SESSION_STATE (0x22 f1 00)
            # every 1000ms until request is accepted, as per 10505691-000-02 Fahrzeugprogrammierung: FL497
            # and FL496
            try:
                ecu_response = diagnostic_client.ping_session_state()
                event_timestamp = self.countdown_uds_request.time_elapsed
            except (EOFError, HsfzError, OSError, RuntimeError):
                exception_trace_ping_session_state = traceback.format_exc()
                self.responses_log.append(
                    (ecu_response, self.countdown_uds_request.time_elapsed, exception_trace_ping_session_state)
                )
            else:
                self.responses_log.append((ecu_response, event_timestamp, exception_trace_ping_session_state))
                # Wait until valid response is obtained
                if self.responses_log[-1][RESPONSE_PAYLOAD] is not None:
                    return event_timestamp
            time.sleep(self.poll_interval)

    def wait_for_target_reachability_network(self):
        """Perform regular network ping
        :return Tuple[bool, float]: to presents target_reachable and target_reachable_timestamp
        """
        while self.countdown_target_connected:
            # Get target reachability
            if target.check_network():
                return True, self.countdown_target_connected.time_elapsed
            time.sleep(self.poll_interval)

        return False, None

    def check_responses(self, test_cycle=""):
        """Check all responses to each request"""
        last_valid_response = None

        # Error message that details obtained responses or lack thereof
        error_msgs = [f"Failure on test cycle {test_cycle}: \n"]
        for response in self.responses_log:
            if response[RESPONSE_PAYLOAD] is not None:
                last_valid_response = response
                # Error message if ECU responded before performing reset
                # And no other requests have been processed
                error_msgs.append(
                    f"""Expected valid response to RDBI_PING_SESSION_STATE UDS request between
                    {self.minimum_time} - {self.timeout_value_uds_request[self.target_key]} seconds after reset.
                    But timestamp of last known response was: {last_valid_response[RESPONSE_TIMESTAMP]} seconds"""
                )
            else:
                # Error message if ECU did not respond at all
                error_msgs.append(
                    f"""Failed to ping ECU via UDS at timestamp: {response[RESPONSE_TIMESTAMP]} seconds. Handled
                    exception: {response[RESPONSE_EXCEPTION_TRACEBACK]}"""
                )

        error_msg = "\n".join(error_msgs)

        # Check last valid response was received after reset
        if last_valid_response is not None:
            assert_greater_equal(last_valid_response[RESPONSE_TIMESTAMP], self.minimum_time, error_msg)
            assert_less_equal(
                last_valid_response[RESPONSE_TIMESTAMP], self.timeout_value_uds_request[self.target_key], error_msg
            )
        # No responses have been found
        elif self.responses_log:
            final_error_msg = (
                "ECU did not respond to any RDBI_PING_SESSION_STATE UDS requests triggered within"
                f"{self.timeout_value_uds_request[self.target_key]} seconds after ECU Reset."
                f"List of failed attempts: {error_msg}"
            )
            raise AssertionError(final_error_msg)

    def ecu_reset(self, test_cycle=None):
        """Perform ECU reset and reboot checks"""
        error_msg_prepend = f"[Test cycle {test_cycle}]" if test_cycle else "[Test cycle]"
        metric_id_suffix = f"_consecutive_reset{test_cycle}" if test_cycle else "_consecutive_reset"

        # Trigger diagnosis ECU-Reset
        uds_request_error, exception_trace_ecu_reset = self.perform_ecu_reset()
        assert_false(
            uds_request_error,
            f"{error_msg_prepend} Failed to complete ECU Reset UDS request on test cycle. Traceback: "
            f"{exception_trace_ecu_reset}",
        )

        # Perform RDBI_PING_SESSION_STATE (0x22 f1 00) until request is accepted
        uds_request_accepted_timestamp = self.polling_uds_ping_session_state()
        if uds_request_accepted_timestamp:
            metric_logger.publish(
                {
                    "name": self.test_name,
                    "test_name": self.test_name,
                    "metric_id": f"uds_startup{metric_id_suffix}",
                    "timing_secs": uds_request_accepted_timestamp,
                }
            )

        # Wait until target is reachable, by performing regular network ping
        target_reachable, target_reachable_timestamp = self.wait_for_target_reachability_network()
        if target_reachable and target_reachable_timestamp:
            metric_logger.publish(
                {
                    "name": self.test_name,
                    "test_name": self.test_name,
                    "metric_id": f"target_rechable{metric_id_suffix}",
                    "timing_secs": target_reachable_timestamp,
                }
            )

        # Ensure UDS request has been accepted within time limit after ECU Reset
        self.check_responses(test_cycle)

        # Check if target is reachable within time limit after ECU Reset
        assert_true(
            target_reachable,
            f"{error_msg_prepend} Network ping not successful within "
            f"{self.timeout_value_target_connected[self.target_key]} seconds after ECU Reset",
        )
        assert_less_equal(
            target_reachable_timestamp,
            self.timeout_value_target_connected[self.target_key],
            f"{error_msg_prepend} Network ping was successful but exceeded limit of "
            f"{self.timeout_value_target_connected[self.target_key]} seconds after ECU Reset",
        )


class IntensiveRebootRunnerECUReset(IntensiveRebootRunner):
    """Intensive reboot test case for ecu reset"""

    def prepare(self):
        """Make sure the target boots with APP mode"""
        super().prepare()

        if not self._target.check_active_target("application.target"):
            self._target.reboot()
            self._target.resume_after_reboot(skip_ready_checks=False)
            logger.debug("target wasn't active, done reboot")


class IntensiveRebootRunnerCoding(IntensiveRebootRunnerECUReset):
    """Reboot and coding the target"""

    def __init__(self, test_name, *args, **kwargs):
        super().__init__(test_name, *args, **kwargs)

        self._ecu_reset = ECUReset(test_name)

    def prepare(self):
        """Make sure the target boots with APP mode"""
        super().prepare()

        self._ecu_reset.ecu_reset()
        if not self.reboot_check(-1, is_log=False):
            raise RuntimeError("ECU reset error")

    def reboot(self, boot_cycle, is_log=True):
        is_reboot = True

        reboot_steps = (
            ("coding_target", lambda: self._target.install_coding_esys(enable_doip_protocol=True)),
            ("ecu_reset_and_uds_check", lambda: self._ecu_reset.ecu_reset(boot_cycle)),
        )
        for step_name, func in reboot_steps:
            if not is_reboot:
                break

            error_log = None
            with StopWatch() as fun_step_watch:
                try:
                    func()
                except Exception as err:
                    error_log = str(err)
                    is_reboot = False

            logger.info(
                f"{self.test_name} - {boot_cycle}'th reboot on {step_name} - after {fun_step_watch.duration} secs"
            )

            if is_log:
                self.reporter.add_reboot_item_log(
                    boot_cycle, step_name, not bool(error_log), error_log, fun_step_watch.duration
                )
            elif error_log:
                logger.error(
                    "%s - %d'th reboot-step error - %s - %s", self.test_name, boot_cycle, step_name, error_log
                )

        return is_reboot


@metadata(testsuite=["SI-long", "IDCEVO-SP21"])
class TestIntensiveReboot:
    """Intensive reboot test cases"""

    def setup(self):
        """Test case preparation"""
        pass

    def teardown(self):
        """Test case teardown"""
        pass

    def _run_test(self, runner, test_case_name=""):
        """
        Run the IntensiveRebootRunner test case

        It also counts the running time for the test case and logs it.

        :param IntensiveRebootRunner runner: the runner
        :param str test_case_name: the name for logging.  If your test function
            name does not starts with "test_", please call the function with
            it.  Otherwise, the final logs show "unknown test case name".
        """
        # Get the test case name from callers
        # If the function name of the caller starts with "test_", it might be a
        # test case.
        if not test_case_name:
            frame = inspect.currentframe().f_back
            while frame:
                frameinfo = inspect.FrameInfo(*((frame,) + inspect.getframeinfo(frame)))
                if frameinfo.function.startswith("test_"):
                    test_case_name = frameinfo.function
                    break
                frame = frame.f_back

            test_case_name = test_case_name or "unknown test case name"

        with StopWatch() as test_exec:
            is_passed = runner.run()

        logging.info("%s exec time: %f", test_case_name, test_exec.duration)

        return is_passed

    @metadata(testsuite=["SI-long", "IDCEVO-SP21"], traceability={""})
    def test_001_intensive_reboot_ecu_reset_stability(self):
        """Check that there is no error happened for 50 times of ecu reset

            The test case runs ecu reset for 50 times. After each ecu reset, the
            test case will check uds state, ssh connection, hmi ready,
            unexpected_dtcs and crashed dlt messages. If there is an error happened,
            it will be recorded to the output file.

            After the tests of ecu reset, the test will reboot target to reset
            the status of target.

        **Pre-conditions**
            N/A

        **Required Steps**
            #. Trigger diagnosis ECU-Reset and check uds state
            #. Check that boot mode is not an empty string.
            #. Check that ssh connection is establishable.
            #. Check that unexpected dtcs are founded.
            #. Check that hmi ready message is founded.
            #. Check that the crash messages are detected.

        **Expected outcome**
            * No errors happen during the test

        **Output File**
            - `intensive_reboot/ecu_reset_intensive_reboot_report.json`
        """
        test_name = "ecu_reset"

        # The reboot_fun does
        # 1. Reset ecu
        # 2. Check uds state
        # 3. Check target network state through `target.check_network()`
        ecu_reset = ECUReset(test_name)

        runner = IntensiveRebootRunnerECUReset(
            test_name=test_name,
            reboot_times=REBOOT_CYCLES,
            description="Run ecu_reset function for 50 times.",
            expected_boot_mode="APP",
            reboot_fun=ecu_reset.ecu_reset,
            reboot_fun_name="ecu_reset_and_uds_check",
            pass_reboot_fun_boot_cycle=True,
        )
        assert_true(
            self._run_test(runner),
            f"Reboots failed: {runner.reporter.num_reboot_failed}, "
            f"After reboot checks failed:{runner.reporter.num_reboot_check_failed}. "
            "Please check intensive_reboot/ecu_reset_intensive_reboot_report.json for more details",
        )

    @skip("Not yet ready")
    @metadata(testsuite=["SI-long", "IDCEVO-SP21"], traceability={""})
    def test_002_intensive_reboot_coding_stability(self):
        """Check coding stability after 5 times reboot

        The test case runs ecu_reset then coding the target for 5 times.
        After the ecu_reset, it checks the target status to make sure
        that the target boots successfully.

        **Pre-conditions**
            N/A

        **Required Steps**
            #. Run coding target
            #. Trigger diagnosis ECU-Reset and check uds state
            #. Check that boot mode is not an empty string.
            #. Check that ssh connection is establishable.
            #. Check that unexpected dtcs are founded.
            #. Check that hmi ready message is founded.
            #. Check that the crash messages are detected.

        **Expected outcome**
            * No errors happen during the test
        """
        runner = IntensiveRebootRunnerCoding(
            test_name="coding_as_fast_as_possible",
            description="Coding and ecu_reset then check the reboot status for 5 times.",
            expected_boot_mode="APP",
            reboot_times=5,
        )
        assert_true(self._run_test(runner))

    @metadata(testsuite=["SI-long", "IDCEVO-SP21"], traceability={""})
    def test_003_intensive_reboot_into_app_mode_through_nsm(self):
        """Check that there is no error happened for 50 times of rebooting to APP mode through nsm

        **Pre-conditions**
            N/A

        **Required Steps**
            #. NSM reboot to APP mode
            #. Check that boot mode is not an empty string.
            #. Check that ssh connection is establishable.
            #. Check that unexpected dtcs are founded.
            #. Check that hmi ready message is founded.
            #. Check that the crash messages are detected.

        **Expected outcome**
            * No errors happen during the test

        **Output File**
            - `intensive_reboot/nsm_reboot_app_mode_intensive_reboot_report.json`
        """
        runner = IntensiveRebootRunner(
            test_name="nsm_reboot_app",
            reboot_times=REBOOT_CYCLES,
            description="Reboot to APP mode through NSM for 50 times",
            reboot_fun=target.boot_into_appl,
            reboot_fun_name="nsm_reboot_app",
            expected_boot_mode="APP",
            resume_before_reboot=False,
        )
        assert_true(
            self._run_test(runner),
            f"Reboots failed: {runner.reporter.num_reboot_failed}, "
            f"After reboot checks failed:{runner.reporter.num_reboot_check_failed}. "
            "Please check intensive_reboot/nsm_reboot_app_mode_intensive_reboot_report.json for more details.",
        )

    @metadata(testsuite=["SI-long", "IDCEVO-SP21"], traceability={""})
    def test_004_intensive_reboot_into_bol_mode_through_nsm(self):
        """Check that there is no error happened for 50 times of rebooting to BOL mode through nsm

        **Pre-conditions**
            N/A

        **Required Steps**
            #. NSM reboot to BOL mode
            #. Check that boot mode is not an empty string.
            #. Check that unexpected dtcs are founded.
            #. Check that the crash messages are detected.

        **Expected outcome**
            * No errors happen during the test

        **Output File**
            - `intensive_reboot/nsm_reboot_bol_mode_intensive_reboot_report.json`
        """
        runner = IntensiveRebootRunner(
            test_name="nsm_reboot_bol",
            reboot_times=REBOOT_CYCLES,
            description="Reboot to BOL mode through NSM for 50 times",
            reboot_fun=target.boot_into_flashing,
            reboot_fun_name="nsm_reboot_bol",
            expected_boot_mode="BOL",
            resume_before_reboot=False,
        )
        assert_true(
            self._run_test(runner),
            f"Reboots failed: {runner.reporter.num_reboot_failed}, "
            f"After reboot checks failed:{runner.reporter.num_reboot_check_failed}."
            "Please check intensive_reboot/nsm_reboot_bol_mode_intensive_reboot_report.json for more details.",
        )

    @skip("TODO to be implemented, Issue: IDCEVODEV-87061")
    @metadata(testsuite=["SI-long", "IDCEVO-SP21"], traceability={""})
    def test_005_intensive_reboot_into_rsu_mode_through_nsm(self):
        """Check that there is no error happened for 50 times of rebooting to RSU mode through nsm

        **Pre-conditions**
            N/A

        **Required Steps**
            #. NSM reboot to RSU mode
            #. Check that boot mode is not an empty string.
            #. Check that the crash messages are detected.

        **Expected outcome**
            * No errors happen during the test

        **Output File**
            - `intensive_reboot/nsm_reboot_rsu_mode_intensive_reboot_report.json`
        """
        with target.prepare_rsu_environment():
            target.prepare_for_reboot()
            runner = IntensiveRebootRunner(
                test_name="nsm_reboot_rsu",
                reboot_times=REBOOT_CYCLES,
                description="Reboot to RSU mode through NSM for 50 times",
                reboot_fun=target.boot_into_rsu,
                reboot_fun_name="nsm_reboot_rsu",
                expected_boot_mode="RSU",
                resume_before_reboot=False,
                serial=True,
            )
            assert_true(self._run_test(runner))

    @metadata(testsuite=["SI-boot-stability"], traceability={""})
    def test_006_intensive_reboot_into_app_mode_through_nsm(self):
        """[SIT_Automated] Intensive Reboot testing

        Steps:
            - NSM reboot to APP mode
            - Check that boot mode is not an empty string.
            - Check that ssh connection is establishabled.
            - Check that unexpected dtcs are founded.
            - Check that hmi ready message is founded.
            - Check that the crash messages are detected.
            - Wait 120s for give time to the system to stabilize

        Expected outcome
            No errors happen during the test

        **Output File**
            - `intensive_reboot/nsm_reboot_app_mode_intensive_reboot_report.json`
        """
        runner = IntensiveRebootRunner(
            test_name="nsm_reboot_app",
            reboot_times=200,
            description="Reboot to APP mode through NSM for 200 times",
            reboot_fun=target.boot_into_appl,
            reboot_fun_name="nsm_reboot_app",
            expected_boot_mode="APP",
            resume_before_reboot=False,
            cool_down_time_after_reboot=120,
        )
        assert_true(
            self._run_test(runner),
            f"Reboots failed: {runner.reporter.num_reboot_failed}, "
            f"After reboot checks failed:{runner.reporter.num_reboot_check_failed}. "
            "Please check intensive_reboot/nsm_reboot_app_mode_intensive_reboot_report.json for more details.",
        )
