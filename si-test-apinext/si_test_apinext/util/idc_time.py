import datetime
import logging
import re
import time
import os

from dateutil import parser
from mtee.testing.tools import image_to_text, OcrMode, TimeoutCondition
from si_test_apinext.util.screenshot_utils import crop_image

TimeTrustee_base = "TimeTrusteeSDaT.getSecureDateAndTime."
TimeTrustee_tta = TimeTrustee_base + "ttaQualifier"
TimeTrustee_tts = TimeTrustee_base + "ttsQualifier"
logger = logging.getLogger(__name__)


def get_current_time_from_ui(test, element=None, idc_ui_time_box_bounds=None, invert=None):
    """
    Return the time displayed on HU Android UI
    Take screenshot of display, crop the image for the area where the time is displayed,
    invert colors in order to have light background and dark letters/numbers, and convert
    the resulting image into text

        Args:
            apinext_target - Apinext target
            element - Element ID to extract time

        Returns:
            str with time found

        Raises:
            AssertionError - If text found doesn't have 5 character corresponding to format "11:11"
    """
    logger.info("Searching for time in UI")
    if idc_ui_time_box_bounds is None:
        for time_element in element:
            is_time = test.driver.find_elements(*time_element)
            if is_time:
                time_in_ui = is_time[0].text
                time_regex = re.compile("^(2[0-3]|[01]?[0-9]):([0-5][0-9])$")  # noqa: W605
                error = []
                logger.info(f"Found this UI time: '{time_in_ui}', with len:{len(time_in_ui)}")
                if time_in_ui:
                    assert re.search(time_regex, time_in_ui), (
                        f"The text found doesn't have the expected format: " f"{time_in_ui}"
                    )
                    hour, minute = re.search(time_regex, time_in_ui).group(1), re.search(time_regex, time_in_ui).group(
                        2
                    )
                    return datetime.datetime.now().replace(hour=int(hour), minute=int(minute))
                else:
                    error.append(f"Extracted time from UI was: '{time_in_ui}'")
                    raise RuntimeError(error)
    # This section is specifically for Mini
    screenshot_name = "IDC_CID_screenshot.png"
    screenshot_path = os.path.join(test.results_dir, screenshot_name)
    test.apinext_target.take_screenshot(screenshot_path)
    curr_time_shot = os.path.join(test.results_dir, "current_time_screenshot.png")
    for bounds in idc_ui_time_box_bounds:
        crop_image(screenshot_path, bounds, output=curr_time_shot)
        logger.info("Searching for text on image: " + curr_time_shot)
        time_regex = re.compile("^(2[0-3]|[01]?[0-9]):([0-5][0-9])$")  # noqa: W605
        error = []
        for pagesegmode in (
            OcrMode.PAGE_SEGMENTATION_WITHOUT_OSD,
            OcrMode.SINGLE_UNIFORM_BLOCK_OF_TEXT,
            OcrMode.SINGLE_LINE,
        ):
            text = image_to_text(curr_time_shot, invert=invert, pagesegmode=pagesegmode)
            logger.debug(f"Found this UI time: '{text}', with len:{len(text)}, on image: {curr_time_shot}")
            if text and re.search(time_regex, text):
                assert re.search(time_regex, text), f"The text found doesn't have the expected format: {text}"
                hour, minute = re.search(time_regex, text).group(1), re.search(time_regex, text).group(2)
                return datetime.datetime.now().replace(hour=int(hour), minute=int(minute))
            else:
                error.append(f"Extracted text: '{text}' using OCR mode:'{pagesegmode}'")


def get_time_zone_offset(time_zone_str):
    """
    Return the timezone offset from a given timezone text

        Args:
            time_zone_str - str with current timezone

        Returns:
            datetime.timedelta object with timezone offset

        Raises:
            ValueError or AssetionError - If given text doesn't have expected format
    """
    tmz_hour = 0
    tmz_minute = 0

    regex_filter = re.compile(r".*GMT(?P<hour>(\+|-)\d*)(:(?P<minute>\d*)|\s).*")

    match = regex_filter.search(time_zone_str)
    if match:
        match_dict = match.groupdict()
        tmz_hour = int(match_dict["hour"] or 0)
        tmz_minute = int(match_dict["minute"] or 0)

    assert -12 <= tmz_hour <= 14 and 0 <= tmz_minute <= 59, f"Got invalid time zone offset: {tmz_hour}:{tmz_minute}"
    tmz_offset_aux = datetime.timedelta(hours=tmz_hour, minutes=tmz_minute)
    return tmz_offset_aux


