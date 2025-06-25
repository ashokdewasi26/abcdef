# Copyright (C) 2024. BMW Car IT. All rights reserved.
import logging
import re

from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import assert_false, assert_process_returncode, run_command
from nose.tools import assert_in

logger = logging.getLogger(__name__)

PARTUUID_PATTERN = r"PARTUUID=([0-9a-fA-F\-]+)"
ROOT_PATTERN = r"root=([^ ]+)"

target = TargetShare().target


def disable_dm_verity():
    """
    Disabling dm-verity with disable_dm_verity.sh script.
    """
    dmverity_result = target.disable_dm_verity(reboot_after_disable=True)
    if dmverity_result:
        target.options.disable_dm_verity = True


def adb_disable_verity():
    """
    Disabling dm-verity in android with adb commands.

    Steps:
        1 - Disable dm-verity on Android with an ADB command
        2 - Reboot
        3 - Remount the device and check if it was successful
        4 - Check if the android device is set successfully
    """
    try:
        # Restarts adb as root
        run_command_on_host(["adb", "root"])
        logger.info("Disabling dm-verity on Android device")
        run_command_on_host(["adb", "disable-verity"], timeout=300)
        target.reboot(prefer_softreboot=False)
        run_command_on_host(["adb", "wait-for-device", "devices"], timeout=60)
        run_command_on_host(["adb", "root"])

        logger.info("Remounting the target after disabling dm-verity...")
        remount_cmd = ["adb", "remount"]
        remount_result = run_command(remount_cmd, timeout=600)
        logger.info(
            f"Execute command: {remount_cmd}, stdout: {remount_result.stdout}, stderr: {remount_result.stderr}"
        )
        is_remounted = "remount succeeded" in remount_result.stdout and remount_result.returncode == 0
        is_remounted = is_remounted or (
            "Now reboot your device for settings to take effect" in remount_result.stderr
            and remount_result.returncode != 0
        )

        if not is_remounted:
            logger.info("Fail to remount after disabling dm-verity! Rebooting the target again...")
            target.reboot(prefer_softreboot=False)
            run_command_on_host(["adb", "wait-for-device", "devices"], timeout=60)
            run_command_on_host(["adb", "root"])
            run_command_on_host(["adb", "remount"], timeout=600, exp_result=["remount succeeded"])
        else:
            logger.info("Remount succeeded after disabling dm-verity.")

        run_command_on_host(["adb", "devices"])
        output = run_command(["adb", "shell", "uname", "-a"])
        assert_process_returncode(0, output)

        return is_remounted

    except AssertionError as e:
        logger.info(f"AssertionError as e: '{e}'")

        # Collects logs in case any failures in adb remount
        try:
            result_dir = target.options.result_dir
            logging.info(result_dir)

            target.execute_console_command("dmesg > /data/local/tmp/dmesg_log.txt")
            target.execute_console_command("chmod 0777 /data/local/tmp")
            run_command_on_host(f"adb pull /data/local/tmp/dmesg_log.txt {result_dir}", shell=True)
            target.execute_console_command("logcat -b all > /data/local/tmp/logcat_adb.txt")
            raise Exception("adb remount failed")
        except RuntimeError as e:
            logger.info(f"RuntimeError as e: '{e}'")
            run_command_on_host(f"adb pull /data/local/tmp/logcat_adb.txt {result_dir}", shell=True)
            raise Exception("adb remount failed")


def execute_cmd_and_validate(command, exp_result=None):
    """
    Function to send the command and validate the output
    :param str command: commands to be sent
    :param list | str exp_result: Expected output string
    :returns: Response received for command
    """
    if exp_result is None:
        exp_result = []
    elif isinstance(exp_result, str):
        exp_result = [exp_result]
    logging.info(f"Command sent: {command}")
    # Default option for executing commands should be through SSH. If SSH fails, trying with serial
    try:
        result = target.execute_command(command)
        validate_output(result, exp_result)
    except Exception as error:
        logger.debug(f"Command execution failed with exception : {error}")
        block = True if exp_result else False
        result = target.execute_console_command(command, block=block)
        if result is not None:
            validate_output(result, exp_result)
    return result


def run_command_on_host(cmd, exp_result=None, timeout=60, shell=False):
    """Function to execute the given command in host pc
    :param command: Command to be executed
    :type command: string
    :param exp_result: Expected result
    :type exp_result: list
    :param timeout: time taken to execute the command
    :type timeout: integer
    :param shell: shell
    :type shell: bool
    ...
    :raises RuntimeError: If command execution fails
    """
    result = run_command(cmd, timeout=timeout, shell=shell)
    logger.info("Execute command: %s, stdout: %s, stderr: %s" % (cmd, result.stdout, result.stderr))
    if exp_result:
        if result.stdout:
            for expected in exp_result:
                assert_in(
                    expected, result.stdout, "Mismatch in result. Expected: %s, Actual: %s" % (expected, result.stdout)
                )
        else:
            raise RuntimeError("Error on result: %s" % result.stderr)


def validate_output(result, exp_result):
    """
    Validate received response from target
    :param ProcessResult result: Actual response from Target
    :param list exp_result: Expected output string
    """

    assert_process_returncode(0, result)
    if exp_result:
        if not result.stderr:
            logging.info(f"Response Received : {result.stdout}")
            for expected in exp_result:
                assert_in(
                    expected, result.stdout, f"Mismatch in result. Expected: {expected}, Actual: {result.stdout}"
                )
        else:
            assert_false(bool(result.stderr), f"Error on result. {result.stderr}")


def validate_output_using_regex_list(result, regex_list):
    """
    Validate received response from target with a list of regex
    Will pass only when result matches all the regex in the provided list
    :param ProcessResult result: Actual response from Target
    :param list regex_list: Regex list to match with output string
    """
    for regex in regex_list:
        match = re.search(regex, result.stdout)
        if match is None:
            return False
        else:
            logger.info(f"Expected string- {regex} found")
    return True
