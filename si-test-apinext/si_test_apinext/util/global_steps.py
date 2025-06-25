import time

from appium.webdriver.common.touch_action import TouchAction
from selenium.webdriver.support import expected_conditions as ec

# VHAL events templates for testing AZV touch buttons
vhal_custom_key_event = "cmd car_service inject-custom-input "
vhal_key_event = "cmd car_service inject-key "
vhal_rotary_event = "cmd car_service inject-rotary -c "


class GlobalSteps:
    @classmethod
    def click_button_and_expect_elem(cls, wb, button, elem, sleep_time=0):
        """
        Clicks on a button and expects that some element with id: 'elem' is visible

        Args:
            wb - WebDriverWait object
            button - located WebDriver element
            elem - Element (namedtuple) object

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
        return wb.until(
            ec.visibility_of_element_located(elem),
            message=f"Unable to find element:'{elem}'" f"after click on button {button_id} with text: '{button_text}'",
        )

    @classmethod
    def click_button_and_not_expect_elem(cls, wb, button, elem):
        """
        Clicks on a button and expects that some element with id: 'elem' is invisible

        Args:
            test - TestBase singleton object
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
        return wb.until(
            ec.invisibility_of_element_located(elem),
            message=f"Found element:'{elem.selector}' after click\
                 on button {button_id} with text: '{button_text}'",
        )

    @classmethod
    def get_package_running(cls, driver):
        """
        Clicks on a button and expects that package to open

        Args:
            driver - WebDriver object

        Returns:
            Package currently running
        """

        return driver.current_package

    @classmethod
    def swipe_from_to(cls, driver, from_elem, to_elem):
        """
        Swipe from one element to another

        Args:
            driver - WebDriver object
            from_elem - WebElement object
            to_elem - WebElement Object
        """
        action = TouchAction(driver)
        action.press(from_elem).move_to(to_elem).release().perform()

    @classmethod
    def input_text_and_get_elements(cls, driver, text_elem, input_text, expected_elems):
        """
        Search elements with ID after given a text input.

        Args:
            driver - WebDriver object
            text_elem - EditText element that will receive text input
            input_text - Text to input on textbox
            expected_elems - ID of expected elements

        Returns:
            List of WebElements matching the expected id
        """

        text_elem.send_keys(input_text)

        return driver.find_elements(*expected_elems)

    @classmethod
    def inject_custom_vhal_input(cls, apinext_target, event_keycode):
        """
        Simulate touch/button press using VHAL event
        Refer: https://developer.bmwgroup.net/docs/apinext/deploymenttargets/emulator/

        Args:
            apinext_target - Apinext target object
            vhal_event_keycode - int: VHAL event keycode
        """
        key_down_event = vhal_custom_key_event + str(event_keycode)
        key_up_event = vhal_custom_key_event + str(event_keycode + 1)
        apinext_target.execute_adb_command(["shell", key_down_event])
        time.sleep(0.2)
        apinext_target.execute_adb_command(["shell", key_up_event])

    @classmethod
    def inject_key_input(cls, apinext_target, event_keycode, count=1):
        """
        Inject android key events
        Refer: https://developer.bmwgroup.net/docs/apinext/deploymenttargets/emulator/#examples-with-inject-key

        param: apinext_target - Apinext target object
        param: event_keycode(int) - Android keycodes
        param: count(int) - number of times to input the keycode
        """
        key_event = vhal_key_event + str(event_keycode)
        for _ in range(count):
            apinext_target.execute_adb_command(["shell", key_event])
            time.sleep(0.2)

    @classmethod
    def inject_rotary_input(cls, apinext_target, rotary_input, count=1):
        """
        Inject ZBE rotations
        Use inject_key_input for ZBE UP/DOWN/LEFT/RIGHT

        param: apinext_target - Apinext target object
        param: rotary_input(int) - 1 -> clockwise, 0 -> counter-clockwise
        param: count(int) - number of times the rotary to be turned
        """

        rotary_event = vhal_rotary_event + ("true" if rotary_input == 1 else "false")
        for _ in range(count):
            apinext_target.execute_adb_command(["shell", rotary_event])
            time.sleep(0.2)

    @classmethod
    def inject_custom_vhal_w_retry(cls, apinext_target, wait_elem, vhal_event_keycode, inject_type="key", retry_num=3):
        """
        Simulate injecting input with retries

        Args:
            apinext_target - Apinext target object
            wait_elem - WebElement object
            vhal_event_keycode - int: VHAL event keycode to populate VHAL event template
            retry_num - int: number of retries

        Returns:
            The number of iterations until success, or -1 if unsuccessful
        """
        for i in range(1, retry_num):
            if inject_type == "key":
                cls.inject_key_input(apinext_target, vhal_event_keycode)
            elif inject_type == "rotary":
                cls.inject_rotary_input(apinext_target, vhal_event_keycode)
            else:
                cls.inject_custom_vhal_input(apinext_target, vhal_event_keycode)
            time.sleep(1)
            if ec.presence_of_element_located(wait_elem):
                return i
        return -1
