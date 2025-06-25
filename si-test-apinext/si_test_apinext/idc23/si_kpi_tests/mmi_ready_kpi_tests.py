# Copyright (C) 2023. BMW Car IT. All rights reserved.
import logging

from mtee.testing.tools import assert_greater_equal, assert_true
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.si_kpi_tests.kpi_marker import KpiMarker as Marker
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.kpi_dlt_detector import KPIDltDetector
from si_test_apinext.util.mtee_utils import MteeUtils
from tee.target_common import VehicleCondition
from tee.tools.lifecycle import LifecycleFunctions

logger = logging.getLogger(__name__)
ACCEPTED_TEST_KPI = 8


class TestMMIKpi:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.mtee_util = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        utils.start_recording(cls.test)
        Launcher.go_to_home()
        cls.lc = LifecycleFunctions()
        utils.pop_up_check(cls.test)
        utils.ensure_no_alert_popup(cls.test.results_dir, cls.test.driver, cls.test.apinext_target)

    @classmethod
    def teardown_class(cls):
        cls.test.quit_driver()
        if not cls.test.driver:
            logger.info("Driver not available, invoking driver.")
            cls.test.setup_driver()
        Launcher.go_to_home()
        utils.stop_recording(cls.test, "TestMMIKpi")
        cls.test.quit_driver()

    @utils.gather_info_on_fail
    def test_01_mmi_ready_kpi(self):
        """
        KPI measurement for MMI ready after resuming from STR
        Accepted value: <= 8 seconds.

        *Steps*
        1. Check if STR is active, if not, enabled it
            - Perform a lifecycle of the vehicle via STR
        2. Check if target resumed after lifecycle and no cold boot happened
            - If a cold boot happens, below KPI threshold will not be met and the test might fail
        3. Calculate the KPI time taken to get the home screen (Not the animation)
        4. Check if time is <= Accepted value

        Traceability: ABPI-260458
        """
        # Enable STR if not already active
        if not self.lc.get_str_state():
            self.lc.set_str_state(state="0")
            assert_true(self.lc.get_str_state, "Could not enable STR on the target")
        self.mtee_util.set_str_budget(str_budget="5616000")
        self.mtee_util.step_down_vehicle_state_to_parken()
        self.lc.stop_keepalive()
        self.lc.ecu_to_enter_sleep(timeout=180)
        with KPIDltDetector(Marker.RECEIVED_VEHICLE_PRUEFEN, Marker.HOME_SCREEN_DLT_PATTERN) as kpi_monitor:
            self.test.mtee_target.set_vehicle_lifecycle_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
            self.lc.wakeup_target(wait_for_serial_reboot=False)
            timestamp_of_begin = kpi_monitor.get_timestamp_for_event_start()
            timestamp_of_end = kpi_monitor.get_timestamp_for_event_end()
            assert_greater_equal(timestamp_of_end, timestamp_of_begin)
            actual_duration = timestamp_of_end - timestamp_of_begin
            utils.take_apinext_target_screenshot(
                self.test.apinext_target, self.test.results_dir, "test_01_mmi_ready_kpi.png"
            )
            assert_greater_equal(
                ACCEPTED_TEST_KPI,
                actual_duration,
                f"Time taken to load home screen is greater than {ACCEPTED_TEST_KPI}. It took {actual_duration} secs",
            )
