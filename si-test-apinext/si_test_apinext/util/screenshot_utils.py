import glob
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional, Tuple

import si_test_apinext.util.driver_utils as utils
from mtee.testing.tools import OcrMode, image_to_text, retry_on_except
from mtee_apinext.util.images import compare_images
from PIL import Image, ImageChops, ImageDraw, ImageStat
from selenium.common.exceptions import ScreenshotException
from si_test_apinext.testing.test_base import TestBase

logger = logging.getLogger(__name__)
screenshot_cmd = (
    'echo -n "/tmp/screenshot_blah_SCREEN_XXXXXXXX.png" | socat -u STDIN UNIX-CONNECT:/var/run/logntrace/command'
)


@retry_on_except(retry_count=3)
def capture_screenshot(test: TestBase, test_name: str, bounds=None, results_dir_path=""):
    """
    -Take screenshot of display, crop the image for the area parsed
    Args:
            test - TestBase singleton object
            test_name - string to be used for screenshots name
            bounds - area which will be cropped from screenshots
    Returns:
            File path of the captured screenshot
    """
    results_path = results_dir_path if results_dir_path else test.results_dir
    screenshot_name = f"{test_name}.png"
    file_path = os.path.join(results_path, screenshot_name)
    screenshot_path = utils.deconflict_file_path(file_path, extension=".png")
    try:
        utils.take_screenshot_appium(test.driver, screenshot_path)
    except ScreenshotException:
        logger.warning("Screenshot not possible on target using appium.")
        screenshot_name = f"{test_name}_adb.png"
        screenshot_path = os.path.join(results_path, screenshot_name)
        utils.take_apinext_target_screenshot(test.apinext_target, test.results_dir, screenshot_path)
    if not os.path.exists(screenshot_path) or os.stat(screenshot_path).st_size == 0:
        msg = "Screenshot not possible on target using appium and screencap."
        logger.error(msg)
        raise RuntimeError(msg)
    if bounds:
        box_screenshot = os.path.join(results_path, f"{test_name}_box.png")
        crop_image(screenshot_path, bounds, output=box_screenshot)
        return box_screenshot
    else:
        return screenshot_path


def extract_text(
    screenshot,
    region=None,
    brightness=False,
    contrast=False,
    monochrome=False,
    invert=True,
    resize_height=False,
    resize_width=False,
    lang="eng",
    pagesegmode=OcrMode.PAGE_SEGMENTATION_WITHOUT_OSD,
):
    """
    -Extract the text present in the given screenshot via OCR
    Args:
            screenshot - File path of the captured screenshot.
            region - area which will be used to extract the text.
            brightness - Brightness multiplier.
            contrast - Contrast multiplier.
            monochrome - Turn image monochrome.
            invert - Invert colors (black on white is easier to recognise).
            resize_height - Multiplier for resized image height.
            resize_width - Multiplier for resized image width.
            lang - language which tesseract should consider when extracting the text.
            pagesegmode - pagesegmentation mode to control layout analysis.
    Returns:
            image_text - Extracted text from the image
            regex.findall - returns list of the matched regex
    """
    if os.path.exists(screenshot) and os.stat(screenshot).st_size > 0:
        logger.info(f"Searching for text on image: '{screenshot}'")
        image_path = screenshot
        if region:
            image_path = os.path.join(Path(screenshot).parent, Path(screenshot).stem + "_cropped.png")
            crop_image(screenshot, region, image_path)
        image_text = image_to_text(
            image_path,
            lang=lang,
            monochrome=monochrome,
            brightness=brightness,
            contrast=contrast,
            invert=invert,
            resize_height=resize_height,
            resize_width=resize_width,
            pagesegmode=pagesegmode,
        ).replace("\n", " ")
        logger.debug(f"Extracted text: '{image_text}' using OCR mode:'{pagesegmode}'")
        return image_text
    else:
        err = "Image file size is 0 or file not found at: " + screenshot
        logger.info(err)
        raise RuntimeError(err)


