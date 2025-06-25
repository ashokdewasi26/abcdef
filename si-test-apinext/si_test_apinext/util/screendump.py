# Copyright (C) 2021. BMW Car IT GmbH. All rights reserved.

from abc import ABC, abstractmethod
import logging
import os
from pathlib import Path
import re
import time

from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import image_to_text
from PIL import Image
from si_test_helpers.images import compare_images, crop_image

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

BMW_CID_REGEX = re.compile("Radio|Phone|Connect|Station|Audio|source|Telephone|Listening")
MINI_CID_REGEX = re.compile(".*(?:TELEPHONE|Connect|phone|AUDIO|SOURCE|Radio|station)")


class ScreenData(ABC):
    @abstractmethod
    def validate(self):
        """Validate screen given against predefined elements"""


class ScreenDataIDC23(ScreenData):
    bmw_cid_size = [(1920, 960), (2880, 960)]
    bmw_ic_size = (1920, 720)
    mini_cid_ic_size = [(1752, 1660), (1536, 1496), (1534, 1496)]

    def __init__(self, screenshot):
        img = Image.open(screenshot)
        self.screenshot = screenshot
        self.img_size = img.size
        self.img_name = os.path.basename(screenshot)

    def get_bmw_cid_elements(self):
        widget_box = [(5, 5, 42, 80), (69, 5, 98, 80)]
        test_list = [("Home_screen", widget_box, BMW_CID_REGEX)]  # noqa: W605
        return test_list

    def get_bmw_ic_elements(self):
        temp_box = (73, 90, 88, 100)
        speed_box = (44, 27, 61, 63)
        max_speed_range_box = (19, 10, 28, 17)
        test_list = [
            ("Temp", temp_box, re.compile(".*(OFF|\+.*\d+.*C)")),  # noqa: W605
            ("Speed", speed_box, re.compile(".*(?:mph|km/h)")),  # noqa: W605
            ("Max Speed", max_speed_range_box, re.compile("\d+.*(?:mph|km/h)")),  # noqa: W605
        ]
        return test_list

    def get_mini_elements(self):
        test_list = None
        speed_box = (42, 0, 63, 24)
        telephone_box = (5, 42, 98, 60)
        speed_aux_box = (42, 0, 59, 34)
        if self.img_size == self.mini_cid_ic_size[0]:
            if "CID" in self.img_name:
                test_list = [("Telephone", telephone_box, MINI_CID_REGEX)]  # noqa: W605
            elif "ICHMI" in self.img_name:
                test_list = [("Speed", speed_box, re.compile(".*(?:mph|km/h)"))]  # noqa: W605
        else:
            if "CID" in self.img_name:
                test_list = [("Telephone", telephone_box, MINI_CID_REGEX)]  # noqa: W605
            if "ICHMI" in self.img_name:
                test_list = [("Speed", speed_aux_box, re.compile(".*(?:mph|km/h)"))]  # noqa: W605
        return test_list

    def __get_elements_to_verify(self):
        if self.img_size in self.bmw_cid_size:
            return self.get_bmw_cid_elements()
        elif self.img_size == self.bmw_ic_size:
            return self.get_bmw_ic_elements()
        elif self.img_size in self.mini_cid_ic_size:
            return self.get_mini_elements()
        else:
            logger.info("any element to test on this image %s", self.img_name)
            return None

    def validate(self):
        test_elems = self.__get_elements_to_verify()
        list_errors = []
        if test_elems:
            try:
                for prop, crop_region, regex_pattern in test_elems:
                    logger.debug("Checking text of: %s", prop)
                    # Since OCR is not 100% accurate changing parameters to extract text if fails in 1st try
                    crop_region = [crop_region] if isinstance(crop_region, tuple) else crop_region
                    for region in crop_region:
                        for pagesegmode in (3, 11):
                            logger.info("extracting text with pagesegmode: %s", pagesegmode)
                            text = image_to_text(self.screenshot, region=region, invert=True, pagesegmode=pagesegmode)
                            logger.debug("Text found in %s: %s", self.screenshot, text)
                            re_result = regex_pattern.findall(text)
                            if re_result:
                                break
                        if re_result:
                            break
                    #   As re_result might be a list, validate that each elem is not empty
                    if not re_result:
                        list_errors.append(f"[{self.img_name}] Error on checking {prop}. Text found: {text}")
            except Exception as e:
                list_errors.append(f"[{self.img_name}] No Content validation. Exception occured: {e}")
        else:
            list_errors.append(f"[{self.img_name}] No Content validation exists for this image.")

        return list_errors


