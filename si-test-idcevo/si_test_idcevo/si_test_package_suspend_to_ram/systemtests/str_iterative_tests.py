# Copyright (C) 2025. BMW Car IT GmbH. All rights reserved.
"""Intensive-STR test cases"""
import logging
import re

from mtee.testing.test_environment import TEST_ENVIRONMENT, require_environment, require_environment_setup
from mtee.testing.tools import parse_whitelisted_ids
from si_test_idcevo.si_test_helpers.android_helpers import wait_for_all_widgets_drawn
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.diagnostic_helper import (
    check_and_disable_postpone_shutdown,
    enable_postpone_shutdown,
    get_postpone_shutdown_status,
)
from si_test_idcevo.si_test_helpers.report_helpers import IterativeSTRReporter
from si_test_idcevo.si_test_helpers.str_helpers import (
    get_str_state,
    perform_str,
    set_str_state_and_reboot_target,
    str_post_check_validations,
    str_pre_check_validations,
)
from tee.target_common import SocketConnectionMode, VehicleCondition
from tee.tools.dlt_helper import DLTLogLevelMapping, set_dlt_log_level
from tee.tools.lifecycle import LifecycleFunctions

lf = LifecycleFunctions()
logger = logging.getLogger(__name__)

NUMBER_OF_STR_CYCLES = 100
EXTRA_WHITELISTED_SERVICES = [
    "safety_A.service",
    "safety_B.service",
]


