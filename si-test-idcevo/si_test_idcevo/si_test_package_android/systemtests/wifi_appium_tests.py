# Copyright (C) 2025. BMW CTW PT. All rights reserved.
import configparser
import logging

from pathlib import Path

from mtee.testing.tools import assert_false, assert_true, metadata

import si_test_idcevo.si_test_helpers.test_helpers as utils
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.pages.idcevo.connectivity_page import ConnectivityPage as Connectivity
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class TestWifiAppium:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(enable_appium=True, root=True)
        wait_for_application_target(cls.test.mtee_target)
        cls.test.start_recording()

    @classmethod
    def teardown_class(cls):
        video_name = "WifiAppium"
        cls.test.stop_recording(video_name)
        cls.test.teardown_base_class()

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI", "SI-android"],
        component="tee_idcevo",
        domain="Connectivity",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
    )
    def test_01_turn_off_wifi_via_cardomain_ui(self):
        """
        Turn OFF the wifi via appium
        """
        Connectivity.turn_off_wifi_ui()

        wifi_state = Connectivity.check_wifi_state_ui()
        utils.get_screenshot_and_dump(self.test, self.test.results_dir, "turn_off_wifi_via_ui")
        assert_false(wifi_state, "Unable to turn off wifi")

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI", "SI-android"],
        component="tee_idcevo",
        domain="Connectivity",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
    )
    def test_02_turn_on_wifi_via_cardomain_ui(self):
        """
        Turn ON the wifi via appium
        """
        Connectivity.turn_on_wifi_ui()

        wifi_state = Connectivity.check_wifi_state_ui()
        utils.get_screenshot_and_dump(self.test, self.test.results_dir, "turn_on_wifi_via_ui")
        assert_true(wifi_state, "Unable to turn on wifi")
