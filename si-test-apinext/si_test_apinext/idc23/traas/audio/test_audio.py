import glob
import logging
import os
import re
import time

import si_test_apinext.util.driver_utils as utils
from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.support.target_share import TargetShare
from mtee.testing.support.usb_control import USBControl
from mtee.testing.tools import assert_equal, assert_false, assert_true, metadata, retry_on_except
from si_test_apinext.idc23 import AUDIO_REF_IMAGES_PATH
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.media_page import MediaPage as Media
from si_test_apinext.idc23.pages.top_right_status_bar_page import TopRightStatusBarPage as TopBar
from si_test_apinext.idc23.traas.audio.helpers.analyzer import AudioAnalyzer
from si_test_apinext.idc23.traas.audio.helpers.audio_utils import (
    ANDROID_KEYCODE_VOLUME_MUTE,
    alsa_mixer_min_config,
    check_usb_and_push_audio_file,
    get_volume_value_from_dlt,
    reset_usb,
    set_mute_status,
)
from si_test_apinext.idc23.traas.audio.helpers.volume_controller import VolumeController
from si_test_apinext.testing.test_base import TestBase
from si_test_apinext.util.mtee_utils import MteeUtils
from si_test_apinext.util.screenshot_utils import capture_screenshot, compare_snapshot, match_template

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

video_name = "test_audio"

DEFAULT_IBOX_DEVICE = "/dev/ttyUSB_PowerSupply"
IMAGE_DIFFERENCE_THRESHOLD = 1


