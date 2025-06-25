# Copyright (C) 2022. BMW CTW. All rights reserved.
import logging
import os
from pathlib import Path
import re
import subprocess
import time

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import retry_on_except, TimeoutCondition, TimeoutError
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.media_page import MediaPage as Media
from si_test_apinext.util.global_steps import GlobalSteps

USB_ANDROID_PATH = "/mnt/user/"
ANDROID_KEYCODE_VOLUME_MUTE = 164
# Recovery attempts of USB
RECOVERY_ATTEMPTS = 4
USB_TIMEOUT = 65
logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


def check_usb_available(apinext_target, timeout=USB_TIMEOUT, mnt_usb_path=USB_ANDROID_PATH):
    """Check if an USB drive is mounted under a /mnt path, if it is returns it

    :param apinext_target: target instance to be able to execute the commands
    :type apinext_target: target
    :param timeout: given timeout to check USB (check is done from 5 in 5s)
    :type timeout: int, optional
    :param mnt_usb_path: alternative path to check USB instead of the default
    :type mnt_usb_path: str, path

    """
    current_user = str(apinext_target.get_current_user_id())

    cmd = ["ls", mnt_usb_path + current_user]

    logger.info("Waiting {}s for USB".format(timeout))
    timeout_condition = TimeoutCondition(timeout)
    try:
        while timeout_condition():
            logger.info("Executing target command: {}".format(cmd))
            response = str(apinext_target.execute_command(cmd, privileged=True)).splitlines()
            if response[0] not in ["emulated", "self"]:
                usb_drive = response[0]
                logger.info("Found USB - {}, after {}s".format(usb_drive, int(timeout_condition.time_elapsed)))
                return usb_drive
            else:
                logger.info("No USB available after {}s".format(int(timeout_condition.time_elapsed)))
                time.sleep(5)
    except TimeoutError:
        logger.info("No USB found within {}s".format(timeout))
        return None


def reset_usb(usb_controller, apinext_target, timeout=USB_TIMEOUT, retry_attempts=RECOVERY_ATTEMPTS):
    """Reset USB and wait for it to be available under a /mnt path

    :param usb_controller: usb controller instance
    :type usb_controller: USBControl instance
    :param apinext_target: target instance to send commands
    :type apinext_target: target
    :param timeout: given timeout to check USB
    :type timeout: int, optional
    :param retry_attempts: number of attempts to reset USB if it fails
    :type retry_attempts: int, optional

    :return: Return usb device name under /mnt or None
    :rtype: str, None
    """

    for i in range(retry_attempts):
        logger.info("Resetting USB... attempt {}/{}".format((i + 1), retry_attempts))
        usb_controller.power_off()
        time.sleep(2)
        usb_controller.power_on()
        usb_drive = check_usb_available(apinext_target, timeout)
        if usb_drive is not None:
            return usb_drive

    raise RuntimeError(
        f"No USB drive available in {timeout} seconds, in {retry_attempts} attempts, cannot proceed with the test"
    )


def push_audio_file_to_usbdrive(apinext_target, audio_file, usb_path, force=False):
    """Push audio file to usbdrive path

    1. Receive an audio file.
    2. Receive USB drive path to copy
    3. Makes sure directory is empty.
    4. Uploads the audio file to the path inside the drive.

    :param apinext_target: target to push the file
    :type apinext_target: target
    :param audio_file: audio file to be pushed into target
    :type audio_file: str, path
    :param usb_path: path to the usb
    :type usb_path: str, path
    :param force: Force the pushing of file even if it exists
    :type force: bool

    :raises RuntimeError: if no USB drive available
    """

    if not audio_file.is_file():
        raise RuntimeError("Audio file not found")
    logger.info("Loading audio file: {}".format(audio_file))
    audio_file_name = Path(audio_file).name

    temp_file_path = "/sdcard/" + audio_file_name
    apinext_target.push_as_current_user(audio_file, temp_file_path)

    cmd = ["ls", usb_path]
    logger.info("Executing target command: {}".format(cmd))
    response = str(apinext_target.execute_command(cmd, privileged=True)).splitlines()
    if len(response) != 0:
        if not force and audio_file_name in response:
            logger.info("audio file {} is already present in the USB. Will avoid recopying".format(audio_file_name))
            return
        # erase all from inside Music folder
        for file in response:
            rm_cmd = ["rm", os.path.join(usb_path, file)]
            logger.info("Executing target command to remove file: {}".format(rm_cmd))
            response = str(apinext_target.execute_command(rm_cmd, privileged=True)).splitlines()

    cmd = ["mv", temp_file_path, usb_path]
    logger.info("Executing target command: {}".format(cmd))
    response = str(apinext_target.execute_command(cmd, privileged=True)).splitlines()
    logger.info("Result of moving file to Music folder: {}".format(response))
    time.sleep(2)


def press_mute_get_status(mtee_target, driver):
    """
    Press ANDROID_KEYCODE_VOLUME_MUTE and parse mute status from DLT

    :param mtee_target: mtee_target object
    :param driver: WebDriver object
    :return: status of mute on target
    :rtype: str
    """
    with DLTContext(mtee_target.connectors.dlt.broker, filters=[("AUDI", "DEF")]) as dlt_detector:
        dlt_msg = r"muteState= (\w+)"
        search_text = re.compile(dlt_msg)
        driver.keyevent(ANDROID_KEYCODE_VOLUME_MUTE)
        messages_list = dlt_detector.wait_for(
            {"apid": "AUDI", "ctid": "DEF", "payload_decoded": search_text},
            timeout=10,
            regexp=True,
        )
        if not messages_list:
            raise RuntimeError("No DLT mute message found")
        good_msgs = []
        for msg in messages_list:
            if "muteState=" in msg.payload_decoded:
                good_msgs += [msg]
        assert len(good_msgs) == 1, "Found more than one expected messages"
        mute_status = search_text.search(good_msgs[0].payload_decoded).group(1)
        logger.info(f"Found this mute status: '{mute_status}'")
        time.sleep(1)
        return mute_status


