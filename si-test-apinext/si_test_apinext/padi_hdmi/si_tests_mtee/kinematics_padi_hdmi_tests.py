import logging
import os
import re
import time

import si_test_apinext.util.driver_utils as utils
from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import TimeoutError as MteeTimeoutError
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.padi import REF_IMAGES_PATH
from si_test_apinext.padi.pages.ce_area_page import CEAreaPage as Launcher
from si_test_apinext.padi.pages.left_panel_page import LeftPanel
from si_test_apinext.testing.test_base import TestBase
from si_test_apinext.util.mtee_utils import MteeUtils
from si_test_apinext.util.screenshot_utils import capture_screenshot, check_screendump, compare_snapshot

logger = logging.getLogger(__name__)


class TestKinematicsPADI:
    ref_images_path = REF_IMAGES_PATH
    # Button to be clicked to change position and translation and rotation values expected in dlt payloads
    mapping_ml = {
        "cinemaposition_rotation_30": (LeftPanel.SIDE_PANEL_ANGLE_NEXT_ID, (252, 103)),
        "cinemaposition_rotation_45": (LeftPanel.SIDE_PANEL_ANGLE_PREVIOUS_ID, (252, 102)),
        "cinemaposition_rotation_90": (LeftPanel.SIDE_PANEL_ANGLE_PREVIOUS_ID, (252, 101)),
        "touchposition_rotation_90": (LeftPanel.SIDE_PANEL_POSITION_CINEMATIC_ID, (100, 252)),
        "touchposition_rotation_45": (LeftPanel.SIDE_PANEL_ANGLE_NEXT_ID, (252, 102)),
        "touchposition_rotation_30": (LeftPanel.SIDE_PANEL_ANGLE_NEXT_ID, (252, 103)),
    }

    mapping_pu = {
        "cinemaposition_rotation_30": (LeftPanel.SIDE_PANEL_ANGLE_NEXT_ID_PU, (252, 103)),
        "cinemaposition_rotation_45": (LeftPanel.SIDE_PANEL_ANGLE_PREVIOUS_ID_PU, (252, 102)),
        "cinemaposition_rotation_90": (LeftPanel.SIDE_PANEL_ANGLE_PREVIOUS_ID_PU, (252, 101)),
        "touchposition_rotation_90": (LeftPanel.SIDE_PANEL_POSITION_CINEMATIC_ID_PU, (100, 252)),
        "touchposition_rotation_45": (LeftPanel.SIDE_PANEL_ANGLE_NEXT_ID_PU, (252, 102)),
        "touchposition_rotation_30": (LeftPanel.SIDE_PANEL_ANGLE_NEXT_ID_PU, (252, 103)),
    }

    vcar_mapping = {
        "cinemaposition_rotation_30": (2, 2),
        "cinemaposition_rotation_45": (2, 1),
        "cinemaposition_rotation_90": (2, 0),
        "touchposition_rotation_90": (4, 0),
        "touchposition_rotation_45": (4, 1),
        "touchposition_rotation_30": (4, 2),
    }
    mtee_log_plugin = True

    def __restore_default_vcar_values(self):
        self.vcar_manager.send(f"req_SunBlinds.blindStatusList = {self.default_blindSatusList}")
        self.vcar_manager.send(f"req_SunBlinds.blindStatusList.0.type = {self.default_blindSatusList_type}")
        self.vcar_manager.send(f"req_SunBlinds.blindStatusList.0.position = {self.default_blindSatusList_pos}")
        self.vcar_manager.send(f"ControlPaDI.statusPaDi.statusPaDiPosition = {self.default_statusPosition}")
        self.vcar_manager.send(f"CDS2.statusChildSafetyLock.statusChildSafetyLock = {self.default_childblock}")
        self.vcar_manager.send(f"ControlPaDI.statusPaDi.statusPaDiMotion = {self.default_padiMotion}")

    def __test_vcar_values(self):
        self.default_blindSatusList = self.vcar_manager.send("req_SunBlinds.blindStatusList")
        self.default_blindSatusList_type = self.vcar_manager.send("req_SunBlinds.blindStatusList.0.type")
        self.default_blindSatusList_pos = self.vcar_manager.send("req_SunBlinds.blindStatusList.0.position")
        self.default_statusPosition = self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPosition")
        self.default_childblock = self.vcar_manager.send("CDS2.statusChildSafetyLock.statusChildSafetyLock")
        self.default_padiMotion = self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiMotion")
        self.vcar_manager.send("req_SunBlinds.blindStatusList = 1")
        self.vcar_manager.send("req_SunBlinds.blindStatusList.0.type = 3")
        self.vcar_manager.send("req_SunBlinds.blindStatusList.0.position = 1")
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPosition = 2")
        self.vcar_manager.send("CDS2.statusChildSafetyLock.statusChildSafetyLock = 0")
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiMotion = 0")

    @classmethod
    def setup_class(cls):
        # TestBase is a singleton class to re-use appium driver and target vars
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.button_mapping = cls.mapping_pu if cls.test.branch_name == "pu2403" else cls.mapping_ml
        cls.vcar_manager = TargetShare().vcar_manager
        cls.mtee_utils = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)
        # This set is required to enable PADI get FZD commands.
        # FZD CAN version (low) => FZD send commands to BCP (vcar), then its forward from BCP to PADI (160.48.199.16)
        # FZD SOME/IP version (high) => FZD send commands directly to PADI (160.48.199.86)
        # cls.test.mtee_target.execute_command("devcoding write FZD_VARIANT 1")
        # Place correct default values for kinematics work
        cls.__test_vcar_values(cls)
        Launcher.stop_hdmi_animation()
        utils.start_recording(cls.test)

    @classmethod
    def teardown_class(cls):
        utils.stop_recording(cls.test, "TestKinematicsPADI")
        cls.__restore_default_vcar_values(cls)
        cls.test.quit_driver()
        cls.mtee_utils.reboot_target(apply_adb_workaround=True)

    def __wait_for_dlt(
        self, dlt_detector, dlt_msg, assert_msg, timeout=30, default_apid="ALD", default_ctid="LCAT", regex=False
    ):
        try:
            return dlt_detector.wait_for(
                {"apid": default_apid, "ctid": default_ctid, "payload_decoded": dlt_msg},
                timeout,
                regexp=regex,
                raise_on_timeout=True,
            )
        except MteeTimeoutError:
            logging.debug(assert_msg)
            raise AssertionError(assert_msg)

    def check_popup_text(self, popup_text, search_element, screenshot):
        """
        Check the popup message which is appearing on Padi is same as expected.
        Trying validation using element text if the driver was able to find it.
        if the element is not found try validating using OCR.

        param: popup_text - List of expected popup string
        param: search_element - Android element of the popup.(None if not found)
        param: screenshot - Screenshot file captured when popup appears
        """

        error_msg = ""
        for expected_text in popup_text:
            if search_element and expected_text in search_element.text:
                break
            elif not search_element:
                test_result, message = check_screendump(
                    screenshot,
                    expected_text,
                    region=LeftPanel.child_lock_popup,
                    lang="chi_sim" if self.test.mtee_target.hardware_variant == "padi_china" else "eng",
                )
                if test_result:
                    break
                error_msg += message + "\n"
        else:
            if search_element:
                raise AssertionError(f"expected popup text: '{popup_text}' but found '{search_element.text}'")
            raise AssertionError(error_msg)

    def click_and_validate_position(self, padi_position):
        """
        padi_position: Position of the PaDi to be changed

        Click on the mapped button wrt each position
        Validate the dlt message after each click
        Stimulate PaDi using Vcar
        Verify the position using reference image
        """
        press_button_dlt = re.compile(
            r"kinematics\.KinematicsControl\[\d+\].*triggerSetPaDiAlignment.*t\:.(\d+).r\:.(\d+)"
        )
        button_elem = self.test.wb.until(
            ec.presence_of_element_located(self.button_mapping[padi_position][0]),
            f"Error while validating presence of the element: {self.button_mapping[padi_position][0].selector}",
        )
        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as dlt_detector:
            button_elem.click()
            time.sleep(1)
            messages = self.__wait_for_dlt(
                dlt_detector,
                press_button_dlt,
                f"Kinematics Control message after press button {self.button_mapping[padi_position][0]} was not found",
                regex=True,
                timeout=10,
            )
            for message in messages:
                log_payload = message.payload_decoded
                logger.debug("Message: %s", log_payload)
                match = press_button_dlt.search(log_payload)
                if match:
                    translation, rotation = match.group(1), match.group(2)
                    logger.debug("Found values translation= %s and rotation= %s", translation, rotation)
                    assert translation == str(
                        self.button_mapping[padi_position][1][0]
                    ), f"Expected translation = {self.button_mapping[padi_position][1][0]}.Received = {translation}"
                    assert rotation == str(
                        self.button_mapping[padi_position][1][1]
                    ), f"Expected rotation = {self.button_mapping[padi_position][1][1]}. Received = {rotation}"
        LeftPanel.enable_interaction_panel()
        self.vcar_manager.send(f"ControlPaDI.statusPaDi.statusPaDiPosition = {self.vcar_mapping[padi_position][0]}")
        self.vcar_manager.send(f"ControlPaDI.statusPaDi.statusPaDiPosition2 = {self.vcar_mapping[padi_position][1]}")
        time.sleep(2)
        elem_bounds = LeftPanel.get_display_settings_elem_bounds(
            LeftPanel.SIDE_PANEL_DISPLAY_LAYOUT_ID, LeftPanel.SIDE_PANEL_DISPLAY_LAYOUT_ID_PU
        )
        screenshot_path = capture_screenshot(
            test=self.test,
            test_name=f"PaDi_in_{padi_position}",
            bounds=elem_bounds,
        )
        _, error_message = compare_snapshot(
            screenshot_path,
            os.path.join(self.ref_images_path, padi_position + ".png"),
            f"PaDi_in_{padi_position}",
            fuzz_percent=99,
        )
        return error_message

    @utils.gather_info_on_fail
    def test_001_check_padi_kinematics_status(self):
        """
        Test Status UI display

        *Background information*

        This test case verifies the following functionality described at ABPI-75329:
            -This test verifies that:
                * kinematics UI change after status position and angle change (rotation and translation).
                * All kinematic positions combination are tested (6)

        **Pre-Requisites**
            -Place kinematics on Cinema Position and Angle 90 degrees.
            -Place Position 16:9 and center

        **Steps**
            1. Stop cearea screen (without this step it's not possible take screenshots due android protection flags)
            2. Open Display Settings
            3. Fullfill pre-requisites place angle 90 degrees and cinemaposition
            4. Change rotation angle for position 1
            5. Change rotation angle for position 2
            6. Change position to Touchposition (Translation Movement, direction rear seat)
            7. Change rotation angle for position 1
            8. Change rotation angle for position 0

        **Expected outcome**
            - Verified that at step 3 padi is in expected position (cinemaposition on 90 degrees)
            - Verified that at step 4 padi is in expected position (cinemaposition on 45 degrees)
            - Verified that at step 5 padi is in expected position (cinemaposition on 30 degrees)
            - Verified that at step 6 padi is in expected position (touchposition on 30 degrees)
            - Verified that at step 7 padi is in expected position (touchposition on 45 degrees)
            - Verified that at step 8 padi is in expected position (touchposition on 90 degrees)

        ..note:: To validate it, in test is used vcar commands to change status and taking screenshots and
        compare it with reference images.
        """
        # angles of touch position [90,45]
        touch_positions = 2, 4
        # angles of cinema position [90,45,30] (list-for rverse functionality)
        cinema_positions = [0, 1, 2]
        # degrees for appending images cinema position
        degrees = {0: 90, 1: 45, 2: 30}
        # dictionary for images touch position
        error_message = ""
        test_result = True
        LeftPanel.enable_interaction_panel()
        for touch_position in touch_positions:
            LeftPanel.open_display_settings()
            self.vcar_manager.send(f"ControlPaDI.statusPaDi.statusPaDiPosition = {touch_position}")
            for cinema_position in cinema_positions:
                self.vcar_manager.send(f"ControlPaDI.statusPaDi.statusPaDiPosition2 = {cinema_position}")
                time.sleep(1)
                test_case_name = (
                    f"cinemaposition_rotation_{degrees[cinema_position]}"
                    if touch_position == 2
                    else f"touchposition_rotation_{degrees[cinema_position]}"
                )
                self.test.apinext_target.send_tap_event(
                    LeftPanel.side_center_coords[0], LeftPanel.side_center_coords[1]
                )
                elem_bounds = LeftPanel.get_display_settings_elem_bounds(
                    LeftPanel.SIDE_PANEL_DISPLAY_LAYOUT_ID, LeftPanel.SIDE_PANEL_DISPLAY_LAYOUT_ID_PU
                )
                screenshot_path = capture_screenshot(
                    test=self.test,
                    test_name=test_case_name,
                    bounds=elem_bounds,
                )
                test_result, message = compare_snapshot(
                    screenshot_path,
                    os.path.join(self.ref_images_path, test_case_name + ".png"),
                    test_case_name,
                    fuzz_percent=99,
                )
                error_message += message
            message_close_settings = r"PANEL|DisplaySettingsLayout\[\d+\]\.*Close display settings"
            with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as dlt_detector:
                # Validate data received
                self.__wait_for_dlt(
                    dlt_detector,
                    message_close_settings,
                    "Display Settings didn't close",
                    regex=True,
                )
            # reversing values  Change position to Touchposition (Translation Movement, direction rear seat)
            cinema_positions.reverse()
        if not test_result:
            raise AssertionError(error_message)

    @utils.gather_info_on_fail
    def test_002_check_padi_kinematics_control(self):
        """
        Test Control UI display

        **Pre-Requisites**
            -Place kinematics on Cinema Position and Angle 45 degrees.

        *Background information*

        This test case verifies the following functionality of ABPI-75329:
            -In this test we expect validate PADI send controls for actuators (FZD)

        *Steps*
            1. Open Display Settings
            2. Press Next Angle button(30°)
            3. 2 x Press Previous Angle button(45°, 90°)
            4. Press Next Position button
            5. Place kinematics on Touch Position and Angle 45 degrees.
            6. Press Previous Angle button(90°)
            7. Press Next Position button(45°, 90°)
            8. Press Previous Position button

        **Expected outcome**
            - Verified that at step 2 padi sent triger for FZD (Cinemaposition rotate back)
            - Verified that at step 3 padi sent triger for FZD (Cinemaposition rotate front)
            - Verified that at step 4 padi sent triger for FZD (Cinemaposition translate front)
            - Verified that at step 5 padi sent triger for FZD (Touchposition rotate front)
            - Verified that at step 6 padi sent triger for FZD (Touchposition rotate back)
            - Verified that at step 7 padi sent triger for FZD (Touchposition translate back)

        ..note:: To validate it, in test is pressed buttons, e.g. next angle, and check trigger message is sent on dlt.
        """
        error_msg = []
        LeftPanel.open_display_settings()
        # Set PaDi to cinemaposition and angle to 45 as precondition
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPosition = 2")
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPosition2 = 1")
        time.sleep(2)
        position_order = [
            "cinemaposition_rotation_30",
            "cinemaposition_rotation_45",
            "cinemaposition_rotation_90",
            "touchposition_rotation_90",
            "touchposition_rotation_45",
            "touchposition_rotation_30",
            "cinemaposition_rotation_30",
        ]
        for padi_position in position_order[:4]:
            error_message = self.click_and_validate_position(padi_position)
            if error_message:
                error_msg.append(error_message)
        self.vcar_manager.send("ControlPaDI.statusPaDi.statusPaDiPosition2 = 1")
        # Update buttom mapping in touch position
        self.button_mapping.update(
            {
                "touchposition_rotation_90": (LeftPanel.SIDE_PANEL_ANGLE_PREVIOUS_ID_PU, (252, 101)),
                "cinemaposition_rotation_30": (LeftPanel.SIDE_PANEL_POSITION_TOUCH_ID_PU, (0, 252)),
            }
            if self.test.branch_name == "pu2403"
            else {
                "touchposition_rotation_90": (LeftPanel.SIDE_PANEL_ANGLE_PREVIOUS_ID, (252, 101)),
                "cinemaposition_rotation_30": (LeftPanel.SIDE_PANEL_POSITION_TOUCH_ID, (0, 252)),
            }
        )
        for padi_position in position_order[3:]:
            error_message = self.click_and_validate_position(padi_position)
            if error_message:
                error_msg.append(error_message)
        if error_msg:
            raise AssertionError(error_msg)

    @utils.gather_info_on_fail
    def test_003_check_padi_kinematics_popup_childlock(self):
        """
        Test childlock Popups in UI display

        **Pre-Requisites**
            -Place kinematics on Cinema Position and Angle 45 degrees.

        *Background information*

        This test case verifies the following functionality of ABPI-75329:
            -In this test we expect validate PADI Popups appears

        *Steps*
        1. Open Display Settings
        2. Enable ChildLock
        3. Validate child lock is activated by dlt
        4. Press the fold up button

        **Expected outcome**
            - Verified that at step 4 padi shows a popup message regarding child lock

        ..note:: To validate it, in test is changed ChildLock status and pressed an button,
        first trying validation using element text if the driver was able to find it
        if not compare the screenshot text with expected.
        """

        LeftPanel.open_display_settings()
        utils.take_apinext_target_screenshot(
            self.test.apinext_target, self.test.results_dir, "child_lock_open_display_settings"
        )
        elem_bounds = LeftPanel.get_display_settings_elem_bounds(LeftPanel.SIDE_PANEL_DISPLAY_FOLD_BUTTON_ID)
        # Check child lock is active via dlt
        kisi_enable_dlt = r".*onKiSiStatusChanged\:\ ACTIVE.*"
        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as dlt_detector:
            self.vcar_manager.send("CDS2.statusChildSafetyLock.statusChildSafetyLock = 1")
            try:
                dlt_detector.wait_for(
                    {"apid": "ALD", "ctid": "LCAT", "payload_decoded": kisi_enable_dlt},
                    30,
                    regexp=True,
                    raise_on_timeout=True,
                )
            except MteeTimeoutError:
                assert_msg = f"Unable to find {kisi_enable_dlt} after enabling childlock via vcar"
                logging.debug(assert_msg)
                raise AssertionError(assert_msg)

        # Check child lock is active via popup message
        LeftPanel.open_display_settings()
        utils.take_apinext_target_screenshot(
            self.test.apinext_target, self.test.results_dir, "child_lock_open_display_settings"
        )
        self.test.driver.tap([((elem_bounds[0] + 5), (elem_bounds[1] + 5))])
        time.sleep(1.5)

        screenshot_path = capture_screenshot(test=self.test, test_name="child_popup")

        popup_text = (
            "Panorama display cannot be moved. Please check the child safety lock status.",
            "Theatre Screen cannot be adjusted. Please check child lock.",
        )
        search_element = None
        popup_content = self.test.driver.find_elements(*Launcher.CHILD_LOCK_POP_UP_ID)
        if popup_content:
            search_element = popup_content[0]
        popup_content_pu = self.test.driver.find_elements(*Launcher.CHILD_LOCK_POP_UP_ID_PU)
        if popup_content_pu:
            search_element = popup_content_pu[0]
        self.check_popup_text(popup_text, search_element, screenshot_path)

    @utils.gather_info_on_fail
    def test_004_check_padi_fold_up_button(self):
        """
        Test Padi fold up button

        **Pre-Requisites**
            -Place top_cearea_package.
        *Background information*
        This test case verifies the following functionality of ABPI-75329:
        *Steps*
        1. Stop cearea screen (without this step it's not possible take screenshots due android protection flags)
        2. Open Display Settings
        3. Press Fold Up button
        4. Validate no trigger is sent to FZD (r"kinematics.KinematicsControl(147).*triggerFold")
        """
        # disabling child locks
        self.vcar_manager.send("CDS2.statusChildSafetyLock.statusChildSafetyLock = 0")
        LeftPanel.open_display_settings()
        foldup_button = LeftPanel.SIDE_PANEL_DISPLAY_FOLD_BUTTON_ID
        foldup_button_elem = self.test.wb.until(
            ec.presence_of_element_located(foldup_button),
            f"Error while validating presence of the element: {foldup_button.selector}",
        )
        message_foldup_fzd = r"kinematics.KinematicsControl\[\d+\].*triggerFold"
        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as dlt_detector:
            foldup_button_elem.click()
            time.sleep(0.5)
            capture_screenshot(test=self.test, test_name="padi_foldup")
            self.__wait_for_dlt(dlt_detector, message_foldup_fzd, "Padi is not folding up", regex=True, timeout=40)
