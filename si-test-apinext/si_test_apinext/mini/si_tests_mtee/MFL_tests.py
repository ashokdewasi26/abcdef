import logging
import os
import re
import time
from unittest import skip
from unittest.case import TestCase

import si_test_apinext.util.driver_utils as utils
from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import assert_true
from mtee.testing.tools import TimeoutError as MteeTimeoutError
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.common.pages.base_page import BasePage
from si_test_apinext.mini import REF_IMAGES_PATH
from si_test_apinext.mini.pages.connectivity_page import ConnectivityPage
from si_test_apinext.mini.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.mini.pages.media_page import MediaPage
from si_test_apinext.testing.test_base import TestBase
from si_test_apinext.util.global_steps import GlobalSteps
from si_test_apinext.util.screenshot_utils import (
    capture_screenshot,
    compare_snapshot,
    extract_text,
    take_ic_screenshot_and_extract,
)

logger = logging.getLogger(__name__)


class TestMFL(TestCase):
    # https://asc.bmwgroup.net/wiki/display/APINEXT/Mapping+of+KEYCODEs+in+bmw-input-service
    # https://asc.bmwgroup.net/wiki/display/APINEXT/MFL+integration

    ref_images_path = REF_IMAGES_PATH

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.vcar_manager = TargetShare().vcar_manager
        utils.start_recording(cls.test)
        Launcher.turn_on_bluetooth()

    @classmethod
    def teardown_class(cls):
        utils.stop_recording(cls.test, "MFL_tests")
        Launcher.go_to_home()
        cls.test.quit_driver()

    def __wait_for_dlt(self, dlt_detector, dlt_msg, assert_msg, timeout=30, default_apid="AUDI", default_ctid="DEF"):
        try:
            dlt_detector.wait_for(
                {"apid": default_apid, "ctid": default_ctid, "payload_decoded": dlt_msg},
                timeout,
                raise_on_timeout=True,
            )
        except MteeTimeoutError:
            logging.debug(assert_msg)
            raise AssertionError(assert_msg)

    @skip("Test requires RAM ECU. Skipping for test farm environment.")
    def test_000_thumbwheel_buttons(self):
        """
        Thumbwheel Buttons Event

        *Background information*

        This test case verifies the following functionality of HLF : IDC22PM-4300
        * In this test case, it's tested the Thumbwheel Button Press ( Left/Right/Up/Down/Enter)

        *Pre-Condition*
        1. List must be selected, and be android content

        *Steps*
        1. Check elemet selected
        2. Send UP event
        3. Verify element selected is upper than previous
        4. Send Down event
        5. Verify element selected is lower than previous, and it's previous element
        6. Send Right event
        7. Verify element selected is at right position
        8. Send Left event
        9. Verify element selected is at left position, and it's previous element
        10. Send Enter event
        11. Verify application started

        """
        Launcher.go_to_home()
        media_button = self.test.driver.find_element(*Launcher.MEDIA_BUTTON_ID)
        GlobalSteps.click_button_and_expect_elem(self.test.wb, media_button, MediaPage.get_media_element_id())

        # alias(SteeringWheelPushButton.statusRotarySteps.operationStepsKnurlSteeringWheel, IK.OP_STEPS_KRL_STW)
        self.vcar_manager.send("IK.OP_STEPS_KRL_STW = 150")
        time.sleep(2)
        self.vcar_manager.send("IK.OP_STEPS_KRL_STW = 100")
        time.sleep(2)
        self.vcar_manager.send("IK.OP_STEPS_KRL_STW = 127")
        time.sleep(1)
        # alias(SteeringWheelPushButton.statusSearchSwitch1.operationPushButtonAudioAutomaticTuningSteeringWheel,
        # IK.OP_PUBU_SKP_STW)
        # Tilt left/right might not behaving as expected per HU22DM-11190 and HU22DM-14334
        self.vcar_manager.send("IK.OP_PUBU_SKP_STW = 1")
        time.sleep(2)
        self.vcar_manager.send("IK.OP_PUBU_SKP_STW = 2")
        time.sleep(2)
        self.vcar_manager.send("IK.OP_PUBU_SKP_STW = 0")
        time.sleep(1)
        # alias(SteeringWheelPushButton.statusRotaryPress.operationPushButtonKnurlSteeringWheel, IK.OP_PUBU_KRL_STW)
        self.vcar_manager.send("IK.OP_PUBU_KRL_STW = 1")
        time.sleep(1)
        self.vcar_manager.send("IK.OP_PUBU_KRL_STW = 0")

        # TODO: Validate selected elements.

    @skip("Media Popup when pressing MFL appears on Head-up display. Follow up on : ABPI-152522")
    @utils.gather_info_on_fail
    def test_001_media_button(self):
        """
        Media Button Event

        *Background information*

        This test case verifies the following functionality of HLF : IDC22PM-4300
        * In this test case, it's tested the Media Button Press.

        *Steps*
        1. Send Media Button Press Message
        2. Send Media Button Release Message
        3. Validate that CID stays in Launcher home page
        4. Validate that media menu opened on IC

        """
        Launcher.go_to_home()
        self.vcar_manager.send(
            "SteeringWheelPushButton.statusSpecialFunctionButton.operationPushButtonSpecialFunction = 1"
        )
        time.sleep(1)
        self.vcar_manager.send(
            "SteeringWheelPushButton.statusSpecialFunctionButton.operationPushButtonSpecialFunction = 0"
        )
        time.sleep(2)
        capture_screenshot(test=self.test, test_name="MFL_Mediabutton")
        self.test.wb.until(
            ec.visibility_of_element_located(Launcher.MEDIA_BUTTON_ID),
            "Unable to find Media Content after pressing MFL media button",
        )
        screenshot_path = os.path.join(self.test.results_dir, "after_release_Media_Button.png")
        take_ic_screenshot_and_extract(self.test.mtee_target, screenshot_path)
        mfl_media_text_box = 1350, 160, 1810, 300
        text = extract_text(screenshot_path, region=mfl_media_text_box)
        logger.info("Found text on IC Media Content after pressing MFL media button %s", text)
        self.assertRegex(text, r"^MEDIA.*RADIO", "Expected text did not match the actual IC text on Media button")

    def test_002_telephone_button(self):
        """
        Telephone Button Event

        *Background information*

        This test case verifies the following functionality of HLF : IDC22PM-4300
        * In this test case, it's tested the telephone Button Press.

        *Steps*
        1. Send Telephone Button Press Message
        2. Validate Telephone content appears
        3. Validate broadcasted message to
            com.bmwgroup.idnext.conectivity (com.bmwgroup.idnext.connectivity.action.BMW_STW_PHONE)
        """

        expected_broadcasts = [
            ("act", "com.bmwgroup.idnext.connectivity.action.BMW_STW_PHONE"),
            ("pkg", "com.bmwgroup.idnext.connectivity"),
        ]

        self.vcar_manager.send('run_async("steering_wheel_phone")')

        utils.get_screenshot_and_dump(self.test, self.test.results_dir, "steering_wheel_phone")
        connetivity_app_status = BasePage.check_visibility_of_first_and_second_elements(
            ConnectivityPage.CONN_DISC_FRAG_ID, ConnectivityPage.CONN_DISC_FRAG_ID_ML
        )
        assert_true(
            connetivity_app_status,
            "Failed to open connectivity app after telephone button press/release. "
            f"Either element {ConnectivityPage.CONN_DISC_FRAG_ID} or element "
            f"{ConnectivityPage.CONN_DISC_FRAG_ID_ML} were expected to be present after telephone operation ",
        )
        result = self.test.apinext_target.execute_command(
            "dumpsys activity broadcasts | grep BMW_STW_PHONE | grep -v '#'"
        )
        regex = re.compile(r"(?P<type>act|pkg)=(?P<intent>[\w\.]+)")

        matches = regex.findall(result.stdout.decode())
        logger.info("Observed broadcasts: %s", matches)

        self.assertListEqual(
            expected_broadcasts, matches, "Observed BMW STW PHONE broadcasts do not match the expected"
        )

    def test_003_ptt_button(self):
        """
        PTT Button Event

        *Background information*

        This test case verifies the following functionality of HLF : IDC22PM-4300
        * In this test case, it's tested the PTT Button Press.

        *PTT behaviour is described in Android CDD
            https://source.android.com/devices/automotive/voice/
        ... voice_interaction_guide/integration_flows#ptt-triggering
            -Short Press: must start a new voice session
            -Long Press: should be handled first by Android Auto or Carplay then to Bluetooth connected devices,
                and finally to local VIA (Voice Interaction Assistante)
        *Long Press is defined in code implementation 1000 ms as LONG_PRESS_TIME_MS at
            https://android.googlesource.com/platform/packages/services/Car/+/
        ... android-o-mr1-iot-release-1.0.4/service/src/com/android/car/CarInputService.java

        *Steps*
        1. Send PTT Button Press Message
        2. Wait 2 seconds
        3. Send PTT Button Release Message
        4. Verify Voice content appears (Android auto/Bluetooth)
        5. Send PTT Button Press Message
        6. Wait 0.5 seconds
        7. Send PTT Button Release Message
        8. Verify broadcast KeyLongPress broadcast messages regarding steps 1-7
            - Info: https://asc.bmwgroup.net/wiki/pages/viewpage.action?pageId=566949967
        """
        #   From https://asc.bmwgroup.net/wiki/pages/viewpage.action?pageId=566949967 we got:
        Launcher.go_to_home()
        key_long_press_broadcast = "com.bmwgroup.idnext.connectivity.action.SPEECH_PTT_LONG_PRESS"
        pkg_broadcast = "com.bmwgroup.idnext.connectivity"

        permission_broadcast = "com.bmwgroup.idnext.connectivity.permission.SEND_CONN_INT"

        expected_broadcasts = [
            ("act", key_long_press_broadcast),
            ("pkg", pkg_broadcast),
            ("permission", permission_broadcast),
        ]

        self.vcar_manager.send("SteeringWheelPushButton.statusPTTButton1.operationPushButtonPTTSteeringWheel = 1")
        time.sleep(2)
        self.vcar_manager.send("SteeringWheelPushButton.statusPTTButton1.operationPushButtonPTTSteeringWheel = 0")
        utils.get_screenshot_and_dump(self.test, self.test.results_dir, "ptt_button")
        connetivity_app_status = BasePage.check_visibility_of_first_and_second_elements(
            ConnectivityPage.CONN_DISC_FRAG_ID, ConnectivityPage.CONN_DISC_FRAG_ID_ML
        )
        assert_true(
            connetivity_app_status,
            "Failed to open connectivity app after ptt button press/release. "
            f"Either element {ConnectivityPage.CONN_DISC_FRAG_ID} or element "
            f"{ConnectivityPage.CONN_DISC_FRAG_ID_ML} were expected to be present after ptt operation ",
        )

        self.vcar_manager.send('run_async("steering_wheel_ptt")')
        time.sleep(2)
        dumpsys_broadcast = self.test.apinext_target.execute_command(
            "dumpsys activity broadcasts | grep -E 'SPEECH|SEND_CONN_INT' | grep -v '#'"
        )
        # Logging to analyse if failure occurs in future
        logger.info("Observed activity broadcasts: %s", dumpsys_broadcast.stdout.decode())
        regex = re.compile(r"(?P<type>act|pkg|[Pp]ermission)=(?P<intent>[\w\.]+)")

        # Broadcast have act, pkg and permission for long PTT press
        actual_broadcasts = list(set(regex.findall(dumpsys_broadcast.stdout.decode())))
        logger.info("Observed broadcasts %s", actual_broadcasts)

        assert_true(
            all(item in set(actual_broadcasts) for item in expected_broadcasts),
            "Observed SPEECH broadcasts do not match the expected",
        )
        Launcher.go_to_home()

    @skip("MINI it is not expected to have the config button")
    def test_004_config_button(self):
        """
        Config Button Event

        *Background information*

        This test case verifies the following functionality of HLF : IDC22PM-4300
        * In this test case, it's tested the telephone Config Press.

        *Steps*
        1. Send Config Button Press Message
        2. Wait 1 seconds
        3. Send Config Button Release Message
        4. Verify action on Kombi display or in IC-HMI display
        5. Verify CBS is displayed
        6. Verify CBS text content
        """

        config_cbs_box = 1260, 300, 1800, 390
        config_cbs_text_box = 1240, 390, 1805, 450
        screenshot_path = os.path.join(self.test.results_dir, "post_pressing_fav_mfl_button.png")
        self.vcar_manager.send("SteeringWheelPushButton.operationSteerWheelFAV.operationSteerWheelFAV = 1")
        time.sleep(1)
        self.vcar_manager.send("SteeringWheelPushButton.operationSteerWheelFAV.operationSteerWheelFAV = 0")

        try:
            time.sleep(2)
            take_ic_screenshot_and_extract(self.test.mtee_target, screenshot_path)
            capture_screenshot(test=self.test, test_name="MFL_fav_button")
            # check text elements
            text = extract_text(screenshot_path, region=config_cbs_text_box)
            logger.info("Found text on IC after config MFL press %s", text)
            self.assertRegex(text, r"^CONTENT LAYOUT.*HEAD-UP", "Expected text did not match the actual IC text")

            # check image element
            reference_image = os.path.join(self.ref_images_path, "MFL_config_cbs.png")
            result, error = compare_snapshot(
                screenshot_path, reference_image, "MFL_config_cbs", fuzz_percent=2, region=config_cbs_box
            )
            if not result:
                raise AssertionError(
                    f"Error checking config CBS on IC.{screenshot_path} not equal to reference MFL_config_cbs.png"
                )
        finally:
            self.vcar_manager.send("SteeringWheelPushButton.operationSteerWheelFAV.operationSteerWheelFAV = 1")
            time.sleep(1)
            self.vcar_manager.send("SteeringWheelPushButton.operationSteerWheelFAV.operationSteerWheelFAV = 0")

    def test_005_volume_buttons(self):
        """
        Volume Buttons Event - Check through DLT

        Needs to be updated in the future to validate on HMI/Android and not DLT
        *Background information*

        This test case verifies the following functionality of HLF : IDC22PM-4300
        * In this test case, it's tested the Volume Buttons Press ( volume increase and decrease).

        *Steps*
        1. Send Volume Increase Press Message
        2. Verify DLT message for volume up
        3. Send Volume Decrease Press Message
        4. Verify DLT message for volume down
        """
        # TODO: Validate on HMI/Android level

        volume_up_message = "CAmCommandReceiver::volumeStep sinkID= 1 volumeStep= 1"
        volume_down_message = "CAmCommandReceiver::volumeStep sinkID= 1 volumeStep= -1"
        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("AUDI", "DEF")]) as dlt_detector:
            self.vcar_manager.send('run_async("steering_wheel_volume_up")')
            # Validate data received
            self.__wait_for_dlt(dlt_detector, volume_up_message, f"{volume_up_message} message was not found")

            self.vcar_manager.send('run_async("steering_wheel_volume_down")')
            # Validate data received
            self.__wait_for_dlt(dlt_detector, volume_down_message, f"{volume_down_message} message was not found")