@retry_on_except(retry_count=2)
def set_mute_status(mtee_target, driver, action="MUTE"):
    """
    Set mute status according to received 'action'

    :param mtee_target: mtee_target object
    :param driver: WebDriver object
    :param action: final mute status or action to perform, defaults to "MUTE"
    """
    valid_actions = ["MUTE", "UNMUTE"]
    if action not in valid_actions:
        raise RuntimeError(f"Received action '{action}' is not valid ({valid_actions})")
    time.sleep(1)
    # Validate MUTE status
    mute_status = press_mute_get_status(mtee_target, driver)
    if ("MS_MUTED" == mute_status and action == "MUTE") or ("MS_UNMUTED" == mute_status and action == "UNMUTE"):
        return
    else:
        time.sleep(1)
        # Press MUTE
        mute_status = press_mute_get_status(mtee_target, driver)
        if ("MS_MUTED" == mute_status and action == "MUTE") or ("MS_UNMUTED" == mute_status and action == "UNMUTE"):
            return True
        else:
            raise AssertionError(f"Unexpected state after pressing on '{action}': '{mute_status}'")


def alsa_mixer_min_config():
    """
    Set min requirements of alsamixer config to record audio
    There is a new usb audio card at TRAAS setup.
    """
    subprocess.run(["amixer", "set", "Mic", "cap"])
    subprocess.run(["amixer", "set", "Mic", "90%"])


def check_usb_and_push_audio_file(usb_controller, apinext_target):
    """Check if a USB drive is mounted under a /mnt path and if it is, push audio files to usb
    :param usb_controller: usb controller instance
    :param apinext_target: target instance to send commands
    """
    usb_drive = check_usb_available(apinext_target)
    if usb_drive is None:
        usb_drive = reset_usb(usb_controller, apinext_target)
    audio_sample_file = Path(Path(__file__).parent.parent / "samples" / "sinusoid_200_700.mp3")
    logger.debug(f"audio_sample_file path:{audio_sample_file}")
    user_number = apinext_target.get_current_user_id()
    # path to usb music folder
    full_path_usb_music = Path(f"{USB_ANDROID_PATH}/{user_number}/{usb_drive}/Music")
    logger.debug(f"Full path to usb music folder :{full_path_usb_music}")
    push_audio_file_to_usbdrive(apinext_target, audio_sample_file, full_path_usb_music)


def get_source_list_from_media(test):
    """
    Navigates through the UI with appium to Media app and get list of sources

    :return: list with available sources
    :rtype: list of appium webdriver elements
    """
    Launcher.go_to_home()

    # Press media button
    Media.open_media()
    time.sleep(1)

    # Open the audio source selector
    media_source_button = test.driver.find_element(*Media.MEDIA_SOURCE_SELECTOR_ID)
    GlobalSteps.click_button_and_expect_elem(test.wb, media_source_button, Media.AUDIO_SETTINGS_BUTTON_ID)

    # Get all input sources available
    sources_list = Media.get_sources_list()
    return sources_list


def ensure_usb_is_turned_off(usb_controller, apinext_target, timeout=USB_TIMEOUT, retry_attempts=RECOVERY_ATTEMPTS):
    """Ensure USB is turned OFF

    :param usb_controller: usb controller instance
    :type usb_controller: USBControl instance
    :param apinext_target: target instance to send commands
    :type apinext_target: target
    :param timeout: given timeout to check USB
    :type timeout: int, optional
    :param retry_attempts: number of attempts to turn off USB
    :type retry_attempts: int, optional
    """
    usb_drive = check_usb_available(apinext_target, timeout)
    if usb_drive is not None:
        for i in range(retry_attempts):
            usb_controller.power_off()
            time.sleep(2)
            usb_drive = check_usb_available(apinext_target, timeout)
            if usb_drive is None:
                logger.debug(f"USB turned off in {i + 1} attempt")
                break
        else:
            raise RuntimeError(f"USB did not turned off after {retry_attempts} attempts")
    else:
        logger.debug("USB is already turned off")


def get_volume_value_from_dlt(messages_list, search_text):
    """
    Return the value of volume form the received list of dlt messages

    :param messages_list: List of dlt messages
    :type messages_list: List[str]
    :param search_text: Regex compiled expression to be searched on messages
    :type search_text: Regex compiled expression
    :raises RuntimeError: Raised when more than one value is found
    """

    good_msgs = []
    for msg in messages_list:
        if "volume:" in msg.payload_decoded:
            logger.info(f"Adding the following good msg: '{msg.payload_decoded}'")
            good_msgs += [msg]
    if good_msgs:
        current_volume = -1
        for good_msg in good_msgs:
            if search_text.search(good_msg.payload_decoded):
                candidate_volume = search_text.search(good_msg.payload_decoded).group(1)
                if current_volume == -1 or candidate_volume == current_volume:
                    current_volume = candidate_volume
                else:
                    raise RuntimeError(
                        "Found more than one value of Volume while expecting only one ",
                        f"first value was '{current_volume}', second value was '{candidate_volume}'",
                    )
    return current_volume
