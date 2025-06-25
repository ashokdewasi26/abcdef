# Copyright (C) 2025. BMW CTW PT. All rights reserved.
"""Helpers for testing suspend to RAM."""
import logging
import os
import re
import time

from mtee.testing.connectors.connector_dlt import DLTContext
from si_test_idcevo.si_test_helpers.android_helpers import ensure_launcher_page, wait_for_all_widgets_drawn
from si_test_idcevo.si_test_helpers.apinext_target_handlers import LIST_HUD_DISPLAY_ID
from si_test_idcevo.si_test_helpers.dlt_helpers import check_dlt_trace
from si_test_idcevo.si_test_helpers.screenshot_utils import check_if_image_is_fully_black
from tee.target_common import VehicleCondition
from tee.tools.lifecycle import LifecycleFunctions
from validation_utils.utils import TimeoutCondition

logger = logging.getLogger(__name__)
lf = LifecycleFunctions()

COREDUMP_TIMEOUT = 30  # Timeout to check for coredumps after resuming from STR
MAX_SUCCESSIVE_STR_CYCLES_BEFORE_COLD_BOOT = 80  # Limit of consecutive STR iterations before cold boot
MAX_TIME_TO_GET_INTO_STR = 139  # This is the timeout to ensure target's network is down after going to STR
SERVICE_FAILURE_TIMEOUT = 5  # Timeout to check for service failures after resuming from STR
TOLERANCE_TO_LC_TMSP_DEVIATION = 10  # Deviations above this value may indicate that a cold boot happened during STR
STR_VERIFICATION_MESSAGES = {
    "entering_parken": (
        r"PowerStateMachine input: pwf is: PARKEN|"
        r".*NodeState: NsmNodeState_Shutdown.*NmState: BusSleepMode.*Bpn: NoCommunication.*"
    ),
    "entering_str": (
        r"Going to suspend to ram.*SUSPEND_TO_RAM.*|.*shutdownType.*SuspendToRam.*|Start for unit.*suspend.target"
    ),
    "entering_wohnen": (
        r"PowerStateMachine input: pwf is: WOHNEN|"
        r".*NodeState: NsmNodeState_FullyOperational.*NmState: ReadySleepState.*Bpn: Wohnen.*"
    ),
    "resume_number": r"ApplicationState:.*ResumeNumber: 0x([0-9a-fA-F]+)|ResumeNo: ([0-9]+)",
    "vm_control_suspended": r"MARKER vm shutdown started",
    "vm_control_resumed": r"MARKER vm running",
}
STR_FAILURE_MESSAGES = {
    "service_failure": r"Service failure: (.*service)",
    "coredump_found": r"Transfer complete for (\w+).*",
}


def check_network_down_during_str(max_time=MAX_TIME_TO_GET_INTO_STR):
    """Check if target network goes down after entering STR
    :param int max_time: timeout to check if network is down
    :returns bool: True, if target network is down, False otherwise
    """
    logger.info(f"Starting {max_time} second(s) timeout to check if network is down")
    timer = TimeoutCondition(max_time)
    while timer:
        time.sleep(1)
        if not lf.is_alive():
            logger.debug(f"Target network is down after {timer.time_elapsed}, Timeout was set to {max_time}")
            return True
    else:
        return False


