import logging
import os
import time
from unittest import skip

from mtee.testing.tools import metadata
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.mini.pages.connectivity_page import ConnectivityPage as Connect
from si_test_apinext.mini.pages.deskclock_page import DeskclockPage as Deskclock
from si_test_apinext.mini.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.mini.pages.media_page import MediaPage as Media
from si_test_apinext.mini.pages.navigation_page import NavigationPage as Navi
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.global_steps import GlobalSteps
from si_test_apinext.util.mtee_utils import MteeUtils
from si_test_apinext.util.screenshot_utils import capture_screenshot

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


@metadata(testsuite=["SI"])
class TestLauncher:

    mtee_log_plugin = True

    @classmethod
    def setup_class(cls):
        # TestBase is a singleton class to re-use appium driver and target vars
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.mtee_util = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        cls.mtee_util.change_language("en_GB")

        if not Launcher.validate_launcher():
            logger.info("Failed to validate launcher. Restarting target to try to recover Launcher")
            # Try to recover Launcher
            cls.test.teardown_base_class()
            cls.test.apinext_target.restart()
            cls.test.setup_base_class()
        Launcher.turn_on_bluetooth()

    @classmethod
    def teardown_class(cls):
        cls.test.quit_driver()

    def _check_widgets_and_move(self, expected_widgets, from_widget, to_widget, new_widget):
        Launcher.assert_shown_ordered_widgets(expected_widgets)
        GlobalSteps.swipe_from_to(self.test.driver, from_widget, to_widget)
        next_id = new_widget.get_attribute("resource-id")
        self.test.wb.until(ec.presence_of_element_located((By.ID, next_id)), f"Unable to find {next_id} after swipe")

    @utils.gather_info_on_fail
    def test_000_check_launcher_available_and_capture_snapshot(self):
        """

        Check launcher is available and capture a screenshot 01

        *Background information*

        In this test we expect the launcher is available by checking the content and capture a screenshot as well.
        This test in named '01' because the Launcher availability should be validated on the startup of the target,
        so you want this test to be the first to run, to avoid a new restart of the target

        *Steps*
        1. Validate through adb the BMW Launcher activity is running
        2. Validate through UI the BMW launcher is present
        3. Take screenshot

        """
        try:
            assert (
                Launcher.validate_launcher()
            ), "Expected activity com.bmwgroup.idnext.launcher/.MainActivity to be active"
            self.test.wb.until(
                ec.presence_of_element_located(Launcher.MINI_HOME_PAGER_ID),
                "Error while validating Menu Bar presence",
            )
            Launcher.wait_to_check_visible_element(Launcher.BACKGROUND_OUTER_CIRCLE_ID)
            self.test.driver.save_screenshot("launcher_available_screenshot.png")
        except Exception:
            self.test.apinext_target.take_screenshot("launcher_unavailable_screenshot.png")
            raise

    @skip("Test is skipped due to widgets funcionallity not fully working")
    @utils.gather_info_on_fail
    def test_001_check_main_menu_bar_contents_on_bmw_launcher(self):
        """
        Check Main Menu bar contents on BMW Launcher

        *Background information*

        In this test case we expect that the content on main menu bar of BMW launcher should be Menu, Media,
        Telephony,
        and Navigation. These buttons should be clickable and open the respective functionality.

        This test case validates the following set of requirements:

        IDC22PM-1107 :
        * ABPI-8267 (The Main Menu Bar on the BMW launcher It hosts the menu (previously "all apps"), media,
         telephony,
        navigation buttons)

        *Steps*
        1. Validate that Main Menu Bar on BMW launcher has the following buttons:
        - Menu (MENU)
        - Media (MEDIA)
        - Telephony (TEL)
        - Navigation (NAV)
        2. For each button:
        - Click button
        - Validate that opened button functionality
        - Go to Home
        """
        Launcher.go_to_home()
        menu_button = self.test.driver.find_element(*Launcher.ALL_APPS_BUTTON_ID)
        GlobalSteps.click_button_and_expect_elem(self.test.wb, menu_button, Launcher.ALL_APPS_SEARCH_LABEL_ID)
        Launcher.go_to_home()

        media_button = self.test.driver.find_element(*Launcher.MEDIA_BUTTON_ID)
        GlobalSteps.click_button_and_expect_elem(self.test.wb, media_button, Media.get_media_element_id())
        Launcher.go_to_home()

        tel_button = self.test.driver.find_element(*Launcher.TEL_BUTTON_ID)
        GlobalSteps.click_button_and_expect_elem(self.test.wb, tel_button, Connect.CONN_DISC_FRAG_ID)
        Launcher.go_to_home()

        nav_button = self.test.driver.find_element(*Launcher.NAV_BUTTON_ID)
        GlobalSteps.click_button_and_expect_elem(self.test.wb, nav_button, Navi.NAV_MAIN_MAP_ID)
        Launcher.go_to_home()

    @skip("Test is skipped due to widgets funcionallity not fully working")
    @utils.gather_info_on_fail
    def test_002_check_if_swipe_flick_moves_widgets(self):
        """

        Check if swipe or flick moves widgets

        *Background information*

        In this test case we expect that we can swipe or flick through the widgets and they will
        stay correctly aligned.

        This test case validates the following set of requirements:

        IDC22PM-1107 :
        * ABPI-5540 (Swipe/flick left/right moves widgets and aligns it nicely)

        *Steps*
        1. Validate static widgets(Radio and Telephone) are displayed
        2. Create at least 3 widgets by pressing keyevent A and selecting a new widget to add.
        3. Go to Home
        4. Swipe right until reaching static widgets(Radio and Telephone), widgets should maintain
            a descending order by creation date from right to left. Where items on the right are younger
            than the left
        5. Swipe left until reaching last created widget, widgets should maintain a ascending order by
            creation date from right to left. Where items on the right are younger than the left
        6. Flick right
        7. Validate that widgets being shown are a subset of the created on Step 4 and 5.
        8. Validate that shown widgets are aligned by creation order.
        9. Flick left
        10. Validate that Media and Telephone widgets are being shown as well as the first created Widget on Step #2
        11. Delete all widgets by pressing D
        12. Add static widgets (Radio and Telephone)

        """
        try:
            widgets = []

            widgets.append(
                self.test.wb.until(
                    ec.presence_of_element_located(Launcher.MEDIA_WIDGET_ID),
                    message=f"Unable to find {Launcher.MEDIA_WIDGET_ID.selector}",
                )
            )
            widgets.append(
                self.test.wb.until(
                    ec.presence_of_element_located(Launcher.TEL_WIDGET_ID),
                    message=f"Unable to find {Launcher.TEL_WIDGET_ID.selector}",
                )
            )

            widgets.append(Launcher.add_new_widget_to_launcher("Digital clock", Deskclock.DIGITAL_CLOCK_WIDGET_ID))

            analog_clock = "Analog clock" if os.getenv("PRODUCT_TYPE") == "mvp_mgupp" else "Analogue clock"
            widgets.append(Launcher.add_new_widget_to_launcher(analog_clock, Deskclock.ANALOG_CLOCK_WIDGET_ID))

            widgets.append(Launcher.add_new_widget_to_launcher("Calendar", Launcher.EVENT_LIST_ID))

            for index in range(2):
                expected_widgets = widgets[-3 - index : -index] if index else widgets[-3:]  # noqa: E203
                self._check_widgets_and_move(
                    expected_widgets,
                    widgets[-2 - index],
                    widgets[-1 - index],
                    widgets[-3 - index],
                )

            for index in range(2):
                expected_widgets = widgets[index : index + 3]  # noqa: E203
                self._check_widgets_and_move(
                    expected_widgets,
                    widgets[index + 1],
                    widgets[index],
                    widgets[index + 2],
                )

            self._check_widgets_and_move(widgets[-3:], widgets[-3], widgets[-1], widgets[0])
            Launcher.assert_shown_ordered_widgets(widgets[:3])

            self._check_widgets_and_move(widgets[:3], widgets[2], widgets[0], widgets[4])
            Launcher.assert_shown_ordered_widgets(widgets[2:])

        finally:
            Launcher.go_to_home()
            Launcher.delete_widgets()
            Launcher.add_new_widget_to_launcher("Media/Radio", Launcher.MEDIA_WIDGET_ID)
            Launcher.add_new_widget_to_launcher("Telephone", Launcher.TEL_WIDGET_ID)

    @skip("Test is skipped due to widgets funcionallity not fully working")
    @utils.gather_info_on_fail
    def test_003_check_bmw_launcher_widgets_are_clickable(self):
        """

        Check if widgets from BMW Launcher are clickable

        *Background information*

        In this test case we check if we can click on Widgets from BMW Launcher.

        This test case validates the following set of requirements:
        IDC22PM-1107 :
        * ABPI-5540 (Pushing ZBE opens app for the currently focused widget)

        *Steps*

        1. Validate static widgets(Radio and Telephone) are displayed
        2. Click on Radio widget
        3. Validate that Radio widget is open
        4. Click on Telephony widget
        5. Validate that Telephony widget is open
        6. Go to Home
        7. Create a new Widget
        8. Click on created widget
        9. Validate that created widget is open

        """
        try:
            media_widget = self.test.wb.until(ec.presence_of_element_located(Launcher.MEDIA_WIDGET_ID))
            tel_widget = self.test.wb.until(ec.presence_of_element_located(Launcher.TEL_WIDGET_ID))

            GlobalSteps.click_button_and_expect_elem(self.test.wb, media_widget, Media.get_media_element_id())
            Launcher.go_to_home()

            GlobalSteps.click_button_and_expect_elem(self.test.wb, tel_widget, Connect.CONN_DISC_FRAG_ID)
            Launcher.go_to_home()

        finally:
            Launcher.go_to_home()
            Launcher.delete_widgets()
            Launcher.add_new_widget_to_launcher("Media/Radio", Launcher.MEDIA_WIDGET_ID)
            Launcher.add_new_widget_to_launcher("Telephone", Launcher.TEL_WIDGET_ID)

    @utils.gather_info_on_fail
    def test_004_check_all_apps_menu_search_for_an_available_app(self):
        """
        Check All Apps Menu search for an available app

        *Background information*

        In this test case we expect that we can go to Menu and search existing app.

        Precondition: _App_ should be available on Menu

        This test case validates the following set of requirements:

        IDC22PM-1107 :
        * ABPI-11942 *Launcher All Apps Menu: Search functionality*
        * ABPI-18835 *Launcher: All Apps Menu: Search functionality for settings contents*

        *Steps*
        1. Go to Menu
        2. Validate that Menu is open
        3. Click on Search Bar
        4. Validate that Search functionality is ready
        5. Type an available app, e.g: Connected Drive Store
        6. On Results list should only be "Connected Drive Store" app

        """
        search_app = "Store"
        edit_text = Launcher.open_all_apps_search_from_home()

        displayed_apps = GlobalSteps.input_text_and_get_elements(
            self.test.driver, edit_text, search_app, Launcher.SEARCH_RESULT_APP_ITEM_ID
        )

        assert len(displayed_apps) == 1, f"Expected 1 result, received {len(displayed_apps)}"

        app_text = displayed_apps[0].get_attribute("text")

        assert search_app in app_text, f"Expected {search_app} as result, instead received {app_text}"

    @utils.gather_info_on_fail
    def test_005_check_all_apps_menu_search_for_an_unavailable_app(self):
        """
        Check All Apps Menu search for an unavailable app

        *Background information*

        In this test case we expect that we can go to Menu and search unavailable app.

        Precondition: _App_ should not be available on Menu

        This test case verifies the following set of requirements:

        IDC22PM-1107 :
        * ABPI-11942 *Launcher All Apps Menu: Search functionality*
        * ABPI-18835 *Launcher: All Apps Menu: Search functionality for settings contents*

        *Steps*
        1. Go to Menu
        2. Validate that Menu is open
        3. Click on Search Bar
        4. Validate that Search functionality is ready
        5. Type an unavailable app name, e.g: Unavailable App
        6. On Results list should be empty

        """
        edit_text = Launcher.open_all_apps_search_from_home()

        displayed_apps = GlobalSteps.input_text_and_get_elements(
            self.test.driver, edit_text, "Unavailable App", Launcher.SEARCH_RESULT_APP_ITEM_ID
        )

        assert not displayed_apps, f"Expected 0 results, received {len(displayed_apps)}"

    @utils.gather_info_on_fail
    def test_006_check_all_apps_menu_search_for_relevant_matches(self):
        """
        Check All Apps Menu search for relevant matches

        *Background information*

        In this test case we expect that we can go to Menu and search for relevant apps given a text input.

        Precondition: Relevant apps should have a matching name subset

        This test case verifies the following set of requirements:

        IDC22PM-1107:
        * ABPI-11942 *Launcher All Apps Menu: Search functionality*
        * ABPI-18835 *Launcher: All Apps Menu: Search functionality for settings contents*

        *Steps*
        1. Go to Menu
        2. Validate that Menu is open
        3. Click on Search Bar
        4. Validate that Search functionality is ready
        5. Type an available app, e.g: vehicle
        6. On Results list should be all apps that have vehicle on their names
            Expecting apps: Live Vehicle and Vehicle Status

        """
        search_text = "mini"
        edit_text = Launcher.open_all_apps_search_from_home()
        edit_text.send_keys(search_text)
        # Waiting for the searched text to appear.
        time.sleep(1)
        capture_screenshot(test=self.test, test_name="test_006_check_all_apps_menu_search_list")
        results_dict = {}

        prev_last_result_text = None

        window_size = self.test.driver.get_window_size()

        starty = window_size.get("height") * 0.8
        endy = window_size.get("height") * 0.20
        startx = window_size.get("width") * 0.8

        while True:
            results_text_elem = self.test.driver.find_elements(*Launcher.SEARCH_RESULT_APP_ITEM_ID)

            if results_text_elem[-1].get_attribute("text") == prev_last_result_text:
                break

            for elem in results_text_elem:
                elem_text = elem.get_attribute("text").lower()
                assert search_text in elem_text, f"Expected to find {search_text} in element text, found {elem_text}"
                results_dict[elem_text] = elem

            self.test.driver.swipe(startx, starty, startx, endy)

            prev_last_result_text = results_text_elem[-1].get_attribute("text")

        assert len(results_dict) >= 2, f"Expected at least 2 matching apps, received {len(results_dict)}"

    @utils.gather_info_on_fail
    def test_007_check_go_back_to_home(self):
        """
        Check that after going to menu we can go back to home

        *Background information*

        In this test case we expect that we can go back to Home menu by clicking on the back arrow,
        while at the All Apps Menu (MENU) and the Telephony Menu (TEL).

        Precondition: *App* should be available on Menu

        This test case validates the following set of requirements:

        IDC22PM-1107:
        * ABPI-8583 *Basic All Apps Activity*

        *Steps*
        1. Go to MENU
        2. Validate that MENU is open
        3. Click on Search Bar
        4. Validate that Search functionality is ready
        5. Click on left arrow to go back to MENU
        6. Click on left arrow to go back to Home
        7. Go to Telephony Menu (TEL)
        8. Validate that TEL is open
        9. Click on left arrow to go back to Home
        10. Validate that Home is open

        """
        Launcher.open_all_apps_search_from_home()
        hide_keyboard_button = self.test.driver.find_element(*Launcher.HIDE_KEYBOARD)
        back_arrow_button = GlobalSteps.click_button_and_expect_elem(
            self.test.wb, hide_keyboard_button, Launcher.BACK_ARROW_BUTTON_ID
        )
        GlobalSteps.click_button_and_expect_elem(self.test.wb, back_arrow_button, Launcher.RECYCLER_APPS_ID)
        back_arrow_button = self.test.driver.find_element(*Launcher.BACK_ARROW_BUTTON_ID)
        GlobalSteps.click_button_and_expect_elem(self.test.wb, back_arrow_button, Launcher.MINI_HOME_PAGER_ID)
        # tel button
        tel_button = self.test.driver.find_element(*Connect.OVERLAY_CONN_BUTTON)
        GlobalSteps.click_button_and_expect_elem(self.test.wb, tel_button, Connect.CONN_DISC_FRAG_ID, 2)
        conn_back_button = self.test.driver.find_element(*Connect.CONN_BACK_ARROW)
        GlobalSteps.click_button_and_expect_elem(self.test.wb, conn_back_button, Launcher.MINI_HOME_PAGER_ID)
