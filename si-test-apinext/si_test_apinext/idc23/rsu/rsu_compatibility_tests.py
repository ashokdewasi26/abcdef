# Copyright (c) 2024. BMW Car IT GmbH. All rights reserved.
"""RSU compatibility flash test with version checks"""
import logging
from pathlib import Path
import time
import re

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.test_environment import require_environment, TEST_ENVIRONMENT as TE
from mtee.testing.tools import assert_equal, assert_true, metadata
from selenium.common.exceptions import NoSuchElementException
from si_test_apinext.idc23.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.idc23.pages.rsu_page import RSUPage
from si_test_apinext.idc23.pages.settings_app_page import SettingsAppPage as Settings
from si_test_apinext.idc23.rsu.rsu_compatibility_helper import RSUHelper
from si_test_apinext.idc23.rsu.const import ADDITIONAL_PAYLOADS, RSU_ERROR_PAYLOADS, RSU_PAYLOADS, VERSION_AFTER_RSU
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.global_steps import GlobalSteps
from si_test_apinext.util.mtee_utils import MteeUtils
from si_test_apinext.util.screenshot_utils import capture_screenshot
from tee.target_common import VehicleCondition

try:
    from validation_utils.utils import TimeoutError
except ModuleNotFoundError:
    from node0_ssh_client.tools import TimeoutError

logger = logging.getLogger(__name__)
TEST_CONFIG_FILE = (Path(__file__).parent.parent / "rsu" / "data" / "rsu-config-test.json").absolute()
TARGET_RSU_PATH = "/var/data/rsu-shared/"