def enter_str(test, missing_messages=[], fail_messages=[]):
    """Enter STR and wait for the ECU to be asleep
    :param TestBase test: instance of the test class
    :param list missing_messages: var to store missing message in case target does not enter in PARKEN state
    :returns tupple (
        target_uptime_before_str(float): /proc/uptime of the target before STR,
        worker_timestamp_before_str(float): last recorded timestamp of Worker before STR
    )
    """
    target_uptime_before_str = 0
    worker_timestamp_before_str = 0

    logger.info("Starting STR procedure... ")
    logger.info("Setting STANDFUNKTIONEN... ")

    try:
        test.mtee_target.switch_vehicle_to_state(VehicleCondition.STANDFUNKTIONEN_KUNDE_NICHT_IM_FZG)
        time.sleep(1)

        with DLTContext(test.mtee_target.connectors.dlt.broker, filters=[("NSG", "LCMG"), ("NSG", "NSG")]) as trace:
            logger.info("Setting PARKEN... ")
            test.mtee_target.switch_vehicle_to_state(VehicleCondition.PARKEN_BN_IO)
            parken_msg = check_dlt_trace(trace, rgx=STR_VERIFICATION_MESSAGES["entering_parken"])

            if not parken_msg:
                missing_messages.append(f"entering_parken: {STR_VERIFICATION_MESSAGES['entering_parken']}")
                raise RuntimeError("Failed to change Vehicle State to PARKEN before entering STR!")
            else:
                logger.info(f"Vehicle State changed to PARKEN: {parken_msg[-1].payload_decoded}")
                worker_timestamp_before_str = parken_msg[-1].storage_timestamp
                ret = test.mtee_target.execute_command("cat /proc/uptime", shell=True)
                target_uptime_before_str = float(ret.stdout.split()[0])

        logger.info(f"Target uptime before STR: {target_uptime_before_str}")
        logger.info(f"Host tmsp before STR: {worker_timestamp_before_str}")

        test.mtee_target.prepare_for_reboot()
        lf.stop_keepalive(stop_all=True)

    except Exception as e:
        # If the failure was due to other reason than the missing PARKEN message
        if not missing_messages:
            fail_messages.append(f"Failure entering STR! Error: {e}")
            raise RuntimeError(fail_messages)

    return target_uptime_before_str, worker_timestamp_before_str


def exit_str(test, missing_messages):
    """Resume from STR and restores SSH connection
    :param TestBase test: instance of the test class
    :param list missing_messages: var to store missing message in case target does not enter in WOHNEN state
    :returns tuple (
        target_uptime_after_str(float): /proc/uptime of the target after STR,
        worker_timestamp_after_str(float): last recorded timestamp of Worker after STR
    )
    """
    target_uptime_after_str = 0
    worker_timestamp_after_str = 0
    logger.info("Waking up from STR")

    with DLTContext(test.mtee_target.connectors.dlt.broker, filters=[("NSG", "LCMG"), ("NSG", "NSG")]) as trace:
        logger.info("Setting WOHNEN... ")
        test.mtee_target.switch_vehicle_to_state(VehicleCondition.WOHNEN)
        lf.setup_keepalive()
        test.mtee_target.wakeup_from_sleep()
        test.mtee_target._recover_ssh(record_failure=False)
        wohnen_msg = check_dlt_trace(trace, rgx=STR_VERIFICATION_MESSAGES["entering_wohnen"])

        if not wohnen_msg:
            missing_messages.append(f"entering_wohnen: {STR_VERIFICATION_MESSAGES['entering_wohnen']}")
            raise RuntimeError("Failed to change Vehicle State to WOHNEN before exiting STR!")
        else:
            logger.info(f"Vehicle State changed to WOHNEN: {wohnen_msg[-1].payload_decoded}")
            worker_timestamp_after_str = wohnen_msg[-1].storage_timestamp
            ret = test.mtee_target.execute_command("cat /proc/uptime", shell=True)
            target_uptime_after_str = float(ret.stdout.split()[0])

    logger.info(f"Targer tmsp after STR: {target_uptime_after_str}")
    logger.info(f"Host tmsp after STR: {worker_timestamp_after_str}")

    return target_uptime_after_str, worker_timestamp_after_str


def get_str_resume_number(match):
    """Get the Resume Number from the DLT payload Match Object
    :param re.Match match: Regex Match Object, which contains resume number
    :returns int resume_number: Resume Number from match
    """
    val = next(filter(None, match.groups()))
    base = 16 if match.group(1) else 10
    resume_number = int(val, base)
    return resume_number


def get_str_state(test):
    """Check STR state by devcoding command
    :param TestBase test: instance of the test class
    :return bool: True if enabled, False if disabled
    """
    str_state_regex = re.compile(r"LIFECYCLE.*SHUTDOWN_TARGET = (?P<state>[a-z].*_[a-z].).*")
    cmd_check_str_state = "devcoding read SHUTDOWN_TARGET"

    stdout, stderr, return_code = test.mtee_target.execute_command(cmd_check_str_state)

    assert (
        return_code == 0
    ), f"Failure reading STR state, returned code: {return_code}\nstdout: {stdout}\nstderr: {stderr}"

    match = re.search(str_state_regex, stdout)
    assert match, "Couldn't get current state of STR"
    str_state = True if "instant_on" in match.group("state") else False

    if str_state:
        logger.info("STR is Enabled!")
    else:
        logger.info("STR is Disabled!")

    return str_state


