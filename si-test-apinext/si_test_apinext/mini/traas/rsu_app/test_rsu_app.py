# Copyright (C) 2022. BMW Car IT. All rights reserved.
import logging
import time

from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import assert_process_returncode, metadata
from si_test_apinext.mini.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.mini.pages.rsu_page import RSUPage
from si_test_apinext.mini.pages.settings_app_page import SettingsAppPage as Settings
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.global_steps import GlobalSteps
from si_test_apinext.util.mtee_utils import MteeUtils

logger = logging.getLogger(__name__)
target = TargetShare().target


@metadata(testsuite=["SI"])
class TestRSU:
    mtee_log_plugin = True
    rsu_config = "/opt/node1/rootfs/etc/rsu/rsu-config.json"
    # RSU config file for testing purposes
    rsu_test_config = "/var/data/rsu-shared/rsu-config-test.json"

    @classmethod
    def setup_class(cls):
        # TestBase is a singleton class to re-use appium driver and target vars
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.mtee_utils = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        ret = cls.test.mtee_target.execute_command(f"cp {cls.rsu_config} {cls.rsu_test_config}")
        assert_process_returncode(
            0, ret.returncode, f"Failed to copy file: {cls.rsu_config} into {cls.rsu_test_config}. Result: {ret}"
        )
        cls.mtee_utils.restart_target_and_driver(cls.test)
        utils.start_recording(cls.test)

    @classmethod
    def teardown_class(cls):
        utils.stop_recording(cls.test, "RSU_APP")
        logger.info("Removing uploaded rsu config test file")
        cls.test.mtee_target.execute_command(["rm", "-rf", cls.rsu_test_config])
        cls.test.quit_driver()

    @utils.gather_info_on_fail
    def test_001_check_app_rsu_is_available(self):
        """
        Check RSU App is available
        In this test case we expect that "Remote Software Upgrade" option is available under system settings.

        Precondition:
         - /var/data/rsu-shared/rsu-config-test.json file should be available.
         - Provisioning should be enabled. Checking by opening navigation

        Traceability: ABPI-63672, ABPI-176826


        *Steps*
        1. Go to Settings
        2. Click on start RSU app
        2. Check RSU app is open

        """
        Launcher.go_to_home()
        Settings.launch_settings_activity()
        # Press back two times to deal with the scenario of the settings app being left on some
        # sub settings menu
        GlobalSteps.inject_key_input(self.test.apinext_target, Settings.back_keycode)
        time.sleep(1)
        GlobalSteps.inject_key_input(self.test.apinext_target, Settings.back_keycode)
        time.sleep(1)
        Settings.launch_settings_activity()
        # Scroll until RSU option is found
        rsu_app_btn = self.test.driver.find_element(*Settings.START_RSU_BUTTON)
        GlobalSteps.click_button_and_expect_elem(self.test.wb, rsu_app_btn, RSUPage.CONTAINER_ID)
        package = GlobalSteps.get_package_running(self.test.driver)
        Launcher.go_to_home()
        assert package == RSUPage.RSU_PACKAGE_NAME, f"Package running {package}"
