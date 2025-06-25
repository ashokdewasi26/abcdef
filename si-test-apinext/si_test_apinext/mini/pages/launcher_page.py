import logging
import os
import time

from mtee.testing.tools import retry_on_except
from mtee_apinext.enablers.support.android_generic_hid_mapping import AndroidGenericKeyCodes
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from si_test_apinext.common.pages.base_page import BasePage, Element
from si_test_apinext.mini.pages.connectivity_page import ConnectivityPage as Connect
from si_test_apinext.mini.pages.media_page import MediaPage as Media
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.global_steps import GlobalSteps

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class LauncherPage(BasePage):

    PACKAGE_NAME = "com.bmwgroup.idnext.launcher"
    LAUNCHER_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".MainActivity"
    # Launcher elements resource ID / locators
    MINI_HOME_PAGER_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "pager")
    BACKGROUND_OUTER_CIRCLE_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "background_outer_circle")
    MAIN_CONTENT_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "main_content")
    ALL_APPS_AREA = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "all_apps_area")
    RECYCLER_APPS_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "recycler_apps")
    ALL_APPS_BUTTON_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "all_apps_button")
    MEDIA_BUTTON_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "media_button")
    TEL_BUTTON_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "com_button")
    NAV_BUTTON_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "nav_button")
    ALL_APPS_SEARCH_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "edit_search")
    SEARCH_BUTTON_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "btn_search")
    MEDIA_WIDGET_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "media_widget")
    TEL_WIDGET_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "phoneWidget")
    WIDGET_PICKER_LIST_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "widgetPickerList")
    WIDGET_PICKER_ITEM_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "widgetPickerItem")
    WIDGET_PICKER_ITEM_LABEL_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "item_label")
    WIDGET_CONTAINER_ROOT_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "widget_container_root")
    WIDGET_AREA_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "widget_area")
    WIDGET_PAGER_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "pager")
    KEYBOARD_PLACEHOLDER_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "keyboard_area")
    EDIT_SEARCH_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "search_box")
    SEARCH_RESULTS_HEADER_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "results_header")
    SEARCH_RESULT_APP_ITEM_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "item_label")
    APPS_CONTAINER_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "apps_container")
    BACK_ARROW_BUTTON_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "back_arrow")
    MENU_HEADER_ITEM_ID = Element(By.ID, LAUNCHER_RESOURCE_ID_PREFIX + "title")
    HIDE_KEYBOARD = Element(By.ID, "com.bmwgroup.idnext.keyboard:id/hideKeyBoard")
    OVERLAY_HOME_BUTTON = Element(By.ID, "com.bmwgroup.idnext.overlay:id/det_home")
    OVERLAY_TIME = Element(By.ID, "com.bmwgroup.idnext.overlay:id/time")
    # language tests
    LANGUAGE_POPUP_ID = Element(By.ID, "com.bmwgroup.idnext.speech.core:id/rootWindow")
    LANGUAGE_POPUP_CLOSE_ID = Element(By.ID, "com.bmwgroup.idnext.speech.core:id/option_2")
    # inside apps back button
    BACK_BUTTON_ID = Element(By.ID, "com.bmwgroup.apinext.appstore:id/back_arrow_no_navigation")
    CURRENT_TIME = Element(
        By.XPATH,
        "//*[@resource-id='com.bmwgroup.idnext.overlay:id/layout_current_time']"
        "/*[@resource-id='com.bmwgroup.idnext.overlay:id/time']",
    )
    menu_event_keycode = 1050

    # Tap Coordinates
    menu_coords = (862, 1545)
    nav_coords = (995, 1545)
    media_coords = (762, 1545)
    tel_coords = (1085, 1545)
    hide_keyboard_coords = (130, 753)

    @classmethod
    def validate_launcher(cls):
        # Verify through adb if Launcher is running
        activities = cls.apinext_target.execute_adb_command(["shell", "dumpsys activity activities"])
        return "com.bmwgroup.idnext.launcher/.MainActivity" in activities

    @classmethod
    @retry_on_except(retry_count=2)
    def turn_on_bluetooth(cls):
        """
        Activating bluetooth if bluetooth not activated
        """
        cls.go_to_home()
        tel_button = cls.driver.find_elements(*Connect.OVERLAY_CONN_BUTTON)
        if tel_button:
            tel_button[0].click()
        time.sleep(3)
        activate_bt = cls.driver.find_elements(*Connect.ACTIVATE_BLUETOOTH_ID)
        if activate_bt:
            logger.info("Bluetooth is off. Activating...")
            GlobalSteps.click_button_and_expect_elem(cls.wb, activate_bt[0], Connect.BT_NAME)
            utils.ensure_no_alert_popup(cls.results_dir, cls.driver, cls.apinext_target)
            # Go back and come inside to find updated page source
            GlobalSteps.inject_key_input(cls.apinext_target, cls.back_keycode)
            time.sleep(5)
            cls.wb.until(
                ec.visibility_of_element_located(Connect.CONN_DISC_FRAG_ID),
                message=f"Unable to find :'{Connect.CONN_DISC_FRAG_ID.selector}' element after turning on BT",
            )
        else:
            bt_turned_on = cls.driver.find_elements(*Connect.CONN_DISC_FRAG_ID)
            phone_connected = cls.driver.find_elements(*Connect.CONN_DEVICE)
            if bt_turned_on or phone_connected:
                logger.info("Bluetooth is already activated")
            else:
                cls.apinext_target.take_screenshot(
                    os.path.join(cls.results_dir, f'connectivity_{time.strftime("%Y-%h-%d_%H-%M-%S")}.png')
                )
        cls.go_to_home()

    @classmethod
    def reconnect_media(cls):
        """
        Reconnecting media if reconnect popup appears in media screen
        """
        cls.go_to_media()
        media_elem = Media.MEDIA_BAR_ID
        cls.wb.until(
            ec.visibility_of_element_located(media_elem),
            message=f"Unable to find media element:'{media_elem.selector}' after tapping on MEDIA button",
        )
        if cls.driver.find_elements(*Media.RECONNECT_MEDIA):
            reconnect_media = cls.wb.until(
                ec.visibility_of_element_located(Media.RECONNECT_MEDIA),
                message=f"Unable to find {Media.RECONNECT_MEDIA.selector} element on All Apps search",
            )
            GlobalSteps.click_button_and_expect_elem(cls.wb, reconnect_media, Media.MEDIA_SOURCE_SELECTOR_ID)
        cls.go_to_home()

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
        GlobalSteps.inject_custom_vhal_input(cls.apinext_target, cls.menu_event_keycode)
        cls.wb.until(
            ec.visibility_of_element_located(cls.RECYCLER_APPS_ID),
            message=f"Unable to find menu element {cls.RECYCLER_APPS_ID.selector}",
        )

    @classmethod
    def open_media_from_home(cls):
        """
        Opens media app from Home screen

        Raises:
            NoSuchElementException - If it was not able to get Media button
            TimeoutException - If it was not able to find Media elements
        """
        cls.go_to_home()
        media_button_elem = cls.wb.until(ec.presence_of_element_located(cls.MEDIA_BUTTON_ID))
        GlobalSteps.click_button_and_expect_elem(cls.wb, media_button_elem, cls.ALL_APPS_SEARCH_LABEL_ID)

    @classmethod
    def go_to_home(cls):
        """
        Go to Home and checks that Menu Bar and Widget Area are present

        Raises:
            TimeoutException - If it was unable to find element with id: 'elem_id'
        """

        cls.driver.keyevent(AndroidGenericKeyCodes.KEYCODE_HOME)

        focused_app = cls.apinext_target.execute_adb_command(
            ["shell", "dumpsys activity activities | grep 'mFocusedApp'"]
        )

        logger.debug(f"Focused Application: {focused_app}")
        except_app = cls.PACKAGE_NAME + "/" + cls.PACKAGE_ACTIVITY

        if except_app not in focused_app:
            logger.error(f"Current focused application isn't launcher page: {focused_app}")

        try:
            WebDriverWait(cls.driver, 2).until(
                ec.presence_of_element_located(cls.MINI_HOME_PAGER_ID),
                f"Error while validating: {cls.MINI_HOME_PAGER_ID}",
            )
        except TimeoutException:
            logger.error(f"Unable to find: {cls.MINI_HOME_PAGER_ID}")

        try:
            WebDriverWait(cls.driver, 2).until(
                ec.presence_of_element_located(cls.BACKGROUND_OUTER_CIRCLE_ID),
                f"Error while validating: {cls.BACKGROUND_OUTER_CIRCLE_ID}",
            )
        except TimeoutException:
            logger.error(f"Unable to find: {cls.BACKGROUND_OUTER_CIRCLE_ID}")

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
        cls.go_to_main_menu()
        cls.wb.until(
            ec.visibility_of_element_located(cls.RECYCLER_APPS_ID),
            message=f"Unable to find menu element {cls.RECYCLER_APPS_ID.selector}",
        )
        edit_search_ele = cls.driver.find_elements(*cls.EDIT_SEARCH_ID)
        if len(edit_search_ele) == 0:
            search_button = cls.wb.until(
                ec.visibility_of_element_located(cls.SEARCH_BUTTON_ID),
                message=f"Unable to find {cls.SEARCH_BUTTON_ID.selector} element on All Apps search",
            )
            search_button.click()
        return cls.wb.until(
            ec.visibility_of_element_located(cls.EDIT_SEARCH_ID),
            message=f"Unable to find {cls.EDIT_SEARCH_ID.selector} element on All Apps search",
        )

    @classmethod
    def _check_widgets_and_move(cls, expected_widgets, from_widget, to_widget, new_widget):
        cls.assert_shown_ordered_widgets(expected_widgets)
        cls.swipe_from_to(cls.driver, from_widget, to_widget)
        next_id = new_widget.get_attribute("resource-id")
        cls.wb.until(ec.presence_of_element_located((By.ID, next_id)), f"Unable to find {next_id} after swipe")

    @classmethod
    @retry_on_except(retry_count=2)
    def go_to_main_menu(cls):
        """
        this method is used to go to main menu through tap
        as of now we have tap keycode is not working and we didn't find better approach  in future we can change
        if we have better approach

        """
        cls.go_to_home()
        GlobalSteps.inject_custom_vhal_input(cls.apinext_target, cls.menu_event_keycode)
        status = cls.driver.find_elements(*cls.SEARCH_BUTTON_ID)
        if status:
            return True
        else:
            for i in range(3):
                cls.apinext_target.send_keycode(AndroidGenericKeyCodes.KEYCODE_BACK)
                time.sleep(1)
        GlobalSteps.inject_custom_vhal_input(cls.apinext_target, cls.menu_event_keycode)
        cls.wb.until(
            ec.visibility_of_element_located(cls.SEARCH_BUTTON_ID),
            message=f"Unable to find menu element {cls.SEARCH_BUTTON_ID.selector}",
        )

    @classmethod
    def go_to_media(cls):
        """
        Opens the media app in the HMI
        """
        GlobalSteps.inject_custom_vhal_input(cls.apinext_target, Media.media_vhal_event_keycode)

    @classmethod
    def go_to_tel(cls):
        """
        Opens the Tel app in the HMI
        """
        GlobalSteps.inject_custom_vhal_input(cls.apinext_target, Connect.conn_vhal_event_keycode)

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
    def return_from_submenu(cls, title_id, exp_submenu_text, loop_count=5):
        """
        Return from submenus of an app

        param: title_id - Android id of the page title.
        param: exp_submenu_text - Expected page title(str or list of strings).
        param: loop_count - Number of times to press back button.
        """
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
