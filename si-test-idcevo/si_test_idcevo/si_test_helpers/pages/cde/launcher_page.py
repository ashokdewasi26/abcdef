# Copyright (C) 2025. BMW CTW PT. All rights reserved.
import logging

from selenium.webdriver.common.by import By
from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage, Element

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class LauncherPage(BasePage):
    PACKAGE_NAME = "com.bmwgroup.apinext.cdelauncherapp"
    LAUNCHER_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".presentation.ui.MainActivity"
    # Launcher elements resource ID / locators
    ALL_APPS_SEARCH_LABEL_ID = Element(By.XPATH, "//*[@resource-id='IconicBarAllAppsButton']")
    ALL_APPS_MENU_ID = Element(By.XPATH, "//*[contains(@text,'All apps')]")
    HOME_BUTTON_ID = Element(By.XPATH, "//*[@resource-id='IconicBarHomeButton']")
    HOME_MENU_ID = Element(By.XPATH, "//*[@resource-id='HomeScreen']")

    @classmethod
    def press_all_apps_button(cls):
        """
        Clicks on the 'All Apps' button
        """
        all_apps_button = cls.check_visibility_of_element(cls.ALL_APPS_SEARCH_LABEL_ID)

        if all_apps_button:
            logger.debug("All Apps button is visible")
            if cls.click_button_and_expect_elem(all_apps_button, cls.ALL_APPS_MENU_ID, 2):
                logger.debug("All Apps button clicked successfully")
                return True
            else:
                logger.debug("All Apps button click failed")
                raise AssertionError("Failed to click All Apps button")
        else:
            logger.debug("All Apps button is not visible")
            raise AssertionError("All Apps button is not visible")

    @classmethod
    def go_to_home(cls):
        """
        Clicks on the home button
        """
        home_button = cls.check_visibility_of_element(cls.HOME_BUTTON_ID)

        if home_button:
            logger.debug("Home button is visible")
            if cls.click_button_and_expect_elem(home_button, cls.HOME_MENU_ID, 2):
                logger.debug("Home button clicked successfully")
                return True
            else:
                logger.debug("Home button click failed")
                raise AssertionError("Failed to click Home button")
        else:
            logger.debug("Home button is not visible")
            raise AssertionError("Home button is not visible")
