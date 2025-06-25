# Copyright (C) 2023. BMW CTW PT. All rights reserved.
import logging
import os
import time

from collections import namedtuple
from appium.webdriver.common.touch_action import TouchAction
from mtee_apinext.enablers.support.android_generic_hid_mapping import AndroidGenericKeyCodes
from mtee_apinext.util.images import compare_images
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from si_test_idcevo import APPIUM_ELEMENT_TIMEOUT
from si_test_idcevo.si_test_helpers.screenshot_utils import crop_image

# Declaring Element namedtuple() to be used on Page selectors
Element = namedtuple("Element", ["strategy", "selector"])

logger = logging.getLogger(__name__)


class BasePage:
    """Base page class that with methods common to every page object class."""

    GENERIC_BACK_ARROW = Element(By.XPATH, "//*[contains(@resource-id, 'back_arrow_no_navigation')]")
    HANDLE_BAR_ID = Element(By.ID, "com.android.systemui:id/" + "handle_bar")
    CANCEL_EMERGENCY = Element(By.XPATH, "//*[contains(@text,'Cancel emergency')]")

    # Keycodes
    back_keycode = AndroidGenericKeyCodes.KEYCODE_BACK

    driver = None
    web_driver_wait = None
    apinext_target = None
    results_dir = None

    @classmethod
    def click(cls, locator):
        element = cls.check_visibility_of_element(locator)
        element.click()

    @classmethod
    def click_list_item(cls, locator, pos):
        cls.check_visibility_of_element(locator)
        element = cls.driver.find_elements(*locator)[pos]
        element.click()

    @classmethod
    def click_list_item_by_text(cls, locator, text):
        cls.check_visibility_of_element(locator)
        for element in cls.driver.find_elements(*locator):
            if text == element.text:
                element.click()

    @classmethod
    def get_elem_bounds(cls, element):
        """Find element and return it's bounds

        :param elem: Element object
        :type elem: namedtuple
        :return: String with element bounds with the structure: '[x_start, y_start][x_end, y_end]'
        """

        found_elem = cls.web_driver_wait.until(
            ec.presence_of_element_located(element), f"Error while validating {element.selector}"
        )

        return found_elem.get_attribute("bounds")

    @classmethod
    def check_visibility_of_element(cls, check_element_visible, web_driver_timeout=APPIUM_ELEMENT_TIMEOUT):
        """Wait until visibility of check_element_visible is found and return it

        An exception is raised by selenium if no element is found

        :param check_element_visible: id of the element to check
        :type check_element_visible: Element
        :param web_driver_timeout: WebDriverWait timeout, default is APPIUM_ELEMENT_TIMEOUT
        :type web_driver_timeout: int
        :return: visible element
        :rtype: Webdriver element
        """

        visible_element = WebDriverWait(cls.driver, web_driver_timeout).until(
            ec.visibility_of_element_located(check_element_visible),
            f"Unable to find element:'{check_element_visible.selector}' after waiting {web_driver_timeout} seconds",
        )

        return visible_element

    @classmethod
    def check_presence_of_element_located(cls, check_element_present):
        """Wait until presence of check_element_present is found and return it

        An exception is raised by selenium if no element is found

        :param check_element_present: id of the element to check
        :type check_element_present: Element
        :return: located element
        :rtype: Webdriver element
        """

        located_element = cls.web_driver_wait.until(
            ec.presence_of_element_located(check_element_present),
            message=f"Unable to find element:'{check_element_present.selector}'",
        )

        return located_element

    @classmethod
    def wait_to_check_visible_element(cls, check_element_visible, web_driver_timeout=APPIUM_ELEMENT_TIMEOUT):
        """Used for elements that take a while to show, but also might not show up at all

        A TimeoutException is raised by selenium if no element is found

        :param check_element_visible: id of the element to check
        :type check_element_visible: Element
        :return: visible element
        :rtype: Webdriver element
        """

        try:
            visible_element = WebDriverWait(cls.driver, web_driver_timeout).until(
                ec.visibility_of_element_located(check_element_visible),
                message=f"Unable to find element:'{check_element_visible.selector}' "
                f"after waiting {web_driver_timeout} seconds",
            )
            return visible_element
        except TimeoutException:
            return None

    @classmethod
    def try_back_arrow_click(cls):
        """Try to click on back arrow button if it's present"""
        back_arrow_elems = cls.driver.find_elements(*cls.GENERIC_BACK_ARROW)
        for element in back_arrow_elems:
            if element.get_attribute("clickable") == "true":
                element.click()
                time.sleep(1)
                return True
        return False

    @classmethod
    def get_element_by_text(cls, element_text):
        """Return a Element object defined by having the received text

        :param element_text: element text
        :type element_text: sting
        :return: Element object
        :rtype: namedtuple
        """
        return Element(By.XPATH, f"//*[@text='{element_text}']")

    @classmethod
    def click_button_and_expect_elem(cls, button, elem, sleep_time=0):
        """
        Clicks on a button and expects that some element with id: 'elem' is visible

        Args:
            button - located WebDriver element
            elem - Element (namedtuple) object
            sleep_time - sleep time between a click and webdriverwait until

        Returns:
            WebElement with id equal to 'elem'

        Raises:
            TimeoutException - If it was unable to find element with id: 'elem'
        """

        button_id = button.get_attribute("resource-id")
        button_text = button.get_attribute("text")
        button_text = button_text if button_text is not None else ""
        button.click()
        time.sleep(sleep_time)
        return cls.web_driver_wait.until(
            ec.visibility_of_element_located(elem),
            message=f"Unable to find element:'{elem}'" f"after click on button {button_id} with text: '{button_text}'",
        )

    @classmethod
    def click_button_and_not_expect_elem(cls, button, elem):
        """
        Clicks on a button and expects that some element with id: 'elem' is invisible

        Args:
            button - located WebDriver element
            elem - Element (namedtuple) object

        Returns:
            WebElement with id equal to 'elem'

        Raises:
            TimeoutException - If it was able to find element with id: 'elem'
        """

        button_id = button.get_attribute("resource-id")
        button_text = button.get_attribute("text")
        button_text = button_text if button_text is not None else ""
        button.click()
        return cls.web_driver_wait.until(
            ec.invisibility_of_element_located(elem),
            message=f"Found element:'{elem.selector}' after click\
                 on button {button_id} with text: '{button_text}'",
        )

    @classmethod
    def swipe_from_to(cls, from_elem, to_elem):
        """
        Swipe from one element to another

        Args:
            from_elem - WebElement object
            to_elem - WebElement Object
        """
        action = TouchAction(cls.driver)
        action.press(from_elem).move_to(to_elem).release().perform()

    @classmethod
    def input_text_and_get_elements(cls, text_elem, input_text, expected_elems):
        """
        Search elements with ID after given a text input.

        Args:
            text_elem - EditText element that will receive text input
            input_text - Text to input on textbox
            expected_elems - ID of expected elements

        Returns:
            List of WebElements matching the expected id
        """

        text_elem.send_keys(input_text)

        return cls.driver.find_elements(*expected_elems)

    @classmethod
    def get_activity_name(cls):
        """Return the current activity name"""
        return f"{cls.PACKAGE_NAME}/{cls.PACKAGE_ACTIVITY}" if cls.PACKAGE_ACTIVITY else f"{cls.PACKAGE_NAME}"

    @classmethod
    def set_activity_name(cls, new_name):
        cls.PACKAGE_ACTIVITY = new_name

    @classmethod
    def domain_identifier_command(cls):
        cmd = f" -a {cls.ACTION_ACTIVITY}"
        cmd += f" --es com.bmwgroup.idnext.launcher.car.domain.EXTRA_PLUGIN_ID {cls.DOMAIN_IDENTIFIER}"
        return cmd

    @classmethod
    def get_command_cold_start(cls):
        """Return the command to cold start the activity"""
        cmd = "am start -W -S"
        if hasattr(cls, "DOMAIN_IDENTIFIER"):
            cmd += cls.domain_identifier_command()
        else:
            cmd += f" -n {cls.get_activity_name()}"
        return cmd

    @classmethod
    def get_command_warm_hot_start(cls):
        """Return the command to warm/hot start the activity"""
        cmd = "am start -W"
        if hasattr(cls, "DOMAIN_IDENTIFIER"):
            cmd += cls.domain_identifier_command()
        else:
            cmd += f" -n {cls.get_activity_name()}"
        return cmd

    @classmethod
    def start_activity(cls, cmd=""):
        """Start the activity"""
        cmd = cmd if cmd else f"am start -n {cls.get_activity_name()}"
        return_stdout = cls.apinext_target.execute_command(cmd)
        return return_stdout

    @classmethod
    def validate_activity(cls, list_activities=[]):
        """Validate if expected list of activities are running (currently resumed/ in foreground)"""
        # Verify through adb if Launcher is running
        list_activities = list_activities if list_activities else [cls.get_activity_name()]
        dumpsys_activities = cls.apinext_target.execute_command(
            ["dumpsys activity activities | grep -E 'ResumedActivity'"]
        )
        logger.info(f"Found the following activities: '{dumpsys_activities}', expected: '{list_activities}'")
        return any(str(activity) in dumpsys_activities for activity in list_activities)

    @classmethod
    def go_to_notification_container(cls):
        handle_bar = cls.web_driver_wait.until(
            ec.visibility_of_element_located(cls.HANDLE_BAR_ID),
            message=f"Unable to find {cls.HANDLE_BAR_ID.selector} element",
        )
        handle_bar.click()

    @classmethod
    def check_and_close_emergency_stop_page(cls, wait_until_stop_visible=5):
        """
        Checks if the Emergency stop page is showing and if it is, close it.
        Returns:
        - True - Exit successfully from the Emergency stop page if it existed.
        Raises:
        - `AssertionError` -  If unable to exit from the Emergency stop page.
        """
        try:
            cls.check_visibility_of_element(cls.CANCEL_EMERGENCY, web_driver_timeout=wait_until_stop_visible)
        except TimeoutException:
            logger.info("Emergency stop element was not found")
            return True
        try:
            logger.info("Going to click on 'CANCEL' to close emergency page")
            cls.click(cls.CANCEL_EMERGENCY)
            return True
        except (NoSuchElementException, TimeoutException) as exc:
            raise AssertionError("Unable to exit from the Emergency stop page ") from exc

    @classmethod
    def swipe_using_coordinates(cls, coordinates, duration=1000):
        """
        Swipe from one location to another with the help of coordinates.
        :param coordinates: (List) [start_w, start_h, end_w, end_h]
        :param duration: (int) Duration of scroll (in milliseconds) defaults to 1 second here
        """
        cls.driver.swipe(coordinates[0], coordinates[1], coordinates[2], coordinates[3], duration)

    @classmethod
    def check_if_background_changed(cls, screenshot_before, screenshot_after, region=(2300, 600, 2750, 915)):
        """
        Verify change by comparing the images of the main display before and after action.

        Args:
            screenshot_before - Path to screenshot before changes
            screenshot_after - Path to screenshot after changes
            Region [tuple] - Region coordinates to crop image.
        Returns:
            True if background changed between the screenshots
            False if background did not change between the screenshots
        """
        path_to_cropped_images = os.path.join(os.path.dirname(screenshot_before), "cropped_images")
        os.makedirs(path_to_cropped_images, exist_ok=True)

        before_filename = os.path.basename(screenshot_before)
        after_filename = os.path.basename(screenshot_after)

        before_filename_with_cropped = (
            os.path.splitext(before_filename)[0] + "_cropped" + os.path.splitext(before_filename)[1]
        )
        after_filename_with_cropped = (
            os.path.splitext(after_filename)[0] + "_cropped" + os.path.splitext(after_filename)[1]
        )

        background_before = os.path.join(path_to_cropped_images, before_filename_with_cropped)
        background_after = os.path.join(path_to_cropped_images, after_filename_with_cropped)

        crop_image(screenshot_before, region, background_before)
        crop_image(screenshot_after, region, background_after)

        return not compare_images(background_after, background_before, concat=True, acceptable_fuzz_percent=5)
