# Copyright (C) 2022. BMW Car IT. All rights reserved.
import logging

from mtee.testing.support.target_share import TargetShare
from mtee.testing.support.usb_control import USBControl
from mtee.testing.test_environment import require_environment, require_environment_setup
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import assert_greater, assert_greater_equal
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.media_page import MediaPage as Media
from si_test_apinext.idc23.si_kpi_tests.kpi_marker import KpiMarker as Marker
from si_test_apinext.idc23.traas.audio.helpers.audio_utils import (
    check_usb_and_push_audio_file,
    ensure_usb_is_turned_off,
)
from si_test_apinext.idc23.traas.audio.helpers.volume_controller import MAX_VOLUME_STEPS, VolumeController
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.global_steps import GlobalSteps
from si_test_apinext.util.kpi_dlt_detector import KPIDltDetector
from si_test_apinext.util.screenshot_utils import capture_screenshot

logger = logging.getLogger(__name__)
REQUIREMENTS = TE.target_type.hu, TE.test_bench.rack


@require_environment(*REQUIREMENTS)
class TestEntertainmentKpi:
    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.vcar_manager = TargetShare().vcar_manager
        cls.volume_controller = VolumeController(cls.vcar_manager)
        # Set up USB controller, initializing it to HIGH (connected)
        cls.usb_controller = USBControl()
        utils.start_recording(cls.test)
        utils.pop_up_check(cls.test)
        utils.ensure_no_alert_popup(cls.test.results_dir, cls.test.driver, cls.test.apinext_target)

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def teardown_class(cls):
        Launcher.go_to_home()
        utils.stop_recording(cls.test, "TestEntertainmentKpi")
        cls.test.quit_driver()

    def setup(self):
        # Common preconditions for kpi entertainment tests.
        self.usb_controller.power_on()
        Media.reconnect_media()
        self.volume_controller.mute_volume()
        self.volume_controller.increase_volume(steps=int(MAX_VOLUME_STEPS / 4))
        check_usb_and_push_audio_file(self.usb_controller, self.test.apinext_target)

    @utils.gather_info_on_fail
    def test_01_switch_fm_to_usb(self):
        """
        Switch media source from FM to USB and measure the time taken to switch the source.
        Accepted value: <= 3s.
        *Steps*
        1. Set preconditions for the test.
        2. Select current media source as FM.
        3. Go to media source selector screen
        4. Start monitoring the dlt messages.
        5. Click usb drive as media source.
        6. Calculate the time difference between the dlt markers. Should be <= Accepted value.

        Traceability: ABPI-224856
        """
        Media.select_fm_tuner_source()
        media_source_button = self.test.driver.find_element(*Media.MEDIA_SOURCE_SELECTOR_ID)
        GlobalSteps.click_button_and_expect_elem(self.test.wb, media_source_button, Media.AUDIO_SETTINGS_BUTTON_ID)
        usb_source = Media.validate_usb_source()
        capture_screenshot(test=self.test, test_name="test_01_Radio_as_selected_source")
        with KPIDltDetector(Marker.APPIUM_CLICK_DLT_PATTERN, Marker.USB_SOURCE_DLT_PATTERN) as kpi_monitor:
            usb_source.click()
            timestamp_of_begin = kpi_monitor.get_timestamp_for_event_start()
            timestamp_of_end = kpi_monitor.get_timestamp_for_event_end()
            assert_greater(timestamp_of_end, timestamp_of_begin)
            actual_duration = timestamp_of_end - timestamp_of_begin
            capture_screenshot(test=self.test, test_name="test_01_USB_as_selected_source")
            accepted_duration = 3
            assert_greater_equal(
                accepted_duration,
                actual_duration,
                f"Switching from FM to USB takes {actual_duration} seconds, "
                f"but the expected time is {accepted_duration}",
            )

    @utils.gather_info_on_fail
    def test_02_playback_audio_usb(self):
        """
        Playback audio from USB and measure the time taken to replay the audio.
        Accepted value: <= 8s.
        *Steps*
        1. Set preconditions for the test.
        2. Disconnect USB device.
        3. Start monitoring the dlt messages.
        4. Connect USB device.
        5. Calculate the time difference between the dlt markers. Should be <= Accepted value.

        Traceability: ABPI-244949
        """
        ensure_usb_is_turned_off(self.usb_controller, self.test.apinext_target)
        with KPIDltDetector(Marker.NEW_USB_SOURCE_DLT_PATTERN, Marker.USB_SOURCE_DLT_PATTERN) as kpi_monitor:
            self.usb_controller.power_on()
            timestamp_of_begin = kpi_monitor.get_timestamp_for_event_start()
            timestamp_of_end = kpi_monitor.get_timestamp_for_event_end()
            assert_greater(timestamp_of_end, timestamp_of_begin)
            actual_duration = timestamp_of_end - timestamp_of_begin
            capture_screenshot(test=self.test, test_name="test_02_Playback_USB_as_selected_source")
            accepted_duration = 8
            assert_greater_equal(
                accepted_duration,
                actual_duration,
                f"Playing back USB takes {actual_duration} seconds, but the expected time is {accepted_duration}",
            )
