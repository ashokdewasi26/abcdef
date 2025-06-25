import logging
import os
import re
from zipfile import ZipFile

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import TimeoutError as MteeTimeoutError
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.padi.pages.ce_area_page import CEAreaPage as Launcher
from si_test_apinext.padi.pages.padi_page import PadiPage as Padi
from si_test_apinext.testing.test_base import TestBase
from si_test_apinext.util.mtee_utils import MteeUtils
from si_test_apinext.util.screenshot_utils import capture_screenshot

logger = logging.getLogger(__name__)


class TestLauncherRebootPADI:
    _screenshot_list = []
    _resolution_8k = "7680x2160"

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.vehicle_initial_state = cls.test.mtee_target.vehicle_state
        cls.mtee_utils = MteeUtils(mtee_target=cls.test.mtee_target, apinext_target=cls.test.apinext_target)

    @classmethod
    def teardown_class(cls):
        if cls.test.mtee_target.vehicle_state != cls.vehicle_initial_state:
            cls.test.mtee_target.switch_vehicle_to_state(cls.vehicle_initial_state)
        cls.mtee_utils.resume_default_conditions()
        cls.test.quit_driver()

    def __check_launcher(self):
        expected_activity = Padi.PACKAGE_ACTIVITY if self.test.branch_name == "pu2403" else Padi.PACKAGE_ACTIVITY_ML
        try:
            assert (
                expected_activity == self.test.driver.current_activity
            ), f"Failure on validating Launcher, expected activity is not active: {expected_activity}"

            self.test.wb.until(
                ec.presence_of_element_located(Launcher.CE_AREA_NOT_FOCUSED_ID),
                f"Error while validating {Launcher.CE_AREA_NOT_FOCUSED_ID} presence",
            )
        except Exception:
            capture_screenshot(
                test=self.test,
                test_name="padi_launcher_unavailable_screenshot_reboot_exception",
            )
            raise

    def __validate_bootanimation_files(self, filepath):
        """ "
        Unzip bootanimation.zip and check file desc.txt contains
        information about folder structure to be shown
        and check it too.
        param: filepath :absolute path of bootanimation.zip
        """
        with ZipFile(filepath, "r") as zipobject:
            file_name_list = zipobject.namelist()
            file_dir_names = []
            with zipobject.open("desc.txt", "r") as myfile:
                next(myfile)  # reading from second line
                for line in myfile:
                    file_dir_names.append(line.split()[-1].decode("utf-8"))
            for file in file_dir_names:
                file_not_find = False
                for filename in file_name_list:
                    if file == filename[:-1]:
                        file_not_find = True
                        break
                if not file_not_find:
                    raise ValueError(f"{file} file/dir not found in the {filepath}")

    def check_dlt_context(self, dlt_msg, max_wait, name, drop=False, count=1, raise_on_timeout=True, reboot=False):
        """Check DLT for matching messages w.r.t given regular expression and return a list

        param: dlt_msg: regular expression for B2B connection or CE area content
        param: max_wait: maximum waiting time for dlt
        param: name: name for B2B connection or CE area content
        param: bool drop: Set to True to don't collect non matching messages
        param: int count: number of messages to remove and return. 0 implies no limit, Defaults to 1
        param: bool raise_on_timeout: Whether to raise an exception on timeout. If set to False, all messages
        collected until timeout are returned.
        param: bool reboot: reboot the target, default set to False.
        returns: list of all messages received in current DLT context (until attributes match)
        """

        dlt_messages = []
        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as dlt_detector:
            if reboot:
                self.test.mtee_target.reboot()
            try:
                dlt_messages = dlt_detector.wait_for(
                    {"apid": "ALD", "ctid": "LCAT", "payload_decoded": dlt_msg},
                    timeout=max_wait,
                    regexp=True,
                    raise_on_timeout=raise_on_timeout,
                    count=count,
                    drop=drop,
                )
            except MteeTimeoutError:
                raise AssertionError(
                    f"Expected message to validate '{name}' was not received (or took longer than): "
                    f"'{max_wait}' sec). Expected message is: {dlt_msg}"
                )
        return dlt_messages

    def test_000_padi_launcher_available_after_reboot(self):
        """
        Check launcher is available and resolution is 8k after reboot

        *Background information*

        In this test we expect the launcher is available by checking the content, screen resolution is 8k
         and capture a screenshot as well after a target reboot.

        *Steps*
        1. Validate through UI the BMW launcher is present
        2. Reboot Target
        3. Take screenshot
        4. Validate through UI the BMW launcher is present
        5. Validate that PaDi android launcher starts with 8K resolution
        """

        self.__check_launcher()

        self.test.quit_driver()
        self.mtee_utils.reboot_target(apply_adb_workaround=True)
        self.test.setup_base_class()

        capture_screenshot(
            test=self.test,
            test_name="padi_launcher_available_screenshot_after_reboot",
        )

        self.__check_launcher()

        # Closing driver as next test is not using it
        self.test.quit_driver()

        resolution = self.test.apinext_target.execute_adb_command(["shell", "wm size"])
        assert resolution.stdout.decode("UTF-8") == f"Physical size: {self._resolution_8k}\n"

    def test_001_padi_bootanimation_validation(self):
        """Boot animation validation

        *steps*
         1. Check Boot Animation has started
         2. Register Boot Animation start time"
         3. Validate Boot animation file structure"

        """

        kpi_file_name, kpi_name = ("kpi_values", "K - USER Boot Animation Start")
        cmd = f"cat $(find /sys/kernel -name {kpi_file_name}) | grep '{kpi_name}'"
        res = self.test.mtee_target.execute_command(cmd, shell=True)
        if kpi_name not in res.stdout:
            raise ValueError(f"No value was found for the KPI: '{kpi_name}'")
        dir_to_copy = self.test.results_dir
        self.test.apinext_target.pull(src="/product/media/bootanimation.zip", dest=dir_to_copy, timeout=600)
        self.__validate_bootanimation_files(os.path.join(dir_to_copy, "bootanimation.zip"))

    def test_002_check_b2b_connection(self):
        """
        Check B2BConnection

         *Background information*

        1. In this test we expect the CE area content to be established in between 10 and 90 sec
            since the beginning of the lifecycle"
        2. Log check to verify the B2B connection heartbeat --> DLT/Logcat check the string
           "[B2B]B2BConnectionClient[2063]: requestConnectionOk()".And the time difference between
           heartbeat should be less than 1.8 sec.

        *Steps*
        1. Reboot the target
        2. Check the CE Area content dlt payload with "apid":"ALD", "ctid":"LCAT" it should arrive between 10-90 sec.
        3. Validate time stamps does it arrived between 10-90 seconds else raise MteeTimeoutError
        4. Check the B2B connection heartbeat
        5. Check the time difference between B2B connection heartbeat, it should be less than 1.8 sec.

        """
        maximum_wait = 120
        # checking CE area content payload arrived within 15-90 seconds
        ce_content_message = (
            r"BRSS\|AnimationManager\[*[\d]*\]:\ HDMI-Only variant, no need to wait for EB Boot complete, "
            r"stopping animation loop \(AnimationManager#.*:*[\d]*\)"
        )
        ce_dlt_messages = self.check_dlt_context(ce_content_message, maximum_wait, "CE area content", reboot=True)
        ce_valid_payload_time = True
        for ce_dlt_msg in ce_dlt_messages:
            if re.search(ce_content_message, ce_dlt_msg.payload_decoded):
                if not 10 < ce_dlt_msg.tmsp < 90:
                    ce_valid_payload_time = False
                    break
        assert ce_valid_payload_time, (
            f"Received expected CE area content but not in the range of 15-90 seconds, "
            f"it is arrived at '{ce_dlt_msg.tmsp}', and received payload is '{ce_dlt_msg.payload_decoded}'"
        )
        # checking B2B payload arrived in each 1-1.8 seconds
        b2b_connect_message = r"\[B2B\]B2BConnectionClient\[*[\d]*\]:\srequestConnectionOk"
        b2b_dlt_messages = self.check_dlt_context(
            b2b_connect_message,
            max_wait=maximum_wait,
            name="B2BConnectionClient",
            count=0,
            raise_on_timeout=False,
            drop=True,
        )
        b2b_valid_payload_time = True
        prev_time_tmsp = b2b_dlt_messages[0].tmsp
        for b2b_dlt_msg in b2b_dlt_messages[1:]:
            if b2b_dlt_msg.tmsp - prev_time_tmsp > 1.8:
                b2b_valid_payload_time = False
                break
            prev_time_tmsp = b2b_dlt_msg.tmsp
        assert b2b_valid_payload_time, (
            f"Received expected B2BConnection heartbeat but the time difference between all heartbeats is not less"
            f" than 1.8 sec, the B2BConnection heartbeat is arrived in '{b2b_dlt_msg.tmsp - prev_time_tmsp}' sec"
        )
        self.test.setup_base_class()
        self.__check_launcher()
