# Copyright (C) 2023. BMW CTW PT. All rights reserved.

import logging
import time
import sh

from si_test_idcevo.si_test_helpers.android_helpers import ensure_launcher_page
from tee.target_common import NsmRestartReasons  # noqa: AZ100
from tee.tools.lifecycle import LifecycleFunctions
from validation_utils.utils import TimeoutCondition

lf = LifecycleFunctions()
logger = logging.getLogger(__name__)


def reboot_no_wait(mtee_target, sleep_time=None, prefer_softreboot=True):
    """Perform a reboot in the HU with possibility to not wait for reboot
    :param logger: test logger object
    :param mtee_target: test mtee_target object
    :param sleep_time: number of seconds to sleep before rebooting
    :param prefer_softreboot: if false, performs hard reboot using power supply
    """

    if sleep_time is not None:
        time.sleep(sleep_time)
        logger.info(f"Rebooting after {sleep_time}s")

    logger.info("Rebooting...")

    if prefer_softreboot:
        cmd = "nsm_control --requestRestart {}".format(NsmRestartReasons.Application)
        mtee_target.execute_command(cmd)
        mtee_target.prepare_for_reboot()
    else:
        logger.info("Rebooting target using power supply")
        mtee_target.prepare_for_reboot()
        mtee_target._power_off()
        time.sleep(10)
        mtee_target._power_on()


def reboot_and_wait_for_android_target(test, wait_time=180, prefer_softreboot=True):
    """Perform a reboot in the HU and ensure the android target is available
    :param test: Testbase object
    :param wait_time: timeout for boot completed flag, defaults to 180
    :param prefer_softreboot: Set to False for performing hard reboot, default is set to True i.e. soft reboot
    """

    try:
        test.mtee_target.reboot(prefer_softreboot=prefer_softreboot)
        test.apinext_target.wait_for_boot_completed_flag(wait_time=wait_time)
        ensure_launcher_page(test)
        return
    except sh.TimeoutException:
        pass

    logger.info(f"Android was not initialized properly ({wait_time} seconds). Doing hard/cold reboot")
    test.mtee_target.reboot(prefer_softreboot=False)
    test.apinext_target.wait_for_boot_completed_flag()
    ensure_launcher_page(test)


def reboot_using_serial(mtee_target):
    """Reboot the target using serial"""
    cmd = f"nsg_control --requestRestart {NsmRestartReasons.Application}"
    mtee_target.execute_console_command(cmd)
    mtee_target.prepare_for_reboot()
    mtee_target.wait_for_reboot(serial=True, skip_ready_checks=True)


def is_application_mode(mtee_target):
    return_stdout, _, return_code = mtee_target.execute_command(["systemctl", "is-active", "application.target"])
    return return_code == 0 and return_stdout == "active"


def wait_for_application_target(mtee_target, timeout=130):
    """Wait for application target to be active with timeout (defaults to 130s)"""
    timeout_condition = TimeoutCondition(timeout)
    while timeout_condition:
        if is_application_mode(mtee_target):
            return True
        time.sleep(5)
    return False


def ensure_application_target_for_specific_timeout(mtee_target, timeout=30):
    """Ensure target is in application mode throughout timeout condition (defaults to 30)"""
    timeout_condition = TimeoutCondition(timeout)
    while timeout_condition:
        if not is_application_mode(mtee_target):
            return False
        time.sleep(3)
    return True


def wakeup_from_sleep_and_restore_vehicle_state(test):
    """This function can be used to wakeup the target and switch to default vehicle state in case if not alive.
    Specially in cases when target is switch to PARKEN OR STANDFUNCTION and a teardown is needed.
    :param test: Testbase object
    """
    if not lf.is_alive():
        logger.debug("Waking up the target after PWF transition State")
        test.mtee_target.wakeup_from_sleep()
        lf.setup_keepalive()
    lf.set_default_vehicle_state()
    test.mtee_target.resume_after_reboot()