def check_screendump(
    screenshot,
    search_text,
    region=None,
    brightness=False,
    contrast=False,
    monochrome=False,
    invert=True,
    resize_height=False,
    resize_width=False,
    lang="eng",
    pagesegmode=OcrMode.PAGE_SEGMENTATION_WITHOUT_OSD,
) -> Tuple[bool, str]:
    """
    -Extract the text present in the given screenshot via OCR
    Args:
            screenshot - File path of the captured screenshot.
            search_text - expected sting to be extracted from the image.
            region - area which will be used to extract the text.
            brightness - Brightness multiplier.
            contrast - Contrast multiplier.
            monochrome - Turn image monochrome.
            invert - Invert colors (black on white is easier to recognise).
            resize_height - Multiplier for resized image height.
            resize_width - Multiplier for resized image width.
            lang - language which tesseract should consider when extracting the text.
            pagesegmode - pagesegmentation mode to control layout analysis.
    Returns:
            test_result_text - True or False
            error_message - Empty or Error Message in case of Failure
    """
    test_result_text = True
    error_message = ""
    image_text_found = []

    # In case we get a list of regions to try iterate the list, if not create list
    region = [region] if not isinstance(region, list) else region
    for region_box in region:
        for pagesegmode in [
            OcrMode.PAGE_SEGMENTATION_WITHOUT_OSD,
            OcrMode.SINGLE_WORD_IN_A_CIRCLE,
            OcrMode.SINGLE_UNIFORM_BLOCK_OF_TEXT,
            OcrMode.SINGLE_LINE,
            OcrMode.SINGLE_CHARACTER,
        ]:
            image_text = extract_text(
                screenshot,
                region=region_box,
                lang=lang,
                monochrome=monochrome,
                brightness=brightness,
                contrast=contrast,
                invert=invert,
                resize_height=resize_height,
                resize_width=resize_width,
                pagesegmode=pagesegmode,
            )
            image_text_found += [image_text.strip()]
            logger.debug(
                f"check_screendump, on image:'{screenshot}' searching for: '{search_text}' ---> Found: '{image_text}'"
            )
            # If search_text is regex expression or string search for it
            if isinstance(search_text, re.Pattern):
                if re.search(search_text, image_text.replace(" ", "")) or any(
                    search_text.findall(image_text.replace(" ", ""))
                ):
                    return test_result_text, error_message
            elif isinstance(search_text, str):
                if search_text in image_text:
                    return test_result_text, error_message
            else:
                raise RuntimeError(
                    f"Unexpected type of expression to be searched on image: '{search_text}' ",
                    f"Got type: '{type(search_text)}' expected: str or regex expression",
                )
    test_result_text = False
    error_message = (
        f"Didn't find expected: '{search_text}' on image: '{screenshot}' ---> Found this text: '{image_text_found}'"
    )
    logger.info(error_message)
    return test_result_text, error_message


def compare_snapshot(
    screenshot_path,
    reference_image,
    test_name: str,
    fuzz_percent: Optional[int] = 3,
    region: Optional[tuple] = None,
    unlink_files: Optional[bool] = False,
) -> Tuple[bool, str]:
    """
    -Compare the captured image with the reference image
    Args:
            screenshot_path - File path of the captured screenshot
            reference_image - expected sting to be extracted from the image
            test_name - test scenario name
            fuzz_percent - acceptable fuzz percent acceptable when comparing two images
            region - area which will be cropped out from actual image.
            unlink_files - remove this file or link
    Returns:
            test_result - True or False
            string - Empty or Error Message in case of Failure
    """
    test_result_comp = True
    error_message = ""
    output_path = Path(Path(screenshot_path).parent, f"{test_name.replace(' ', '_')}.png")
    if region:
        cropped_image = Path(Path(screenshot_path).parent, Path(screenshot_path).stem + "_cropped.png")
        crop_image(screenshot_path, region, cropped_image)
        screenshot_path = cropped_image
    try:
        result = compare_images(
            screenshot_path, reference_image, output=output_path, acceptable_fuzz_percent=fuzz_percent
        )
    except Exception:
        return False, error_message
    logger.info(f"Compare screenshots {screenshot_path} and {reference_image}," f" got the result: {str(result)}")
    if not result:
        test_result_comp = False
        error_message += f"Failure compare image {test_name.replace(' ', '_')} \n"
        logger.info(error_message)
    #  Remove temp files created for testing
    elif result and unlink_files:
        for each_file in (output_path, screenshot_path):
            if each_file.exists():
                each_file.unlink()
    return test_result_comp, error_message


def take_ic_screenshot_and_extract(mtee_target, dest=None):
    """
    Take screenshot of IC
    Extract screenshot from mtee to destination folder

    :param mtee_target: mtee_target object
    :param dest: Destination file to extract screenshot.
                 If not specified, use mtee result dir.
    """
    # screenshot_blah_SID_ICHMI
    permissions_to_files = "chmod 660 /tmp/screenshot_blah*"
    mtee_target.execute_command(screenshot_cmd)
    time.sleep(10)
    mtee_target.execute_command(permissions_to_files)

    cmd_shown = "ls /tmp"
    cmd_rm = "rm /tmp/"
    result = mtee_target.execute_command(cmd_shown)
    screenshot_search_pattern = "screenshot_blah_.*_ICHMI_.*.png"
    screenshot_files = [file for file in str(result).splitlines() if re.search(screenshot_search_pattern, file)]
    if screenshot_files:
        file_to_download = "/tmp/" + screenshot_files[0]
        logger.info(f"Extracting screenshot '{file_to_download}' to '{dest}'")
        mtee_target.download(file_to_download, dest)
        time.sleep(5)
        mtee_target.execute_command(cmd_rm + screenshot_files[0])
    else:
        logger.info(f"Directory tmp contains:\n{str(result)}")
        raise Exception(
            f"instrument cluster screenshot file cannot be found"
            f"after executing: '{screenshot_cmd}'. Instead found: '{result}'"
        )


