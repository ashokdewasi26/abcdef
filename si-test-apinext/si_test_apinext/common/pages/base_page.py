import logging
import time
from collections import namedtuple

from mtee.testing.tools import retry_on_except
from mtee_apinext.enablers.support.android_generic_hid_mapping import AndroidGenericKeyCodes
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from si_test_apinext.util.wait_element import WaitForElement

# Declaring Element namedtuple() to be used on Page selectors
Element = namedtuple("Element", ["strategy", "selector"])

logger = logging.getLogger(__name__)


class BasePage:
    """Base page class that with methods common to every page object class."""

    GENERIC_BACK_ARROW = Element(By.XPATH, "//*[contains(@resource-id, 'back_arrow_no_navigation')]")

    # Keycodes
    back_keycode = AndroidGenericKeyCodes.KEYCODE_BACK

    driver = None
    wb = None
    apinext_target = None
    results_dir = None
    mtee_target = None
    branch_name = None

    @classmethod
    def click(cls, locator):
        WaitForElement.wait(cls.driver, locator)
        element = cls.driver.find_element(*locator)
        element.click()

    @classmethod
    def click_list_item(cls, locator, pos):
        WaitForElement.wait(cls.driver, locator)
        element = cls.driver.find_elements(*locator)[pos]
        element.click()

    @classmethod
    def click_list_item_by_text(cls, locator, text):
        WaitForElement.wait(cls.driver, locator)
        for element in cls.driver.find_elements(*locator):
            if text == element.text:
                element.click()

    @classmethod
    @retry_on_except(retry_count=3)
    def start_activity(cls, validate_activity=True):
        """Call start activity on the target"""
        activity_name = f"{cls.PACKAGE_NAME}/{cls.PACKAGE_ACTIVITY}" if cls.PACKAGE_ACTIVITY else f"{cls.PACKAGE_NAME}"
        cls.apinext_target.execute_adb_command(["shell", f"am start -n {activity_name}"])
        time.sleep(1)
        if validate_activity:
            current_package = cls.driver.current_package
            if current_package != cls.PACKAGE_NAME:
                raise RuntimeError(
                    f"Web driver couldn't find expected package after starting {cls.PACKAGE_NAME}/"
                    f"{cls.PACKAGE_ACTIVITY}.Instead found package: {current_package}"
                )

    @classmethod
    def get_elem_bounds(cls, elem, wb_timeout=2):
        """
        Find element and return it's bounds

        Args:
            elem - Element (namedtuple) object
            wb_timeout - Int - WebDriverWait timeout, 2 sec by default

        Returns:
            String with element bounds with the structure:
            '[x_start, y_start][x_end, y_end]'
        """
        found_elem = WebDriverWait(cls.driver, wb_timeout).until(
            ec.presence_of_element_located(elem), f"Error while validating {elem.selector}"
        )
        return found_elem.get_attribute("bounds")

    @classmethod
    def check_presence_of_element_located(cls, check_elem_present):
        """Wait until presence of check_elem_present is found and return it

        An exception is raised by selenium if no element is found

        :param check_elem_present: id of the element to check
        :type check_elem_present: Element
        :return: located element
        :rtype: Webdriver element
        """
        located_element = cls.wb.until(
            ec.presence_of_element_located(check_elem_present),
            message=f"Unable to find element:'{check_elem_present.selector}'",
        )
        return located_element

    @classmethod
    def check_visibility_of_element(cls, check_elem_visible):
        """Wait until visibility of check_elem_visible is found and return it

        An exception is raised by selenium if no element is found

        :param check_elem_visible: id of the element to check
        :type check_elem_visible: Element
        :return: visible element
        :rtype: Webdriver element
        """
        visible_element = cls.wb.until(
            ec.visibility_of_element_located(check_elem_visible),
            message=f"Unable to find element:'{check_elem_visible.selector}'",
        )
        return visible_element

    @classmethod
    def check_visibility_of_first_and_second_elements(cls, first_element, second_element):
        """The purpose of this method is to check the presence of first element. If first element is not visible
        then it will check the presence of second element
        :param first_element: first element to be checked
        :param second_element: second element to be checked
        """
        elements = [first_element, second_element]
        for element in elements:
            visible_element = cls.driver.find_elements(*element)
            if visible_element:
                return visible_element
        return visible_element

    @classmethod
    def wait_to_check_visible_element(cls, check_elem_visible):
        """Used for elements that take a while to show, but also might not show up at all"""
        try:
            visible_element = cls.wb.until(
                ec.visibility_of_element_located(check_elem_visible),
                message=f"Unable to find element:'{check_elem_visible.selector}'",
            )
            return visible_element
        except TimeoutException:
            return None

    @classmethod
    def try_back_arrow_click(cls):
        """
        Try to click on back arrow button if it's present
        """
        back_arrow_elems = cls.driver.find_elements(*cls.GENERIC_BACK_ARROW)
        for elem in back_arrow_elems:
            if elem.get_attribute("clickable") == "true":
                elem.click()
                time.sleep(1)
                return True
        return False

    @classmethod
    def get_element_by_text(cls, element_text):
        """Return an Element object defined by having the received text"""
        return Element(By.XPATH, f"//*[@text='{element_text}']")

    @classmethod
    def wait_and_click_on_element(cls, element, wait=1, iteration=3):
        """
        This Function can be used in case if element is taking more time to appear.
        It will find and click by waiting for an element in iteration

        Args:
            element - Element to be clicked on
            wait - sleep time
            iteration - Iteration to find an element
        """
        for i in range(iteration):
            time.sleep(wait)
            button = cls.driver.find_elements(*element)
            if button:
                button[0].click()
                break
            else:
                logger.info(f"Waiting after: {i}")
