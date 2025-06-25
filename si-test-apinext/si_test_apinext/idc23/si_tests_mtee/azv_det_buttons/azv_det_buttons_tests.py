import logging
import time

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT
from mtee.testing.tools import metadata, retry_on_except
from mtee.testing.tools import assert_true
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.common.pages.base_page import BasePage
from si_test_apinext.idc23.pages.connectivity_page import ConnectivityPage as Connect
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.media_page import MediaPage as Media
from si_test_apinext.idc23.pages.navigation_page import NavigationPage as Navi
from si_test_apinext.idc23.traas.bluetooth.helpers.bluetooth_utils import BluetoothUtils
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.global_steps import GlobalSteps
from unittest import skipIf

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name
target = TargetShare().target


@metadata(testsuite=["SI"])
class TestAZVDETButtons:
    mtee_log_plugin = True

    @classmethod
    def setup_class(cls):
        # TestBase is a singleton class to re-use appium driver and target vars
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.bluetooth_utils = BluetoothUtils(cls.test)

        if not Launcher.validate_launcher():
            logger.info("Failed to validate launcher. Restarting target to try to recover Launcher")
            # Try to recover Launcher
            cls.test.teardown_base_class()
            cls.test.apinext_target.restart()
            cls.test.setup_base_class()
        utils.start_recording(cls.test)
        Media.reconnect_media()

    @classmethod
    def teardown_class(cls):
        Launcher.go_to_home()
        utils.stop_recording(cls.test, "test_azv_det_buttons")
        cls.test.quit_driver()

    @utils.gather_info_on_fail
    @retry_on_except()
    def test_001_check_azv_touch_media_button(self):
        """
        Check AZV touch MEDIA button

        *Background information*
        This test validates the functionality of MEDIA and Back Buttons

        *Steps*
        1. From Home click MEDIA button
        2. Validate MEDIA app is open
        3. Click BACK button
        4. Validate target is HOME
        """
        Launcher.go_to_home()
        GlobalSteps.inject_custom_vhal_input(self.test.apinext_target, Media.media_vhal_event_keycode)
        self.test.wb.until(
            ec.presence_of_element_located(Media.MEDIA_BAR_ID),
            message=f"Unable to find media elemenst:'{Media.MEDIA_BAR_ID.selector}' "
            f"after click on AZV Media touch button",
        )
        GlobalSteps.inject_key_input(self.test.apinext_target, Launcher.back_keycode)
        Launcher.validate_home_screen()

    @utils.gather_info_on_fail
    @retry_on_except()
    def test_002_check_azv_connectivity_button(self):
        """
        Check AZV touch PHONE (connectivity) button

        *Background information*
        This test validates the functionality of PHONE and Back Buttons

        *Steps*
        1. From Home click PHONE button
        2. Validate connectivity app is open
        3. Click BACK button
        4. Validate target is HOME
        """
        Connect.open_connectivity()
        Launcher.go_to_home()
        GlobalSteps.inject_custom_vhal_input(self.test.apinext_target, Connect.conn_vhal_event_keycode)
        utils.get_screenshot_and_dump(self.test, self.test.results_dir, "conn_vhal_event_keycode")
        connetivity_app_status = BasePage.check_visibility_of_first_and_second_elements(
            Connect.PAGE_TITLE_ID, Connect.PAGE_TITLE_ID_ML
        )
        assert_true(
            connetivity_app_status,
            "Failed to open connectivity app after telephone button press/release. "
            f"Either element {Connect.PAGE_TITLE_ID} or element "
            f"{Connect.PAGE_TITLE_ID_ML} were expected to be present after telephone operation ",
        )
        GlobalSteps.inject_key_input(self.test.apinext_target, Launcher.back_keycode)
        Launcher.validate_home_screen()

    @skipIf(target.has_capability(TEST_ENVIRONMENT.test_bench.farm), "Navigation cannot be started on test workers")
    @utils.gather_info_on_fail
    @retry_on_except()
    def test_003_check_azv_touch_navigation_button(self):
        """
        Check AZV touch NAV (navigation) button

        *Background information*
        This test validates the functionality of NAV and Back Buttons

        *Steps*
        1. From Home click NAV button
        2. Validate navigation app is open
        3. Click BACK button
        4. Validate target is HOME
        """
        Launcher.go_to_home()
        GlobalSteps.inject_custom_vhal_input(self.test.apinext_target, Navi.nav_vhal_event_keycode)
        navi_elem = Navi.NAV_MAIN_MAP_ID
        self.test.wb.until(
            ec.visibility_of_element_located(navi_elem),
            message=f"Unable to find navigation element:'{navi_elem.selector}' after click on AZV NAV touch button",
        )
        GlobalSteps.inject_key_input(self.test.apinext_target, Launcher.back_keycode)
        Launcher.validate_home_screen()

    @skipIf(target.has_capability(TEST_ENVIRONMENT.test_bench.farm), "Navigation cannot be started on test workers")
    @utils.gather_info_on_fail
    @retry_on_except()
    def test_004_check_azv_touch_buttons_transitions(self):
        """
        Check AZV touch buttons transitions between them

        *Background information*
        This test validates the functionality of BACK, MEDIA, PHONE, NAV Buttons and the transitions between these apps
        Starting from one of the apps, transition to another app, click back button and transition to the previous one

        *Steps*
        1 For each app (MEDIA, PHONE, NAV):
            2.1 Click on app Button
            2.2 Validate app is open
            2.3 For each of the remaining apps:
                3.1 Click on app button
                3.2 Validate app is open
                3.3 Click BACK button
                3.4 Validate previous app is open
        """
        Launcher.go_to_home()
        base_azv_apps_list = [
            (Media.MEDIA_BAR_ID, Media.media_vhal_event_keycode),
            (Navi.NAV_MAIN_MAP_ID, Navi.nav_vhal_event_keycode),
            (Connect.PAGE_TITLE_ID, Connect.conn_vhal_event_keycode),
        ]
        secondary_azv_list = base_azv_apps_list[:-1]
        # If TEL is started then transitions will work only device is connected. Refer ABPI-338043 for details
        for wait_elem, app_vhal_code in secondary_azv_list:
            GlobalSteps.inject_custom_vhal_input(self.test.apinext_target, app_vhal_code)
            self.test.wb.until(
                ec.visibility_of_element_located(wait_elem),
                message=f"Unable to find element:'{wait_elem.selector}' after click on AZV touch button",
            )
            remaining_apps = base_azv_apps_list[:]
            remaining_apps.remove((wait_elem, app_vhal_code))
            for rem_wait_elem, rem_vhal_code in remaining_apps:
                GlobalSteps.inject_custom_vhal_input(self.test.apinext_target, rem_vhal_code)
                self.test.wb.until(
                    ec.visibility_of_element_located(rem_wait_elem),
                    message=f"Unable to find element:'{rem_wait_elem.selector}'" "after click on AZV touch button",
                )
                result = GlobalSteps.inject_custom_vhal_w_retry(
                    self.test.apinext_target, wait_elem, Launcher.back_keycode, retry_num=5
                )
                assert result > 0, f"Failed to press button and get elem, total number of iterations: {result}"
                self.test.wb.until(
                    ec.presence_of_element_located(wait_elem),
                    message=f"Unable to find element:'{wait_elem.selector}', while trying to press back"
                    f"from '{rem_wait_elem}' to {wait_elem} having result: '{result}'",
                )

    @skipIf(target.has_capability(TEST_ENVIRONMENT.test_bench.farm), "Navigation cannot be started on test workers")
    @utils.gather_info_on_fail
    @retry_on_except()
    def test_005_check_azv_touch_buttons_three_transitions(self):
        """
        Check AZV touch buttons three transitions between them

        *Background information*
        This test validates the functionality of BACK, MEDIA, PHONE, NAV Buttons and the transitions between these apps
        Starting from one of the apps, transition to another app, then transition to a third app, click BACK button,
         transition to the previous one, click BACK button, transition to the initial app
        Currently it's not possible to return to CONN (TEL) app, so the only way to do this test is to have CONN app
         as the third app

        *Steps*
        1 From HOME click MEDIA button
        2 From MEDIA click NAVI button
        3 From NAVI click CONN button
        4 Click BACK button, from CONN to NAVI
        5 Click BACK button, from NAVI to MEDIA
        6 Click BACK button, from MEDIA to HOME
        """
        Launcher.go_to_home()
        GlobalSteps.inject_custom_vhal_input(self.test.apinext_target, Media.media_vhal_event_keycode)
        time.sleep(1)
        self.test.wb.until(
            ec.visibility_of_element_located(Media.MEDIA_BAR_ID),
            message="Unable to find element:{} after click on AZV touch button".format(Media.MEDIA_BAR_ID.selector),
        )
        GlobalSteps.inject_custom_vhal_input(self.test.apinext_target, Navi.nav_vhal_event_keycode)
        time.sleep(1)
        self.test.wb.until(
            ec.visibility_of_element_located(Navi.NAV_MAIN_MAP_ID),
            message=f"Unable to find element:'{Navi.NAV_MAIN_MAP_ID.selector}' after click on AZV touch button",
        )
        GlobalSteps.inject_custom_vhal_input(self.test.apinext_target, Connect.conn_vhal_event_keycode)
        time.sleep(1)
        self.test.wb.until(
            ec.visibility_of_element_located(Connect.PAGE_TITLE_ID),
            message=f"Unable to find element:'{Connect.PAGE_TITLE_ID.selector}' after click on AZV touch button",
        )
        GlobalSteps.inject_custom_vhal_w_retry(
            self.test.apinext_target, Navi.NAV_MAIN_MAP_ID, Launcher.back_keycode, retry_num=5
        )
        self.test.wb.until(
            ec.visibility_of_element_located(Navi.NAV_MAIN_MAP_ID),
            message=f"Unable to find element:'{Navi.NAV_MAIN_MAP_ID.selector}' after click on AZV touch button",
        )
        GlobalSteps.inject_custom_vhal_w_retry(
            self.test.apinext_target, Media.MEDIA_BAR_ID, Launcher.back_keycode, retry_num=5
        )
        self.test.wb.until(
            ec.visibility_of_element_located(Media.MEDIA_BAR_ID),
            message="Unable to find element:{} after click on AZV touch button".format(Media.MEDIA_BAR_ID.selector),
        )
        GlobalSteps.inject_key_input(self.test.apinext_target, Launcher.back_keycode, count=5)
        Launcher.validate_home_screen()