def turn_off_date_and_time_sync(vcar_manager):
    """
    Turn off trustee_datesync.prg

        Args:
            vcar_manager

        Raises:
            AssetionError - If result of command to turn off date synchronizer is not the expected
    """
    vcar_manager.send("trustee_datesync.exit = 1")
    time.sleep(1)
    result = vcar_manager.send("trustee_datesync.exit")
    assert result == "1.000000", "Date and time not correctly turned off"


def turn_on_date_and_time_sync(vcar_manager):
    """
    Turn on trustee_datesync.prg

        Args:
            vcar_manager

        Raises:
            AssetionError - If result of command to turn on date synchronizer is not the expected
    """
    vcar_manager.send("trustee_datesync.exit = 0")
    time.sleep(1)
    result = vcar_manager.send("trustee_datesync.exit")
    assert result == "0.000000", "Date and time not correctly turned on"


def get_trusted_time_hour(vcar_manager):
    return vcar_manager.send(f"{TimeTrustee_base}trustedTime.uTCTagTime.hour")


def change_trusted_time_hour(vcar_manager, new_hour="22"):
    """
    Change TimeTrustee trustedTime hour to the given one

        Args:
            vcar_manager
            new_hour - str final hour to change to

        Raises:
            AssetionError - If result of command to change TimeTrustee trustedTime hour is not the expected
    """
    logger.info(f"Changing hour with vcar to {new_hour}")
    vcar_manager.send(f"{TimeTrustee_base}trustedTime.uTCTagTime.hour = {new_hour}")
    time.sleep(1)
    result_hour = vcar_manager.send(f"{TimeTrustee_base}trustedTime.uTCTagTime.hour")
    assert int(float(result_hour)) == int(new_hour), "Changing hour failed"


def change_trusted_time_min_sec(vcar_manager, new_minute, new_second):
    """
    Change TimeTrustee trustedTime hour to the given one

        Args:
            vcar_manager
            new_minute - str final minute to change to
            new_second - str final second to change to

        Raises:
            AssetionError - If result of command to change TimeTrustee trustedTime hour is not the expected
    """
    logger.info(f"Changing minute and second with vcar to {new_minute}:{new_second}")
    vcar_manager.send(f"{TimeTrustee_base}trustedTime.uTCTagTime.second = {new_second}")
    vcar_manager.send(f"{TimeTrustee_base}trustedTime.uTCTagTime.minute = {new_minute}")
    time.sleep(1)
    result_minute = vcar_manager.send(f"{TimeTrustee_base}trustedTime.uTCTagTime.minute")
    assert int(float(result_minute)) == int(new_minute), "Changing hour failed"


def wait_for_hour_in_ui(test, new_hour, element_id=None, wait_time=300):
    """
    Wait for hour value update in UI

        Args:
            apinext_target - Apinext target object
            new_hour - str with hour to be found
            element_id - Element ID to extract time
            wait_time - time to wait for change to happen on UI, default: 5min

        Raises:
            AssetionError - If after wait_time the expected hour didn't show on HU UI
    """
    timer = TimeoutCondition(wait_time)
    while timer:
        # # Get current time in Android UI ------------------------------
        current_time_text = get_current_time_from_ui(test, element_id)
        if current_time_text and new_hour == current_time_text.hour:
            return current_time_text
        time.sleep(1)
    msg = f"Failed to see new time: {new_hour} in UI in {wait_time} seconds"
    msg += f"instead UI presents:{current_time_text.hour}:{current_time_text.minute}" if current_time_text else ""
    raise AssertionError(msg)


def get_android_system_time(apinext_target):
    """
    Return Android system time from $EPOCHREALTIME

    TODO: Clarify which is the right way to get system time

        Args:
            apinext_target - Apinext target

        Returns:
            datetime.datetime object with current system time from $EPOCHREALTIME
    """
    epoch_time = apinext_target.execute_adb_command(["shell", "echo $EPOCHREALTIME"])
    new_date_epoch_time = datetime.datetime.fromtimestamp(float(epoch_time))

    date_ctime_format = apinext_target.execute_adb_command(["shell", "date"])
    new_date_ctime_now = parser.parse(str(date_ctime_format).strip("\n"), ignoretz=True)
    # CET = GMT +1
    # Central European Time = Green Meridian Time + 1 hour
    if new_date_epoch_time.hour != new_date_ctime_now.hour:
        logger.info(
            f"Attention! ' adb shell echo $EPOCHREALTIME' doesn't match 'adb shell date' to get android system time:\
        new_date_epoch_time.hour = {new_date_epoch_time.hour}\
        new_date_ctime_now.hour = {new_date_ctime_now.hour}\
        new_date_epoch_time.minute = {new_date_epoch_time.minute}\
        new_date_ctime_now.minute = {new_date_ctime_now.minute}"
        )
    return new_date_epoch_time