@metadata(testsuite=["SI"])
class TestAudio:
    audio_ref_images_path = AUDIO_REF_IMAGES_PATH
    # This sine wave refers to the audio file /samples/sinusoid_200_700.mp3
    # Tone frequency = 'first_freq' Hz for 10s + 'second_freq' Hz for subsequent 10s
    sine_wave_audio = {"first_freq": 200, "second_freq": 700}

    # Max frequency deviation accepted
    frequency_deviation = 80
    min_strength = 0.4

    @classmethod
    def setup_class(cls):
        # TestBase is a singleton class to re-use appium driver and target vars
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.vcar_manager = TargetShare().vcar_manager

        cls.analyzer = AudioAnalyzer(cls.test)
        cls.volume_controller = VolumeController(cls.vcar_manager)
        # Set up USB controller, initializing it to HIGH (connected)
        cls.usb_controller = USBControl()

        if cls.analyzer.connector_audio.start() is None:
            raise RuntimeError("Failed to start connector Audio, phonesimu might not be running")

        utils.pop_up_check(cls.test)
        utils.ensure_no_alert_popup(cls.test.results_dir, cls.test.driver, cls.test.apinext_target)

        alsa_mixer_min_config()

        cls.mtee_utils = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)

        cls.mute_icon_results_dir = os.path.join(cls.test.results_dir, "mute_icon_tests")
        cls.slider_pos_results_dir = os.path.join(cls.test.results_dir, "slider_pos_tests")
        cls.tests_results_dir = [cls.mute_icon_results_dir, cls.slider_pos_results_dir]
        cls.create_results_folders(cls)

    @classmethod
    def teardown_class(cls):
        cls.analyzer.connector_audio.stop()
        cls.test.quit_driver()

    def setup(self):
        utils.start_recording(self.test)

    def teardown(self):
        video_name = "Test_Audio"
        utils.stop_recording(self.test, video_name)

    def create_results_folders(self):
        """
        Create all folders for specific tests results
        """
        for results_folder in self.tests_results_dir:
            if not os.path.exists(results_folder):
                logger.debug("Creating recordings directory '%s'", results_folder)
                os.makedirs(results_folder)
            else:
                logger.debug("Log file directory exists: '%s'", results_folder)

    @retry_on_except(retry_count=3)
    def navigate_ui_play_first_song_from_usbdrive(self):
        """
        Navigates through the UI with appium, expecting that there is a usb media source.
        *Steps*
        1. Go home
        2. Press media button
        3. Press media source selector
        4. Press usb drive media source
        5. Select category songs
        6. select first song
        """
        Launcher.go_to_home()
        # Press media button
        Media.open_media()

        Media.select_audio_source(Media.MEDIA_USB_SOURCE_ID)

        # Get browse list (first song's category)
        browse_list = Media.get_browse_list()
        browse_list[0].click()
        time.sleep(1)

        Media.go_back_from_submenu()

    @retry_on_except(retry_count=3)
    def select_radio_station(self):
        """
        Select the first radio source from the list

        :return: True if selected valid station and is properly displayed
                 False if there are no valid Radio Stations to play
        :rtype: Bool
        :raises RuntimeError: if no source is displayed
        """
        # Get radio station list
        radio_station_list = Media.get_browse_list()
        if len(radio_station_list) == 0:
            return False
        else:
            for radio_station in radio_station_list:
                radio_station_elem = radio_station.find_elements(*Media.MEDIA_BROWSE_ITEM_LABEL_ID)
                radio_name = radio_station_elem[0].text if radio_station_elem and radio_station_elem[0].text else ""
                if not radio_name:
                    logger.debug("Unable to select a valid radio station, because no valid radio name")
                    return False
                elif "87.5" not in radio_name:  # we dont want to select this station
                    time.sleep(0.5)
                    radio_station.click()
                    logger.debug(f"Selected Radio station: '{radio_name}'")
                    time.sleep(1)
                    return True
                elif len(radio_station_list) == 1 and "87.5" in radio_name:
                    logger.info("There are no valid Radio Stations to play")
                    return False

    def search_radio_stations(self):
        """
        Try to search manually for a radio station
        """
        radio_selected_widget = self.test.driver.find_element(*Media.MEDIA_RADIO_TUNER_WIDGET_ID)
        radio_selected_widget.click()
        time.sleep(1)

        manual_frequency_tuner = self.test.driver.find_element(*Media.MEDIA_RADIO_TUNER_MANUAL_FREQ)
        manual_frequency_tuner.click()
        time.sleep(2)

        search_frequency = self.test.driver.find_element(*Media.MEDIA_RADIO_TUNER_SEARCH_FREQ_BACK)
        search_frequency.click()
        time.sleep(10)

        go_back_submenu = self.test.driver.find_element(*Media.MEDIA_RADIO_TUNER_GO_BACK_SUBMENU)
        go_back_submenu.click()
        time.sleep(2)

        close_radio_widget_submenu = self.test.driver.find_element(*Media.MEDIA_RADIO_TUNER_CLOSE_SUBMENU)
        close_radio_widget_submenu.click()
        time.sleep(1)

    def try_play_valid_radio_station(self, retry_attempts=3):
        """
        Try to play a valid radio station

        :param retry_attempts: number os retry attempts, defaults to 3
        :type retry_attempts: int, optional
        :raises RuntimeError: if none valid radio station is found
        """

        for i in range(1, retry_attempts + 1):
            valid_station = self.select_radio_station()

            if valid_station is False and i < 3:
                logger.info(f"Searching new radio station, attempt {i}/3")
                self.search_radio_stations()
                continue
            if valid_station is True:
                # Valid station found
                return

        raise RuntimeError("Found none valid radio stations")

    def validate_status_bar_audio_icon(
        self, audio_status, test_name="test_validate_status_bar_audio_icon", mute_icon_bounds=None
    ):
        """
        Validate the status of the audio icon through a image comparison with a reference image

        :param audio_status: expected status of the audio icon
        :type audio_status: str
        :param test_name: name of current test, defaults to "test_validate_status_bar_audio_icon"
        :type test_name: str, optional
        :raises RuntimeError: when received audio_status is invalid
        :return: result of validation and error message
        :rtype: bool, str
        """
        valid_status = ["muted", "unmuted"]
        if audio_status not in valid_status:
            raise RuntimeError(f"Received status '{audio_status}' is not valid ({valid_status})")
        Launcher.open_all_apps_from_home()
        time.sleep(1)

        screenshot_path = capture_screenshot(test=self.test, test_name=test_name, bounds=mute_icon_bounds)
        ref_mute_icon_list = glob.glob(os.path.join(self.audio_ref_images_path, f"*_{audio_status}*.png"))
        for ref_mute_icon in ref_mute_icon_list:
            result, error = compare_snapshot(
                screenshot_path, ref_mute_icon, test_name + "_compare_audio_icon_" + audio_status, fuzz_percent=10
            )
            if result:
                return True, None
        return result, error

    @utils.gather_info_on_fail
    def test_001_play_usb_audio(self):
        """
        First audio test, playing audio from USB drive.

        * HW Requirements*
        - USB drive plug into IDC and have switching capabilities
        - Audio Level Shifter (LS) connected to test rack
        - RCA to 3.5mm jack adapter. From LS to worker.

        * SW requirements *
        - Have phonesimu running

        *Steps*
        1. Push Audio file to usb drive
        2. Switch USB off/on, to remount it
        3. Navigate through UI and play the first (and only) song
        4. Increase volume to the max
        5. Have phonesimu watching for the frequency of the sine wave
        """
        errors_list = []

        check_usb_and_push_audio_file(self.usb_controller, self.test.apinext_target)
        reset_usb(self.usb_controller, self.test.apinext_target)
        time.sleep(5)

        self.navigate_ui_play_first_song_from_usbdrive()

        self.volume_controller.initialize_volume()
        time.sleep(1.0)
        # Increase volume to the max
        self.volume_controller.max_volume()

        timeout = 20
        # check first frequency
        expected_track_frequency = self.sine_wave_audio["first_freq"]
        result = self.analyzer.check_frequency(
            expected_track_frequency,
            self.frequency_deviation,
            "test_001_play_usb_audio_test_first_freq",
            timeout,
            min_strength=self.min_strength,
        )
        if not result:
            errors_list.append(
                f"Expected frequency {expected_track_frequency} Hz, with deviation {self.frequency_deviation},\
                     was not detected within timeout {timeout}"
            )

        # check second frequency
        expected_track_frequency = self.sine_wave_audio["second_freq"]
        result = self.analyzer.check_frequency(
            expected_track_frequency,
            self.frequency_deviation,
            "test_001_play_usb_audio_test_second_freq",
            timeout,
            min_strength=self.min_strength,
        )

        if not result:
            errors_list.append(
                f"Expected frequency {expected_track_frequency} Hz, with deviation {self.frequency_deviation},\
                     was not detected within timeout {timeout}"
            )
        assert_false(errors_list, "\n".join(errors_list))

    @utils.gather_info_on_fail
    def test_002_radio_audio_source_mute(self):
        """
        Audio test radio source and mute.

        In this test we validate:
        - Radio is playing, through voice audio detection
        - The mute works, detecting silence and validate it status through DLT

        *Steps*
        1. Select Radio as Source
        2. Set volume to level maximum
        3. Measure Output (detect voice)
        4. Press Mute Button
        5. Measure Output (detect silence)
        """
        errors_list = []
        vad_timeout = 30

        Launcher.go_to_home()
        Media.open_media()
        Media.select_audio_source(Media.MEDIA_RADIO_SOURCE_ID)

        self.try_play_valid_radio_station()

        # Increase volume to the max
        self.volume_controller.max_volume()
        # To make sure volume is up
        set_mute_status(self.test.mtee_target, self.test.driver, action="UNMUTE")
        time.sleep(2)

        # Measure Output to detect voice
        result_wait_for_voice = self.analyzer.check_voice_detection(
            context="test_002_VAD_radio_test", timeout=vad_timeout, post_record_duration=5.0
        )
        if not result_wait_for_voice:
            errors_list.append(f"Voice was not detected within {vad_timeout}s")

        # Press Mute Button
        set_mute_status(self.test.mtee_target, self.test.driver)
        time.sleep(2)

        # Measure Output and assert silence
        check_silence_result = self.analyzer.verify_silence(context="test_002_check_silence")

        if not check_silence_result:
            errors_list.append("Silence was not found after clicking on mute")

        # Assert at the end to complete the sequence and record mute and unmute state
        assert_false(errors_list, "\n".join(errors_list))

    @utils.gather_info_on_fail
    def test_003_mute_w_hmi_icon(self):
        """
        Test Mute Icon is present on HMI, and pressing it unmute source

        *Steps*
        1. Select a audio Source
        2. Set volume
        3. Measure Output (detect audio)
        4. Press Mute Button/Send adb keyevent
        5. Measure Output (ENT source is Mute)
        6. Check UI mute button is present
        7. press UI unMute
        8. Measure Output (ENT source is unMute)
        """
        errors_list = []

        # Select a audio Source
        self.navigate_ui_play_first_song_from_usbdrive()

        # Set volume
        self.volume_controller.max_volume()
        # Measure Output and assert no silence
        check_silence_result = self.analyzer.verify_silence(context="t_003_check_radio_sound")

        if check_silence_result:
            errors_list.append(f"No sound detected, result: {check_silence_result}")
        # Press Mute Button
        set_mute_status(self.test.mtee_target, self.test.driver)
        time.sleep(1)
        # Measure Output and assert silence
        check_silence_result = self.analyzer.verify_silence(context="t_003_check_silence")
        if not check_silence_result:
            errors_list.append(f"Silence was not found after clicking on mute, result: {check_silence_result}")

        Launcher.open_all_apps_from_home()
        time.sleep(1)

        mute_icon = self.test.driver.find_element(*TopBar.MUTE_ICON_ID)
        mute_icon_bounds = utils.get_elem_bounds_detail(mute_icon, crop_region=True)
        # Validate audio icon on status bar
        result_mute, error_mute = self.validate_status_bar_audio_icon(
            audio_status="muted", test_name="test_003_expect_mute", mute_icon_bounds=mute_icon_bounds
        )

        if not check_silence_result:
            errors_list.append(f"Audio icon is not muted as expected, result: '{result_mute}', error: '{error_mute}'")

        # Tap on mute icon to UNMUTE
        mute_icon.click()
        time.sleep(2)

        mute_icon = self.test.driver.find_element(*TopBar.MUTE_ICON_ID)
        mute_icon_bounds = utils.get_elem_bounds_detail(mute_icon, crop_region=True)
        # Validate audio icon on status bar
        result_unmute, error_unmute = self.validate_status_bar_audio_icon(
            audio_status="unmuted", test_name="test_003_expect_unmute", mute_icon_bounds=mute_icon_bounds
        )

        if not result_mute:
            errors_list.append(
                f"Audio icon is not unmuted as expected, result: '{result_unmute}', error: '{error_unmute}'"
            )

        # Assert at the end to complete the sequence and record mute and unmute state
        assert_false(errors_list, "\n".join(errors_list))

    @utils.gather_info_on_fail
    def test_004_usb_audio_mute(self):
        """
        Play audio from usb source and check if mute works.

        *Requirements*
        - This test need test_001 to be be ran previously because,
            this test takes for granted that we have an USB and a audio file.

        *Steps*
        1. Select USB as Source and play audio file
        2. Set volume to max level
        3. Measure Output (detect sine wave frequency)
        4. Press Mute Button
        5. Measure Output (detect silence)
        """
        errors_list = []

        self.navigate_ui_play_first_song_from_usbdrive()

        self.volume_controller.max_volume()
        # To make sure volume is up
        set_mute_status(self.test.mtee_target, self.test.driver, action="UNMUTE")
        time.sleep(2)

        timeout = 30
        # check first frequency
        expected_track_frequency = self.sine_wave_audio["first_freq"]
        result = self.analyzer.check_frequency(
            expected_track_frequency,
            self.frequency_deviation,
            "test_004_play_usb_audio_mute_test",
            timeout,
            min_strength=self.min_strength,
        )

        if not result:
            errors_list.append(
                f"Expected frequency {expected_track_frequency} Hz, "
                f"with deviation {self.frequency_deviation}, was not detected within timeout {timeout}"
            )

        # Press Mute Button
        set_mute_status(self.test.mtee_target, self.test.driver)
        time.sleep(2)

        # Measure Output for silence
        check_silence_result = self.analyzer.verify_silence(context="test_004_check_silence")

        if not check_silence_result:
            errors_list.append("Silence was not found after clicking on mute")
        # Assert at the end to complete the sequence and record mute and unmute state
        assert_false(errors_list, "\n".join(errors_list))

    @utils.gather_info_on_fail
    def test_005_volume_slider_mute_pos(self):
        """
        Test Volume slider is not affected by Mute function - HMI

        In this test we validate:
        - If the volume level before and after the mute - unmute remains the same on the HMI

        *Steps*
        1. Set Volume (for example 25%)
        2. Capture HMI volume slider
        3. Press Mute (ENT source is muted)
        4. Press unMute (ENT source is unmuted)
        5. Capture HMI (Volume slider must be on same spot)
        """
        volume_bar_bounds = (390, 600, 1530, 770)

        # Press media button
        Media.open_media()
        time.sleep(1)
        self.volume_controller.initialize_volume()

        # Assure it is muted
        set_mute_status(self.test.mtee_target, self.test.driver)
        time.sleep(3)  # wait for volume pop up to go away

        self.test.driver.keyevent(ANDROID_KEYCODE_VOLUME_MUTE)  # unmute
        time.sleep(0.5)  # wait for pop up to show before taking screenshot
        screenshot_volume_path = capture_screenshot(
            test=self.test,
            test_name="test_005_volume_slider_init_UNMUTE",
            bounds=volume_bar_bounds,
            results_dir_path=self.slider_pos_results_dir,
        )
        time.sleep(3)

        self.test.driver.keyevent(ANDROID_KEYCODE_VOLUME_MUTE)  # mute
        time.sleep(0.5)
        capture_screenshot(
            test=self.test,
            test_name="test_005_volume_slider_MUTE",
            bounds=volume_bar_bounds,
            results_dir_path=self.slider_pos_results_dir,
        )
        time.sleep(3)

        self.test.driver.keyevent(ANDROID_KEYCODE_VOLUME_MUTE)  # unmute
        time.sleep(0.5)
        screenshot_unmute_path = capture_screenshot(
            test=self.test,
            test_name="test_005_volume_slider_UNMUTE_FINAL",
            results_dir_path=self.slider_pos_results_dir,
        )

        extended_volume_bar_bounds = (380, 570, 1540, 810)
        # The lower the better. A perfect match would be around 0.015. Here we expect perfect match.
        # This way if the volume level instead of 50% is at 49% we may catch it.
        acceptable_diff = 0.05
        result, _ = match_template(
            image=screenshot_unmute_path,
            image_to_search=screenshot_volume_path,
            region=extended_volume_bar_bounds,
            results_path=self.test.results_dir,
            context="test_005_",
            acceptable_diff=acceptable_diff,
        )
        assert_true(result, "Volume slider is not in the expected level.")

    @utils.gather_info_on_fail
    def test_006_keep_vol_level_dlt(self):
        """
        Test Volume level is not affected by Mute function - DLT

        In this test we validate:
        - If the volume level before and after the mute - unmute remains the same on the DLT

        *Steps*
        1. Set Volume (for example 25%)
        2. Catch volume level on DLT
        3. Press Mute (ENT source is muted)
        4. Press unMute (ENT source is unmuted)
        5. Catch volume level on DLT and assert is constant
        """

        dlt_msg = r"BMWAudioServiceHAL.*onVolumeChangedEvent.*volume: (\d+)"

        search_text = re.compile(dlt_msg)

        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as dlt_detector:
            set_mute_status(self.test.mtee_target, self.test.driver, action="UNMUTE")
            messages_list = dlt_detector.wait_for(
                {"apid": "ALD", "ctid": "LCAT", "payload_decoded": dlt_msg},
                timeout=20,
                regexp=True,
                raise_on_timeout=False,
            )
            if not messages_list:
                raise RuntimeError("No DLT volume message found")
            initial_volume = get_volume_value_from_dlt(messages_list, search_text)
            set_mute_status(self.test.mtee_target, self.test.driver, action="UNMUTE")
            messages_list = dlt_detector.wait_for(
                {"apid": "ALD", "ctid": "LCAT", "payload_decoded": search_text},
                timeout=20,
                regexp=True,
                raise_on_timeout=False,
            )
            if not messages_list:
                raise RuntimeError("No DLT volume message found")
            final_volume = get_volume_value_from_dlt(messages_list, search_text)

        assert_equal(
            initial_volume,
            final_volume,
            f"Final volume level: '{final_volume}' found on DLT was not the same as before mute : '{initial_volume}' ",
        )

    @utils.gather_info_on_fail
    def test_007_audio_source_stored_non_volatile_memory(self):
        """
        Check audio source is stored in non-volatile memory
        *Background information*
        This test case validates that current audio source is saved in the system and
        when restarting the system should remember the last used audio source.
         *Steps*
        1. Select USB as audio Source(selecting USB as radio is default source)
        2. Save USB name
        3. Play any content in USB
        4. System Restart
        5. Go to media and check the audio source is still USB
        6. Validate the USB name

        Traceability: ABPI-166562
        """

        Launcher.go_to_home()
        check_usb_and_push_audio_file(self.usb_controller, self.test.apinext_target)
        time.sleep(5)
        self.navigate_ui_play_first_song_from_usbdrive()
        capture_screenshot(test=self.test, test_name="test_007_media_before_restart")
        media_source_name = Media.get_current_media_source()
        logger.debug(f"Media source before restart :{media_source_name}")

        # restarting system
        self.mtee_utils.restart_target_and_driver(self.test)
        Media.open_media()
        capture_screenshot(test=self.test, test_name="test_007_media_after_restart")
        current_media_source = Media.get_current_media_source()
        logger.debug(f"Media source after restart :{current_media_source}")
        Launcher.go_to_home()
        assert media_source_name == current_media_source, (
            f"Couldn't found same media source : {media_source_name} after restarting."
            f"Media source name after restart is: {current_media_source}."
        )

    @utils.gather_info_on_fail
    def test_008_mute_non_volatile_reboot(self):
        """
        Test Mute value is stored in non-volatile memory on target reboot
        *Steps*
        1. Select Radio as Source
        2. Validate status bar audio icon unmuted
        3. Press Mute Button/Simulate with Vcar
        4. Validate status bar audio icon muted
        5. System Restart
        6. Validate status bar audio icon muted
        7. Measure Ouput (ENT must be mute)
        """
        errors_list = []

        Launcher.go_to_home()
        Media.open_media()
        Media.select_audio_source(Media.MEDIA_RADIO_SOURCE_ID)

        mute_icon = self.test.driver.find_element(*TopBar.MUTE_ICON_ID)
        mute_icon_bounds = utils.get_elem_bounds_detail(mute_icon, crop_region=True)
        # Validate audio icon on status bar
        result, error = self.validate_status_bar_audio_icon(
            audio_status="unmuted", test_name="test_008_expect_unmute", mute_icon_bounds=mute_icon_bounds
        )

        # Press Mute Button
        set_mute_status(self.test.mtee_target, self.test.driver, action="MUTE")
        # Validate audio icon on status bar
        result, error = self.validate_status_bar_audio_icon(
            audio_status="muted", test_name="test_008_expect_mute_before_reboot", mute_icon_bounds=mute_icon_bounds
        )
        if result is False:
            errors_list.append(
                f"Audio icon is not muted as expected (before reboot), result: '{result}', error: '{error}'"
            )
        # Restart target
        self.mtee_utils.restart_target_and_driver(self.test)

        mute_icon = self.test.driver.find_element(*TopBar.MUTE_ICON_ID)
        mute_icon_bounds = utils.get_elem_bounds_detail(mute_icon, crop_region=True)
        # Validate audio icon on status bar
        result, error = self.validate_status_bar_audio_icon(
            audio_status="muted", test_name="test_008_expect_mute_after_reboot", mute_icon_bounds=mute_icon_bounds
        )
        if result is False:
            errors_list.append(
                f"Audio icon is not muted as expected (after reboot), result: '{result}', error: '{error}'"
            )
        # Assert at the end to complete the sequence and record mute and unmute state
        assert_false(errors_list, "\n".join(errors_list))
