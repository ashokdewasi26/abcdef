import base64
import logging
import os
import re
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from re import split

from appium import webdriver
from mtee.testing.connectors.connector_dlt import DLTContext
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.remote_connection import LOGGER as seleniumLogger  # noqa: N811
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from si_test_apinext import DEFAULT_PORT_SERVER
from si_test_apinext.common.pages.base_page import Element
from si_test_apinext.padi.pages.hdmi_page import HdmiAppPage
from si_test_apinext.padi.pages.left_panel_page import LeftPanel

# APPIUM
APK_APPIUM = "io.appium.settings"
APK_APPIUM_SERVER = "io.appium.uiautomator2.server"
APK_APPIUM_SERVER_TEST = "io.appium.uiautomator2.server.test"
APPIUM_PACKAGES = [APK_APPIUM, APK_APPIUM_SERVER, APK_APPIUM_SERVER_TEST]

WAIT_FOR_APPIUM_DLT = 20
WAIT_FOR_IDC = 60
WAIT_FOR_PADI = 20
RETRY_ATTEMPTS_FOR_PADI_AVAILABILITY = 3

# TRAAS environment defines this env
RESULTS_DIR = os.getenv("RESULT_DIR", os.path.join(os.getcwd(), "results"))

# Alert elements
ALERT_SOURCE_ID_PREFIX = "android:id/"
CLOSE_ALERT = Element(By.ID, ALERT_SOURCE_ID_PREFIX + "aerr_close")
ALERT_TITLE = Element(By.ID, ALERT_SOURCE_ID_PREFIX + "alertTitle")

# SYSTEM UI for traffic info
SYSTEM_UI_ID_PREFIX = "com.android.systemui:id/"
TRAFFIC_INFO_OK_BUTTON = Element(By.ID, SYSTEM_UI_ID_PREFIX + "okButton")

# IDC23 AVAILABILITY
CHECK_LAUNCHER_ACTIVITY = "com.bmwgroup.idnext.launcher/.MainActivity"
CHECK_UIAUTOMATOR_SERVER = "io.appium.uiautomator2.server"

seleniumLogger.setLevel(logging.INFO)
logger = logging.getLogger(__name__)


