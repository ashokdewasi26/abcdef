# Copyright (C) 2022. BMW CTW PT. All rights reserved.
"""PWF tests SysMan GEN22"""

import logging
import os
import re
import time
from unittest import SkipTest

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import require_environment, require_environment_setup, TEST_ENVIRONMENT
from mtee.testing.tools import assert_false, assert_less_equal, assert_true, metadata
from selenium.webdriver.support import expected_conditions as ec
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.common.pages.base_page import BasePage
from si_test_apinext.idc23.pages.connectivity_page import ConnectivityPage as Connect
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.media_page import MediaPage as Media
from si_test_apinext.testing.test_base import TestBase
from si_test_apinext.util.global_steps import GlobalSteps
from tee.target_common import VehicleCondition
from tee.tools.lifecycle import LifecycleFunctions

lf = LifecycleFunctions()
logger = logging.getLogger(__name__)
target = TargetShare().target

MAX_TIME_TO_DISPLAY_GOODBYE_SCREEN = 15
MAX_TIME_TO_STOP_BUSSES = 10
MAX_TIME_APP_SHUTDOWN = 40
MAX_TIME_SYSTEM_SHUTDOWN = 4
MAX_TIME_TO_ENTER_SLEEP_WITH_BUS_SLEEP = MAX_TIME_TO_STOP_BUSSES + MAX_TIME_APP_SHUTDOWN + MAX_TIME_SYSTEM_SHUTDOWN
MAX_TIME_TO_ENTER_SLEEP_WITH_GOODBYE_SCREEN = (
    MAX_TIME_TO_DISPLAY_GOODBYE_SCREEN + MAX_TIME_APP_SHUTDOWN + MAX_TIME_SYSTEM_SHUTDOWN
)

MSG_STATE = ".*update.*PWF_status.*{}.*"

REQUIREMENTS = (TEST_ENVIRONMENT.target.hardware.gen22,)