def perform_str(
    test,
    expected_messages=STR_VERIFICATION_MESSAGES,
    non_expected_messages=STR_FAILURE_MESSAGES,
    iteration=0,
    resume_number_before_str=0,
    resume_number_after_str=0,
    services_whitelist=None,
):
    """Perform SuspendToRam procedure, Resume the target and perform DLT verifications
    :param TestBase test: instance of the test class
    :param dict expected_messages: Messages to match in DLT collection
    :param dict non_expected_messages: Messages not expected in DLT collection
    :param int iteration: STR Iteration count, default to 0
    :param int resume_number_before_str: Resume Number before performing STR, default to 0
    :param int resume_number_after_str: Resume Number after performing STR, default to 0
    :returns tupple (
        network_down (bool): True, if target's network is down,
        resume_number_after_str (int): Resume Number detected in the respective DLT message after resuming from STR
        str_duration (float): total time the target was suspended during the cycle
        time_to_enter_str (float): time it took between target switching to PARKEN and Suspend DLT message coming up
        time_to_exit_str (float): time it took between target switching to WOHNEN and Resume DLT message coming up
        expected_cold_boot (bool): this value is set to True if in the current cycle we expected a cold boot to happen
    )
    """
    entering_str_timestamp = 0
    resume_msg_timestamp = 0
    str_duration = 0
    time_to_enter_str = 0
    time_to_exit_str = 0
    worker_timestamp_before_str = 0
    resume_number_after_str = resume_number_before_str + 1
    missing_msgs = []
    fail_messages = []
    resume_no_mismatch_msgs = []
    timestamp_tolerance_exceeded_msgs = []
    expected_cold_boot = False

    logger.info("Starting STR Routine!")

    with DLTContext(
        test.mtee_target.connectors.dlt.broker,
        filters=[("NSM", None), ("NSG", None), ("CDM", None), ("RECM", None), ("VMC", "VMC")],
    ) as trace:
        try:
            target_uptime_before_str, worker_timestamp_before_str = enter_str(test, missing_msgs, fail_messages)
            network_down = check_network_down_during_str()
            if network_down:
                # Delay for ECU to suspend after Network down
                time.sleep(10)
                test.mtee_target.reset_connector_dlt_state()

            with DLTContext(
                test.mtee_target.connectors.dlt.broker, filters=[("NSM", None), ("NSG", None), ("VMC", "VMC")]
            ) as resume_trace:
                target_uptime_after_str, worker_timestamp_after_str = exit_str(test, missing_msgs)
                test.mtee_target.wait_for_nsm_fully_operational()

                # Check if Android VM was correctly resumed
                vm_control_resume_msg = check_dlt_trace(
                    resume_trace, rgx=expected_messages["vm_control_resumed"], timeout=60
                )
                if not vm_control_resume_msg:
                    missing_msgs.append(f"vm_control_resumed: {expected_messages['vm_control_resumed']}")
                else:
                    logger.info(
                        f"vm_control_resumed DLT message detected: {vm_control_resume_msg[-1].payload_decoded}"
                    )

                # Check if 'Resume Number' DLT message came up after target switching to WOHNEN
                resume_msg = check_dlt_trace(resume_trace, rgx=expected_messages["resume_number"], timeout=60)
                if not resume_msg:
                    missing_msgs.append(f"resume_number: {expected_messages['resume_number']}")
                else:
                    # Store the number present in 'Resume Number' DLT message
                    match = re.search(expected_messages["resume_number"], resume_msg[-1].payload_decoded)
                    logger.info(f"resume_number DLT message detected: {resume_msg[-1].payload_decoded}")
                    current_resume_no = get_str_resume_number(match)
                    if resume_number_after_str == MAX_SUCCESSIVE_STR_CYCLES_BEFORE_COLD_BOOT:
                        expected_resume_no = 0
                        expected_cold_boot = True
                    else:
                        expected_resume_no = resume_number_after_str

                    # Store the time it took to Resume after target switching to WOHNEN
                    resume_msg_timestamp = resume_msg[-1].storage_timestamp
                    time_to_exit_str = resume_msg_timestamp - worker_timestamp_after_str

                    logger.debug(f"At iteration {iteration}:")
                    logger.debug(f"Current Resume Number: {current_resume_no}")
                    logger.debug(f"Expected Resume Number: {expected_resume_no}")

                    # Check if the obtained Resume Number was the expected
                    if expected_resume_no != current_resume_no:
                        resume_no_mismatch_msgs.append(
                            f"Expected {str(expected_resume_no)} but got: {str(current_resume_no)}"
                        )
                        resume_number_after_str = current_resume_no

            # If in the current STR iteration we were expecting a cold boot,
            # we don't want to proceed with further verifications
            if resume_number_after_str != MAX_SUCCESSIVE_STR_CYCLES_BEFORE_COLD_BOOT:
                # Following time differences must be similar:
                time_diff_host = worker_timestamp_after_str - worker_timestamp_before_str
                time_diff_target = target_uptime_after_str - target_uptime_before_str
                time_diff_between_host_and_target = time_diff_host - time_diff_target
                logger.info(f"Time diff in Host: {time_diff_host}")
                logger.info(f"Must be similar to Time diff in target: {time_diff_target}")

                # If Resume Number is the expected but timestamp difference exceeds the tolerance
                if not resume_no_mismatch_msgs and time_diff_between_host_and_target > TOLERANCE_TO_LC_TMSP_DEVIATION:
                    timestamp_tolerance_exceeded_msgs.append(
                        "Timestamp difference between host and target after STR exceeds "
                        f"{TOLERANCE_TO_LC_TMSP_DEVIATION} second tolerance. Cold boot might have happened!"
                    )
                    raise RuntimeError(
                        "Timestamp difference between host and target exceeds tolerance. Cold boot might have happened"
                    )

        except Exception as e:
            logger.exception(f"Failure during STR execution!: Error: {str(e)}")

        # This block verifies if the expected "suspend to ram" DLT messages were detected.
        # It also verifies if any service failure or coredump was raised during or after STR
        finally:
            # If in the current STR iteration we were expecting a cold boot,
            # we don't want to proceed with further verifications
            if resume_number_after_str != MAX_SUCCESSIVE_STR_CYCLES_BEFORE_COLD_BOOT:
                # Check if Android VM was correctly suspended
                vm_control_suspended_msg = check_dlt_trace(trace, rgx=expected_messages["vm_control_suspended"])
                if vm_control_suspended_msg:
                    logger.info(
                        f"vm_control_suspended DLT message detected: {vm_control_suspended_msg[-1].payload_decoded}"
                    )
                else:
                    missing_msgs.append(f"vm_control_suspended: {expected_messages['vm_control_suspended']}")

                # Check if 'Suspending to Ram' DLT message came up after target switching to PARKEN
                entering_str_msg = check_dlt_trace(trace, rgx=expected_messages["entering_str"])
                if entering_str_msg:
                    logger.info(f"entering_str DLT message detected: {entering_str_msg[-1].payload_decoded}")
                    # Store the time it took to Suspend after target switching to PARKEN
                    entering_str_timestamp = entering_str_msg[-1].storage_timestamp
                    time_to_enter_str = entering_str_timestamp - worker_timestamp_before_str
                else:
                    missing_msgs.append(f"entering_str: {expected_messages['entering_str']}")

                # Total time target spent in 'Suspended' state
                str_duration = resume_msg_timestamp - entering_str_timestamp

                # Check for service failures or coredumps detected, during or after STR
                for item, message in non_expected_messages.items():
                    timeout = SERVICE_FAILURE_TIMEOUT if item == "service_failure" else COREDUMP_TIMEOUT
                    # Check if any of the DLT regex's present in "STR_FAILURE_MESSAGES" are detected
                    msg = check_dlt_trace(trace, rgx=message, timeout=timeout)
                    if msg:
                        match = re.search(message, msg[-1].payload_decoded)
                        if match.group(1) in services_whitelist:
                            logger.info(f"Service {match.group(1)} is whitelisted, skipping service failure")
                            continue
                        fail_messages.append(": ".join((item, match.group(1) if match.group(1) else message)))

        # If any missing message or failure was detected during or after the STR cycle,
        # we raise an Error message featuring all the detected errors
        if missing_msgs or fail_messages or resume_no_mismatch_msgs or timestamp_tolerance_exceeded_msgs:
            raise AssertionError(
                f"Missing log: {missing_msgs} | Fail log: {fail_messages} | "
                f"Resume Number Mismatch log: {resume_no_mismatch_msgs} | "
                f"Timestamp tolerance log: {timestamp_tolerance_exceeded_msgs}"
            )

        # If we detect an expected cold boot, resume_number_after_str var has to be updated before returning otherwise
        # we will be expecting Resume Number = MAX_SUCCESSIVE_STR_CYCLES_BEFORE_COLD_BOOT + 1 in the next cycle
        if expected_cold_boot and current_resume_no == expected_resume_no:
            resume_number_after_str = current_resume_no

        # If no errors were detected during the cycle, we return the cycle statistics for further reporting
        return (
            network_down,
            resume_number_after_str,
            str_duration,
            time_to_enter_str,
            time_to_exit_str,
            expected_cold_boot,
        )