def open_appium_session(options, mtee_target, apinext_target, url=f"http://localhost:{DEFAULT_PORT_SERVER}/wd/hub"):
    """Open appium session following up the DLT logs.
    If ECU is IDC23 we also wait for the widget of mediaapp to be loaded,
    since .MainActivity is launched when opening appium session.
    param: options: appium options that include the session capabilities.
    param: mtee_target: mtee target instance to use DLT.
    param: url: (Optional) session url.
    :return: - Return driver and opened session ID extracted from DLT.
             - Return driver and False if appium session opened but,
                 ECU not operational to work with session or DLT message not found.
             - Return False, False if there is no session opened.
    :rtype: tuple
    """
    error_msg = ""
    with DLTContext(mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as dlt_detector:
        dlt_new_session_msg = re.compile(r"appium.*Created the new session")
        try:
            driver = webdriver.Remote(url, options=options)
            appium_session_msg = dlt_detector.wait_for(
                {"apid": "ALD", "ctid": "LCAT", "payload_decoded": dlt_new_session_msg},
                timeout=WAIT_FOR_APPIUM_DLT,
                drop=True,
                raise_on_timeout=False,
            )
            if appium_session_msg:
                logger.debug(f"Found appium_session_msg: '{appium_session_msg[0].payload_decoded}'")
                session_id = re.match(r".*id ([\s\S]*?) and.*", appium_session_msg[0].payload_decoded).group(1)
                logger.info(f"Session created with id {session_id}")
            else:
                error_msg = f"Did not find Appium message for new session. Pattern: '{dlt_new_session_msg}'"
                logger.error(error_msg)
                remove_appium_apk(apinext_target)
                return driver, False, error_msg
        except WebDriverException as error:
            error_msg = f"Appium session failed with '{error}'"
            logger.error(error_msg)
            return False, False, str(error)

        if mtee_target.options.target == "idc23":
            if validate_idc23_home_availability(apinext_target, dlt_detector):
                return driver, session_id, ""
            return (
                driver,
                False,
                "idc23 not fully operational",
            )  # Return session False. Meaning idc23 not fully operational

        elif mtee_target.options.target == "rse22":
            if validate_padi_availability(driver, apinext_target, retry_attempts=RETRY_ATTEMPTS_FOR_PADI_AVAILABILITY):
                return driver, session_id, ""
            return (
                driver,
                False,
                "padi not fully operational",
            )  # Return session False. Meaning padi not fully operational

        else:
            return driver, session_id, ""


def close_appium_session(driver, mtee_target, opened_session):
    """Close appium session following up the DLT logs.
    Quit driver and wait for the messages for stopping uiautomator2
    and the appium response with session ID closed.
    param: driver: appium driver to quit.
    param: mtee_target: mtee target instance to use DLT.
    param: opened_session: Session to match with the closed session.
    :return: True if successfully closed. False if fails to close.
    :rtype: tuple
    """
    with DLTContext(mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as dlt_detector:
        dlt_stop_uiautomator_msg = re.compile(r"appium.*Stopping uiautomator2.*")
        try:
            driver.quit()
        except Exception as e:
            # Temporary workaround. Follow-up -> ABPI-221342
            logger.debug(
                f"The method driver.quit() raised the following exception, however we are continuing the run"
                f" assuming the session is deleted: {e}"
            )
            return True
        stop_msg = dlt_detector.wait_for(
            {"apid": "ALD", "ctid": "LCAT", "payload_decoded": dlt_stop_uiautomator_msg},
            timeout=WAIT_FOR_APPIUM_DLT,
            count=1,
            drop=True,
            raise_on_timeout=False,
        )
        if not stop_msg:
            logger.error(f"Did not find message for stopping uiautomator2 with pattern {dlt_stop_uiautomator_msg}")
            return False

        logger.debug(f"Found driver stop_msg: '{stop_msg[0].payload_decoded}'")
        dlt_close_session_msg = r"appium.*AppiumResponse: {\"sessionId\":.*"
        appium_response_msg = dlt_detector.wait_for(
            {"apid": "ALD", "ctid": "LCAT", "payload_decoded": dlt_close_session_msg},
            timeout=WAIT_FOR_APPIUM_DLT,
            count=1,
            drop=True,
            raise_on_timeout=False,
        )
        if appium_response_msg:
            logger.debug(f"Found appium_response_msg : '{appium_response_msg[0].payload_decoded}'")
            # Closing session without DLT session id
            if opened_session is False:
                return True

            session_id = re.match(r".*sessionId\":\"([\s\S]*?)\",.*", appium_response_msg[0].payload_decoded).group(1)
            if session_id == opened_session:
                logger.debug(f"Session closed with id {session_id}")
                return True
            else:
                logger.error(f"Different session id found, expecting {opened_session}, got: {session_id}")
                return False
        else:
            logger.error(f"Did not find appium response message with session id. Pattern: {dlt_close_session_msg}")
            return False


def start_recording(test):
    try:
        test.record_test = True
        test.driver.start_recording_screen()
    except Exception as e:
        logger.error(f"Found exception while trying to start video recording on {test.results_dir}, error: '{e}'")


def stop_recording(test, video_name):
    try:
        raw_data = test.driver.stop_recording_screen()
        # If video_name is a results path ok, if not make it be
        if test.results_dir not in video_name:
            video_path = os.path.join(test.results_dir, video_name)
        else:
            video_path = video_name
        video_path = f"{video_path}.mp4"
        final_video_path = deconflict_file_path(video_path)

        with open(final_video_path, "wb") as vd:
            vd.write(base64.b64decode(raw_data))
    except Exception as e:
        logger.error(f"Found exception while trying to save video recording on {test.results_dir}, error: '{e}'")


def deconflict_file_path(apath, extension=".mp4"):
    """Adds numbers to the end of path until the resulting path does not exist"""
    apath = os.path.abspath(apath)
    apath = str(apath).replace(extension, "")
    full_apath = str(apath + extension) if extension not in apath else apath
    if not os.path.exists(full_apath):
        return full_apath
    if len(apath) < 3 or not apath[-2:].isdigit():
        return deconflict_file_path(apath + "_01", extension=extension)
    return deconflict_file_path("{}{:02}".format(apath[:-2], int(apath[-2:]) + 1), extension=extension)


def take_screenshot_appium(driver, file_name):
    driver.get_screenshot_as_file(file_name)


def remove_appium_apk(apinext_target):
    android_packages = apinext_target.execute_adb_command(["shell", "pm", "list packages", "-a"])
    for package in APPIUM_PACKAGES:
        if package in android_packages:
            logger.info(f"Uninstalling: {package}")
            apinext_target.execute_adb_command(["uninstall", package])


def gather_info_on_fail(fn):
    @wraps(fn)
    def with_screen_shot(self, *args, **kwargs):
        """Take a Screen-shot of the drive page, when a function fails."""
        try:
            return fn(self, *args, **kwargs)
        except Exception:
            # This will only be reached if the test fails
            func_name = fn.__name__

            if hasattr(self, "test"):
                current_module = self.test
                current_module.stop_padi_video_streaming_apps()
            else:
                # In case gather_info_on_fail is called during a Page method
                current_module = self

            output_results = current_module.results_dir if current_module.results_dir else RESULTS_DIR
            take_apinext_target_screenshot(current_module.apinext_target, output_results, f"{func_name}_fail.png")

            if current_module.driver:
                get_xml_dump(current_module.driver, output_results, f"{func_name}_dump_fail.xml")
            else:
                logger.debug(f"Unable to UI dump. Context: {func_name}")
            raise

    return with_screen_shot


def get_xml_dump(driver, results_dir, file_name):
    """Take a dump of the elements on the UI into an xml file

    :param driver: WebDriver object
    :param results_dir: path to results folder
    :type results_dir: str
    :param file_name: name for created file
    :type file_name: str
    """
    page_source = driver.page_source
    file_name = os.path.join(results_dir, file_name) if results_dir not in file_name else file_name
    file_name = str(file_name + ".xml") if ".xml" not in file_name else file_name
    file_name = deconflict_file_path(file_name, extension=".xml")
    with open(file_name, "w") as f:
        f.write(page_source)
        f.close()


def get_screenshot_and_dump(test, results_dir, file_name):
    """Take a screenshot and a UI dump

    :param test: TestBase singleton object
    :param results_dir: path to results folder
    :type results_dir: str
    :param file_name: name for created file
    :type file_name: str
    """
    take_apinext_target_screenshot(test.apinext_target, results_dir, file_name)
    get_xml_dump(test.driver, results_dir, file_name)


def get_elem_bounds_detail(elem_from_driver, crop_region=False):
    assert hasattr(
        elem_from_driver, "get_attribute"
    ), "Given element seems to not be given by appium\
        webdriver as it doesn't have the method get_attribute"

    bounds = elem_from_driver.get_attribute("bounds")
    bounds_list = split(r"[\[\],]", bounds)
    bounds_list = list(filter(None, bounds_list))
    bounds_list = list(map(float, bounds_list))
    if crop_region:
        return bounds_list[0], bounds_list[1], bounds_list[2], bounds_list[3]
    else:
        return {
            "x_ini": bounds_list[0],
            "y_ini": bounds_list[1],
            "x_end": bounds_list[2],
            "y_end": bounds_list[3],
            "x_width": bounds_list[2] - bounds_list[0],
            "y_height": bounds_list[3] - bounds_list[1],
            "ratio": (bounds_list[2] - bounds_list[0]) / (bounds_list[3] - bounds_list[1]),
        }


def get_elem_aspect_ratio(elem_from_driver):
    assert hasattr(
        elem_from_driver, "size"
    ), "Given element seems to not be given by appium\
        webdriver as it doesn't have the method size"

    tolerance = 0.05

    size = elem_from_driver.size
    ratio = size["width"] / size["height"]

    if (16 / 9) - tolerance < ratio < (16 / 9) + tolerance:
        aspect_ratio = "16/9"
    elif (21 / 9) - tolerance < ratio < (21 / 9) + tolerance:
        aspect_ratio = "21/9"
    elif (32 / 9) - tolerance < ratio < (32 / 9) + tolerance:
        aspect_ratio = "32/9"
    else:
        aspect_ratio = f"Not an expected aspect ratio, instead got {ratio}"
    return aspect_ratio


def validate_padi_availability(driver, apinext_target, retry_attempts):
    """Validation of Padi availability
        This function is meant to understand if we have padi:
        - Operational
            Padi has MainActivity started. With display setting element available.
        - Inactive
            Padi has an inactive overlay layer. If we obtain this state
            we will tap on padi to make it operational.
        - Other
            None of the options above was found. Maybe padi comes from a
            reboot and we have boot animation on going...
    :param driver: Appium driver to interact with appium elements
    :param apinext_target: Target instance to execute adb command.
    :param retry_attempts: Number of retries to wait for PADI to be available
    :type retry_attempts: int
    :return: Return True or False depending on availability
    :rtype: bool
    Note: We use Try-Except because the WebDriverWait raises exception
            The intent here is to do not raise exceptions. We want to be able to retry.
    """
    for _ in range(retry_attempts):
        # Validation for regular PADI
        try:
            apinext_target.send_tap_event(*LeftPanel.side_center_coords)
            # Look for an element that will show if active
            WebDriverWait(driver, WAIT_FOR_PADI).until(
                ec.presence_of_element_located(LeftPanel.SIDE_PANEL_DISPLAY_MENU_BUTTON_ID)
            )
            logger.info("Padi MainActivity operational")
            return True
        except TimeoutException:
            logger.debug(
                f"Unable to find display menu button with id: {LeftPanel.SIDE_PANEL_DISPLAY_MENU_BUTTON_ID.selector}"
            )

        # Validation for PADI HDMI only
        try:
            apinext_target.send_tap_event(*LeftPanel.side_center_coords)
            # Look for an element that will show if active
            WebDriverWait(driver, WAIT_FOR_PADI).until(ec.presence_of_element_located(HdmiAppPage.HDMIPLUG_ID))
            logger.info("Padi HDMI only MainActivity operational")
            return True
        except TimeoutException:
            logger.debug(f"Unable to find display menu button with id: {HdmiAppPage.HDMIPLUG_ID.selector}")

        try:
            # Check overlay layer for PADI inactive
            inactivity_elem = WebDriverWait(driver, 2).until(
                ec.presence_of_element_located(LeftPanel.SIDE_PANEL_INACTIVITY_OVERLAY_ID),
                "Error while validating SidePanel element presence: "
                f"{LeftPanel.SIDE_PANEL_INACTIVITY_OVERLAY_ID.selector}",
            )
            logger.debug("Found Padi inactive layer. Taping to wake..")
            inactivity_elem.click()
        except TimeoutException:
            logger.debug(
                f"Unable to find inactive layer with id: {LeftPanel.SIDE_PANEL_INACTIVITY_OVERLAY_ID.selector}"
            )

    return False


def validate_idc23_home_availability(apinext_target, dlt_detector):
    """Validate the MainActivity of IDC23 through 3 different methods
    This function validates that after opening an appium session, when starting MainActivity
    for the first time, Laucher MainActivity was started and checks that the uiautomator server
    is also running. As a next step, we also verify that the media or connectivity widgets are
    set via the DLT message. If this last check fails, we only write that information in the log,
    but it does not mean that the target is not operational
    :param apinext_target: Apinext target object
    :param dlt_detector: DLTcontext listener to catch DLT messages
    :return: True if operational or False if not
    :rtype: bool
    Note: The widget is not set all the time we click on HomePage. It is when
        idc boots and when appium opens a new session.
    """
    # Get just the sixth word of the 'Hist #' command that only contains the package/activity
    launched_activities = apinext_target.execute_adb_command(
        ["shell", "dumpsys activity activities | grep 'Hist.*#' | awk '{print $6}'"]
    )

    logger.debug(f"Launched activities: {launched_activities}")

    if CHECK_LAUNCHER_ACTIVITY not in launched_activities:
        logger.error(f"Launcher MainActivity not found: {launched_activities}")
        return False

    # Check if uiautomator server is running
    check_uiautomator = apinext_target.execute_adb_command(["shell", "ps | grep uiautomator2"])

    if CHECK_UIAUTOMATOR_SERVER not in check_uiautomator:
        logger.error(f"uiautomator server not found: {check_uiautomator}")
        return False

    # wait for radio widget available on .MainActivity or phone/connectivity widget available
    dlt_widget_msg = re.compile(r"mediaapp.*Set widget with|ConnectivityApp.*PhoneWidgetController.*updating widget")
    widget_available_msg = dlt_detector.wait_for(
        {"apid": "ALD", "ctid": "LCAT", "payload_decoded": dlt_widget_msg},
        timeout=WAIT_FOR_IDC,
        count=1,
        drop=True,
        raise_on_timeout=False,
    )
    if widget_available_msg:
        logger.debug(f"Found widget_available_msg: '{widget_available_msg[0].payload_decoded}'")
        logger.info("MainActivity loaded media widget")
    else:
        # Non-blocking issue. Widget not set will let run the tests.
        logger.debug(f"Did not find message of mediaapp, Radio widget not set.Pattern:{widget_available_msg}.")
    return True


def pop_up_check(test):
    """Close pop-ups and if there is a pop-up with an OK button click on it to close the pop-up"""
    test.apinext_target.close_popups()
    pop_up_id = (By.ID, "com.android.systemui:id/okButton")
    pop_up_button = test.driver.find_elements(*pop_up_id)
    if pop_up_button:
        pop_up_button[0].click()
    time.sleep(2)


def is_alert_popup(driver):
    """Check if alter pop-up displays"""
    return driver.find_elements(*ALERT_TITLE)


def ensure_no_alert_popup(results_dir, driver, apinext_target):
    """If there is an alert, capture screenshot of the alert
    save it as 'test_name_alert_title_timestamp_now.png', then close the alert
    and proceed with the test"""

    alert_artifacts = Path(Path(results_dir).parent / "app_crashes")
    if not alert_artifacts.exists():
        alert_artifacts.mkdir(exist_ok=True, parents=True)
    alert = driver.find_elements(*ALERT_TITLE)
    # Sometimes, there are multiple alter pop-ups
    while alert:
        alert_title = alert[0].text.replace(" ", "_")
        test_name = Path(results_dir).stem
        timestamp_now = str(datetime.strftime(datetime.now(), "%Y-%m-%d.%H-%M-%S.%f"))
        screenshot_path = Path(Path(alert_artifacts), f"{test_name}_{alert_title}_{timestamp_now}.png")
        apinext_target.take_screenshot(screenshot_path)
        close_bt = driver.find_elements(*CLOSE_ALERT)
        if close_bt:
            close_bt[0].click()
            time.sleep(2)
        # Check if there is next alter pop-up
        alert = driver.find_elements(*ALERT_TITLE)


def ensure_no_traffic_info(results_dir, driver, apinext_target):
    """If there is a system traffic UI, capture screenshot of the system info as
    'test_name_traffic_info_timestamp_now.png', then close the alert
    and proceed with the test"""
    alert_artifacts = Path(Path(results_dir).parent / "system_info")
    if not alert_artifacts.exists():
        alert_artifacts.mkdir(exist_ok=True, parents=True)
    traffic_info_button = driver.find_elements(*TRAFFIC_INFO_OK_BUTTON)
    if traffic_info_button:
        # Take & save a screenshot
        test_name = Path(results_dir).stem
        timestamp_now = str(datetime.strftime(datetime.now(), "%Y-%m-%d.%H-%M-%S.%f"))
        screenshot_path = Path(Path(alert_artifacts), f"{test_name}_traffic_info_{timestamp_now}.png")
        apinext_target.take_screenshot(screenshot_path)
        # Close the traffic info
        traffic_info_button[0].click()
        time.sleep(2)


def take_apinext_target_screenshot(apinext_target, results_dir, file_name):
    """Take a screenshot using adb
    :param apinext_target: Apinext target object
    :param results_dir: path to results folder
    :type results_dir: str
    :param file_name: name for created file
    :type file_name: str
    """
    file_name = os.path.join(results_dir, file_name) if results_dir not in file_name else file_name
    file_name = str(file_name + ".png") if ".png" not in file_name else file_name
    file_name = deconflict_file_path(file_name, extension=".png")
    apinext_target.take_screenshot(file_name)