@require_environment(TEST_ENVIRONMENT.feature.suspend_to_ram)
class TestIterativeSTR:
    """Iterative STR test cases"""

    @classmethod
    @require_environment_setup(TEST_ENVIRONMENT.feature.suspend_to_ram)
    def setup_class(cls):
        """Enable STR code flag and disable postpone shutdown"""
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.test.mtee_target.user_data.remount_as_exec()

        set_dlt_log_level(DLTLogLevelMapping.info, SocketConnectionMode.UNIX)
        logger.info("Loglevel changed to info.")

        check_and_disable_postpone_shutdown(cls.test.diagnostic_client)
        assert (
            get_postpone_shutdown_status(cls.test.diagnostic_client) == "00"
        ), "Failed to disable Postpone Shutdown prior to test execution"

        if not get_str_state(cls.test):
            set_str_state_and_reboot_target(cls.test, 0)
            assert get_str_state(cls.test), "Failed to enable STR code flag prior to test execution"
        else:
            cls.test.mtee_target.reboot(prefer_softreboot=False)
            cls.test.mtee_target.wait_for_nsm_fully_operational()

        cls.test.apinext_target.wait_for_boot_completed_flag()
        wait_for_all_widgets_drawn(cls.test)

    @classmethod
    @require_environment_setup(TEST_ENVIRONMENT.feature.suspend_to_ram)
    def teardown_class(cls):
        """Re-enable postpone shutdown and disable STR code flag"""
        cls.test.mtee_target.user_data.remount_as_exec()

        set_dlt_log_level(DLTLogLevelMapping.debug, SocketConnectionMode.UNIX)
        logger.info("Loglevel changed to debug.")

        if get_str_state(cls.test):
            set_str_state_and_reboot_target(cls.test, 1)
            assert not get_str_state(cls.test), "Failed to disable STR code flag after test execution"

        if get_postpone_shutdown_status(cls.test.diagnostic_client) != "01":
            enable_postpone_shutdown(cls.test.diagnostic_client)
            assert (
                get_postpone_shutdown_status(cls.test.diagnostic_client) == "01"
            ), "Failed to enable Postpone Shutdown after test execution"

    def setup(self):
        """Ensure PWF State is WOHNEN and Android is up and running before each STR cycle"""
        if self.test.mtee_target.vehicle_state != VehicleCondition.WOHNEN:
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.WOHNEN)

        lf.setup_keepalive()
        if not lf.is_alive():
            self.test.mtee_target.reset_connector_dlt_state()
            lf.wakeup_target(wait_for_serial_reboot=False)
            # If ECU Still not alive trigger hard reboot:
            if not lf.is_alive():
                self.test.mtee_target.reboot(prefer_softreboot=False)
                self.test.apinext_target.wait_for_boot_completed_flag()
                wait_for_all_widgets_drawn(self.test)
            self.test.mtee_target.wait_for_nsm_fully_operational()
            assert lf.is_alive(), "Failed to wake up target before test execution"

    def teardown(self):
        """Restore target into awake state"""
        lf.set_default_vehicle_state()

        if not lf.is_alive():
            logger.debug("Sleeping after test execution, rebooting ...")
            lf.wakeup_target(wait_for_serial_reboot=False)
            self.test.mtee_target.wait_for_nsm_fully_operational()
            assert lf.is_alive(), "Failed to restore target state - Target is not alive after test execution"

    def test_str_iterations(self):
        """[SIT_Automated] STR Iterative Test

        "This test currently performs 100 STR successive iterations
        Individual and global metrics for all STR cycles, as well as eventual failure reasons, are reported in
        "test-artifacts/results/reports/test_str_iterations_report.json". Screenshots of the IDCEvo UI interfaces
        before and after each STR cycle are saved in results/str_iterative_tests/<number_of_the_str_iteration>

        A STR cycle is considered successful if the ECU goes through all this stages:
            1. Vehicle state is set to PARKEN
            2. Keep alive UDP message is stopped and "Suspending to Ram" DLT message is detected
            3. "Suspended Android VM" DLT message is detected
            4. Vehicle state is set to WOHNEN
            5. "Resuming from STR" and "Android VM running" DLT messages are detected.
            6. Resume Number is as expected, i.e., one unit higher than the last iteration
            7. Timestamp difference between host and target at the time of Resume is less than 139 seconds
            8. No service failures or coredumps are detected during the STR cycle

        In addition to this conditions, a pre check verification is performed in order to ensure that
        we can validate the CID UI after each STR cycle:
            1. Ensure that CID Launcher page is up and focused before entering STR

        Plus, three post checks are performed in order to validate the cycle:
            1. Confirm that CID and PHUD have the expected UI content after each cycle
            2. Confirm that target's network was down during the STR cycle
            3. Confirm that target stays awake after resuming from STR

        If any of the above steps fail during the routine, the STR cycle will be reported as failed,
        and the reason for the failure will be visible in the report json file.
        The test is only considered successful if no failures are detected in any of the STR cycles.

        Steps:
            - For each STR cycle defined in 'NUMBER_OF_STR_CYCLES':
                1. Ensure Launcher is up and loaded
                2. Perform STR routine and collect statistics
                3. Perform post check validations
                4. Update resume number after STR
                5. If errors happened during STR, add error info to 'error_msg'
                6. Add STR cycle summary for further reporting
                7. Prepare target for next STR iteration
                8. Publish all collected stats in json format

        Expected Outcome:
            1. All STR iterations are successful
        """
        resume_no_before_str = 0
        resume_no_after_str = 0
        failures_during_str = 0
        failures_during_pre_check_validation = 0
        failures_during_post_check_validation = 0
        str_duration = 0
        time_to_enter_str = 0
        time_to_exit_str = 0
        is_str_success = False
        is_str_pre_check_success = False
        is_str_post_check_success = False
        expected_cold_boot = False
        error_msg = ""

        reporter = IterativeSTRReporter(
            test_name="test_str_iterations",
            str_cycles=NUMBER_OF_STR_CYCLES,
            description=f"Run {NUMBER_OF_STR_CYCLES} STR consecutive iterations",
        )

        try:
            services_whitelist = parse_whitelisted_ids("/resources/services-whitelist-idcevo", [])
        except Exception:
            logger.info("Service whitelist could not be parsed, using default whitelist.")
            services_whitelist = []

        services_whitelist.extend(EXTRA_WHITELISTED_SERVICES)

        for str_cycle in range(1, NUMBER_OF_STR_CYCLES + 1):
            # For each str cycle, we create a new directory with the cycle number as name, under 'test.results_dir'
            # Screenshots taken throughout the cycle will be placed there
            screenshot_dir = "{0:03}".format(str_cycle)
            try:
                str_pre_check_validations(self.test, screenshot_dir)
                is_str_pre_check_success = True

                (
                    network_down,
                    current_resume_number,
                    str_duration,
                    time_to_enter_str,
                    time_to_exit_str,
                    expected_cold_boot,
                ) = perform_str(
                    self.test,
                    iteration=str_cycle,
                    resume_number_before_str=resume_no_before_str,
                    resume_number_after_str=resume_no_after_str,
                    services_whitelist=services_whitelist,
                )
                resume_no_after_str = current_resume_number
                is_str_success = True

                # If a cold boot was expected, then the STR post validations are not applicable
                if not expected_cold_boot:
                    str_post_check_validations(self.test, network_down, screenshot_dir)
                    is_str_post_check_success = True

            except Exception as e:
                # If pre check validations fail
                if not is_str_pre_check_success:
                    error_msg = f"STR iteration failed during pre check validations. Error: {str(e)}"
                    logger.debug(error_msg)
                    failures_during_pre_check_validation += 1
                    is_str_success = "STR cycle was not executed since pre-check was unsuccessful"
                    is_str_post_check_success = "Not applicable since pre-check was unsuccessful"

                # If STR failed during 'perform_str' method execution
                elif not is_str_success:
                    error_msg = f"Failed to Execute STR Successfully! {str(e)}"
                    logger.debug(error_msg)
                    error_splitted = [cause_of_error.strip() for cause_of_error in str(e).split(" | ")]

                    # If the failure was due to some error before entering STR
                    if "PowerStateMachine input: pwf is: PARKEN" in error_splitted[0]:
                        resume_no_after_str = 0

                    # If target entered PARKEN but some Error was raised before entering STR
                    elif "Failure entering STR!" in error_splitted[1]:
                        # If target still entered STR
                        if not "vm_control_suspended" or "entering_str" in error_splitted[0]:
                            resume_no_after_str += 1
                        # If target failed to enter STR
                        else:
                            resume_no_after_str = 0

                    # If the failure was due to a mismatch in STR Resume Number
                    elif not error_splitted[2].endswith("[]"):
                        # Search the mismatch message for the actual Resume Number received
                        resume_numbers = re.findall(r"\d+", str(e))
                        expected_resume_number = int(resume_numbers[0])
                        resume_no_after_str = int(resume_numbers[-1])
                        # If we were expecting a cold boot but it didn't happen
                        if expected_resume_number == 0:
                            expected_cold_boot = True

                    # If the failure was due to timestamp tolerance being exceeded
                    elif not error_splitted[3].endswith("[]"):
                        resume_no_after_str = 0

                    # If the failure was due to WOHNEN message or Resume messages not appearing
                    # but still the target entered STR
                    elif (
                        (
                            "entering_wohnen" in error_splitted[0]
                            or "resume_number" in error_splitted[0]
                            or "vm_control_resumed" in error_splitted[0]
                        )
                        and "vm_control_suspended" not in error_splitted[0]
                        and "entering_str" not in error_splitted[0]
                    ):
                        resume_no_after_str += 1

                    # If the failure was due to a detected service failure but still the STR cycle was successful
                    elif (
                        ("service_failure" in error_splitted[1] or "coredump_found" in error_splitted[1])
                        and error_splitted[0].endswith("[]")
                        and error_splitted[2].endswith("[]")
                        and error_splitted[3].endswith("[]")
                    ):
                        resume_no_after_str += 1

                    failures_during_str += 1
                    # If STR fails during 'perform_str', post check validations are not performed
                    is_str_post_check_success = "Not applicable since STR cycle was not successful"

                # If STR post check validations failed
                else:
                    error_msg = f"STR iteration failed during post check validations. Error: {str(e)}"
                    logger.debug(error_msg)
                    failures_during_post_check_validation += 1
                    # If a cold boot happened during post check validations, reset counter
                    if "Screenshot can be checked at:" in str(e):
                        resume_no_after_str = 0

            finally:
                reporter.add_str_cycle_summary(
                    str_cycle,
                    is_str_success,
                    is_str_pre_check_success,
                    is_str_post_check_success,
                    error_msg,
                    str_duration,
                    time_to_enter_str,
                    time_to_exit_str,
                    expected_cold_boot,
                )
                logger.debug(f"At iteration {str_cycle}:")
                logger.debug(f"Resume Number before STR: {resume_no_before_str}")
                logger.debug(f"Resume Number after STR: {resume_no_after_str}")

                resume_no_before_str = resume_no_after_str
                expected_cold_boot = False
                is_str_success = False
                is_str_post_check_success = False
                is_str_pre_check_success = False
                error_msg = ""
                str_duration = 0
                time_to_enter_str = 0
                time_to_exit_str = 0
                self.setup()

        total_failures = (
            failures_during_str + failures_during_post_check_validation + failures_during_pre_check_validation
        )
        reporter.add_report_summary()

        assert total_failures == 0, (
            f"Number of STR cycles failed: {total_failures}/{NUMBER_OF_STR_CYCLES}\n"
            f"Number of failures during STR execution: {failures_during_str}\n"
            f"Number of failures during STR pre-check-validations: {failures_during_pre_check_validation}\n"
            f"Number of failures during STR post-check-validations: {failures_during_post_check_validation}\n"
            f"Check 'results/reports/test_str_iterations_report.json' "
            "and 'results/str_iterative_tests' for more details."
        )
