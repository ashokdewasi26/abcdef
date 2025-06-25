import logging
import math
import os
import re
import subprocess
import time
from pathlib import Path
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageStat

from diagnose.tools import enhex
from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import OcrMode, assert_true, image_to_text, run_command
from si_test_idcevo.si_test_helpers.file_path_helpers import verify_file_in_host_with_timeout

logger = logging.getLogger(__name__)


def crop_image(image_path, box, output="test.png"):
    """Crop an image given a certain coordinates(box)

    :param image_path: Path for the image to be cropped
    :param box: Box coordinates to perform the crop
    :param output: Path to save the cropped image
    """

    with Image.open(image_path) as img:
        if img.mode == "RGBA":
            im1 = img.convert("RGB")
        im1 = img.crop(box)
        im1.save(output)


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
    if Path(screenshot).exists() and Path(screenshot).stat().st_size > 0:
        logger.info(f"Searching for text on image: '{screenshot}'")
        image_path = screenshot
        if region:
            image_path = Path(Path(screenshot).parent, Path(screenshot).stem + "_cropped.png")
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
        err = "Image file size is 0 or file not found at: " + str(screenshot)
        logger.info(err)
        raise RuntimeError(err)


def take_phud_driver_screenshot(test, screenshot_path, try_via_diag_job=True):
    """Take a PHUD driver display screenshot using adb. If it fails, try it via Diag job

    :param test: instance of the test class
    :type test: TestBase
    :param screenshot_path: full path to create the screenshot
    :type screenshot_path: Path
    :param try_via_diag_job: flag to trigger screenshot via Diag job if adb fails
    :type try_via_diag_job: bool
    """
    logger.info(f"Taking phud driver screenshot with adb: {screenshot_path}")
    with open(screenshot_path, mode="wb") as screenshot:
        try:
            run_command(
                ["adb", "exec-out", "screencap", "-p", "-d", "4633128631561747460"], check=True, stdout=screenshot
            )
        except Exception as e:
            logger.info(f"Failed to take screenshot using adb. Error: {e}")
            if try_via_diag_job:
                logger.info("Trying to trigger screenshot via Diag job")
                take_phud_driver_diag_job_screenshot(test, screenshot_path)
                return
            else:
                raise AssertionError("Failed to take PHUD screenshot using adb")

        # If the adb command succeeds but the screenshot file is empty, try to trigger the screenshot via Diag job
        if os.path.getsize(screenshot_path) == 0:
            logger.info("adb screenshot command generated an empty screenshot file.")
            if try_via_diag_job:
                logger.info("Trying to trigger screenshot via Diag job")
                take_phud_driver_diag_job_screenshot(test, screenshot_path)
                return
            else:
                raise AssertionError(
                    f"adb screenshot command generated an empty screenshot file. Screenshot path: {screenshot_path}"
                )


def take_phud_driver_diag_job_screenshot(test, screenshot_path):
    """Take a screenshot using Diag job, targeting the PHUD driver display
    Steps:
        1. Trigger screenshot via diag job
        2. Wait for PHUD driver display screenshot file to be transferred by ExtractFilesPlugin
        3. Check expected screenshot file is in results/Coredumps directory

    :param test: instance of the test class
    :type test: TestBase
    :param screenshot_path: Full path where the screenshot is saved
    :type screenshot_path: Path
    """
    phud_screenshot_dlt_pattern = re.compile(r"screenshot-IDCEVO25-(\d+)-(\w+)-2-linux\.png")
    logger.info(f"Taking phud driver screenshot via Diag job: {screenshot_path}")

    with DLTContext(test.mtee_target.connectors.dlt.broker, filters=[("SYS", "FILE")]) as trace:
        rid = 0xA2F4
        with test.diagnostic_client.diagnostic_session_manager() as ecu:
            enhex(ecu.start_routine(rid))

        timeout_message = "Timeout reached while waiting for DLT file-transfer message of PHUD screenshot"
        diag_job_screenshot_message = trace.wait_for(
            {"payload_decoded": phud_screenshot_dlt_pattern}, timeout=10, drop=True, timeout_message=timeout_message
        )

        screenshot_png_file_name = phud_screenshot_dlt_pattern.search(diag_job_screenshot_message[0].payload_decoded)
        logger.info(f"Matched screenshot filename: {screenshot_png_file_name.group()}")

    logger.info(
        "Finished PHUD screenshot trigger via Diag job. "
        "Waiting for screenshot to be transferred via DLT to Host PC 'Coredumps' directory"
    )

    screenshot_file_path = os.path.join(
        test.mtee_target.options.result_dir, "extracted_files", "Coredumps", screenshot_png_file_name.group()
    )
    assert_true(
        verify_file_in_host_with_timeout(screenshot_file_path, 20),
        f"File {screenshot_png_file_name.group()} not found at path '{screenshot_file_path}' on Host PC.",
    )
    logger.info(f"PHUD screenshot file found at path: {screenshot_file_path}")

    logger.info(f"Copying screenshot file to: '{screenshot_path}'")
    cp_cmd = ["cp", screenshot_file_path, screenshot_path]
    subprocess.run(cp_cmd, check=True)


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
    with Image.open(image) as main_image, Image.open(image_to_search) as template_image:
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
                    main_image = Image.open(image)
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


def fetch_expected_color_present_in_image(image_path, expected_hex_color, threshold=30):
    """
    Fetch if the expected color is present in the image within a given threshold.
    Args:
        image_path (str): The path to the image file.
        expected_hex_color (str): The expected color in hex format (e.g., "#FF5733").
        note: you can use Image Color Picker to fetch the hex color code from the image.
        threshold (int): The maximum allowed distance between colors to consider them similar (default is 30).
    Returns:
        bool: True if the expected color is present within the threshold, False otherwise.
    """
    rgb = ImageColor.getrgb(expected_hex_color)  # Returns (255, 0, 170)
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            pixels = list(img.getdata())
            for color in pixels:
                # Calculate the Euclidean distance between the expected RGB color and the actual color.
                # If the distance is less than or equal to the threshold, the colors are considered similar.
                if math.sqrt(sum((a - b) ** 2 for a, b in zip(rgb, color))) <= threshold:
                    return True
            return False
    except Exception as e:
        logger.info(f"An error occurred while looking for expected color in image. Error message: {e}")
        return None


def check_if_image_is_fully_black(image_path):
    """Check if all pixels in a image are black
    :param image_path: Path where image file is located
    :return: True if all pixels in the image are black, False otherwise
    """
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        pixels = img.getdata()
        return all(pixel == (0, 0, 0) for pixel in pixels)
