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
from si_test_apinext.common.pages.base_page import BasePage
from si_test_apinext.idc23 import MFL_REF_IMG_PATH
from si_test_apinext.idc23.pages.connectivity_page import ConnectivityPage
from si_test_apinext.idc23.pages.display_settings_page import DisplaySettingsAppPage as DisplaySet
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.media_page import MediaPage
from si_test_apinext.idc23.traas.bluetooth.helpers.bluetooth_utils import BluetoothUtils
from si_test_apinext.testing.test_base import TestBase
from si_test_apinext.util.global_steps import GlobalSteps
from si_test_apinext.util.screenshot_utils import compare_snapshot, extract_text, take_ic_screenshot_and_extract
from si_test_apinext.util.mtee_utils import MteeUtils

logger = logging.getLogger(__name__)


class TestMFL(TestCase):
    # https://asc.bmwgroup.net/wiki/display/APINEXT/Mapping+of+KEYCODEs+in+bmw-input-service
    # https://asc.bmwgroup.net/wiki/display/APINEXT/MFL+integration

    mfl_ref_img_path = MFL_REF_IMG_PATH

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.bluetooth_utils = BluetoothUtils(cls.test)
        cls.mtee_util = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        cls.vcar_manager = TargetShare().vcar_manager
        cls.mtee_util.change_language("en_GB")
        utils.start_recording(cls.test)
        cls.bluetooth_utils.turn_on_bluetooth_via_adb_commands()

    @classmethod
    def teardown_class(cls):
        utils.stop_recording(cls.test, "MFL_tests")
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
        GlobalSteps.click_button_and_expect_elem(self.test.wb, media_button, MediaPage.MEDIA_BAR_ID)

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
        time.sleep(0.2)
        self.vcar_manager.send(
            "SteeringWheelPushButton.statusSpecialFunctionButton.operationPushButtonSpecialFunction = 0"
        )
        time.sleep(2)
        screenshot_path = os.path.join(self.test.results_dir, "after_release_Media_Button.png")
        take_ic_screenshot_and_extract(self.test.mtee_target, screenshot_path)
        text = ""
        # Two regions defined respectively as media box appear on different regions of screen for ML and PU2303 branch
        regions = [1398, 44, 1590, 150], [1242, 138, 1465, 238]
        for mfl_media_region in regions:
            text += extract_text(screenshot_path, region=mfl_media_region).replace("\n", "")
        logger.info("Found text on IC Media Content after pressing MFL media button %s", text)
        self.assertRegex(text, r"MEDIA|Radio", "Expected text did not match the actual IC text on Media button")

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
            "Failed to open connectivity app after PTT button press/release. "
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
        logger.info("expected broadcasts %s", expected_broadcasts)

        assert_true(
            all(item in set(actual_broadcasts) for item in expected_broadcasts),
            "Observed SPEECH broadcasts do not match the expected",
        )
        Launcher.go_to_home()

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
        config_cbs_box = 1370, 428, 1802, 512
        config_cbs_text_box = 1440, 526, 1805, 562
        DisplaySet.start_activity(validate_activity=False)
        hud_button = self.test.driver.find_elements(*DisplaySet.HEAD_UP_DISPLAY_SUBMENU_ID)
        if hud_button:
            hdu_submenu_title = GlobalSteps.click_button_and_expect_elem(
                self.test.wb, hud_button[0], DisplaySet.DISPLAY_SUBMENU_TITLE_ID, sleep_time=2
            )
            assert (
                hdu_submenu_title.text == "HEAD-UP DISPLAY"
            ), "Not able to select and enter the Head-up display submenu"
            config_re = r"^CONTENT LAYOUT.*HEAD-UP"
            reference_image = os.path.join(self.mfl_ref_img_path, "MFL_config_cbs_with_hud.png")
        else:
            logger.debug("Didn't find Head-up display submenu option")
            config_re = r".*CONTENT LAYOUT$"
            reference_image = os.path.join(self.mfl_ref_img_path, "MFL_config_cbs_no_hud.png")
        screenshot_path = os.path.join(self.test.results_dir, "post_pressing_config_mfl_button.png")
        self.vcar_manager.send("SteeringWheelPushButton.operationSteerWheelFAV.operationSteerWheelFAV = 1")
        time.sleep(1)
        self.vcar_manager.send("SteeringWheelPushButton.operationSteerWheelFAV.operationSteerWheelFAV = 0")

        try:
            time.sleep(3)
            take_ic_screenshot_and_extract(self.test.mtee_target, screenshot_path)
            # check text elements
            text = extract_text(screenshot_path, region=config_cbs_text_box)
            logger.info("Found text on IC after config MFL press %s", text)
            self.assertRegex(text, config_re, "Expected text did not match the actual IC text")
            # check image element
            result, error = compare_snapshot(
                screenshot_path, reference_image, "MFL_config_cbs", fuzz_percent=99, region=config_cbs_box
            )
            if not result:
                raise AssertionError(
                    f"Error checking config CBS on IC.{screenshot_path} not equal to reference.{reference_image}"
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
