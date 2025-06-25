import logging
import os
import re
import time

from pathlib import Path
from PIL import Image, ImageEnhance

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import OcrMode

from si_test_idcevo.si_test_config.idcevo_kpi_metrics_config import GENERIC_DLT_KPI_CONFIG
from si_test_idcevo.si_test_helpers.dlt_logs_handlers import validate_expected_dlt_payloads_in_dlt_trace
from si_test_idcevo.si_test_helpers.pages.cde.launcher_page import LauncherPage as CDELauncher
from si_test_idcevo.si_test_helpers.pages.idcevo.launcher_page import LauncherPage as Launcher
from si_test_idcevo.si_test_helpers.pages.idcevo.perso_page import PersoBMWIDPage as Perso
from si_test_idcevo.si_test_helpers.pages.rse26.launcher_page import LauncherPage as RSE26Launcher
from si_test_idcevo.si_test_helpers.screenshot_utils import extract_text, take_phud_driver_screenshot

logger = logging.getLogger(__name__)

EARLY_CLUSTER_DLT_FILTERS = [("EARL", "HMI"), ("EARL", "KPI")]
EARLY_CLUSTER_FILTERS = [
    {"apid": "EARL", "ctid": "HMI", "payload_decoded": re.compile(r"Initializing EarlyCluster graphics.")},
    {"apid": "EARL", "ctid": "KPI", "payload_decoded": re.compile(r"First image shown.")},
    {"apid": "EARL", "ctid": "KPI", "payload_decoded": re.compile(r"Full content shown.")},
]

CROP_READY_BOX = (915, 145, 1035, 190)


def check_early_cluster_after_cold_reboot(test):
    with DLTContext(test.mtee_target.connectors.dlt.broker, filters=EARLY_CLUSTER_DLT_FILTERS) as trace:
        test.mtee_target.reboot(prefer_softreboot=False)
        dlt_msgs = trace.wait_for_multi_filters(
            filters=EARLY_CLUSTER_FILTERS,
            drop=True,
            count=0,
            timeout=60,
        )
        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, EARLY_CLUSTER_FILTERS)
    test.apinext_target.wait_for_boot_completed_flag()


def retrieve_speed_phud(test, image_path, crop_region):
    """Capture screenshot from PHUD and extract speed"""
    screenshot_path = Path(test.results_dir, str(image_path))
    take_phud_driver_screenshot(test, screenshot_path)
    speed_text = extract_text(screenshot_path, region=crop_region, pagesegmode=OcrMode.SINGLE_LINE)
    logger.debug(f"Speed text before replacing unexpected characters: {speed_text}")
    speed = speed_text.replace("O", "0").replace("P", "8")
    return speed


def get_ready_textbox_phud(test, image_path):
    """Capture screenshot from PHUD and returns the text it found in the 'READY' box"""
    screenshot_path = Path(test.results_dir, str(image_path))
    take_phud_driver_screenshot(test, screenshot_path)
    ready_box_text = extract_text(screenshot_path, region=CROP_READY_BOX, pagesegmode=OcrMode.SINGLE_LINE)
    return ready_box_text.upper().strip()


def change_image_contrast_ratio(image_path, contrast_ratio):
    """change image contrast with the given ratio and save changed image on the same path"""
    with Image.open(image_path) as img:
        img = ImageEnhance.Contrast(img).enhance(contrast_ratio)
        img.save(image_path)


def get_text_from_phud_with_ocr(test, image_path, crop_region, ocr_mode=OcrMode.SINGLE_LINE, contrast_ratio=None):
    """This function captures the screenshot, contrast it and extracts the text with respect to crop region and OCR
    mode"""
    screenshot_path = Path(test.results_dir, str(image_path))
    take_phud_driver_screenshot(test, screenshot_path)
    if contrast_ratio:
        change_image_contrast_ratio(screenshot_path, contrast_ratio)
    ocr_text = extract_text(screenshot_path, region=crop_region, pagesegmode=ocr_mode)
    logger.debug(f"Extracted text from cropped image : {ocr_text}")
    return ocr_text.strip()


def check_android_launcher(test):
    """Check if Launcher activity is in list of activities"""
    time.sleep(2)
    if test.mtee_target.options.target.lower() in ["cde"]:
        list_activities = [CDELauncher().get_activity_name()]
    elif test.mtee_target.options.target.lower() in ["rse26"]:
        list_activities = [RSE26Launcher().get_activity_name()]
    else:
        list_activities = [Launcher().get_activity_name(), Perso().get_activity_name()]

    launcher_available = Launcher().validate_activity(list_activities=list_activities)
    if launcher_available:
        logger.info("Launcher activity started successfully")
    else:
        logger.warning("Failed on starting Launcher activity")
    return launcher_available


def ensure_launcher_page(test, screenshot_path_inside_results_dir="", image_file_sufix="", pre_screenshot=True):
    """Ensure that the launcher page is the page currently focused
    Note: Used for exiting the "Emergency stop" pop-up"""
    screenshot_path = os.path.join(test.results_dir, screenshot_path_inside_results_dir)
    if pre_screenshot:
        test.take_apinext_target_screenshot(screenshot_path, "before_trying_focus_on_launcher" + image_file_sufix)
    if not check_android_launcher(test) and test.driver:
        Launcher.check_and_close_emergency_stop_page(wait_until_stop_visible=3)
    if not check_android_launcher(test):
        logger.info("Launcher was not initially focused. Trying to focus on it with back+home key.")
        test.go_back_android_keyevent()
        time.sleep(2)
        test.go_home_android_keyevent()
        time.sleep(2)
        if not check_android_launcher(test):
            test.take_apinext_target_screenshot(screenshot_path, "fail_on_focusing_on_launcher" + image_file_sufix)

    test.take_apinext_target_screenshot(screenshot_path, "launcher_focused" + image_file_sufix)
    return True


def wait_for_all_widgets_drawn(test):
    """
    Wait for all widgets to be drawn
    """
    widget_key = "Android Launcher All Widgets Drawn"
    partern_to_search = GENERIC_DLT_KPI_CONFIG[widget_key]["pattern"]
    apid_to_search = GENERIC_DLT_KPI_CONFIG[widget_key]["apid"]
    ctid_to_search = GENERIC_DLT_KPI_CONFIG[widget_key]["ctid"]
    dlt_msgs = []
    with DLTContext(test.mtee_target.connectors.dlt.broker, filters=[(apid_to_search, ctid_to_search)]) as trace:
        dlt_msgs = trace.wait_for(
            {"payload_decoded": partern_to_search}, drop=True, timeout=200, raise_on_timeout=False
        )
    if dlt_msgs:
        logger.info("All widgets launched successfully")
    else:
        logger.info("Error: Widgets weren't launched successfully")
