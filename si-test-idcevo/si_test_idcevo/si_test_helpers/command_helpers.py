# Copyright (C) 2024. BMW Car IT. All rights reserved.
import logging
import os
import time
from typing import List, Union

from mtee.testing.tools import run_command
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target

logger = logging.getLogger(__name__)
test_base = TestBase.get_instance()


def check_result(result, expected_result: List[str]):
    """
    Validate if everything in "expected_result" is included in "result".
    Returns entries in "expected_result" that couldn't be found.
    Logs a warning message if an unexpected return code is found or if the result STDERR has content.

    Parameters:
    - result: The result returned by the command execution. Contains STDOUT, STDERR and return code.
    - expected_result: Expected output from command execution. Can be nothing, a string or list of strings.

    Returns:
    - missing_expected_result: List of expected results not found in the "result".
    An empty list will be returned if every "expected_result" is found.
    """
    missing_expected_result = []
    if result.returncode != 0:
        logger.warning(f"Executed command returned unexpected code: {result.returncode}.")
    if result.stderr:
        logger.warning(f"Executed command returned stderr: {result.stderr}.")
    logger.info(f"Response Received : {result.stdout}")
    for entry in expected_result:
        if entry not in result.stdout:
            missing_expected_result.append(entry)
    return missing_expected_result


def run_cmd_and_check_result(command: str, expected_result: Union[str, List[str]] = None):
    """
    Executes a command and validates the output against expected results.

    Parameters:
    - command: The command to be executed.
    - expected_result: Expected output from command execution. Can be nothing, a string or list of strings.

    Returns:
    - result: The result returned by the command execution. Contains STDOUT, STDERR and return code.
    - missing_expected_result: List of expected results not found in the "result".
    An empty list will be returned if every "expected_result" is found.
    """
    missing_expected_result = None
    if isinstance(expected_result, str):
        expected_result = [expected_result]

    logger.info(f"Command sent: {command}")
    # Default option for executing commands should be through SSH. If SSH fails, trying with serial
    try:
        result = test_base.mtee_target.execute_command(command)
        missing_expected_result = check_result(result, expected_result)
    except Exception as error:
        logger.debug(f"Command execution failed with exception : {error}")
        block = True if expected_result else False
        result = test_base.mtee_target.execute_console_command(command, block=block)
        if result is not None:
            missing_expected_result = check_result(result, expected_result)
    return result, missing_expected_result


def full_ram_dump(output_path=None):
    """Get a full RAM dump from the target
    Steps:
        1 - Send full ram dump to ipc channel
        2 - Trigger kernel panic
        3 - Wait for target to go into fastboot ramdump mode
        4 - Execute ramdump python script from harman
        5 - Reboot the target into application

    :param output_path (Path): Location were to store the RAM dump content.
        Defaults to ramdump_content folder on test-artifacts/results
    :return Bool: True if RAM dump successfully extracted, False if not
    """

    if not output_path:
        output_path = os.path.join(test_base.mtee_target.options.result_dir, "ramdump_content")
    os.mkdir(output_path)

    try:
        test_base.mtee_target._console.write(r"echo -e -n '\x01\x00\x00\x10\x00\x01' > /dev/ipc12")
        test_base.mtee_target._console.write(r"echo 1 > /sys/nk/prop/nk.panic-trigger")
        test_base.mtee_target._console.clear_read_queue()
        test_base.mtee_target._console.wait_for_re(r"fastboot is now in ramdump mode.*")
        test_base.mtee_target._console.wait_for_re(r"enumeration success.*")
        time.sleep(2)
        logger.info("Successfully entered fastboot ramdump mode")
    except Exception as e:
        logger.debug(f"Rebooting the Target, since target didn't go into fastboot ramdump {e}")
        test_base.mtee_target.reboot(prefer_softreboot=False)
        wait_for_application_target(test_base.mtee_target)
        return False

    try:
        logger.debug("Changing permissions and running ramdump script from harman")
        run_command(
            "chmod +x /images/ramdump/dumptool/bin/fastboot-eauto", cwd="/images/ramdump/dumptool/", shell=True
        )
        result = run_command(
            f"/usr/bin/env python3 eautodump.py -m all -t {output_path}",
            timeout=60 * 15,
            cwd="/images/ramdump/dumptool/",
            shell=True,
        )
        logger.debug(result)
    except Exception as e:
        logger.debug(f"Failed to run the ramdump python script {e}")
        test_base.mtee_target.reboot(prefer_softreboot=False)
        wait_for_application_target(test_base.mtee_target)
        return False

    try:
        test_base.mtee_target._console.wait_for_re(r"enumeration success.*")
        test_base.mtee_target._console.write("\x03")  # Ctrl^C
        time.sleep(1)
        test_base.mtee_target._console.write("boot")
        test_base.mtee_target._console.clear_read_queue()
        test_base.mtee_target.wait_for_reboot(serial=True)
        wait_for_application_target(test_base.mtee_target)
    except Exception as e:
        logger.debug(f"Failed recover target, force rebooting {e}")
        test_base.mtee_target.reboot(prefer_softreboot=False)
        wait_for_application_target(test_base.mtee_target)
        return True

    return True
