import datetime
import logging
import time
from unittest import skipIf

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT
from mtee.testing.tools import assert_process_returncode
from nose.tools import assert_regexp_matches
from si_test_apinext.idc23.pages.date_time_settings_page import DateTimeSettingsAppPage as Date_time_settings
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.settings_app_page import SettingsAppPage as Settings
from si_test_apinext.idc23.pages.top_right_status_bar_page import TopRightStatusBarPage as TopBar
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
import si_test_apinext.util.idc_time as time_utils
from si_test_apinext.util.mtee_utils import MteeUtils

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name
target = TargetShare().target
video_name = "test_time"


class TestTime:
    time_element = [TopBar.GOOGLE_CLOCK_ID, TopBar.TIME_ID]

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.mtee_util = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        cls.vcar_manager = TargetShare().vcar_manager
        if not cls.vcar_manager:
            raise Exception("Vcar didn't started")

        if not Launcher.validate_launcher():
            logger.info("Failed to validate launcher. Restarting target to try to recover Launcher")
            # Try to recover Launcher
            cls.test.teardown_base_class()
            cls.test.apinext_target.restart()
            cls.test.setup_base_class()

        cls.check_preconditions()
        utils.start_recording(cls.test)
        utils.ensure_no_alert_popup(cls.test.results_dir, cls.test.driver, cls.test.apinext_target)
        cls.test.apinext_target.close_popups()
        Launcher.go_to_home()
        Settings.launch_settings_activity()
        Launcher.return_from_submenu(Settings.STATUSBAR_TITLE, Settings.SETTINGS_MENU_TITLE)

    def teardown(self):
        """After each test it should return from settings submenus irrespective of the result"""
        Launcher.return_from_submenu(Settings.STATUSBAR_TITLE, Settings.SETTINGS_MENU_TITLE)

    @classmethod
    def teardown_class(cls):
        Launcher.go_to_home()
        utils.stop_recording(cls.test, video_name)
        cls.test.quit_driver()

    @classmethod
    def check_preconditions(cls):
        """Check autotime and timemanager are running"""
        # Validate timemanager is running
        timemanager_result = cls.test.mtee_target.execute_command(
            "systemctl list-units --full -all | grep secure-datetime-client"
        )

        assert_process_returncode(
            0, timemanager_result, "Executing 'systemctl list-units --full -all | grep secure-datetime-client' failed"
        )
        assert_regexp_matches(
            timemanager_result.stdout,
            r"active\s+running\s+Secure DateTime Client",
            f"Precondition not met: Secure DateTime Client not running \n Error message: {timemanager_result} "
            f"stdout: {timemanager_result.stdout}",
        )
        # Validate autotime is running
        autotime_result = cls.test.mtee_target.execute_command(
            "lxc-attach -n node1 -c u:r:unconfined_t:s0 -- systemctl list-units --full -all | grep autotime"
        )
        assert_process_returncode(
            0, autotime_result, "Executing 'systemctl list-units --full -all | grep autotime' failed"
        )
        assert_regexp_matches(
            autotime_result.stdout,
            r"active\s+running\s+AutoTime",
            f"Precondition not met: AutoTime not running \n Error message: {autotime_result} "
            f"stdout: {autotime_result.stdout}",
        )

    @classmethod
    def prepare_time_zone(cls):
        """
        Set a time zone

        In recent images the time zone is set by default to a non valid option 'World'
        which don't have a time zone value. To overcome this issue we define a time zone
        before starting the tests
        """
        Launcher.return_from_submenu(Settings.STATUSBAR_TITLE, Settings.SETTINGS_MENU_TITLE)
        default_time_zone_country = "Japan"
        Date_time_settings.set_time_zone(wanted_region=default_time_zone_country)
        new_time_zone = Date_time_settings.get_current_manual_time_zone()
        logger.info("Found this new_time_zone after prepare_time_zone: " + new_time_zone)

    @utils.gather_info_on_fail
    def test_00_time_ui_position_prepare_timezone(self):
        """
        Test time position in Ui

        Validate time is at the expected position: in the top right corner
        Prepare the tests by defining a timezone
        """
        Date_time_settings.set_24_hour_format()
        current_time_ui = time_utils.get_current_time_from_ui(self.test, self.time_element)
        assert current_time_ui, "Didn't find any time on the UI on the expected position: top right corner"
        self.prepare_time_zone()

    @skipIf(
        target.has_capability(TEST_ENVIRONMENT.test_bench.rack),
        "Can't change time using VCar on Racks as WAVE is available",
    )
    @utils.gather_info_on_fail
    def test_01_change_time(self):
        """
        Test - try change TimeTrustee time (using vcar)
        """
        # # Get the current time zone in Android UI ------------------------------
        current_time_zone_text = Date_time_settings.get_current_default_time_zone()

        logger.info("Found this current_time_zone_text: " + current_time_zone_text)
        current_time_zone_offset = time_utils.get_time_zone_offset(current_time_zone_text)
        logger.info("Found this current_time_zone_offset: " + str(current_time_zone_offset))
        default_hour = time_utils.get_android_system_time(self.test.apinext_target).hour

        try:
            # # Turn off Date and Time sync ------------------------------
            time_utils.turn_off_date_and_time_sync(self.vcar_manager)

            # # Changing TimeTrustee hour
            new_hour = "21"
            time_utils.change_trusted_time_hour(self.vcar_manager, new_hour)

            new_hour_datetime = datetime.datetime.now().replace(hour=int(new_hour))
            final_hour_datetime = new_hour_datetime + current_time_zone_offset
            final_hour_offset = final_hour_datetime.hour

            final_ui_time_text = time_utils.wait_for_hour_in_ui(self.test, final_hour_offset, self.time_element)

            assert int(final_ui_time_text.hour) == int(
                final_hour_offset
            ), f"Final UI hour: {final_ui_time_text.hour} didn't match new_hour: {final_hour_offset}"
        finally:
            time_utils.change_trusted_time_hour(self.vcar_manager, default_hour)
            system_minute = datetime.datetime.now().minute
            system_seconds = datetime.datetime.now().second
            time_utils.change_trusted_time_min_sec(self.vcar_manager, system_minute, system_seconds)
            time_utils.turn_on_date_and_time_sync(self.vcar_manager)

    @skipIf(
        target.has_capability(TEST_ENVIRONMENT.test_bench.rack),
        "Can't change time using VCar on Racks as WAVE is available",
    )
    @utils.gather_info_on_fail
    def test_02_arbitrary_time(self):
        """
        Test arbitrary time

        *Background information*

        - Simulate in vcar ttaQualifier = 1, ttsQualifier = 3 (inaccuracy <=10, time very trustworthy):
            TimeTrusteeSDaT.getSecureDateAndTime.ttaQualifier = 1
            TimeTrusteeSDaT.getSecureDateAndTime.ttsQualifier = 3
        - Simulate in vcar current worker time
        - Get the current time zone in Android UI
        - Get current time in Android UI
        - Get system time
        - Change the current time zone in Android UI

        Expected outcome:
        - Android time (UI) will be UTC time sent by worker, plus TZ offset and daylight saving time
        - System time will be the same simulated in vcar
        - After changing the timezone, the time (android) will be updated according to the new timezone,
         system time is the same
        """
        # # Get system time ------------------------------
        initial_android_sys_time = time_utils.get_android_system_time(self.test.apinext_target)
        logger.info("Found this system_time: " + str(initial_android_sys_time))

        # # Get the current time zone in Android UI ------------------------------
        current_time_zone_text = Date_time_settings.get_current_default_time_zone()
        logger.info("Found this current_time_zone_text: " + current_time_zone_text)
        current_time_zone_offset = time_utils.get_time_zone_offset(current_time_zone_text)
        logger.info("Found this current_time_zone_offset: " + str(current_time_zone_offset))

        # # Turn off Date and Time sync ------------------------------
        time_utils.turn_off_date_and_time_sync(self.vcar_manager)

        # # Simulate in vcar ttaQualifier = 1, ttsQualifier = 3 (inaccuracy <=10, time very trustworthy) ----------
        tta_qualifier = 1  # INACCURANCY_LESS_THAN_10MS_ON
        self.vcar_manager.send(f"{time_utils.TimeTrustee_tta}={tta_qualifier}")
        time.sleep(1)
        tts_qualifier = 3
        self.vcar_manager.send(f"{time_utils.TimeTrustee_tts}={tts_qualifier}")
        time.sleep(1)

        # # Simulate in vcar current worker time ------------------------------
        current_worker_time = datetime.datetime.now(datetime.timezone.utc)
        final_hour = str(int(datetime.datetime.strftime(current_worker_time, "%H")))

        msg_list = [
            "trustedTime.uTCTagDate.day = " + str(int(datetime.datetime.strftime(current_worker_time, "%d"))),
            "trustedTime.uTCTagDate.month = " + str(int(datetime.datetime.strftime(current_worker_time, "%m"))),
            "trustedTime.uTCTagDate.year = " + str(int(datetime.datetime.strftime(current_worker_time, "%Y"))),
            "trustedTime.uTCTagTime.hour = " + final_hour,
            "trustedTime.uTCTagTime.minute = " + str(int(datetime.datetime.strftime(current_worker_time, "%M"))),
            "trustedTime.uTCTagTime.nanosecond = 0",
            "trustedTime.uTCTagTime.second = " + str(int(datetime.datetime.strftime(current_worker_time, "%S"))),
        ]

        for msg in msg_list:
            self.vcar_manager.send(f"{time_utils.TimeTrustee_base}{msg}")

        new_hour_datetime = datetime.datetime.now().replace(hour=int(final_hour))
        final_hour_datetime = new_hour_datetime + current_time_zone_offset
        final_hour_offset = final_hour_datetime.hour

        time_utils.wait_for_hour_in_ui(self.test, final_hour_offset, self.time_element)

        # # Get system time ------------------------------
        new_date_epoch_time = time_utils.get_android_system_time(self.test.apinext_target)

        logger.info("Found this system_time: " + str(new_date_epoch_time))
        assert new_date_epoch_time.hour == int(
            final_hour
        ), f"Android system time ($EPOCHREALTIME) didn't change as expected to:{final_hour}"
        f"instead is: {new_date_epoch_time.hour}"
        Launcher.return_from_submenu(Settings.STATUSBAR_TITLE, Settings.SETTINGS_MENU_TITLE)
        # # Change the current time zone in Android UI ------------------------------
        Date_time_settings.set_time_zone(wanted_region="Turkey")

        new_time_zone = Date_time_settings.get_current_manual_time_zone()

        logger.info("Found this new_time_zone: " + new_time_zone)
        new_time_zone_offset = time_utils.get_time_zone_offset(new_time_zone)
        logger.info("Found this new_time_zone_offset: " + str(new_time_zone_offset))

        # # Get current time in Android UI ------------------------------
        try:
            final_time_text = time_utils.get_current_time_from_ui(self.test, self.time_element)

            final_hour_datetime = new_hour_datetime + new_time_zone_offset
            final_hour = final_hour_datetime.hour
            assert final_time_text and final_hour == int(
                float(final_time_text.hour)
            ), f"New UI hour ({final_time_text.hour}) is not the expected ({final_hour})"

            # # Get system time ------------------------------
            final_date_epoch_time = time_utils.get_android_system_time(self.test.apinext_target)

            logger.info("Found this system_time: " + str(final_date_epoch_time))
            assert final_date_epoch_time.hour == new_date_epoch_time.hour, (
                f"System time hour unexpectedly changed from: {new_date_epoch_time.hour} "
                + f"to {final_date_epoch_time.hour}"
            )
        finally:
            time_utils.change_trusted_time_hour(self.vcar_manager, new_date_epoch_time.hour)
            system_minute = datetime.datetime.now().minute
            system_seconds = datetime.datetime.now().second
            time_utils.change_trusted_time_min_sec(self.vcar_manager, system_minute, system_seconds)
            time_utils.turn_on_date_and_time_sync(self.vcar_manager)
