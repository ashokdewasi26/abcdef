import logging
import random
import time
from typing import Optional

from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.common.pages.base_page import BasePage, Element
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.global_steps import GlobalSteps

logger = logging.getLogger(__name__)


class NavigationPage(BasePage):

    # Navigation App
    PACKAGE_NAME = "com.bmwgroup.idnext.navigation"
    NAV_RESOURCE_ID_PREFIX = PACKAGE_NAME + ":id/"
    PACKAGE_ACTIVITY = ".map.MainActivity"

    NAV_MAIN_MAP_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "action_bar_root")
    STOP_GUIDANCE_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "stop_guidance_button")
    CAMERA_BUTTON_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "camera_button")
    CENTER_VEHICLE_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "center_location_button")
    SEARCH_DESTINATION_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "search_destination_view")
    QUICK_SEARCH_TOGGLE_ARROW_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "panel_guidance_inactive_toggle_arrow")
    TOGGLE_ARROW_ICON_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "panel_toggle_arrow_icon_background")
    MY_DESTINATIONS_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "button_panel_guidance_inactive_my_destinations")
    MAIN_MAP_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "map_view")
    MAP_PLAYER_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "map_player")
    SEARCH_BOX_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "search_box")
    SEARCH_RESULT_LIST_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "set_significant_location")
    OK_BUTTON_ID = Element(By.XPATH, "//*[contains(@text, 'OK')]")
    SEARCH_RESULT_CARD_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "quick_search_card")
    START_GUIDANCE_BT_ID = Element(By.XPATH, "//*[@text='Start guidance']")
    START_ROUTE_GUIDANCE_BT_ID = Element(By.XPATH, "//*[@text='Start route guidance']")
    ADD_INT_DEST = Element(By.XPATH, "//*[@text='Add']")
    FIRST_ROUTE_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "select_first_route_button")
    EVENT_LINE_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "event_line_view")
    DYNAMIC_GUIDING_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "dynamic_guiding_label")
    RETRY_SEARCH_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "retry_search_button")
    POI_PAGE_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "panel_guidance_inactive_pager")
    POI_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "button_panel_guidance_inactive_quick_search_1")

    # Ids are different if the guidance is enabled
    ACTIVE_TOGGLE_ARROW = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "panel_guidance_active_toggle_arrow")
    PANEL_SEARCH = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "panel_search_button")
    EDIT_INTERMEDIATES_ROUTES = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "eventlist_edit_intermediates_routes")
    EVENTLIST_VIEW = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "eventlist_recyclerview")
    DELETE_BUTTON = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "action_button")
    FINISH_EDITING = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "eventlist_finish_editing_intermediates_routes")
    ACTIVE_INTERMEDIATE_DEST = Element(
        By.XPATH, "//*[contains(@text, 'Destination') or contains(@text, 'Next intermediate destination')]"
    )

    # Settings Id
    SETTINGS_BUTTON_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "settings_button")
    SETTINGS_AREA_ID = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "map_and_route_settings_list")
    TOGGLE_BUTTON = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "button_icon")
    TOGGLE_OPTIONS = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "settings_list_item_toggle")
    LINEAR_LAYOUT = Element(By.CLASS_NAME, "android.widget.LinearLayout")
    SPOKEN_INSTRUCTIONS_ID = Element(By.XPATH, "//*[@text='Spoken instructions']")
    AUTO_ZOOM_ID = Element(By.XPATH, "//*[@text='Auto zoom']")
    POP_UP_LIST = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "pop_up_list")
    PERSPECTIVE = Element(By.XPATH, "//*[@text='Perspective']")
    DIRECTION_OF_TRAVEL = Element(By.XPATH, "//*[@text='In direction of travel']")
    NORTH_ORIENTED = Element(By.XPATH, "//*[@text='North-oriented']")
    MAP_VIEWS = (PERSPECTIVE, DIRECTION_OF_TRAVEL, NORTH_ORIENTED)
    AVOID_MOTORWAYS = Element(By.XPATH, "//*[@text='Avoid motorways']")
    AVOID_TOLL = Element(By.XPATH, "//*[@text='Avoid toll roads']")
    AVOID_FERRIES = Element(By.XPATH, "//*[@text='Avoid ferries']")
    DEMO_MODE = Element(By.XPATH, "//*[@text='Demo mode']")
    BUILD_VERSION = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "textview_build_information_version")
    BUILD_DATE = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "textview_build_information_date")
    MAP_ATTRIBUTION = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "textview_nav_map_data_attribution")
    MAPBOX_ATTRIBUTION = Element(By.ID, NAV_RESOURCE_ID_PREFIX + "textview_nav_mapbox_attribution")

    PERMISSION_ID = Element(By.ID, "com.android.permissioncontroller:id/car_ui_list_item_title")
    NAV_PERMISSION = "com.bmwgroup.apinext.navigation.BMW_SETTING_LEARNING_NAVIGATION"

    nav_vhal_event_keycode = 1010
    NAV_MAIN_SCREEN_ELEMENTS = (SEARCH_DESTINATION_ID, CAMERA_BUTTON_ID, SETTINGS_BUTTON_ID)

    ROUTE_OPTION_SWIPE = (1060, 593, 1060, 463)

    @classmethod
    def open_nav(cls):
        """
        Open the Navigation option on IDC.
        """
        GlobalSteps.inject_custom_vhal_input(cls.apinext_target, cls.nav_vhal_event_keycode)

    @classmethod
    def go_to_navigation(cls):
        """
        Open maps and check basic preconditions for navigation tests
        """
        cls.open_nav()
        utils.ensure_no_alert_popup(cls.results_dir, cls.driver, cls.apinext_target)
        cls.wait_to_load_maps()
        # Validate navigation screen
        # stop any active route guidance
        cls.stop_route_guidance()
        cls.validate_nav_main_screen()

    @classmethod
    def stop_route_guidance(cls):
        """
        Check if active route guidance is ongoing and stop it if available
        """
        cls.open_nav()
        stop_guidance = cls.driver.find_elements(*cls.STOP_GUIDANCE_ID)
        intermediate_dest = cls.driver.find_elements(*cls.ACTIVE_INTERMEDIATE_DEST)
        if stop_guidance:
            if intermediate_dest:
                cls.remove_intermediate_dest()
            GlobalSteps.click_button_and_expect_elem(cls.wb, stop_guidance[0], cls.SEARCH_DESTINATION_ID)
            utils.take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, "guidance_stopped.png")
        else:
            logger.info(f"Seems like guidance is not active. Unable to find element: {cls.STOP_GUIDANCE_ID.selector} ")

    @classmethod
    def wait_to_load_maps(cls, wait_time=60):
        """
        Wait inside navigation for the maps to be loaded.
        if system has undergone reboot maps loading will take few seconds.

        param: wait_time(int) - Default wait time in seconds for maps to be loaded.
        """
        start_time = time.time()
        deadline = start_time + wait_time
        while time.time() < deadline:
            maps_loading = cls.driver.find_elements(*cls.MAIN_MAP_ID)
            if not maps_loading:
                time.sleep(5)
            else:
                return cls.wb.until(
                    ec.visibility_of_element_located(cls.MAIN_MAP_ID),
                    message=f"Unable to find element:{cls.MAIN_MAP_ID.selector}",
                )
        raise RuntimeError(f"Map's not loaded after waiting for {wait_time}s")

    @classmethod
    def validate_nav_main_screen(cls):
        """
        Validate basic elements are available in navigation screen
        """
        for each_element in cls.NAV_MAIN_SCREEN_ELEMENTS:
            cls.driver.find_element(*each_element)

    @classmethod
    def move_map(
        cls,
        region: Optional[tuple] = None,
        percent: Optional[float] = 1,
        direction: Optional[str] = "",
        count: Optional[int] = 1,
    ):
        """
        Perform swipe action on the maps screen.

        param: region(tuple) - User defined coordinates to perform swipe.
               Performs swipe in random coordinates if not provided
        param: direction(str) - Swipe direction. Mandatory value.
               Acceptable values are: up, down, left and right (case insensitive)
        Param: percent(float) The size of the swipe as a percentage of the swipe area size.
               Valid values must be float numbers in range 0..1, where 1.0 is 100%. Mandatory value.
        param: count(int) - Number of times the swipe action needs to be performed.
        """
        if region:
            left, top, width, height = region
        else:
            left = random.randint(480, 960)
            top = random.randint(240, 480)
            width = random.randint(300, 480)
            height = random.randint(150, 240)
        directions = ("up", "down", "left", "right")
        if direction not in directions:
            direction = random.choice(directions)
        for _ in range(count):
            cls.driver.execute_script(
                "mobile: swipeGesture",
                {
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height,
                    "direction": direction,
                    "percent": percent,
                    "speed": 2500,
                },
            )
            time.sleep(1)

    @classmethod
    def zoom_in_map(cls, region: Optional[tuple] = None, percent: Optional[float] = 1.0, count: Optional[int] = 1):
        """
        Zoom in the maps.

        param: region(tuple) - User defined coordinates in the order left, top and width, height of bounding area
               The (left + width) & (top + height) shouldn't exceed screen resolution
        param: percent(float) - The size of the pinch as a percentage of the pinch area size.
               Valid values must be float numbers in range 0-1, where 1.0 is 100%. Mandatory value.
        param: count(int) - Number of times to perform gesture on the region.
        """
        if region:
            left, top, width, height = region
        else:
            left = random.randint(300, 500)
            top = random.randint(0, 200)
            width = random.randint(700, 1000)
            height = random.randint(300, 420)
        for _ in range(count):
            cls.driver.execute_script(
                "mobile: pinchOpenGesture",
                {"left": left, "top": top, "width": width, "height": height, "percent": percent},
            )
            time.sleep(1)

    @classmethod
    def zoom_out_map(cls, region: Optional[tuple] = None, percent: Optional[float] = 1.0, count: Optional[int] = 1):
        """
        Zoom out the maps.

        param: region(tuple) - User defined coordinates in the order left, top and width, height of bounding area
               The (left + width) & (top + height) shouldn't exceed screen resolution
        param: percent(float) - The size of the pinch as a percentage of the pinch area size.
               Valid values must be float numbers in range 0-1, where 1.0 is 100%. Mandatory value.
        param: count(int) - Number of times to perform gesture on the region.
        """
        if region:
            left, top, width, height = region
        else:

            left = random.randint(200, 300)
            top = random.randint(0, 200)
            width = random.randint(1000, 1500)
            height = random.randint(300, 420)
        for _ in range(count):
            cls.driver.execute_script(
                "mobile: pinchCloseGesture",
                {"left": left, "top": top, "width": width, "height": height, "percent": percent},
            )
            time.sleep(1)

    @classmethod
    def activate_demo_mode(cls, test, hmihelper, test_name):
        """
        Enable demo mode in nav settings.

        param: test - TestBase singleton object
        param: hmihelper - Object of hmihelper utils
        param: test_name - string to be used for screenshots name
        """
        settings_bt = cls.driver.find_element(*cls.SETTINGS_BUTTON_ID)
        GlobalSteps.click_button_and_expect_elem(cls.wb, settings_bt, cls.SETTINGS_AREA_ID)
        cls.driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR, "new UiScrollable(new UiSelector().scrollable(true)).flingToEnd(2)"
        )
        toggle_options = cls.driver.find_elements(*cls.TOGGLE_OPTIONS)
        for each_element in toggle_options:
            found_demo = each_element.find_elements(*cls.DEMO_MODE)
            if found_demo:
                button = each_element.find_element(*cls.TOGGLE_BUTTON)
                hmihelper.ensure_button_status_on(button, f"{test_name}_demo_mode_on")
                break
        else:
            raise RuntimeError("Unable to find Demo mode toggle button")
        GlobalSteps.inject_key_input(test.apinext_target, cls.back_keycode)

    @classmethod
    def search_destination(cls, destination="Augsburg", wait_time=60):
        """
        Search for any destination inside navigation

        param: destination - User entered destination in string
        param: wait_time - Time to wait for the search results to show up.
        """
        event_line = cls.driver.find_elements(*cls.EVENT_LINE_ID)
        if not event_line:
            dest_search = cls.driver.find_element(*cls.SEARCH_DESTINATION_ID)  # No active guidance is running
        else:
            active_toggle_arrow = (
                cls.driver.find_element(*cls.ACTIVE_TOGGLE_ARROW)
                if cls.branch_name == "pu2403"
                else cls.driver.find_element(*cls.TOGGLE_ARROW_ICON_ID)
            )
            dest_search = GlobalSteps.click_button_and_expect_elem(cls.wb, active_toggle_arrow, cls.PANEL_SEARCH)
        search_box_elem = GlobalSteps.click_button_and_expect_elem(cls.wb, dest_search, cls.SEARCH_BOX_ID)
        search_box_elem.send_keys(destination.strip())
        start_time = time.time()
        deadline = start_time + wait_time
        while time.time() < deadline:
            time.sleep(5)
            search_result = cls.driver.find_elements(*cls.SEARCH_RESULT_LIST_ID)
            if search_result:
                break
            retry_search = cls.driver.find_elements(*cls.RETRY_SEARCH_ID)
            if retry_search:
                retry_search[0].click()
        utils.take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, "destination_search.png")

    @classmethod
    def select_route(cls, press_ok=True):
        """
        Select the route from search result list or directly from keyboard input suggestions

        param: press_ok(bool) - Defaults to True. The "OK" button in the on-screen keyboard is pressed
        and search results are displayed. Clicks on the top option on the search results
        list(right of on-screen keyboard) and start guidance if set to false.
        """
        if press_ok:
            ok_button = cls.driver.find_element(*cls.OK_BUTTON_ID)
            search_result = GlobalSteps.click_button_and_expect_elem(cls.wb, ok_button, cls.SEARCH_RESULT_CARD_ID)
            guidance_button = (
                GlobalSteps.click_button_and_expect_elem(cls.wb, search_result, cls.START_ROUTE_GUIDANCE_BT_ID)
                if cls.branch_name == "pu2407"
                else GlobalSteps.click_button_and_expect_elem(cls.wb, search_result, cls.START_GUIDANCE_BT_ID)
            )
            route_button = GlobalSteps.click_button_and_expect_elem(cls.wb, guidance_button, cls.FIRST_ROUTE_ID)
        else:
            search_result = cls.driver.find_elements(*cls.SEARCH_RESULT_LIST_ID)
            while search_result:
                search_result[0].click()
                time.sleep(0.5)
                search_result = cls.driver.find_elements(*cls.SEARCH_RESULT_LIST_ID)
                if not search_result:
                    route_button = cls.check_visibility_of_element(cls.FIRST_ROUTE_ID)
                    break
        if route_button:
            return
        else:
            raise RuntimeError("Unable to find route option to start guidance")

    @classmethod
    def start_guidance(cls):
        """
        Start guidance by selecting the first result available
        """
        utils.take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, "selected_route.png")
        route_button = cls.check_visibility_of_element(cls.FIRST_ROUTE_ID)
        GlobalSteps.click_button_and_expect_elem(cls.wb, route_button, cls.STOP_GUIDANCE_ID)
        cls.check_visibility_of_element(cls.EVENT_LINE_ID)
        utils.take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, "active_guidance.png")

    @classmethod
    def select_poi(cls):
        """
        Open the first Point Of Interest(POI) option in quick search
        """
        poi_page = cls.driver.find_elements(*cls.POI_PAGE_ID)
        if not poi_page:
            quick_search_toggle = cls.driver.find_element(*cls.QUICK_SEARCH_TOGGLE_ARROW_ID)
            GlobalSteps.click_button_and_expect_elem(cls.wb, quick_search_toggle, cls.POI_PAGE_ID)
        poi_button = cls.driver.find_element(*cls.POI_ID)
        search_result = GlobalSteps.click_button_and_expect_elem(cls.wb, poi_button, cls.SEARCH_RESULT_CARD_ID)
        utils.take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, "poi_search_results.png")
        guidance_button = (
            GlobalSteps.click_button_and_expect_elem(cls.wb, search_result, cls.START_ROUTE_GUIDANCE_BT_ID)
            if cls.branch_name == "pu2407"
            else GlobalSteps.click_button_and_expect_elem(cls.wb, search_result, cls.START_GUIDANCE_BT_ID)
        )
        GlobalSteps.click_button_and_expect_elem(cls.wb, guidance_button, cls.FIRST_ROUTE_ID)

    @classmethod
    def add_intermediate_dest(cls, destination="Laim, Munich"):
        """
        Add intermediate destination to already running route guidance
        """
        cls.check_visibility_of_element(cls.STOP_GUIDANCE_ID)
        cls.search_destination(destination=destination)
        ok_button = cls.driver.find_element(*cls.OK_BUTTON_ID)
        search_result = GlobalSteps.click_button_and_expect_elem(cls.wb, ok_button, cls.SEARCH_RESULT_CARD_ID)
        guidance_button = GlobalSteps.click_button_and_expect_elem(cls.wb, search_result, cls.ADD_INT_DEST)
        utils.take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, "alternate_route.png")
        GlobalSteps.click_button_and_expect_elem(cls.wb, guidance_button, cls.STOP_GUIDANCE_ID)
        utils.take_apinext_target_screenshot(
            cls.apinext_target, cls.results_dir, "active_guidance_with_intermediate_dest.png"
        )

    @classmethod
    def remove_intermediate_dest(cls):
        """
        Remove intermediate destination from route guidance
        """
        event_line = cls.driver.find_element(*cls.EVENT_LINE_ID)
        edit_route = GlobalSteps.click_button_and_expect_elem(cls.wb, event_line, cls.EDIT_INTERMEDIATES_ROUTES)
        utils.take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, "edit_route.png")
        GlobalSteps.click_button_and_expect_elem(cls.wb, edit_route, cls.EVENTLIST_VIEW)
        utils.take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, "list_route.png")
        destinations_list = cls.driver.find_elements(*cls.DELETE_BUTTON)
        destinations_list[-1].click()
        time.sleep(0.5)
        utils.take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, "removed_route+list.png")
        finish_editing = cls.driver.find_element(*cls.FINISH_EDITING)
        GlobalSteps.click_button_and_not_expect_elem(cls.wb, finish_editing, cls.ACTIVE_INTERMEDIATE_DEST)
        utils.take_apinext_target_screenshot(cls.apinext_target, cls.results_dir, "removed_intermediate_dest.png")

    @classmethod
    def toggle_nav_settings(cls, hmihelper, test_name, option_id):
        """
        Toggle the navigation hmi button settings.

        :param hmihelper: Object of hmihelper utils.
        :param test_name: String to be used for screenshots name.
        :param option_id: Element id to be found in the settings.
        """
        settings_area = cls.driver.find_element(*cls.SETTINGS_AREA_ID)
        navi_settings = settings_area.find_elements(*cls.LINEAR_LAYOUT)
        for each_setting in navi_settings:
            found_setting = each_setting.find_elements(*option_id)
            time.sleep(2)
            if found_setting:
                button = each_setting.find_element(*cls.TOGGLE_BUTTON)
                # Finding current button status
                status = hmihelper.find_current_button_status(
                    button, f"{test_name}_start", image_pattern="button_*.png"
                )
                logger.debug(f"Button status of {test_name}: {status}")
                hmihelper.click_and_validate_button_status(button, status, f"{test_name}_final_state")
                break
        else:
            raise RuntimeError(f"Unable to find expected option for {test_name}")

    @classmethod
    def quick_search_toggle(cls):
        """
        Click on Toggle arrow button option
        """
        quick_search_toggle = (
            cls.test.driver.find_element(*cls.QUICK_SEARCH_TOGGLE_ARROW_ID)
            if cls.branch_name == "pu2403"
            else cls.test.driver.find_element(*cls.TOGGLE_ARROW_ICON_ID)
        )
        GlobalSteps.click_button_and_not_expect_elem(cls.test.wb, quick_search_toggle, cls.MY_DESTINATIONS_ID)