class ScreenDataPaDi(ScreenData):

    padi_size = (7680, 2160)
    minutes_box = (9.64, 39.3, 12.1, 45.3)
    temp_box = (86.5, 43, 88.5, 54.6)

    def __init__(self, screenshot):
        img = Image.open(screenshot)
        self.screenshot = screenshot
        self.img_size = img.size
        self.img_name = os.path.basename(screenshot)

    def __get_elements_to_verify(self):
        if self.img_size == self.padi_size:
            return [
                ("Minutes", self.minutes_box, re.compile(r"\d+")),
                ("Temperature", self.temp_box, re.compile(r"\d+")),
            ]
        else:
            logger.info("any element to test on this image %s", self.img_name)
            return None

    def validate(self):
        test_elems = self.__get_elements_to_verify()
        list_errors = []
        if test_elems:
            try:
                for prop, box, regex_pattern in test_elems:
                    logger.debug("Checking text of: %s", prop)
                    text = image_to_text(self.screenshot, region=box, invert=True, pagesegmode="13")
                    logger.debug("Text found in %s: %s", self.screenshot, text)
                    re_result = regex_pattern.findall(text)
                    #   As re_result might be a list, validate that each elem is not empty
                    if not re_result:
                        list_errors.append(f"[{self.img_name}]Error on checking {prop}. Text found: {text}")
            except Exception as e:
                list_errors.append(f"[{self.img_name}] No Content validation. Exception occured: {e}")
        else:
            list_errors.append(f"[{self.img_name}] No Content validation exists for this image.")

        return list_errors


class ScreenDump:
    test_image_name = "test.png"
    idc_screen_res = [(1920, 960), (2880, 960), (1752, 1660), (1536, 1496)]
    idc_screen_region = {
        "1920_960": (760, 842, 1160, 960),
        "2880_960": (1240, 842, 1640, 960),
        "1752_1660": (594, 1505, 1158, 1595),
        "1536_1496": (486, 1341, 1050, 1431),
    }
    ref_images_dir = Path(Path(__file__).parent / ".." / ".." / "resources" / "references").absolute()
    logger.info(ref_images_dir)

    def __init__(self):
        self.target = TargetShare().target

    def test_cid_ic_screen_displayed(self, filename="test", test_ic=False, test_cid=False):
        list_errors = []
        test_screens = []
        if test_ic:
            test_screens.append("IC")
        if test_cid:
            test_screens.append("CID")
            vcar_manager = TargetShare().vcar_manager
            for _ in range(30):
                vcar_manager.send('run_async("zbe_menu")')
                time.sleep(0.3)
                vcar_manager.send('run_async("zbe_push")')
                time.sleep(0.3)
            vcar_manager.send('run_async("zbe_menu")')
            time.sleep(3)

        screenshots = self.target.screendump(filename_base=filename, screens=test_screens)
        for screenshot in screenshots:
            if os.path.isfile(screenshot):
                logger.info("Checking file: %s", screenshot)
                if ".png" in Path(screenshot).suffix and Path(screenshot).suffix != ".png":
                    os.rename(screenshot, os.path.join(Path(screenshot).parent, Path(screenshot).stem + ".png"))
                    screenshot = os.path.join(Path(screenshot).parent, Path(screenshot).stem + ".png")
                if self.target.options.target == "idc23":
                    screen_data = ScreenDataIDC23(screenshot)
                elif self.target.options.target == "rse22":
                    screen_data = ScreenDataPaDi(screenshot)
                else:
                    raise Exception("Unknown target for screendump content")
                list_errors.extend(screen_data.validate())

        return list_errors

    def validate_cid(self, filename="test"):
        """
        Compare the cropped region of the captured screenshot with the reference image saved.

        :param filename(str): File name of the screenshot to be saved.

        """
        comparison_results = []
        screenshots = self.target.screendump(filename_base=filename)
        if screenshots:
            screenshot = screenshots[0]
        else:
            raise RuntimeError("Unable to capture screenshot after coding " + filename)
        with Image.open(screenshot) as img:
            img_size = img.size
        ref = "_".join(map(str, img_size))
        if img_size not in self.idc_screen_res:
            err = "Unknown screen resolution found on this image " + screenshot
            logger.info(err)
            raise RuntimeError(err)
        else:
            image_path = Path(Path(screenshot).parent, Path(screenshot).stem + "_cropped.png")
            output_path = Path(Path(screenshot).parent, Path(screenshot).stem + "_compare_out.png")
            crop_image(screenshot, self.idc_screen_region[ref], image_path)
            ref_files = sorted(self.ref_images_dir.glob("*" + ref + "*.png"))
            logger.info(ref_files)
            for each_ref in ref_files:
                result = compare_images(
                    image_path, each_ref, output=output_path, concat=True, acceptable_fuzz_percent=40
                )
                comparison_results.append(result)
                if result:
                    if output_path.exists():
                        output_path.unlink()
                    break
            image_path.unlink()
            assert any(comparison_results), f"Unable to match {ref_files} on {screenshot}"
