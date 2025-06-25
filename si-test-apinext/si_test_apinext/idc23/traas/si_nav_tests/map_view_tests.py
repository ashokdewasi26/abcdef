# Copyright (C) 2022. BMW Car IT. All rights reserved.
import logging

from mtee.testing.test_environment import require_environment, require_environment_setup, TEST_ENVIRONMENT as TE
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.navigation_page import NavigationPage as Navi
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.hmi_helper import HMIhelper
from si_test_apinext.util.mtee_utils import MteeUtils
from si_test_apinext.util.screenshot_utils import capture_screenshot

logger = logging.getLogger(__name__)
REQUIREMENTS = TE.target_type.hu, TE.test_bench.rack


@require_environment(*REQUIREMENTS)  # Follow-up ticket: ABPI-259855
class TestMapView:
    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.mtee_util = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        cls.hmihelper = HMIhelper(cls.test)
        Launcher.go_to_home()
        utils.start_recording(cls.test)

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def teardown_class(cls):
        Launcher.go_to_home()
        utils.stop_recording(cls.test, "TestMapView")
        cls.test.quit_driver()

    @utils.gather_info_on_fail
    def test_01_check_map_view(self):
        """
        Check if map view changes inside navigation

        Steps:
        1. Go inside navigation.
        2. Validate maps are loaded correctly.
        3. Swipe the maps in random direction.
        4. Zoom in the maps at random region.
        5. Zoom out the maps at random region.
        6. Expect "Center Vehicle" button to appear above actions.

        Traceability: ABPI-36578
        """
        Navi.go_to_navigation()
        capture_screenshot(test=self.test, test_name="test_01_check_map_view_01")
        Navi.quick_search_toggle
        Navi.move_map(count=3)
        capture_screenshot(test=self.test, test_name="test_01_check_map_view_02")
        Navi.zoom_in_map(count=2)
        capture_screenshot(test=self.test, test_name="test_01_check_map_view_03")
        Navi.zoom_out_map(count=3)
        capture_screenshot(test=self.test, test_name="test_01_check_map_view_04")
        center_vehicle = self.test.wb.until(
            ec.visibility_of_element_located(Navi.CENTER_VEHICLE_ID),
            message=f"Expected '{Navi.CENTER_VEHICLE_ID.selector}'after swiping and changing default zoom of maps",
        )
        self.hmihelper.click_and_capture(center_vehicle, "test_01_check_map_view_05", sleep_time=3)
