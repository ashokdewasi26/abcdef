# Copyright (C) 2023. BMW Car IT. All rights reserved.
import logging
from statistics import mean
import time
from unittest import skipIf

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import assert_greater_equal
from si_test_apinext.idc23.pages.connectivity_page import ConnectivityPage as Connect
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.media_page import MediaPage as Media
from si_test_apinext.idc23.pages.navigation_page import NavigationPage as Navi
from si_test_apinext.idc23.si_kpi_tests.kpi_marker import KpiMarker as Marker
from si_test_apinext.idc23.traas.bluetooth.helpers.bluetooth_utils import BluetoothUtils
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.global_steps import GlobalSteps
from si_test_apinext.util.kpi_dlt_detector import KPIDltDetector

logger = logging.getLogger(__name__)
target = TargetShare().target

ACCEPTED_TEST_KPI = 1.5
STEERING_LAYOUT = "LHD"
if target.has_capability(TE.test_bench.rack):  # All testfarm workers have a static FA file which has LHD layout
    vehicle_order_path = target.options.vehicle_order
    STEERING_LAYOUT = Launcher.get_type_key(vehicle_order_path)
logger.info(f"steering_layout of launcher is: {STEERING_LAYOUT}")


class TestDetButtonKpi:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.tap_coords = Launcher.LHD_COORDS if STEERING_LAYOUT == "LHD" else Launcher.RHD_COORDS
        cls.bluetooth_utils = BluetoothUtils(cls.test)
        utils.start_recording(cls.test)
        Media.reconnect_media()
        cls.bluetooth_utils.turn_on_bluetooth_via_adb_commands()
        Launcher.go_to_home()
        utils.pop_up_check(cls.test)
        utils.ensure_no_alert_popup(cls.test.results_dir, cls.test.driver, cls.test.apinext_target)

    @classmethod
    def teardown_class(cls):
        Launcher.go_to_home()
        utils.stop_recording(cls.test, "TestDetButtonKpi")
        cls.test.quit_driver()

    def setup(self):
        Launcher.go_to_home()

    def open_app(self, screen_input, event_start_dlt, event_end_dlt, go_to_home=True):
        """
        Interact with IDC via tap or DET buttons and calculate the response time.

        :param screen_input: (tuple/int) Tap coordinates or CarInputService keycodes.
        :param event_start_dlt: dictionary {"apid":xx, "ctid":xx, "payload_decoded": re.compile(r"xxx")}
        :param event_end_dlt: dictionary {"apid":xx, "ctid":xx, "payload_decoded": re.compile(r"xxx")}
        :param go_to_home: (Bool) If launcher needs to go to home screen.
        """
        kpi_timings = []
        for num in range(5):  # Perform each action five times and calculate the average
            with KPIDltDetector(event_start_dlt, event_end_dlt) as kpi_monitor:
                if isinstance(screen_input, tuple):
                    self.test.driver.tap([screen_input])
                    action = f"Tapping on {screen_input}"
                elif isinstance(screen_input, int):
                    GlobalSteps.inject_custom_vhal_input(self.test.apinext_target, screen_input)
                    action = f"sending DET key-input {screen_input}"
                else:
                    raise RuntimeError("Expected input as tap coordinates or car_service keycode")
                timestamp_of_begin = kpi_monitor.get_timestamp_for_event_start()
                timestamp_of_end = kpi_monitor.get_timestamp_for_event_end()
                assert_greater_equal(timestamp_of_end, timestamp_of_begin)
                actual_duration = timestamp_of_end - timestamp_of_begin
                logger.info(f"payload found after {action} is: {actual_duration}")
                kpi_timings.append(actual_duration)
                assert_greater_equal(
                    ACCEPTED_TEST_KPI,
                    actual_duration,
                    f"Took {actual_duration} seconds after {action} "
                    f"but the time taken is greater than {ACCEPTED_TEST_KPI}",
                )
            time.sleep(1)  # Delay for target to be stable
            if go_to_home:
                Launcher.go_to_home()
            else:
                GlobalSteps.inject_custom_vhal_input(self.test.apinext_target, Connect.conn_vhal_event_keycode)
            time.sleep(1)  # Delay for target to be stable
        return round(mean(kpi_timings), 2)

    @utils.gather_info_on_fail
    def test_01_media_det_button_kpi(self):
        """
        Find Media DET button latency
        Accepted value: <= 1.5s.

        *Steps*
        1. Open Media via Tap event
        2. Calculate the KPI time taken to open media after Tapping on the screen
        3. Repeat steps 1-2 and calculate the average reaction time.
        4. Open Media via DET input
        5. Calculate the KPI time taken to open media after MEDIA DET is stimulated
        6. Repeat steps 4-5 and calculate the average reaction time.
        7. Check if DET reaction time is <= Tap reaction time.

        Traceability: ABPI-260523
        """
        tap_average_time = self.open_app(self.tap_coords["media"], Marker.TAP_COMMAND, Marker.START_MEDIA_WIDGET)
        det_average_time = self.open_app(
            Media.media_vhal_event_keycode, Marker.KEYINPUT_MEDIA_DLT_PATTERN, Marker.START_MEDIA_DET
        )
        logger.info(f"Media Tap average time is:{tap_average_time} \n Media DET average time is:{det_average_time}")
        assert_greater_equal(
            tap_average_time,
            det_average_time,
            f"DET Took {det_average_time} seconds but tapping on screen took only {tap_average_time} seconds",
        )

    @utils.gather_info_on_fail
    def test_02_tel_det_button_kpi(self):
        """
        Find TEL DET button latency
        Accepted value: <= 1.5s.

        *Steps*
        1. Open Tel via Tap event
        2. Calculate the KPI time taken to open Tel after Tapping on the screen
        3. Repeat steps 1-2 and calculate the average reaction time.
        4. Open Tel via DET input
        5. Calculate the KPI time taken to open Tel after TEL DET is stimulated
        6. Repeat steps 4-5 and calculate the average reaction time.
        7. Check if DET reaction time is <= Tap reaction time.

        Traceability: ABPI-260523
        """
        tap_average_time = self.open_app(self.tap_coords["tel"], Marker.TAP_COMMAND, Marker.START_CONNECTIVITY_WIDGET)
        det_average_time = self.open_app(
            Connect.conn_vhal_event_keycode, Marker.KEYINPUT_CONNECTIVITY_DLT_PATTERN, Marker.START_CONNECTIVITY_DET
        )
        logger.info(f"TEL Tap average time is:{tap_average_time} \n TEL DET average time is:{det_average_time}")
        assert_greater_equal(
            tap_average_time,
            det_average_time,
            f"DET Took {det_average_time} seconds but tapping on screen took only {tap_average_time} seconds",
        )

    @skipIf(target.has_capability(TE.test_bench.farm), "Navigation cannot be started on test workers")
    @utils.gather_info_on_fail
    def test_03_nav_det_button_kpi(self):
        """
        Find NAV DET button latency
        Accepted value: <= 1.5s.

        *Steps*
        1. Open Nav via Tap event
        2. Calculate the KPI time taken to open Nav after Tapping on the screen
        3. Repeat steps 1-2 and calculate the average reaction time.
        4. Open Nav via DET input
        5. Calculate the KPI time taken to open Nav after NAV DET is stimulated
        6. Repeat steps 4-5 and calculate the average reaction time.
        7. Check if DET reaction time is <= Tap reaction time.

        Traceability: ABPI-260523
        """
        Navi.go_to_navigation()  # Check navigation is loaded properly
        Launcher.go_to_home()
        tap_average_time = self.open_app(self.tap_coords["nav"], Marker.TAP_COMMAND, Marker.START_MAP)
        det_average_time = self.open_app(
            Navi.nav_vhal_event_keycode, Marker.KEYINPUT_MAP_DLT_PATTERN, Marker.START_MAP
        )
        logger.info(f"NAV Tap average time is:{tap_average_time} \n NAV DET average time is:{det_average_time}")
        assert_greater_equal(
            tap_average_time,
            det_average_time,
            f"DET Took {det_average_time} seconds but tapping on screen took only {tap_average_time} seconds",
        )

    @utils.gather_info_on_fail
    def test_04_back_det_button_kpi(self):
        """
        Find BACK DET button latency
        Accepted value: <= 1.5s.

        *Steps*
        1. Open Media via DET
        2. Open TEL via DET
        3. Press BACK
        4. IDC should return to Media app.
        5. Calculate the KPI time taken to return to Media after pressing Back.
        6. Open TEL via DET
        7. Repeat steps 3-6 and calculate the average reaction time for both Tap event and DET.
        8. Check if DET reaction time is <= Tap reaction time.

        Traceability: ABPI-260523
        """
        Media.open_media()
        Connect.open_connectivity()
        tap_average_time = self.open_app(
            self.tap_coords["back"], Marker.TAP_COMMAND, Marker.RESUME_MEDIA, go_to_home=False
        )
        det_average_time = self.open_app(
            Launcher.back_vhal_event_keycode, Marker.KEYINPUT_BACK_DLT_PATTERN, Marker.RESUME_MEDIA, go_to_home=False
        )
        logger.info(f"Back Tap average time is:{tap_average_time} \n BACK DET average time is:{det_average_time}")
        assert_greater_equal(
            tap_average_time,
            det_average_time,
            f"DET Took {det_average_time} seconds but tapping on screen took only {tap_average_time} seconds",
        )
