# Copyright (C) 2023. BMW Car IT. All rights reserved.
import logging

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import assert_greater_equal
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.si_kpi_tests.kpi_marker import KpiMarker as Marker
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.kpi_dlt_detector import KPIDltDetector

logger = logging.getLogger(__name__)
target = TargetShare().target

ACCEPTED_TEST_KPI = 0.075
STEERING_LAYOUT = "LHD"
if target.has_capability(TE.test_bench.rack):  # All testfarm workers have a static FA file which has LHD layout
    vehicle_order_path = target.options.vehicle_order
    STEERING_LAYOUT = Launcher.get_type_key(vehicle_order_path)
logger.info(f"steering_layout of launcher is: {STEERING_LAYOUT}")


class TestTouchKpi:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.tap_coords = Launcher.LHD_COORDS if STEERING_LAYOUT == "LHD" else Launcher.RHD_COORDS
        utils.start_recording(cls.test)
        Launcher.go_to_home()
        utils.pop_up_check(cls.test)
        utils.ensure_no_alert_popup(cls.test.results_dir, cls.test.driver, cls.test.apinext_target)

    @classmethod
    def teardown_class(cls):
        Launcher.go_to_home()
        utils.stop_recording(cls.test, "TestTouchKpi")
        cls.test.quit_driver()

    @utils.gather_info_on_fail
    def test_01_touch_latency_kpi(self):
        """
        Find touch latency of IDC23
        Accepted value: <= 0.075.

        *Steps*
        1. Touch any button on the screen. Here we open Media via Tap event
        2. Calculate the KPI time taken to open media after Tapping on the screen
        3. Check if tap reaction time is <= Accepted value.

        Traceability: ABPI-260521
        """
        Launcher.go_to_home()
        screen_input = self.tap_coords["media"]
        with KPIDltDetector(Marker.TAP_COMMAND, Marker.START_MEDIA_WIDGET) as kpi_monitor:
            self.test.driver.tap([screen_input], 25)
            timestamp_of_begin = kpi_monitor.get_timestamp_for_event_start()
            timestamp_of_end = kpi_monitor.get_timestamp_for_event_end()
            assert_greater_equal(timestamp_of_end, timestamp_of_begin)
            actual_duration = timestamp_of_end - timestamp_of_begin
            logger.info(f"Message found after tapping: {screen_input}. The time taken was: {actual_duration} seconds")
            utils.take_apinext_target_screenshot(
                self.test.apinext_target, self.test.results_dir, "test_01_touch_latency_kpi.png"
            )
            assert_greater_equal(
                ACCEPTED_TEST_KPI,
                actual_duration,
                f"Took {actual_duration} seconds after Tapping on {screen_input} "
                f"but the time taken is greater than {ACCEPTED_TEST_KPI}",
            )