@require_environment(*REQUIREMENTS)
@metadata(
    testsuite=["domain", "SI", "SI-android"],
    component="lifecycle",
    domain="SYSMAN",
    traceability={"MGU": {"MGUJIRA": ["SIT-323", "SIT-324", "SIT-1324", "SIT-1394", "SIT-1709"]}},
)
class TestParkingState:
    """Parking mode tests"""

    can_timestamp = re.compile(r"\(\d+\-\d+\-\d+ \d+\:\d+\:(.*?)\)")
    can_rx_timestamp = re.compile(r"\(\d+\-\d+\-\d+ \d+\:\d+\:(.*?)\)  can\d  RX")
    can_file = os.path.join(target.options.result_dir, "can0.asc")
    test = None

    @classmethod
    @require_environment_setup(*REQUIREMENTS)
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

    def setup(self):
        lf.set_default_vehicle_state()
        if not lf.is_alive():
            lf.wakeup_target(True)
            # If not alive produce hard reboot:
            if not lf.is_alive():
                target.reboot(prefer_softreboot=False)
        target.wait_for_nsm_fully_operational()

    @classmethod
    def teardown_class(cls):
        cls.test.quit_driver()
        cls.test.mtee_target.switch_vehicle_to_state(VehicleCondition.FAHREN)
        cls.test.mtee_target.wakeup_from_sleep()
        lf.setup_keepalive()
        cls.test.mtee_target.resume_after_reboot()

    def living_driving(self, vehicle_condition, vehicle_message):
        """SYSMAN - Lifecycle test scenarios - NM PWF states - LivingDriving

        **Preconditions**
            #.ECU alive
            #.NM3 messages keep a PN, which the ECU is a member of, awake
        **Required Steps**
            * Switch to each of the following conditions
                #.VehicleCondition = PRUEFEN_ANALYSE_DIAGNOSE ||
                #.VehicleCondition = WOHNEN ||
                #.VehicleCondition = FAHREN ||
                #.VehicleCondition = FAHRBEREITSCHAFT_HERSTELLEN
            * Stop keep alive message if rse22 (BCP simulation)
            * Await Timeout
        **Expected outcome**
            ECU stays alive
            if RSE, ECU won't stay alive
        """
        # Preconditions checks
        logger.debug("PWF LivingDriving test - Testing message : %s", vehicle_message)
        assert_true(lf.is_alive(), "Ecu not alive before test")
        # NM3 messages keep a PN, which the ECU is a member of, awake in testrack env:
        if target.has_capability(TEST_ENVIRONMENT.test_bench.rack):
            lf.nm3_start_standfunktion()
        lf.set_state_and_verify_message(
            VehicleCondition.STANDFUNKTIONEN_KUNDE_NICHT_IM_FZG,
            MSG_STATE.format("STANDFUNKTIONEN"),
            stop_nm3_senders=False,
        )
        lf.set_state_and_verify_message(vehicle_condition, vehicle_message)
        if target.options.target == "rse22":
            lf.set_lifecycle_rear_entertainment_in_vcar(False)
            target.prepare_for_reboot()
            if not target.has_capability(TEST_ENVIRONMENT.test_bench.rack):
                lf.stop_keepalive()  # Target will be in NORMAL OPERATION MODE (except RSE22)
            assert_true(
                lf.ecu_to_enter_sleep(timeout=MAX_TIME_TO_ENTER_SLEEP_WITH_BUS_SLEEP),
                "PWF LivingDriving test - RSE22 Target is not in sleep in {} seconds after setting {} ".format(
                    MAX_TIME_TO_ENTER_SLEEP_WITH_BUS_SLEEP, vehicle_condition.name
                ),
            )
        else:
            assert_false(
                lf.ecu_to_enter_sleep(timeout=MAX_TIME_TO_ENTER_SLEEP_WITH_GOODBYE_SCREEN),
                "PWF LivingDriving test - Target is in sleep in {} seconds after setting vehicle in {}".format(
                    MAX_TIME_TO_ENTER_SLEEP_WITH_GOODBYE_SCREEN, vehicle_condition.name
                ),
            )

    def get_last_log_secs_from_can_log_file(self, only_receive=False):
        """Read can_file and return last timestamp seconds
        :param bool only_receive: check can log with RX (from mgu22 to can logger)
        :rtype float
        """
        with open(self.can_file, "r") as f:
            logs = f.read().splitlines()
            if only_receive:
                for log in logs[::-1]:
                    if self.can_rx_timestamp.findall(log):
                        return float(self.can_timestamp.findall(log)[0])
            else:
                ret = self.can_timestamp.findall(logs[-1])
                if ret:
                    return float(ret[0])
        logger.error("Can log not found")
        raise AssertionError("Failed to find can log in {}".format(self.can_file))

    def can_keep_alive(self):
        """SYSMAN - Can Keep Alive

        **Pre-conditions**
            * ECU is alive

        **Steps**
            * Stop NM3 messages
            * Set Vehicle to PAD state
            * Set I&K CAN messages with valid PN for target
            * Disable SomeIP / Ethernet CAN messages
            * Set Standfunktionen State 3 times

        **Expected Outcome**
            * After 2 seconds target stops sending CAN messages
        """
        if not target.can_loggers:
            raise SkipTest("Skip can_keep_alive_tests - no connector CAN initialized.")
        assert_true(lf.is_alive(), "Ecu not alive before test")

        lf.stop_keepalive()
        target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)

        if TargetShare().vcar_manager:
            # Disable SomeIp/Ethernet messages:
            TargetShare().vcar_manager.send('msg_set_on_change("20.00001531.8001.02", 0)')
            # Set CAN Valid PN: ENTERTAINMENTBETRIEB_FOND_EIN:
            TargetShare().vcar_manager.send("VehicleCondition.VehicleCondition.controlFunctionalPartialNetworks=2048")
            # Set I&K CAN:
            TargetShare().vcar_manager.send("IK.CTR_FKTN_PRTNT=2048")

        for _ in range(0, 3):
            target.switch_vehicle_to_state(VehicleCondition.STANDFUNKTIONEN_KUNDE_NICHT_IM_FZG)
            time.sleep(0.5)
        lf.stop_keepalive()
        logger.debug("Waiting 2 seconds before verifying CAN messages on CAN connector...")
        time.sleep(2)
        before_timestamp = self.get_last_log_secs_from_can_log_file()
        time.sleep(2)
        last_rx_timestasmp = self.get_last_log_secs_from_can_log_file(only_receive=True)
        assert_less_equal(
            last_rx_timestasmp,
            before_timestamp,
            "New Can logs were found after triggering sequence of can keep alive test and setting 3 times "
            "STANDFUNKTIONEN_KUNDE_NICHT_IM_FZG",
        )

    def check_element_presence(self, check_element_located):
        """
        Search the element in the present screen
        """
        self.test.wb.until(
            ec.presence_of_element_located(check_element_located),
            message=f"Unable to find element:'{check_element_located.selector}'",
        )

    def check_media_tel_apps(self):
        """
        Press AZV Connectivity, MEDIA and PHONE button, and validate after each click
        """
        Launcher.go_to_home()
        GlobalSteps.inject_custom_vhal_input(self.test.apinext_target, Connect.conn_vhal_event_keycode)
        utils.get_screenshot_and_dump(self.test, self.test.results_dir, "conn_vhal_event_keycode")
        connetivity_app_status = BasePage.check_visibility_of_first_and_second_elements(
            Connect.PAGE_TITLE_ID, Connect.PAGE_TITLE_ID_ML
        )
        assert_true(
            connetivity_app_status,
            "Failed to open connectivity app after telephone button press/release. "
            f"Either element {Connect.PAGE_TITLE_ID} or element "
            f"{Connect.PAGE_TITLE_ID_ML} were expected to be present after telephone operation ",
        )
        GlobalSteps.inject_key_input(self.test.apinext_target, Launcher.back_keycode)
        Launcher.validate_home_screen()
        Launcher.go_to_home()
        GlobalSteps.inject_custom_vhal_input(self.test.apinext_target, Media.media_vhal_event_keycode)
        self.check_element_presence(Media.MEDIA_BAR_ID)
        GlobalSteps.inject_key_input(self.test.apinext_target, Launcher.back_keycode)
        Launcher.validate_home_screen()
        Launcher.go_to_home()

    def test_001_living_driving_pad_to_parking(self):
        """Lifecycle test scenarios with PWF states PAD and Parking

        Steps:
            Wakeup and keep awake IDC with PWF state PAD
            Activate different applications like Navigation, Entertainment, etc.
            Change from PWF state PAD to Parken
            2 seconds after receiving the last CAN NM Message 0x510 from BCP the MGU/IDC
            must stop sending CAN CAN Messages like 0x43C and 0x43D

        """
        self.living_driving(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE, MSG_STATE.format("(PAD|DIAGNOSE)"))
        self.check_media_tel_apps()
        # setting  PAD to Parking
        if target.has_capability(TEST_ENVIRONMENT.test_bench.rack):
            target.switch_vehicle_to_state(VehicleCondition.PARKEN_BN_IO)
        else:
            lf.set_state_and_verify_message(VehicleCondition.PARKEN_BN_IO, MSG_STATE.format("PARKEN"))
        self.can_keep_alive()