def crop_image(image_path, box, output="test.png"):
    """Crop an image given a certain coordinates(box)

    :param image_path: Path for the image to be cropped
    :param box: Box coordinates to perform the crop
    :param output: Path to save the cropped image
    """

    img = Image.open(image_path)
    if img.mode == "RGBA":
        im1 = img.convert("RGB")
    im1 = img.crop(box)
    im1.save(output)


def match_template(image, image_to_search, region, results_path, context="", acceptable_diff=2.0, save_diff=False):
    """
    To search for a smaller image inside a bigger image
    :param image:(str)- Path to Main image in which template image is to be searched
    :param image_to_search:(str)- Path to Small image which is to be searched.
    :param region:(tuple)- If search is to be performed in a limited region of main_image
    :param results_path:(str)- Path to save the images generated.
    :param context:(str)- Name prefix from which will derive the artifacts saved
    :param acceptable_diff:(float)- Acceptable diff ratio. Defaults to 2.
    :param save_diff:(boolean)- Save the diff image if diff_ratio less than acceptable_diff. Defaults to False.
    disclaimer:
        Searching a template in 1000x150 image takes approx 8-10 seconds
    """
    results_path = Path(results_path) if results_path else Path(image).parent
    logger.debug(f"Searching for '{image_to_search}' inside '{image}'")
    image_name = Path(image).stem
    start = time.time()
    main_image = Image.open(image)
    template_image = Image.open(image_to_search)
    search_image = main_image.crop(region)
    # Convert images to "L" to reduce computation by factor 3 "RGB"->"L"
    search_image = search_image.convert(mode="L")
    template_image = template_image.convert(mode="L")
    search_width, search_height = search_image.size
    template_width, template_height = template_image.size
    diff_ratio_history = []  # keep track of diff ratio
    # Loop over each pixel in the search image
    for xs in range(search_width - template_width + 1):
        for ys in range(search_height - template_height + 1):
            search_crop = search_image.crop((xs, ys, xs + template_width, ys + template_height))
            diff = ImageChops.difference(template_image, search_crop)
            stat = ImageStat.Stat(diff)
            diff_ratio = sum(stat.mean) * 100 / (len(stat.mean) * 255)
            diff_ratio_history.append(diff_ratio)
            if diff_ratio <= acceptable_diff:
                location = (
                    xs + region[0],
                    ys + region[1],
                    xs + template_width + region[0],
                    ys + template_height + region[1],
                )
                draw = ImageDraw.Draw(main_image)
                draw.rectangle(location, outline="red")
                main_image.save(f"{results_path}/{image_name}_{context}_matched_image.png")
                time_elapsed = round(time.time() - start, 3)
                logging.info(f"Found match. diff={round(diff_ratio, 3)} time elapsed: {time_elapsed}s")
                return True, location

            elif save_diff and diff_ratio == min(diff_ratio_history) and diff_ratio < (acceptable_diff + 5):
                # Save the closest match within a 5 diff radius from the desired value
                logging.debug(f"Keeping artifact... Diff_ratio: '{round(diff_ratio, 3)}'")
                screenshot_name_diff = f"{image_name}_{context}_diff_{xs}_{ys}.png"
                screenshot_path_diff = results_path / screenshot_name_diff
                diff.save(screenshot_path_diff, lossless=True)
                logging.debug(f"screenshot_path_diff: '{screenshot_path_diff}'")

    time_elapsed = round(time.time() - start, 3)
    logging.info(f"No match found. time elapsed: {time_elapsed}s")
    if diff_ratio_history:
        logging.info(f"Lowest diff ratio found was: {min(diff_ratio_history)}")
    else:
        logging.info("diff_ratio_history is empty")
    return False, None


def compare_captured_image_with_multiple_snapshots(
    screenshot_path,
    ref_image_path_pattern,
    test_name: str,
    fuzz_percent: Optional[int],
    region: Optional[tuple] = None,
    unlink_files: Optional[bool] = False,
) -> None:
    """
    -Compare the captured image with a list of reference images
    Args:
            screenshot_path - file path of the captured screenshot
            ref_image_path_pattern - reference image folder path and file name pattern
            test_name - test scenario name
            fuzz_percent - acceptable fuzz percent acceptable when comparing two images
            region - area which will be cropped out from actual image.
            unlink_files - remove this file or link
    """
    result = False
    reference_image = ""
    error = ""
    reference_image_list = glob.glob(ref_image_path_pattern)
    logger.info(f"List of {test_name} reference images - {reference_image_list}")
    for reference_image in reference_image_list:
        logger.info(f"Image {reference_image} is getting matched")
        result, error = compare_snapshot(
            screenshot_path,
            reference_image,
            test_name,
            fuzz_percent,
            region,
            unlink_files,
        )
        if result:
            logger.info(f"Image {reference_image} matched.")
            break
    if not result:
        raise AssertionError(
            f"Error on checking {test_name}. "
            f"{screenshot_path} not equal to reference {reference_image}, {error}"
            f"List of {test_name} reference images - {reference_image_list}"
        )
