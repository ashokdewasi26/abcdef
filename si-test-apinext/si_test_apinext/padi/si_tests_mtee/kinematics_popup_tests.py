import logging
import time
from unittest.case import TestCase

from mtee.testing.support.target_share import TargetShare
from si_test_apinext.padi.pages.ce_area_page import CEAreaPage as Launcher
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.mtee_utils import MteeUtils
from si_test_apinext.util.screenshot_utils import capture_screenshot, check_screendump

logger = logging.getLogger(__name__)


class TestKinematicPop(TestCase):

    mtee_log_plugin = True

    def __restore_default_vcar_values(self):
        self.vcar_manager.send(f"req_SunBlinds.blindStatusList = {self.default_blindSatusList}")
        self.vcar_manager.send(f"req_SunBlinds.blindStatusList.0.type = {self.default_blindSatusList_type}")
        self.vcar_manager.send(f"req_SunBlinds.blindStatusList.0.position = {self.default_blindSatusList_pos}")
        self.vcar_manager.send(f"ControlPaDI.statusPaDi.statusPaDiPosition = {self.default_statusPosition}")
        self.vcar_manager.send(f"CDS2.statusChildSafetyLock.statusChildSafetyLock = {self.default_childblock}")

    def __test_vcar_values(self):
        self.default_blindSatusList = self.vcar_manager.send("req_SunBlinds.blindStatusList")
        self.default_blindSatusList_type = self.vcar_manager.send("req_SunBlinds.blindStatusList.0.type")
        self.default_blindSatusList_pos = self.vcar_manager.send("req_SunBlinds.blindStatusList.0.position")
        self.default_statusPosition = self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPosition")
        self.default_childblock = self.vcar_manager.send("CDS2.statusChildSafetyLock.statusChildSafetyLock")
        self.vcar_manager.send("req_SunBlinds.blindStatusList = 1")
        self.vcar_manager.send("req_SunBlinds.blindStatusList.0.type = 3")
        self.vcar_manager.send("req_SunBlinds.blindStatusList.0.position = 1")
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPosition = 2")
        self.vcar_manager.send("CDS2.statusChildSafetyLock.statusChildSafetyLock = 0")

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.vcar_manager = TargetShare().vcar_manager
        cls.mtee_utils = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        cls.__test_vcar_values(cls)
        Launcher.stop_cearea_package()
        utils.start_recording(cls.test)
        # This set is required to enable PADI get FZD commands.
        # FZD CAN version (low)=> FZD send commands to BCP (vcar), then its forward from BCP to PADI (160.48.199.16)
        # FZD SOME/IP version (high)=> FZD send commands directly to PADI (160.48.199.86)
        # self.test.apinext_target.execute_command("setprop persist.bmw.kinematics.fzdvariant low", privileged=True)
        # Place correct default values for kinematics work

    @classmethod
    def teardown_class(cls):
        utils.stop_recording(cls.test, "TestKinematicPopUps")
        cls.__restore_default_vcar_values(cls)
        cls.test.teardown_base_class()
        cls.mtee_utils.reboot_target(apply_adb_workaround=True)

    def setUp(self) -> None:
        if not self.test.driver:
            logger.info("Driver not available executing setup_class.")
            self.test.setup_base_class()
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiMotion = 1")
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiMotion = 0")
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPosition = 4")
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPosition2 = 0")
        time.sleep(2)
        Launcher.stop_cearea_package()

    def check_popup_text(self, popup_text, screenshot):
        """
        Check the popup message which is appearing on Padi is same as expected.
        Trying validation using element text if the driver was able to find it(popup appears for less than 5 sec)
        if the element is not found try validating using OCR.

        param: popup_text - List of expected popup string
        param: screenshot - Screenshot file captured when popup appears
        """
        popup_content = self.test.driver.find_elements(*Launcher.POP_UP_ID)
        if popup_content:
            search_element = popup_content[0]
        popup_content_pu = self.test.driver.find_elements(*Launcher.POP_UP_ID_PU)
        if popup_content_pu:
            search_element = popup_content_pu[0]

        if popup_content or popup_content_pu:
            expected_text = popup_text[0] if self.test.mtee_target.hardware_variant == "padi_china" else popup_text[1]
            assert (
                expected_text in search_element.text
            ), f"Expected popup text is: {expected_text} But found: {search_element.text}"
        else:
            test_result, message = check_screendump(
                screenshot,
                popup_text[0] if self.test.mtee_target.hardware_variant == "padi_china" else popup_text[1],
                lang="chi_sim" if self.test.mtee_target.hardware_variant == "padi_china" else "eng",
            )
            if not test_result:
                raise AssertionError(message)

    @utils.gather_info_on_fail
    def test_001_padiobstacledetected(self):
        """
        Kinematics - Pop up PaDiObstacleDetected

        *Background information*
        This test case verifies the following functionality described at ABPI-91739:
        https://asc.bmwgroup.net/wiki/display/MGU22/Kinematics+Popup+Specification+for+PADI

        *Steps*
        1. Padi Display is ON
        2. Send below some ip messages
        3. ControlPaDI.statusPaDi.statusPaDiPopUp = 2
        4. ControlPaDI.statusPaDi.statusPadiPopUpDirection = 3
        5. Check for the toast message "Canceled: Obstruction detected.Please ensure that the Theater Screen is not
        blocked and reselect the desired position."
        """
        time.sleep(8)
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPopUp = 2")
        time.sleep(1)
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPadiPopUpDirection = 3")
        time.sleep(0.5)
        popup_text = (
            "中断：检测到障碍物。请确保全景娱乐屏未被阻挡，并重新选择所需位置。",
            "Cancelled: obstruction detected. Please ensure that the "
            + "Theatre Screen is not blocked and reselect the desired position.",
        )
        screenshot_path = capture_screenshot(
            test=self.test,
            test_name="test_001_padiobstacledetected",
            bounds=Launcher.cearea_bounds_popups,
        )
        self.check_popup_text(popup_text, screenshot_path)

    @utils.gather_info_on_fail
    def test_002_padiblockedbymovingfrontseat(self):
        """
        Kinematics - Pop up PaDiBlockedByMovingFrontSeat

        *Background information*
        This test case verifies the following functionality described at ABPI-91742:
        https://asc.bmwgroup.net/wiki/display/MGU22/Kinematics+Popup+Specification+for+PADI

        *Steps*
        1. Padi Display is ON
        2. Send below some ip messages
        3. ControlPaDI.statusPaDi.statusPaDiPopUp = 3
        4. ControlPaDI.statusPaDi.statusPadiPopUpDirection = 3
        5. Check for the toast message "Front seat adjustment active. Please wait until the front seat has reached the
        desired position and try again."
        """
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPopUp = 3")
        time.sleep(1)
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPadiPopUpDirection = 3")
        time.sleep(0.5)
        popup_text = (
            "前排座椅调节已启动。请等待前排座椅到达所需位置，然后再次尝试。",
            "Front seat adjustment active. "
            + "Please wait until the front seat has reached the desired position and try again.",
        )
        screenshot_path = capture_screenshot(
            test=self.test,
            test_name="test_002_padiblockedbymovingfrontseat",
            bounds=Launcher.cearea_bounds_popups,
        )
        self.check_popup_text(popup_text, screenshot_path)

    @utils.gather_info_on_fail
    def test_003_padiblockedbyfrontseatposition(self):
        """
        Kinematics - Pop up PaDiMovingBlockedByFrontSeatPosition

        *Background information*
        This test case verifies the following functionality described at ABPI-91743:
        https://asc.bmwgroup.net/wiki/display/MGU22/Kinematics+Popup+Specification+for+PADI

        *Steps*
        1. Padi Display is ON
        2. Send below some ip messages
        3. ControlPaDI.statusPaDi.statusPaDiPopUp = 5
        4. ControlPaDI.statusPaDi.statusPadiPopUpDirection = 3
        5. Check for the toast message "Please move the front seats forwards to ensure that the Theater Screen is not
        blocked"
        """
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPopUp = 5")
        time.sleep(1)
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPadiPopUpDirection = 3")
        time.sleep(0.5)
        popup_text = (
            "请将前排座椅向前移动，确保全景娱乐屏能完全展开。",
            "Please move the front seats forwards to ensure that the Theatre Screen is not blocked.",
        )
        screenshot_path = capture_screenshot(
            test=self.test,
            test_name="test_003_padiblockedbyfrontseatposition",
            bounds=Launcher.cearea_bounds_popups,
        )
        self.check_popup_text(popup_text, screenshot_path)

    @utils.gather_info_on_fail
    def test_004_padicollisionavoidancebecauseseatmoving(self):
        """
        Kinematics - Pop up PaDiCollisionAvoidanceBecauseSeatMoving

        *Background information*
        This test case verifies the following functionality described at ABPI-91746:
        https://asc.bmwgroup.net/wiki/display/MGU22/Kinematics+Popup+Specification+for+PADI

        *Steps*
        1. Padi Display is ON
        2. Send below some ip messages
        3. ControlPaDI.statusPaDi.statusPaDiPopUp = 6
        4. ControlPaDI.statusPaDi.statusPadiPopUpDirection = 3
        5. Check for the toast message "Front seat adjustment active. Adjusting position of the Theater Screen."
        """
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPopUp = 6")
        time.sleep(1)
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPadiPopUpDirection = 3")
        time.sleep(0.5)
        popup_text = (
            "前排座椅调节已启动。正在调整全景娱乐屏位置",
            "Front seat adjustment active. Adjusting position of the Theatre Screen",
        )
        screenshot_path = capture_screenshot(
            test=self.test,
            test_name="test_004_padicollisionavoidancebecauseseatmoving",
            bounds=Launcher.cearea_bounds_popups,
        )
        self.check_popup_text(popup_text, screenshot_path)

    @utils.gather_info_on_fail
    def test_005_padifollowingfrontseat(self):
        """
        Kinematics - Pop up PaDiFollowingFrontSeat

        *Background information*
        This test case verifies the following functionality described at ABPI-128052:
        https://asc.bmwgroup.net/wiki/display/MGU22/Kinematics+Popup+Specification+for+PADI

        *Steps*
        1. Padi Display is ON
        2. Send below some ip messages
        3. ControlPaDI.statusPaDi.statusPaDiPopUp = 8
        4. ControlPaDI.statusPaDi.statusPadiPopUpDirection = 3
        5. Check for the toast message "Theater Screen is being moved forwards as the front seat is no longer blocking
        the Theater Screen."
        """
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPopUp = 8")
        time.sleep(1)
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPadiPopUpDirection = 3")
        time.sleep(0.5)
        popup_text = (
            "因不再受到前排座椅阻挡，全景娱乐屏将向前移动。",
            "Theatre Screen is being moved forwards as the front seat is no longer blocking the Theatre Screen.",
        )
        screenshot_path = capture_screenshot(
            test=self.test,
            test_name="test_005_padifollowingfrontseat",
            bounds=Launcher.cearea_bounds_popups,
        )
        self.check_popup_text(popup_text, screenshot_path)

    @utils.gather_info_on_fail
    def test_006_padioveruse(self):
        """
        Kinematics - Pop up Padi Overuse

        *Background information*
        This test case verifies the following functionality described at ABPI-91754:
        https://asc.bmwgroup.net/wiki/display/MGU22/Kinematics+Popup+Specification+for+PADI

        *Steps*
        1. Padi Display is ON
        2. Send below some ip messages
        3. ControlPaDI.statusPaDi.statusPaDiPopUp = 9
        4. ControlPaDI.statusPaDi.statusPadiPopUpDirection = 3
        5. Check for the toast message "Function temporarily deactivated due to overloading"
        """
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPopUp = 9")
        time.sleep(1)
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPadiPopUpDirection = 3")
        time.sleep(0.5)
        popup_text = (
            "为防负载过大，已暂时关闭该功能。",
            "Function temporarily deactivated due to overloading.",
        )
        screenshot_path = capture_screenshot(
            test=self.test,
            test_name="test_006_padioveruse",
            bounds=Launcher.cearea_bounds_popups,
        )
        self.check_popup_text(popup_text, screenshot_path)
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPopUp = 0")
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPadiPopUpDirection = 3")
