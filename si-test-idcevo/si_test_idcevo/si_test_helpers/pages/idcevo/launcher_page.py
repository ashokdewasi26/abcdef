# Copyright (C) 2023. BMW CTW PT. All rights reserved.
import logging

from selenium.webdriver.common.by import By
from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage, Element

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class LauncherPage(BasePage):
    PACKAGE_NAME = "com.bmwgroup.idnext.launcher"
    LAUNCHER_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".IdxMainActivity"
    # Launcher elements resource ID / locators
    HOME_BUTTON_ID = Element(By.ID, "com.bmwgroup.idnext.overlay:id/" + "homeIcon")
    ALL_APPS_SEARCH_LABEL_ID = Element(By.ID, "com.bmwgroup.idnext.overlay:id/" + "menuIcon")

    @classmethod
    def press_all_apps_button(cls, test):
        """
        Send a inject event on adb to press the 'All Apps' button
        """

        all_apps_elem = cls.get_element_by_text("All apps")
        result = test.inject_custom_vhal_w_retry(all_apps_elem, 1050, inject_type="event")
        return result

    @classmethod
    def open_all_apps_from_home(cls, test):
        """
        Open all apps menu and trigger Search functionality
        Returns:
            Edit Text element to write search text
        Raises:
            NoSuchElementException - If it was not able to get All Apps menu button
            TimeoutException - If it was not able to find keyboard, EditText or Results elements
            after activating search
        """
        cls.go_to_home(test=test)
        cls.press_all_apps_button(test=test)

    @classmethod
    def go_to_home(cls, test):
        """
        Send a inject event on adb to press the 'Home' button
        """
        test.inject_custom_vhal_input(cls.back_keycode)