def set_str_state_and_reboot_target(test, state):
    """Set STR state with devcoding command
    :param TestBase test: instance of the test class
    :param int state: 0 - instant_on | 1 - full_off
    """
    cmd = f"devcoding write SHUTDOWN_TARGET {state}"
    stdout, stderr, return_code = test.mtee_target.execute_command(cmd, shell=True)

    assert (
        return_code == 0
    ), f"Failed changing STR state to {state}, returned code: {return_code}\nstdout: {stdout}\nstderr: {stderr}"

    test.mtee_target.reboot(prefer_softreboot=False)
    test.mtee_target.wait_for_nsm_fully_operational()


def str_post_check_validations(test, network_down, screenshot_dir):
    """Post checks to perform after STR cycle
    :param network_down bool: True if network was down during STR cycle, False otherwise
    :param screenshot_dir str: Folder where the screenshots will be saved
    :raises RuntimeError if any assertion fails
    """
    # Path to save the display's screenshots
    screenshot_path = os.path.join(test.results_dir, screenshot_dir)

    try:
        logger.info("Waiting for Launcher App to be focused after STR!")
        ensure_launcher_page(test, screenshot_dir, "_after_str", False)
        # Ensure CID is not displaying a black image after resuming from STR
        if check_if_image_is_fully_black(os.path.join(screenshot_path, "launcher_focused_after_str.png")):
            # If a black image is detected, a cold boot is performed
            test.mtee_target.reboot(prefer_softreboot=False)
            test.mtee_target.wait_for_nsm_fully_operational()
            test.apinext_target.wait_for_boot_completed_flag()
            wait_for_all_widgets_drawn(test)
            raise AssertionError(
                f"CID is displaying a black image after STR! "
                f"Screenshot can be checked at: {screenshot_path}/launcher_focused_after_str.png"
            )
        # Ensure all HUD's screenshots taken after STR show content
        for display, id in LIST_HUD_DISPLAY_ID.items():
            test.take_apinext_target_screenshot(screenshot_path, display + "_after_str", id)
            hud_screenshot_path = os.path.join(screenshot_path, display + "_after_str.png")
            error_msg = (
                f"'{display}' display does not show content after STR. "
                f"Screenshot can be checked at: {hud_screenshot_path}"
            )
            if check_if_image_is_fully_black(hud_screenshot_path):
                # If a black image is detected, a cold boot is performed
                test.mtee_target.reboot(prefer_softreboot=False)
                test.mtee_target.wait_for_nsm_fully_operational()
                test.apinext_target.wait_for_boot_completed_flag()
                wait_for_all_widgets_drawn(test)
                raise AssertionError(error_msg)

        # Check if target's network was down during the STR cycle
        assert network_down, "Network was not down during STR!"

        # Validate that target stays alive after resuming from STR
        sleep_after_str = lf.ecu_to_enter_sleep(timeout=30)
        assert not sleep_after_str, "Target went into shutdown after resuming from STR!"

    except Exception as e:
        raise RuntimeError(str(e))


def str_pre_check_validations(test, screenshot_dir):
    """Check if CID Launcher page is up and focused before entering STR.
    :param screenshot_dir str: Folder where the screenshots will be saved
    """
    # Path to save the display's screenshots
    screenshot_path = os.path.join(test.results_dir, screenshot_dir)
    os.mkdir(screenshot_path)
    logger.info("Waiting for Launcher App to be focused before STR!")
    ensure_launcher_page(test, screenshot_dir, "_before_str", False)
