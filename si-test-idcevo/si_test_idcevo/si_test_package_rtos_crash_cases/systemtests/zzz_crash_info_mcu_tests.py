# Copyright (C) 2024. BMW Car IT GmbH. All rights reserved.
"""Rtos Crash Cases"""
import configparser
import logging
import re
import time

from pathlib import Path
from mtee.metric import MetricLogger
from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import assert_equal, assert_process_returncode, metadata
from si_test_idcevo import HARD_FAULT_CMD, MEMORY_MANAGE_FAULT_CMD, SAFETY_FAULT_CMD
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.diagnostic_helper import is_dtc_active
from si_test_idcevo.si_test_helpers.dlt_logs_handlers import validate_expected_dlt_payloads_in_dlt_trace
from tee.tools.secure_modes import SecureECUMode
from validation_utils.utils import CommandError, TimeoutError

# Config parser reading data from config file.
config = configparser.ConfigParser()

config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
metric_logger = MetricLogger()

CRASH_DTC = "A7631B"
CRASH_DTC_ID = 0xA7631B

MCU_PAYLOAD_AFTER_REBOOT_DICT = [{"apid": "DIAG", "ctid": "", "payload_decoded": re.compile(r"Sending DTC")}]

SOC_PAYLOAD_AFTER_REBOOT_DICT = [
    {"payload_decoded": re.compile(r"DTC Number\s+\[10969883]")},
    {"payload_decoded": re.compile(r"A7631B")},
]

MCU_PAYLOAD_AFTER_CRASH_COMMON_PATTERNS = [
    {"apid": "CORE", "ctid": "", "payload_decoded": re.compile(r"^Fault occur.*MCU startup")},
    {"apid": "CORE", "ctid": "", "payload_decoded": re.compile(r"^R0.*0x")},
    {"apid": "CORE", "ctid": "", "payload_decoded": re.compile(r"^R1\s+.*0x")},
    {"apid": "CORE", "ctid": "", "payload_decoded": re.compile(r"^R2.*0x")},
    {"apid": "CORE", "ctid": "", "payload_decoded": re.compile(r"^R3.*0x")},
    {"apid": "DIAG", "ctid": "", "payload_decoded": re.compile(r"Sending DTC:\s+10969883")},
    {"apid": "DIAG", "ctid": "", "payload_decoded": re.compile(r"Sending status:\s+1")},
]

MCU_PAYLOAD_AFTER_HARD_CRASH_DICT = [
    {"apid": "CORE", "ctid": "", "payload_decoded": re.compile(r"Hard Fault")},
    *MCU_PAYLOAD_AFTER_CRASH_COMMON_PATTERNS,
]

MCU_PAYLOAD_AFTER_MEM_CRASH_DICT = [
    {"apid": "CORE", "ctid": "", "payload_decoded": re.compile(r"Mem Manage Fault")},
    *MCU_PAYLOAD_AFTER_CRASH_COMMON_PATTERNS,
]

MCU_PAYLOAD_AFTER_SAFETY_CRASH_DICT = [
    {"apid": "CORE", "ctid": "", "payload_decoded": re.compile(r"OS Safety Critical Exception")},
    *MCU_PAYLOAD_AFTER_CRASH_COMMON_PATTERNS,
]

MCU_PAYLOAD_AFTER_RESTART_DICT = [
    {"apid": "SYST", "ctid": "", "payload_decoded": re.compile(r"System has been started")},
    {"apid": "DIAG", "ctid": "", "payload_decoded": re.compile(r"Sending DTC:\s+10969883")},
    {"apid": "DIAG", "ctid": "", "payload_decoded": re.compile(r"Sending status:\s+0")},
]

MCU_PAYLOAD_TIMEOUT = 180
SOC_PAYLOAD_TIMEOUT = 180


