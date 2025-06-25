# Copyright (C) 2024-2025. BMW Group. All rights reserved.
import configparser
import logging
import time
from pathlib import Path
from unittest import skipIf

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT
from mtee.testing.tools import assert_true, metadata

from si_test_idcevo.si_test_helpers import test_helpers as utils
from si_test_idcevo.si_test_helpers.android_helpers import ensure_launcher_page
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.apinext_target_handlers import LIST_MAIN_DISPLAY_ID
from si_test_idcevo.si_test_helpers.pages.idcevo.audio_page import AudioSettingsPage as Audio
from si_test_idcevo.si_test_helpers.reboot_handlers import (
    reboot_and_wait_for_android_target,
    wait_for_application_target,
)

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

target = TargetShare().target

DISPLAY_ID = LIST_MAIN_DISPLAY_ID["idcevo"]


@skipIf(
    target.has_capability(TEST_ENVIRONMENT.test_bench.rack),
    "Test class only applicable for standalone IDCevo",
)
class TestAudioSettingsEvo:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(enable_appium=False)

        # Setup the necessary simulation signals
        cls.send_vehicle_setup_signals()
        time.sleep(5)
        reboot_and_wait_for_android_target(cls.test)
        cls.test.setup_base_class(enable_appium=True, root=True)
        cls.test.apinext_target.wait_for_boot_completed_flag()
        wait_for_application_target(cls.test.mtee_target)

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    @classmethod
    def vcar_send(cls, payload):
        try:
            cls.test.vcar_manager.send(payload)
        except (RuntimeError, UnicodeDecodeError) as e:
            logger.info(f"Vcar error {e} sending {payload}")

    @classmethod
    def send_vehicle_setup_signals(cls):
        # From disabling emergency signals, valet mode
        # to potentially provisioning
        # quotes inside string must be escaped as in the example below:
        # vcar_command =
        # f"UserAccounts.accountsInfo.0 = \"Example\\\"Quoted\\\"String\""

        cls.vcar_send("DriverAttentionControlStatus.statusBreakRecommendation.recommendationStatus = 0")

        cls.vcar_send("AccountController.valetModeStatus.activated = 0")

        cls.vcar_send("AccountControllerBasic.valetModeStatus.activated = 0")

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-android"],
        component="None",
        domain="Audio Infrastructure",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
    )
    def test_001_change_equalizer_settings(self):
        """
        [SIT_Automated] Change Equalizer Settings

        Steps:
            1. Open Audio Settings app
            2. Open Equalizer
            3. Click '-' on Bass
            4. Click 3x '+' on Treble

        Expected outcome:
            1. Check elements are available and clickable
            2. Check value is reflected on AudioControllerHal logs
        """

        ensure_launcher_page(self.test)
        # Open Audio App
        Audio.start_activity()
        time.sleep(2)
        self.test.take_apinext_target_screenshot(self.test.results_dir, "001_001_audio_app", DISPLAY_ID)

        # Open Equalizer Pop-Up
        equalizer_clicked = Audio.open_equalizer()
        self.test.take_apinext_target_screenshot(self.test.results_dir, "001_002_click Equalizer", DISPLAY_ID)
        assert_true(equalizer_clicked, "Failed to open Equalizer settings")

        # Click Minus Bass button
        bass_minus_clicked = Audio.change_bass()
        self.test.take_apinext_target_screenshot(self.test.results_dir, "001_003_click Bass Minus x1", DISPLAY_ID)
        assert_true(bass_minus_clicked, "Failed to change Bass to -1")

        # Click Plus Treble button
        treble_plus_clicked = Audio.change_treble()
        self.test.take_apinext_target_screenshot(self.test.results_dir, "001_004_click Treble Plus x3", DISPLAY_ID)
        assert_true(treble_plus_clicked, "Failed to change Treble to +3")

        # Close Equalizer Pop-Up
        Audio.close_popup()
        self.test.take_apinext_target_screenshot(self.test.results_dir, "001_005_close Pop-Up", DISPLAY_ID)

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-android"],
        component="None",
        domain="Audio Infrastructure",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
    )
    def test_002_change_balance_fader_settings(self):
        """
        [SIT_Automated] Change Balance and Fader Settings

        Steps:
            1. Open Audio Settings app
            2. Open Balance and Fader
            3. Click 2x '-' on Balance
            4. Click 2x '+' on Fader

        Expected outcome:
            1. Check elements are available and clickable
            2. Check value is reflected on AudioControllerHal logs
        """

        self.test.start_recording()

        # Open Audio App
        Audio.start_activity()
        time.sleep(2)
        self.test.take_apinext_target_screenshot(self.test.results_dir, "002_001_audio_app", DISPLAY_ID)

        # Open Balancer Fader Pop-Up
        bal_fader_clicked = Audio.open_balance_fader()
        self.test.take_apinext_target_screenshot(self.test.results_dir, "002_002_click Balance and Fader", DISPLAY_ID)

        self.test.stop_recording("click_balance_fader")

        assert_true(bal_fader_clicked, "Failed to open Balance and Fader settings")

        # Click Minus Balance button
        balance_left_clicked = Audio.change_balance()
        self.test.take_apinext_target_screenshot(self.test.results_dir, "002_003_click Balance Minus x2", DISPLAY_ID)
        assert_true(balance_left_clicked, "Failed to change Bass to -2")

        # Click Plus Fader button
        fader_down_clicked = Audio.change_fader()
        self.test.take_apinext_target_screenshot(self.test.results_dir, "002_004_click Fader Plus x2", DISPLAY_ID)
        assert_true(fader_down_clicked, "Failed to change Fader to +2")

        # Close Pop-Up
        Audio.close_popup()
        self.test.take_apinext_target_screenshot(self.test.results_dir, "002_005_close Pop-Up", DISPLAY_ID)

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-android"],
        component="None",
        domain="Audio Infrastructure",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
    )
    def test_003_change_speed_volume_settings(self):
        """
        [SIT_Automated] Change Speed Volume Settings

        Steps:
            1. Open Audio Settings app
            2. Open Volume Speed
            3. Click on High

        Expected outcome:
            1. Check elements are available and clickable
            2. Check value is reflected on AudioControllerHal logs
        """

        # Open Audio App
        Audio.start_activity()
        time.sleep(2)
        self.test.take_apinext_target_screenshot(self.test.results_dir, "003_001_audio_app", DISPLAY_ID)

        # Open Speed Volume Pop-Up
        speed_vol_clicked = Audio.open_speed_volume()
        self.test.take_apinext_target_screenshot(self.test.results_dir, "003_002_click Speed Volume", DISPLAY_ID)
        assert_true(speed_vol_clicked, "Failed to open Speed Volume settings")

        # Click High Volume Button
        speed_high_clicked = Audio.change_speed_volume()
        self.test.take_apinext_target_screenshot(self.test.results_dir, "003_003_click High", DISPLAY_ID)
        assert_true(speed_high_clicked, "Failed to change to High")

        # Close Pop-Up
        Audio.close_popup()
        self.test.take_apinext_target_screenshot(self.test.results_dir, "003_004_close Pop-Up", DISPLAY_ID)

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-android"],
        component="None",
        domain="Audio Infrastructure",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
    )
    def test_004_change_volume_normalization(self):
        """
        [SIT_Automated] Change Volume Normalization

        Steps:
            1. Open Audio Settings app
            2. Toggle Volume Normalization

        Expected outcome:
            1. Check elements are available and clickable
            2. Check value is reflected on AudioControllerHal logs
        """

        # Open Audio App
        Audio.start_activity()
        time.sleep(2)
        self.test.take_apinext_target_screenshot(self.test.results_dir, "004_001_audio_app", DISPLAY_ID)

        # Open Speed Volume Pop-Up
        speed_vol_clicked = Audio.toggle_volume_normalization()
        self.test.take_apinext_target_screenshot(
            self.test.results_dir, "004_002 Toggle Volume Normalization", DISPLAY_ID
        )
        assert_true(speed_vol_clicked, "Failed to toggle Volme Normalization settings")
