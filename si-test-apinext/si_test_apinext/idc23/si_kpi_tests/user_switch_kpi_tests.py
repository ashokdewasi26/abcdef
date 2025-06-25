# Copyright (C) 2023. BMW Car IT. All rights reserved.
import logging
import time

from mtee.testing.tools import assert_greater_equal
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.perso_page import PersoPage as Perso
from si_test_apinext.idc23.si_kpi_tests.kpi_marker import KpiMarker as Marker
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.kpi_dlt_detector import KPIDltDetector

logger = logging.getLogger(__name__)

USER_SWITCH_SECONDS_KPI = 17
USER_NAME = "Guest"


class TestUserSwitchKpi:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

        cls.current_user_id = cls.test.apinext_target.get_current_user_id()
        cls.current_user_name = Perso.get_current_user_name()
        logger.info(f"Current user name: {cls.current_user_name} and current user-id is: {cls.current_user_id}")
        Launcher.go_to_home()
        utils.pop_up_check(cls.test)
        utils.ensure_no_alert_popup(cls.test.results_dir, cls.test.driver, cls.test.apinext_target)

    @classmethod
    def teardown_class(cls):
        Launcher.go_to_home()
        cls.test.apinext_target.switch_user(cls.current_user_id)
        cls.test.quit_driver()

    @utils.gather_info_on_fail
    def test_01_user_switch_kpi(self):
        """
        Find KPI of IDC when switching to a guest user.
        Accepted value: <= 17s.

        *Steps*
        1. Open BMW ID app.
        2. Open Change profile option.
        3. Switch to Guest profile from current active profile.
        4. Calculate the time taken from clicking on accepting to switch to
        Guest profile till all the widgets are loaded.

        Traceability: ABPI-260527
        """
        Launcher.go_to_home()
        Perso.start_activity(validate_activity=False)
        switch_button = Perso.check_visibility_of_element(Perso.PERSO_SWITCH_USER_ID)
        utils.take_apinext_target_screenshot(self.test.apinext_target, self.test.results_dir, "Start_bmw_id.png")
        switch_button.click()
        Perso.check_visibility_of_element(Perso.ADD_PROFILE_TEXT)
        guest_user = self.test.driver.find_element(*Perso.GUEST_PROFILE_TEXT)
        utils.take_apinext_target_screenshot(self.test.apinext_target, self.test.results_dir, "Found_guest_user.png")
        guest_user.click()
        utils.take_apinext_target_screenshot(self.test.apinext_target, self.test.results_dir, "Confirmation_popup.png")
        activate_button = Perso.check_visibility_of_element(Perso.ACTIVATE_NEW_PROFILE_ID)
        with KPIDltDetector(Marker.SWITCH_USER_START, Marker.SWITCH_USER_END) as kpi_monitor:
            activate_button.click()
            self.test.quit_driver()
            time.sleep(10)
            utils.remove_appium_apk(self.test.apinext_target)
            time.sleep(20)
            for _ in range(0, 5):
                new_user_id = self.test.apinext_target.get_current_user_id()
                new_user_name = Perso.get_current_user_name()
                if new_user_name == USER_NAME:
                    break
                time.sleep(1)
            else:
                RuntimeError(f'Expected user profile name to be "{USER_NAME}" instead found "{new_user_name}"')
            logger.info(f"new user name: {new_user_name} and new user-id is: {new_user_id}")
            timestamp_of_begin = kpi_monitor.get_timestamp_for_event_start()
            timestamp_of_end = kpi_monitor.get_timestamp_for_event_end()
            assert_greater_equal(timestamp_of_end, timestamp_of_begin)
            actual_duration = timestamp_of_end - timestamp_of_begin
            logger.info(f"payload found after switching user in: {actual_duration} seconds")
            assert_greater_equal(
                USER_SWITCH_SECONDS_KPI,
                actual_duration,
                f"Took {actual_duration} seconds after switching user."
                f"but the time taken is greater than {USER_SWITCH_SECONDS_KPI}",
            )
            self.test.setup_driver()
            Launcher.go_to_home()
            utils.take_apinext_target_screenshot(
                self.test.apinext_target, self.test.results_dir, f"{new_user_name}_user_homescreen.png"
            )