@require_environment(TE.target.hardware.idc23, TE.test_bench.rack)
@metadata(
    testsuite="RSU-TEST",
    priority="default",
    domain="SWINT",
    duration="short",
    testbench=["testrack"],
    testtype="non-functional",
    traceability={"MGU": {"JIRA": ["SIT-45086", "ABPI-533292"]}},
)
class TestRSUCompatibility(RSUHelper):
    def __init__(self):
        self.test = TestBase.get_instance()
        self.test.setup_base_class()
        self.mtee_utils = MteeUtils(mtee_target=self.test.mtee_target, apinext_target=self.test.apinext_target)
        self.raise_on_timeout = True
        self.rsu_complete = False
        self.skip_message = True
        self.version_after_rsu_dlt = ""
        self.vipr_exit_code = None
        self.vipr_payload = ""
        super(TestRSUCompatibility, self).__init__(self.test.mtee_target)

    def look_with_error_payloads(
        self,
        trace_object,
        step_name,
        payload,
        timeout,
        obd=True,
        pad_pwf_state=True,
        wait_time=0,
        apid="SUAG",
        ctid="_TM_",
    ):
        """Check for expected and error DLT payloads during RSU"""
        logger.info("Looking for activation possible message for %s seconds ...", timeout)
        for num in range(5):
            try:
                message = trace_object.wait_for(
                    attrs=dict(payload_decoded=re.compile(payload), apid=apid, ctid=ctid),
                    drop=True,
                    skip=True,
                    timeout=timeout,
                    timeout_message=f"Could not find payload: {payload} after {timeout} seconds",
                )
                for msg in message:
                    logger.info("Received message : %s", msg.payload_decoded)
                capture_screenshot(test=self.test, test_name=step_name)
                time.sleep(wait_time)
                self.test.mtee_target._power_supply.obd = obd
                if pad_pwf_state:
                    self.test.mtee_target.set_vehicle_lifecycle_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
                return
            except TimeoutError:
                logger.info("'Activation possible' message not received. Looking for error messages...")
                try:
                    error_message = trace_object.wait_for(
                        attrs=dict(payload_decoded=re.compile(RSU_ERROR_PAYLOADS[-1]), apid=apid, ctid=ctid),
                        drop=True,
                        skip=False,
                        timeout=30,
                    )
                    for msg in error_message:
                        logger.error("Received error message : %s", msg.payload_decoded)
                    raise AssertionError("RSU error observed. Please check traces.")
                except TimeoutError:
                    logger.info("No error messages found. Continuing search number %s for activation", num)

    def look_for_trace(
        self,
        trace_object,
        step_name,
        payload,
        timeout,
        obd=True,
        pad_pwf_state=True,
        wait_time=0,
        apid="SUAG",
        ctid="_TM_",
    ):
        """Check for expected DLT payloads during RSU"""
        message = trace_object.wait_for(
            attrs=dict(payload_decoded=re.compile(payload), apid=apid, ctid=ctid),
            drop=True,
            skip=self.skip_message,
            timeout=timeout,
            timeout_message=f"Could not find payload: {payload} after {timeout} seconds",
            raise_on_timeout=self.raise_on_timeout,
        )
        match = False
        for msg in message:
            logger.info("Received message : %s", msg.payload_decoded)
            if "VIPR_EXIT_CODE" in step_name:
                match = re.compile(payload).search(msg.payload_decoded)
                if match:
                    self.vipr_payload = msg.payload_decoded
                    self.vipr_exit_code = match.group(1)
                    logger.info("Found exit code: %s", self.vipr_exit_code)
            if "VERSION" in step_name:
                match = re.compile(payload).search(msg.payload_decoded)
                if match:
                    self.version_after_rsu_dlt = match.group(1)
                    logger.info("Platform version after RSU is: %s", self.version_after_rsu_dlt)
            match = re.compile(payload).search(msg.payload_decoded)
        if not self.raise_on_timeout and not match:
            return
        if not self.raise_on_timeout and match and "POST_REBOOT" in step_name:
            self.rsu_complete = True
            return
        if "UPDATE" in step_name:
            capture_screenshot(test=self.test, test_name=step_name)
        time.sleep(wait_time)
        self.test.mtee_target._power_supply.obd = obd
        if pad_pwf_state:
            self.test.mtee_target.set_vehicle_lifecycle_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)

    def final_stage_verification(self, trace):
        """Final logs verification after VIPR code receieved
        :param trace: DLTContext object
        :return bool: True if RSU process is successfully completed
        """
        for i in range(30):  # Search for collectively 30 mins maximum for all payloads to appear
            for step in ADDITIONAL_PAYLOADS:
                self.raise_on_timeout = False
                self.skip_message = False
                self.look_for_trace(trace, *step)
                if self.rsu_complete:
                    return True
        return False

    @utils.gather_info_on_fail
    def test_rsu_compatibility(self):
        """RSU compatibility flash test with version checks
        Step 1 to 5 are done using Target manager API in target setup stage
        Below preconditions already done in target manager setup
            - Prepare workspace with desired Image and PDX files.
            - Perform IOC flashing via UART.
            - Perform SOC flashing.
            - Push Engineering token.
            - Push CBB response file.
        1. Clear DTCs inside the target.
        2. Activate node1 container if not active and clear core dumps folder.
        3. Complete provisioning diagnosis enablers.
        4. Trigger RSU option from system settings.
        5. Continuously check error payloads (open file transfer failed) after trigger,
            if found provide nsm_control --r 7.
        6. If RSU preparation completed successfully then give Wohnen and turn off OBD.
        7. Check in DLT respective PWF payloads and give PAD.
        8. After successful activation check SW Version.
        """
        self.clear_dtc_and_activate_container()
        self.clear_coredumps()
        self.mtee_utils.restart_target_and_driver(self.test)
        # Waiting for few seconds as there was a reboot...
        time.sleep(5)
        self.test.mtee_target.upload(TEST_CONFIG_FILE, TARGET_RSU_PATH)
        Launcher.go_to_home()
        Settings.launch_settings_activity()
        capture_screenshot(test=self.test, test_name="system_settings_screen")
        rsu_app_btn = self.test.driver.find_element(*Settings.START_RSU_BUTTON)
        GlobalSteps.click_button_and_expect_elem(self.test.wb, rsu_app_btn, RSUPage.CONTAINER_ID)
        try:
            activate_rsu_btn = self.test.driver.find_element(*Settings.ACTIVATE_RSU_BUTTON)
            GlobalSteps.click_button_and_expect_elem(self.test.wb, activate_rsu_btn, RSUPage.CONTAINER_ID)
        except NoSuchElementException:
            logger.info("RSU option already activated")
        capture_screenshot(test=self.test, test_name="starting_rsu_screen")
        with DLTContext(
            self.test.mtee_target.connectors.dlt.broker,
            filters=[("SUAG", "_TM_"), ("SUAG", "AGNT"), ("VIPR", "VIPR")],
        ) as trace:
            upgrade_start_btn = self.test.driver.find_element(*Settings.START_SEARCH_FOR_UPGRADE)
            GlobalSteps.click_button_and_expect_elem(self.test.wb, upgrade_start_btn, RSUPage.CONTAINER_ID)
            capture_screenshot(test=self.test, test_name="search_started")
            for step in RSU_PAYLOADS:
                self.look_with_error_payloads(trace, *step) if "ACTIVATION_POSSIBLE" in step[
                    0
                ] else self.look_for_trace(trace, *step)
            assert_true(self.final_stage_verification(trace), "RSU master did not reach the final stage of the update")
        self.wait_for_target_to_sleep(180)
        logger.info("Testrack is up after RSU")
        self.test.mtee_target.reset_connector_dlt_state()
        self.test.mtee_target._recover_ssh(record_failure=False)
        assert_equal(
            VERSION_AFTER_RSU,
            self.version_after_rsu_dlt,
            f"Version after RSU: {self.version_after_rsu_dlt} did not match desired version: {VERSION_AFTER_RSU}",
        )