class TestsCrashInfoMCU(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        if not cls.test.mtee_target.connectors.ioc_dlt.broker.isAlive():
            cls.test.mtee_target.connectors.ioc_dlt.start()

        secure_mode_object = SecureECUMode(cls.test.mtee_target)
        current_mode = secure_mode_object.current_mode
        logger.info(f"Current target mode: {current_mode}")

        if current_mode != "ENGINEERING":
            secure_mode_object.switch_mode("ENGINEERING")
            logger.info("Engineering mode activated.")

        cls.test.diagnostic_client.set_energy_mode("NORMAL")

    def setup(self):
        """before each test ensure:
        DTC - "A7631B" is cleared.
        """
        logger.info("Initiating test setup")
        self.test.apinext_target.wait_for_boot_completed_flag(240)
        try:
            self.test.diagnostic_client.fs_loeschen()
        except Exception as e:
            logger.info(f"Error occurred while clearing DTC Memory. Error- {e}")

    def teardown(self):
        """after each test ensure:
        Target is rebooted.
        """
        logger.info("Initiating test teardown")
        self.test.mtee_target.reboot(prefer_softreboot=False)
        self.test.mtee_target._recover_ssh(record_failure=False)

    def trigger_fault_command_on_target(self, cmd):
        """This function can be used to trigger a fault on target
        :param cmd: crash command
        :type cmd: String
        """
        try:
            result = self.test.mtee_target.execute_command(cmd)
            assert_process_returncode(0, result.returncode, msg="Command '{}' failed\n{}\n".format(cmd, result))
        except (CommandError, TimeoutError) as e:
            logger.info(f"Encountered the following error while executing crash echo command: {e}")

    def trigger_crash_on_target_and_validate_mcu_and_soc_logs(self, crash_cmd, mcu_payload_dict, soc_payload_dict):
        """This function triggers a crash on the target and captures SOC and MCU DLT traces in parallel and
        waits for expected dlt payloads messages. Further it validates whether expected payloads are present
        in the trace and fails the function in case all expected dlt messages are not found
        :param str crash_cmd: crash command
        :param list mcu_payload_dict: expected mcu payloads
        :param list soc_payload_dict: expected soc payloads
        """

        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as soc_trace:
            with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as mcu_trace:
                self.trigger_fault_command_on_target(crash_cmd)
                mcu_filtered_trace = mcu_trace.wait_for_multi_filters(
                    filters=mcu_payload_dict,
                    count=0,
                    timeout=MCU_PAYLOAD_TIMEOUT,
                )
            soc_filtered_trace = soc_trace.wait_for_multi_filters(
                filters=soc_payload_dict,
                count=0,
                timeout=SOC_PAYLOAD_TIMEOUT,
            )
        validate_expected_dlt_payloads_in_dlt_trace(mcu_filtered_trace, mcu_payload_dict, "MCU Logs")
        validate_expected_dlt_payloads_in_dlt_trace(soc_filtered_trace, soc_payload_dict, "SOC Logs")
        self.test.mtee_target._recover_ssh(record_failure=False)

    def reboot_target_and_validate_mcu_and_soc_logs(self, mcu_payload_dict, soc_payload_dict):
        """This function reboots the target and captures SOC and MCU DLT traces in parallel and
        waits for expected dlt payloads messages. Further it validates whether expected payloads are present
        in the trace and fails the function in case all expected dlt messages are not found
        :param list mcu_payload_dict: expected mcu payloads
        :param list soc_payload_dict: expected soc payloads
        """
        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as soc_trace:
            with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as mcu_trace:
                self.test.mtee_target.reboot(prefer_softreboot=False)
                mcu_filtered_trace = mcu_trace.wait_for_multi_filters(
                    filters=mcu_payload_dict,
                    count=0,
                    timeout=MCU_PAYLOAD_TIMEOUT,
                )
            soc_filtered_trace = soc_trace.wait_for_multi_filters(
                filters=soc_payload_dict,
                count=0,
                timeout=SOC_PAYLOAD_TIMEOUT,
            )

        validate_expected_dlt_payloads_in_dlt_trace(mcu_filtered_trace, mcu_payload_dict, "MCU Logs")
        validate_expected_dlt_payloads_in_dlt_trace(soc_filtered_trace, soc_payload_dict, "SOC Logs")
        self.test.mtee_target._recover_ssh(record_failure=False)

    def validate_dtc_is_active_or_inactive(self, dtc_id, expected_status):
        """This function can be used to verify whether DTC is present and active or present and inactive.
        Pass "expected_status" = True in case if dtc is expected to be active
        Pass "expected_status" = False in case if dtc is expected to be inactive
        :param str dtc_id: dtc id. for ex - "A7631B"
        :param bool expected_status: expected dtc status
        """
        # It is observed that dtc flag sometimes takes time to update.\
        # Hence Polling the DTC status for 90 seconds at and interval of 10 seconds.
        status = ""
        for counter in range(10):
            status = is_dtc_active(self.test.diagnostic_client, CRASH_DTC)
            if status == expected_status:
                logger.info(f"DTC-{dtc_id} status is as expected. Status: {expected_status}")
                break
            else:
                time.sleep(10)
        assert_equal(
            status,
            expected_status,
            f" Expected DTC-{dtc_id} status: {expected_status}. Actual DTC-{dtc_id} status:{status}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI-crash-info-rtos"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-52149",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "CRASH_INFO"),
            },
        },
    )
    def test_001_crash_info_mcu_hard_fault(self):
        """
        [SIT_Automated] Crash Info MCU: Hard Fault (DTC 0xA7631B)
        **Steps**
             1- Reboot the target and validate SOC and MCU Logs
             2- Send echo command to trigger a Hard fault (3) and validate SOC and MCU Logs
                CMD - "echo -e -n '\\x01\\x00\\x00\\x05\\x00\\x03' > /dev/ipc12"
             3- Check DTC A7631B status
             4- Reboot the target and validate SOC and MCU Logs
             5- Check DTC A7631B status
        **Expected outcome**
            1- Search for "Sending DTC" in MCU Logs.
               Search for "DTC Number [10969863]" and search for "A7631B" in SOC Logs
            2- Search for "Fault occur after MCU startup", "R0 - 0x", "R1 - 0x", "R2 - 0x", "R3 - 0x",
               "Sending DTC: 10969883" with "Sending status 1" in MCU Logs
               Search for "DTC Number[10969883]" and search for "A7631B" in SOC Logs.
            3- Verify that A7631B DTC is present and active.
            4- Search for "System started", "Sending DTC: 10969883" with "Sending status 1" in MCU Logs.
               Search for "DTC Number [10969863]" and search for "A7631B" in SOC Logs
            5- Verify that A7631B DTC is still present but inactive.
        """

        self.reboot_target_and_validate_mcu_and_soc_logs(MCU_PAYLOAD_AFTER_REBOOT_DICT, SOC_PAYLOAD_AFTER_REBOOT_DICT)

        self.trigger_crash_on_target_and_validate_mcu_and_soc_logs(
            HARD_FAULT_CMD, MCU_PAYLOAD_AFTER_HARD_CRASH_DICT, SOC_PAYLOAD_AFTER_REBOOT_DICT
        )
        # Waiting for system to be up after crash.
        time.sleep(45)

        self.validate_dtc_is_active_or_inactive(CRASH_DTC, True)

        self.reboot_target_and_validate_mcu_and_soc_logs(MCU_PAYLOAD_AFTER_RESTART_DICT, SOC_PAYLOAD_AFTER_REBOOT_DICT)

        self.validate_dtc_is_active_or_inactive(CRASH_DTC, False)

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-52141",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "CRASH_INFO"),
            },
        },
    )
    def test_002_crash_info_mcu_memory_fault(self):
        """
        [SIT_Automated] Crash Info MCU: Memory Fault (DTC 0xA7631B)
        **Steps**
             1- Reboot the target and validate SOC and MCU Logs
             2- Send echo command to trigger a Memory Manage Fault (2) and validate SOC and MCU Logs
                CMD - "echo -e -n '\\x01\\x00\\x00\\x05\\x00\\x02' > /dev/ipc12"
             3- Check DTC A7631B status
             4- Reboot the target and validate SOC and MCU Logs
             5- Check DTC A7631B status
        **Expected outcome**
            1- Search for "Sending DTC" in MCU Logs.
               Search for "DTC Number [10969863]" and search for "A7631B" in SOC Logs
            2- Search for "Fault occur after MCU startup", "R0 - 0x", "R1 - 0x", "R2 - 0x", "R3 - 0x",
               "Sending DTC: 10969883" with "Sending status 1" in MCU Logs
               Search for "DTC Number[10969883]" and search for "A7631B" in SOC Logs.
            3- Verify that A7631B DTC is present and active.
            4- Search for "System started", "Sending DTC: 10969883" with "Sending status 1" in MCU Logs.
               Search for "DTC Number [10969863]" and search for "A7631B" in SOC Logs
            5- Verify that A7631B DTC is still present but inactive.
        """

        self.reboot_target_and_validate_mcu_and_soc_logs(MCU_PAYLOAD_AFTER_REBOOT_DICT, SOC_PAYLOAD_AFTER_REBOOT_DICT)

        self.trigger_crash_on_target_and_validate_mcu_and_soc_logs(
            MEMORY_MANAGE_FAULT_CMD, MCU_PAYLOAD_AFTER_MEM_CRASH_DICT, SOC_PAYLOAD_AFTER_REBOOT_DICT
        )
        # Waiting for system to be up after crash.
        time.sleep(45)

        self.validate_dtc_is_active_or_inactive(CRASH_DTC, True)

        self.reboot_target_and_validate_mcu_and_soc_logs(MCU_PAYLOAD_AFTER_RESTART_DICT, SOC_PAYLOAD_AFTER_REBOOT_DICT)

        self.validate_dtc_is_active_or_inactive(CRASH_DTC, False)

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-52151",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "CRASH_INFO"),
            },
        },
    )
    def test_003_crash_info_mcu_safety_fault(self):
        """
        [SIT_Automated] Crash Info MCU: Safety Fault (DTC 0xA7631B)
        **Steps**
             1- Reboot the target and validate SOC and MCU Logs
             2- Send echo command to trigger a Safety Fault (4) and validate SOC and MCU Logs
                CMD - "echo -e -n '\\x01\\x00\\x00\\x05\\x00\\x04' > /dev/ipc12"
             3- Check DTC A7631B status
             4- Reboot the target and validate SOC and MCU Logs
             5- Check DTC A7631B status
        **Expected outcome**
            1- Search for "Sending DTC" in MCU Logs.
               Search for "DTC Number [10969863]" and search for "A7631B" in SOC Logs
            2- Search for "Fault occur after MCU startup", "R0 - 0x", "R1 - 0x", "R2 - 0x", "R3 - 0x",
               "Sending DTC: 10969883" with "Sending status 1" in MCU Logs
               Search for "DTC Number[10969883]" and search for "A7631B" in SOC Logs.
            3- Verify that A7631B DTC is present and active.
            4- Search for "System started", "Sending DTC: 10969883" with "Sending status 1" in MCU Logs.
               Search for "DTC Number [10969863]" and search for "A7631B" in SOC Logs
            5- Verify that A7631B DTC is still present but inactive.
        """

        self.reboot_target_and_validate_mcu_and_soc_logs(MCU_PAYLOAD_AFTER_REBOOT_DICT, SOC_PAYLOAD_AFTER_REBOOT_DICT)

        self.trigger_crash_on_target_and_validate_mcu_and_soc_logs(
            SAFETY_FAULT_CMD, MCU_PAYLOAD_AFTER_SAFETY_CRASH_DICT, SOC_PAYLOAD_AFTER_REBOOT_DICT
        )
        # Waiting for system to be up after crash.
        time.sleep(45)

        self.validate_dtc_is_active_or_inactive(CRASH_DTC, True)

        self.reboot_target_and_validate_mcu_and_soc_logs(MCU_PAYLOAD_AFTER_RESTART_DICT, SOC_PAYLOAD_AFTER_REBOOT_DICT)

        self.validate_dtc_is_active_or_inactive(CRASH_DTC, False)
