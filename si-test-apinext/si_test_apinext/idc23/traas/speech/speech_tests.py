import logging
import os
import subprocess
import time
from pathlib import Path
from unittest import skipIf

import si_test_apinext.util.driver_utils as utils
from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.test_environment import require_environment, require_environment_setup
from mtee.testing.tools import retry_on_except
from si_test_apinext.idc23 import AUDIO_SAMPLES_PATH
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.network_dev_tools_page import NetworkDevToolsPage
from si_test_apinext.idc23.pages.personal_assistant_page import PersonalAssistantPage
from si_test_apinext.idc23.pages.settings_app_page import SettingsAppPage
from si_test_apinext.testing.test_base import TestBase
from si_test_apinext.util.hmi_helper import HMIhelper
from si_test_apinext.util.mtee_utils import MteeUtils

logger = logging.getLogger(__name__)


REQUIREMENTS = (TE.target_type.hu, TE.test_bench.rack)
VIDEO_NAME = "TestSpeech"

real_phone_present = bool(TestBase.get_android_serial_id(config_var_name="ext-real-phone-android-serial"))
logger = logging.getLogger(__name__)
target = TargetShare().target


@require_environment(*REQUIREMENTS)
class TestSpeech:
    mtee_log_plugin = True

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.mtee_util = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        cls.mtee_util.change_language("en_GB")
        cls.mtee_util.connect_to_internet(cls.test)
        cls.hmihelper = HMIhelper(cls.test)

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def teardown_class(cls):
        cls.test.quit_driver()

    @utils.gather_info_on_fail
    def setup(self):
        utils.pop_up_check(self.test)
        utils.ensure_no_alert_popup(self.test.results_dir, self.test.driver, self.test.apinext_target)
        Launcher.go_to_home()
        utils.start_recording(self.test)

    def teardown(self):
        utils.stop_recording(self.test, "Speech_test")

    def play_audio_file(self, audio_file):
        """Play audio file on worker speakers

        :param audio_file: path to audio file
        :type audio_file: path
        :raises AssertionError: In case file doesn't exist
        """
        if not audio_file or not Path(audio_file).exists():
            raise AssertionError(f"Given audio file don't exist: '{str(audio_file)}'")
        logger.info(f"Going to play: {audio_file}")
        cmd = ["/usr/bin/play", audio_file]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return

    @skipIf(not real_phone_present, "Test only applicable for test racks with Real Phone present")
    @utils.gather_info_on_fail
    @retry_on_except(retry_count=1)
    def test_000_01_language_precondition(self):
        """Speech precondition 01: Assistant status installed"""
        PersonalAssistantPage.ensure_language_package_installed()

    @skipIf(not real_phone_present, "Test only applicable for test racks with Real Phone present")
    @utils.gather_info_on_fail
    @retry_on_except(retry_count=1)
    def test_000_02_speech_precondition(self):
        """Speech precondition 02: Assistant active and Personal assistant setup done"""
        PersonalAssistantPage.ensure_voice_control_active(self.hmihelper)

    @skipIf(not real_phone_present, "Test only applicable for test racks with Real Phone present")
    @utils.gather_info_on_fail
    def test_000_03_wave_precondition(self):
        """Speech precondition 03: Validate wave status"""
        NetworkDevToolsPage.validate_wave_status_connected()

    @skipIf(not real_phone_present, "Test only applicable for test racks with Real Phone present")
    @utils.gather_info_on_fail
    @retry_on_except(retry_count=1)
    def test_001_speech_open_settings(self):
        """Speech test 01: Play 'Hey BMW, open settings' and validate"""
        # Speech seems to lag the system and not be ready right away
        # These next steps are useless, but are done to kind of cool down the system and
        # have a feeling about how laggy it is
        Launcher.open_all_apps_from_home()
        time.sleep(1)
        Launcher.go_to_home()
        time.sleep(3)
        utils.pop_up_check(self.test)
        utils.ensure_no_alert_popup(self.test.results_dir, self.test.driver, self.test.apinext_target)
        time.sleep(1)
        filename = os.path.join(AUDIO_SAMPLES_PATH, "Hey_BMW_Open_Settings.wav")
        self.play_audio_file(filename)
        # Wait for System settings to open
        time.sleep(3)
        utils.take_apinext_target_screenshot(self.test.apinext_target, self.test.results_dir, "Hey_BMW_Open_Settings")
        title = SettingsAppPage.check_visibility_of_element(SettingsAppPage.STATUSBAR_TITLE)
        time.sleep(1)
        assert title.text == "SYSTEM SETTINGS"
