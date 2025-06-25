import logging
import os
import re
import sh
import time

import lxml.etree as et
from mtee.testing.tools import retry_on_except
from mtee_apinext.enablers.support.android_generic_hid_mapping import AndroidGenericKeyCodes
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.common.pages.base_page import BasePage, Element
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.global_steps import GlobalSteps

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class LauncherPage(BasePage):

    PACKAGE_NAME = "com.bmwgroup.idnext.launcher"
    LAUNCHER_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".MainActivity"
    # Launcher elements resource ID / locators
    MENU_BAR_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "menubar")
    ALL_APPS_BUTTON_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "all_apps_button")
    MEDIA_BUTTON_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "media_button")
    TEL_BUTTON_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "com_button")
    NAV_BUTTON_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "nav_button")
    ALL_APPS_SEARCH_LABEL_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "btn_search")
    MEDIA_WIDGET_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "upperWidget")
    TEL_WIDGET_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "lowerWidget")
    WIDGET_PICKER_LIST_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "widgetPickerList")
    WIDGET_PICKER_ITEM_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "widgetPickerItem")
    WIDGET_PICKER_ITEM_LABEL_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "item_label")
    WIDGET_CONTAINER_ROOT_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "widget_container_root")
    WIDGET_AREA_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "widget_area_pager")
    WIDGET_PAGER_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "pager")
    KEYBOARD_PLACEHOLDER_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "keyboardPlaceholder")
    EDIT_SEARCH_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "search_box")
    SEARCH_RESULTS_HEADER_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "result_header")
    SEARCH_RESULT_APP_TEXT_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "tv_app_name")
    APPS_CONTAINER_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "apps_container")
    BACK_ARROW_BUTTON_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "back_arrow")
    MENU_HEADER_ITEM_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "title")
    LANGUAGE_POPUP_ID = Element(By.ID, "com.bmwgroup.idnext.speech.core:id/rootWindow")
    LANGUAGE_POPUP_CLOSE_ID = Element(By.ID, "com.bmwgroup.idnext.speech.core:id/option_2")
    PERSONAL_ASSISTANT_APP = Element(By.XPATH, "//*[contains(@text, 'Personal Assistant')]")

    HOME_SCREEN_ACT = [
        "com.bmwgroup.idnext.launcher/.MainActivity",
        "com.bmwgroup.idnext.navigation/.widget.map.MapWidgetActivity",
    ]
    ALL_APPS_MENUICON_ID = Element(By.ID, "com.bmwgroup.idnext.overlay:id/menuIcon")

    back_vhal_event_keycode = 1056
    menu_vhal_event_keycode = 1050

    # Tap coordinates
    LHD_COORDS = {"media": (410, 190), "tel": (410, 560), "nav": (900, 430), "back": (90, 460)}
    RHD_COORDS = {"media": (1500, 190), "tel": (1500, 560), "nav": (900, 430), "back": (90, 460)}

    @classmethod
    def validate_launcher(cls):
        # Verify through adb if Launcher is running
        activities = cls.apinext_target.execute_adb_command(["shell", "dumpsys activity activities"])
        return "com.bmwgroup.idnext.launcher/.MainActivity" in activities

    @classmethod
    @retry_on_except(retry_count=2, backoff_time=2)
    def validate_home_screen(cls):
        try:
            activities = cls.apinext_target.execute_adb_command(
                ["shell", "dumpsys activity activities | grep ResumedActivity"]
            )
        except sh.ErrorReturnCode_1 as err:
            logger.info("Unable to find current activities using adb dumpsys")
            raise err
        for each_act in cls.HOME_SCREEN_ACT:
            if each_act not in activities:
                RuntimeError(f"Expected activity {each_act} not found on home screen")

    @classmethod
    def press_all_apps_button(cls):
        GlobalSteps.inject_custom_vhal_input(cls.apinext_target, cls.menu_vhal_event_keycode)
        # Waiting for all apps screen to be displayed
        time.sleep(0.5)
        status = cls.driver.find_elements(*cls.ALL_APPS_SEARCH_LABEL_ID)
        if status:
            return status[0]
        else:
            all_apps_menu_icon = cls.driver.find_element(*cls.ALL_APPS_MENUICON_ID)
            all_apps_menu_icon.click()
            time.sleep(1)
            status = cls.driver.find_elements(*cls.ALL_APPS_SEARCH_LABEL_ID)
            return status[0]

    @classmethod
    def add_new_widget_to_launcher(cls, widget_item_text, new_widget):
        """
        Open widget list and add new widget into launcher

        Args:
            widget_item_text - Text on widget list item to be selected
            new_widget - ID of the created widget

        Returns:
            Element with id equal to 'new_widget'

        Raises:
            AssertionError - If not able to find widget in widget picker list
            TimeoutException - If it was unable to find element with id  'new_widget'
        """
        cls.driver.keyevent(AndroidGenericKeyCodes.KEYCODE_A)

        found_item = None
        window_size = cls.driver.get_window_size()

        starty = window_size.get("height") * 0.8
        endy = window_size.get("height") * 0.20
        startx = window_size.get("width") / 2

        labels = {}
        while found_item is None:
            widget_picker_list = cls.driver.find_element(*cls.WIDGET_PICKER_LIST_ID)
            items = widget_picker_list.find_elements(
                By.XPATH, f"//*[@resource-id='{cls.WIDGET_PICKER_ITEM_LABEL_ID}']"
            )

            # This means that no new labels were found
            if items[-1].get_attribute("text") in labels:
                break

            for item in items:
                item_text = item.get_attribute("text")
                if item_text == widget_item_text:
                    found_item = item
                    break
                labels[item.get_attribute("text")] = item

            if not found_item:
                cls.driver.swipe(startx, starty, startx, endy)

        assert found_item, f"Could not find {widget_item_text} on widget picker list"

        return GlobalSteps.click_button_and_expect_elem(cls.wb, found_item, new_widget)

    @classmethod
    def open_all_apps_from_home(cls):
        """
        Open all apps menu and trigger Search functionality

        Returns:
            Edit Text element to write search text

        Raises:
            NoSuchElementException - If it was not able to get All Apps menu button
            TimeoutException - If it was not able to find keyboard, EditText or Results elements
                                after activating search
        """
        cls.go_to_home()
        cls.press_all_apps_button()

    @classmethod
    def go_to_home(cls):
        """
        Go to Home and checks that Menu Bar and Widget Area are present

        Raises:
            TimeoutException - If it was unable to find element with id: 'elem_id'
        """
        cls.driver.keyevent(AndroidGenericKeyCodes.KEYCODE_HOME)
        cls.validate_home_screen()
        utils.ensure_no_alert_popup(cls.results_dir, cls.driver, cls.apinext_target)

    @classmethod
    def delete_widgets(cls):
        """
        Delete widgets from widget area

        Raises:
            NoSuchElement - If it was not able to get widget pager
            AssertionError - If found elements on widget pager
        """
        cls.driver.keyevent(AndroidGenericKeyCodes.KEYCODE_D)
        pager = cls.driver.find_element(*cls.WIDGET_PAGER_ID)
        assert not pager.find_elements(*cls.WIDGET_CONTAINER_ROOT_ID), "Unable to delete widgets"

    @classmethod
    def assert_shown_ordered_widgets(cls, ordered_widgets):
        """
        Asserts that widgets are displayed with the correct ordering

        Args:
            ordered_widgets - Ordered list of widgets

        Raises:
            AssertionError - If size of 'ordered_widgets' is not equal to list of displayed widgets
            NoSuchElementException - If it was not able to find an element of 'ordered_widgets' on displayed widgets
        """
        shown_widgets = cls.driver.find_elements(*cls.WIDGET_CONTAINER_ROOT_ID)

        l_shown_widgets = len(shown_widgets)
        l_ordered_widgets = len(ordered_widgets)

        assert (
            l_shown_widgets == l_ordered_widgets
        ), f"Found {l_shown_widgets} widgets and was expecting {l_ordered_widgets}"

        for i, widget in enumerate(shown_widgets):
            ow_id = ordered_widgets[i].get_attribute("resource-id")
            try:
                widget.find_element(By.ID, ow_id)
            except NoSuchElementException:
                raise NoSuchElementException(msg=f"Element with id: '{ow_id}' could not be located on the page")

    @classmethod
    def open_all_apps_search_from_home(cls):
        """
        Open all apps menu and trigger Search functionality

        Returns:
            Edit Text element to write search text

        Raises:
            NoSuchElementException - If it was not able to get All Apps menu button
            TimeoutException - If it was not able to find keyboard, EditText or Results elements
                                after activating search
        """
        cls.go_to_home()
        search_label = cls.press_all_apps_button()
        search_label.click()
        edit_text = cls.wb.until(
            ec.visibility_of_element_located(cls.EDIT_SEARCH_ID),
            message="Unable to find Edit Search element on All Apps search",
        )
        cls.wb.until(
            ec.visibility_of_element_located(cls.SEARCH_RESULTS_HEADER_ID),
            message="Unable to find Results element on All Apps search",
        )

        return edit_text

    @classmethod
    def _check_widgets_and_move(cls, expected_widgets, from_widget, to_widget, new_widget):
        cls.assert_shown_ordered_widgets(expected_widgets)

        cls.swipe_from_to(cls.driver, from_widget, to_widget)
        next_id = new_widget.get_attribute("resource-id")
        cls.wb.until(ec.presence_of_element_located((By.ID, next_id)), f"Unable to find {next_id} after swipe")

    @classmethod
    def get_type_key(cls, vehicle_order):
        """
        Find if the launcher has right-steering-layout or left-steering-layout
        If the second digit of typekey value is 2 then its RHD [3(2)EE] & if its 1 then its LHD [3(1)EE]

        :param vehicle_order: FA file path used to code the target.
        :return: "LHD" or "RHD"

        Reference: https://cc-github.bmwgroup.net/apinext/si-test-apinext/pull/463/files#r1068792
        """
        ns_tag = "ns0"
        type_key_regex = re.compile(r"^\d(\d)[A-Z]{2}$")
        ns = {ns_tag: "http://bmw.com/2005/psdz.data.fa"}
        tree = et.parse(vehicle_order)
        headers = tree.findall(".//{0}:fa/{0}:standardFA".format(ns_tag), ns)
        type_key = headers[0].attrib["typeKey"]
        return "RHD" if re.search(type_key_regex, type_key).group(1) == "2" else "LHD"

    @classmethod
    def go_to_submenu(cls, submenu_option, title_id, exp_submenu_text):
        """
        Go to the submenu option inside the app

        param: submenu_option - Element id of the submenu option.
        param: title_id - Element id of the page title.
        param: exp_submenu_text - Expected page title(str or list of strings).
        """
        submenu_button = cls.check_visibility_of_element(submenu_option)
        menu_title = GlobalSteps.click_button_and_expect_elem(cls.wb, submenu_button, title_id)
        assert (
            menu_title.text in exp_submenu_text
        ), f"Not able to select and enter the {submenu_option.selector} submenu"

    @classmethod
    def return_from_submenu(cls, title_id, exp_submenu_text, loop_count=5, wait_time=3):
        """
        Return from submenus of an app

        param: title_id - Android id of the page title.
        param: exp_submenu_text - Expected page title(str or list of strings).
        param: loop_count - Number of times to press back button.
        param: wait_time - Time delay before searching page title
        """
        time.sleep(wait_time)
        for _ in range(loop_count):
            menu_title = cls.driver.find_elements(*title_id)
            if menu_title and menu_title[0].text in exp_submenu_text:
                return
            GlobalSteps.inject_key_input(cls.apinext_target, cls.back_keycode)
        screenshot = os.path.join(
            cls.results_dir,
            f'Unexpected_menu_{time.strftime("%Y-%h-%d_%H-%M-%S")}.png',
        )
        cls.apinext_target.take_screenshot(screenshot)
        raise Exception(f"Unable to return to expected menu. Refer current screen state in {screenshot}")
