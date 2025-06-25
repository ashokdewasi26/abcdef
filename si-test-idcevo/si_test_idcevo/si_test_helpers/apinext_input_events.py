# Copyright (C) 2023. BMW CTW PT. All rights reserved.
import time

from selenium.webdriver.support import expected_conditions as ec

# VHAL events templates for testing AZV touch buttons
vhal_custom_key_event = "cmd car_service inject-custom-input "
vhal_key_event = "cmd car_service inject-key "


class ApinextInputEvents(object):
    def inject_custom_vhal_input(self, event_keycode):
        """
        Simulate touch/button press using VHAL event
        Refer: https://developer.bmwgroup.net/docs/apinext/deploymenttargets/emulator/

        Args:
            vhal_event_keycode - int: VHAL event keycode
        """
        key_down_event = vhal_custom_key_event + str(event_keycode)
        key_up_event = vhal_custom_key_event + str(event_keycode + 1)
        self.apinext_target.execute_command([key_down_event])
        time.sleep(0.2)
        self.apinext_target.execute_command([key_up_event])

    def inject_key_input(self, event_keycode, count=1):
        """
        Inject android key events
        Refer: https://developer.bmwgroup.net/docs/apinext/deploymenttargets/emulator/#examples-with-inject-key

        param: event_keycode(int) - Android keycodes
        param: count(int) - number of times to input the keycode
        """
        key_event = vhal_key_event + str(event_keycode)
        for _ in range(count):
            self.apinext_target.execute_command([key_event])
            time.sleep(0.2)

    def inject_custom_vhal_w_retry(self, wait_elem, vhal_event_keycode, inject_type="key", retry_num=3):
        """
        Simulate injecting input with retries

        Args:
            wait_elem - WebElement object
            vhal_event_keycode - int: VHAL event keycode to populate VHAL event template
            retry_num - int: number of retries

        Returns:
            The number of iterations until success, or -1 if unsuccessful
        """
        for i in range(1, retry_num):
            if inject_type == "key":
                self.inject_key_input(vhal_event_keycode)
            else:
                self.inject_custom_vhal_input(vhal_event_keycode)
            time.sleep(1)
            if ec.presence_of_element_located(wait_elem):
                return i
        return -1
