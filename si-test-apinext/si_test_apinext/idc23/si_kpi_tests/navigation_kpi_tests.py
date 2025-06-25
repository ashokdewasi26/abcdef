# Copyright (C) 2023. BMW Car IT. All rights reserved.
import logging

from mtee.testing.test_environment import require_environment, require_environment_setup
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import assert_greater_equal
from si_test_apinext.idc23 import HMI_BUTTONS_REF_IMG_PATH
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.navigation_page import NavigationPage as Navi
from si_test_apinext.idc23.si_kpi_tests.kpi_marker import KpiMarker as Marker
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.hmi_helper import HMIhelper
from si_test_apinext.util.mtee_utils import MteeUtils
from si_test_apinext.util.kpi_dlt_detector import KPIDltDetector

logger = logging.getLogger(__name__)

REQUIREMENTS = TE.target_type.hu, TE.test_bench.rack

SHORT_ROUTE_SECONDS_KPI = 2.4
MEDIUM_ROUTE_SECONDS_KPI = 4
LONG_ROUTE_SECONDS_KPI = 6


@require_environment(*REQUIREMENTS)
class TestNavigationKpi:
    hmi_buttons_ref_img_path = HMI_BUTTONS_REF_IMG_PATH

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.mtee_util = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        cls.hmihelper = HMIhelper(cls.test, cls.hmi_buttons_ref_img_path)
        cls.mtee_util.change_language("en_GB")
        utils.start_recording(cls.test)
        utils.pop_up_check(cls.test)
        utils.ensure_no_alert_popup(cls.test.results_dir, cls.test.driver, cls.test.apinext_target)
        Navi.go_to_navigation()
        Navi.activate_demo_mode(cls.test, cls.hmihelper, "TestNavigationKpi")

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def teardown_class(cls):
        Launcher.go_to_home()
        utils.stop_recording(cls.test, "TestNavigationKpi")
        cls.test.quit_driver()

    def setup(self):
        Launcher.go_to_home()
        Navi.go_to_navigation()

    def teardown(self):
        Navi.stop_route_guidance()

    def calculate_guidance_kpi(self, accepted_duration):
        """
        Calculate the kpi time taken to calculate the route.

        :param accepted_duration: Accepted KPI duration in seconds.
        """
        with KPIDltDetector(Marker.ROUTE_CALCULATION_START, Marker.ROUTE_CALCULATION_END) as kpi_monitor:
            Navi.select_route(press_ok=False)
            Navi.start_guidance()
            timestamp_of_begin = kpi_monitor.get_timestamp_for_event_start()
            timestamp_of_end = kpi_monitor.get_timestamp_for_event_end()
            assert_greater_equal(timestamp_of_end, timestamp_of_begin)
            actual_duration = timestamp_of_end - timestamp_of_begin
            logger.info(f"payload is found after: {actual_duration}s")
            assert_greater_equal(
                accepted_duration,
                actual_duration,
                f"Route calculation takes {actual_duration} seconds, but the expected time is {accepted_duration}",
            )

    @utils.gather_info_on_fail
    def test_01_short_route_guidance_kpi(self):
        """
        test_01_short_route_guidance_kpi
        Accepted value: <= 2.4s.

        *Steps*
        1. Open Navigation
        2. Enter a destination less than 10km.
        3. Check navigation is able to load the route results and guidance is started.
        4. Calculate the time difference between the start and end payload.
        5. Check if the time difference between the payload is <= Accepted value.
        """
        Navi.search_destination(destination="Karlsplatz, Munich")
        self.calculate_guidance_kpi(SHORT_ROUTE_SECONDS_KPI)

    @utils.gather_info_on_fail
    def test_02_medium_route_guidance_kpi(self):
        """
        test_02_medium_route_guidance_kpi
        Accepted value: <= 4s.

        *Steps*
        1. Open Navigation
        2. Enter a destination less than 75km.
        3. Check navigation is able to load the route results and guidance is started.
        4. Calculate the time difference between the start and end payload.
        5. Check if the time difference between the payload is <= Accepted value.
        """
        Navi.search_destination(destination="Augsburg")
        self.calculate_guidance_kpi(MEDIUM_ROUTE_SECONDS_KPI)

    @utils.gather_info_on_fail
    def test_03_long_route_guidance_kpi(self):
        """
        test_03_long_route_guidance_kpi
        Accepted value: <= 6s.

        *Steps
        1. Open Navigation
        2. Enter a destination less than 500km.
        3. Check navigation is able to load the route results and guidance is started.
        4. Calculate the time difference between the start and end payload.
        5. Check if the time difference between the payload is <= Accepted value.
        """
        Navi.search_destination(destination="Leipzig")
        self.calculate_guidance_kpi(LONG_ROUTE_SECONDS_KPI)
