# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Verify MCU Safety Mechanism"""
import configparser
import logging
import re
import time
from pathlib import Path
from unittest import SkipTest, skip, skipIf

from mtee.metric import MetricLogger
from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import assert_process_returncode, assert_true, metadata
from si_test_idcevo import (
    IAR_STACK_PROTECTION,
    LOOPBACK_TEST_CMD,
    MULTIBIT_ECC_ERROR_FOR_SRAMU,
    SAFETY_MCU_ROM,
    SAFETY_REACTION_TRIGGER_CMD,
    SAFETY_WAKEUP_REASON_CMD,
    SCG_SPLLCSR_CMD,
    SINGLE_BIT_ECC_CMD,
    SPACE_PROTECTION_CMD,
)
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.dlt_logs_handlers import validate_expected_dlt_payloads_in_dlt_trace
from si_test_idcevo.si_test_helpers.dmverity_helpers import validate_output, validate_output_using_regex_list
from si_test_idcevo.si_test_helpers.reboot_handlers import (
    ensure_application_target_for_specific_timeout,
    reboot_and_wait_for_android_target,
    wait_for_application_target,
)
from si_test_idcevo.si_test_helpers.test_helpers import check_ipk_installed, skip_unsupported_ecus
from tee.tools.lifecycle import LifecycleFunctions
from validation_utils.utils import CommandError, TimeoutError


# Config parser reading data from config file.
config = configparser.ConfigParser()

config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
metric_logger = MetricLogger()
target = TargetShare().target
hw_revision = target.options.hardware_revision
lf = LifecycleFunctions()

required_target_packages = ["audio-dsp-prebuild-mcipctest"]
LOOPBACK_ECHO_TEST_PASSED_PATTERN = re.compile(r".*echo test passed.*")

SAFETY_MCU_ROM_PAYLOAD = [
    {"apid": "TEST", "payload_decoded": re.compile(r"Successful call for ecc test:  0")},
    {"apid": "SYST", "payload_decoded": re.compile(r"System has been started!")},
    {
        "apid": "IOLI",
        "payload_decoded": re.compile(r"Recognized Wake Up: unrecoverable ECC fault for Code Flash memory"),
    },
]

WATCHDOG_EXPIRED_PAYLOAD = [
    {
        "apid": "SAFE",
        "payload_decoded": re.compile(r"Maximum duration between 2 SFI heartbeats is more than 100ms"),
    },
    {
        "apid": "SAFE",
        "payload_decoded": re.compile(r"\[SAFESTATE MGR\] Detected safety violation, reason.*6.*"),
    },
    {
        "apid": "SAFE",
        "payload_decoded": re.compile(
            r"\[SAFESTATE MGR\] Detected safety violation.*\(IPC timeout\).*enable safety reaction",
        ),
    },
]

SAFETY_MCU_DISPLAY_ENABLE = [
    {"apid": "SYST", "payload_decoded": re.compile(r"System has been started!")},
    {"apid": "SAFE", "payload_decoded": re.compile(r"\[SAFESTATE SM\] change state")},
    {"apid": "SAFE", "payload_decoded": re.compile(r"\[SAFESTATE MGR\] Enable.*0.*display")},
    {"apid": "SAFE", "payload_decoded": re.compile(r"\[SAFESTATE MGR\] Enable.*1.*display")},
    {"apid": "SAFE", "payload_decoded": re.compile(r"\[SAFESTATE MGR\] Enable.*2.*display")},
]

WATCHDOG_RESET_PAYLOAD = [
    {"apid": "SYST", "payload_decoded": re.compile(r"System has been started!")},
    {"apid": "SAFE", "payload_decoded": re.compile(r"\[SAFESTATE MGR] Enable.*0.*display")},
    {"apid": "IOLI", "payload_decoded": re.compile(r"Recognized Wake Up: IOC Watchdog reset")},
]

SFI_MCU_SAFETY_UART = [
    {"apid": "SAFE", "payload_decoded": re.compile(r".* Max refresh time in last 500 ms. ms:us  (\d+).*")},
    {"apid": "SAFE", "payload_decoded": re.compile(r".* stats: RX total= (\d+).*")},
]

SAFETY_TEMP_PAYLOAD = [
    {"apid": "IO_E", "payload_decoded": re.compile(r"Req simulate trigger: .*")},
    {"apid": "IO_E", "payload_decoded": re.compile(r"Req simulate temp:  123 , on sensor  3")},
    {"apid": "THM", "payload_decoded": re.compile(r"sensor \( 3 \) has  1230  C degrees \(x10\)")},
    {"apid": "THM", "payload_decoded": re.compile(r"Upgrading temp. level to  0  from  \d .*")},
    {"apid": "THM", "payload_decoded": re.compile(r".*new pwm duty:  99")},
    {"apid": "THM", "payload_decoded": re.compile(r"Initiating temp. shutdown!")},
    {"apid": "SAFE", "payload_decoded": re.compile(r"\[SAFESTATE MGR\].*disable  \d  display.*")},
]

SAFETY_FAULT_SIGNALED_PAYLOAD = [
    {"apid": "SAFE", "payload_decoded": re.compile(r"\[SM\] change value,  1 -> 0 , id  0")},
    {"apid": "SAFE", "payload_decoded": re.compile(r"\[SM\] change value,  1 -> 0 , id  1")},
    {"apid": "SAFE", "payload_decoded": re.compile(r"\[SM\] change value,  1 -> 0 , id  2")},
    {
        "apid": "SAFE",
        "payload_decoded": re.compile(r"\[SAFESTATE MGR\] Detected safety violation, reason  5  .*"),
    },
]

MCIPC_HW_FAULT_CMD = "/var/data/mcipc_test -s 0 -t 0 -c22 -d000C0001 -D4 -m1 -P1 -l1"

SYSTEM_START_AND_WATCHDOG_TIMER_FILTER = [
    {"apid": "SYST", "payload_decoded": re.compile(r".*System has been started.*")},
    {"apid": "SAFE", "payload_decoded": re.compile(r".* Max refresh time in last 500 ms. ms:us  (\d+).*")},
]

WATCHDOG_HEARTBEAT_FAILURE_FILTER = [
    {
        "apid": "SAFE",
        "payload_decoded": re.compile(
            r"\[SAFESTATE MGR\] Detected safety violation \(IPC timeout\), enable safety reaction"
        ),
    }
]


class TestsSafetyReaction(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

        if not cls.test.mtee_target.connectors.ioc_dlt.broker.isAlive():
            cls.test.mtee_target.connectors.ioc_dlt.start()

        cls.ipk_checked = check_ipk_installed(required_target_packages)

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

    def get_timestamp_and_payload_value_from_dlt_traces(self, traces, payload):
        """Extract time/counter from the payload and the timestamp of the log.
        Return the list of time/counter and timestamp"""
        dlt_time_counter = []
        dlt_timestamp = []
        for mcu_msg in traces:
            matches = payload.get("payload_decoded").search(mcu_msg.payload_decoded)
            if matches:
                match_value = matches.group(1)
                match_timestamp = mcu_msg.tmsp
                dlt_time_counter.append(match_value)
                dlt_timestamp.append(match_timestamp)
        logger.info(f"Time/counter list- {dlt_time_counter} and Timestamp list- {dlt_timestamp}")
        return dlt_time_counter, dlt_timestamp

    def periodic_messages_validation(self, values, periodicity):
        """This function can be used to validate Periodicity of payload.
        :param values: list of required payload timestamp
        :param periodicity: expected periodicity
        """
        status = False
        for d1, d2 in zip(values, values[1:]):
            if int(d1) + periodicity <= int(d2):
                status = True
                logger.info(f"Periodicity of payload {periodicity} found ")
                break
        return status

    def verify_target_wakeup_post_crash(self):
        """This Function will verify target wakeup post crash,
        :Raises: AssertionError and reboots the target if the target didn't wake up post crash.
        """
        if not wait_for_application_target(self.test.mtee_target):
            logger.debug("Rebooting the Target, since target didn't wakeup post crash")
            reboot_and_wait_for_android_target(self.test, prefer_softreboot=False)
            raise AssertionError(
                "Aborting the Test since target didn't wakeup post crash",
                "Rebooting the target and waiting for application mode.....",
            )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Safety",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Safety reaction test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-11420",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "MCU_INTERNAL_INTEGRITY"),
            },
        },
    )
    def test_001_verify_safety_reaction(self):
        """[SIT_Automated] Safety Mechanism MCU ROM Integrity | ECC fault for Code Flash memory
        Steps:
        - Enter the below Command for SFI Listen test.
          "echo -e -n '\\x01\\x00\\x00\\x07\\x00\\x00' > /dev/ipc12"
        - Verify reboot happened and expected payloads are available in IOC dlt
        Expected Payloads:
            - apid: "TEST", payload: "Successful call for ecc test: 0"
            - apid: "SYST", payload: "System has been started!",
            - apid: "IOLI", payload: "Recognized Wake Up: unrecoverable ECC fault for Code Flash memory"
        """

        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as trace:
            logger.info("Running echo cmd for SFI Listen test")
            self.trigger_fault_command_on_target(SAFETY_MCU_ROM)
            self.test.mtee_target._recover_ssh(record_failure=False)
            filterd_msg = trace.wait_for_multi_filters(
                filters=SAFETY_MCU_ROM_PAYLOAD,
                count=0,
                drop=True,
                timeout=60,
            )
        validate_expected_dlt_payloads_in_dlt_trace(filterd_msg, SAFETY_MCU_ROM_PAYLOAD)

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Safety",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Safety reaction test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-50736",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "SFI_MONITORING"),
            },
        },
    )
    def test_002_verify_safety_reaction(self):
        """[SIT_Automated] Safety Manager watchdog - IOC | Verify MCU triggers safe state when Safety manager stop
        sending periodic message ( Watchdog expired)
        Steps:
        - Install audio-dsp-prebuild-mcipctest ipk file
        - Send the below command on SOC Serial console to set FAULT_SAFETY_WATCHDOG fault in SFI.
          "mcipc_test -s 0 -t 0 -c22 -d000C0001 -D4 -m1 -P1 -l1"
        - Validate below keywords are found in the command response.
          "mcipc_sendmessage:successful", "[normal received]", "0x00,0x0c,0x00,0x00,"
        - Validate below payloads are observed in the IOC dlt.
          - Maximum duration between 2 SFI heartbeats is more than 100ms
          - [SAFESTATE MGR] Detected safety violation, reason  6  [2 - INTERNAL FAULT, 5 - IPC SFI REQ OFF,
          6 - IPC SFI TIMEOUT],.*0  display.*[.*0 - CID.*]
          - [SAFESTATE MGR] Detected safety violation, reason  6  [2 - INTERNAL FAULT, 5 - IPC SFI REQ OFF,
          6 - IPC SFI TIMEOUT],.*1  display.*[.*1 - HUD.*]
          - [SAFESTATE MGR] Detected safety violation, reason  6  [2 - INTERNAL FAULT, 5 - IPC SFI REQ OFF,
          6 - IPC SFI TIMEOUT],.*2  display.*[.*2 - PHUD.*]
        """

        if not self.ipk_checked:
            raise SkipTest(
                f"Skipping this test because the required IPKs, {required_target_packages}, "
                "weren't installed successfully!"
            )

        self.test.mtee_target.execute_command("mount -o remount,exec /var/data")
        command = "/var/data/mcipc_test -s 0 -t 0 -c22 -d000C0001 -D4 -m1 -P1 -l1"
        exp_result = [
            re.compile(r"mcipc_sendmessage:successful"),
            re.compile(r".*normal received.*"),
            re.compile(r".*,0x0c,0x00,.*"),
        ]
        self.test.mtee_target.execute_command("chmod +x /var/data")
        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as trace:
            result = self.test.mtee_target.execute_console_command(command, block=True)
            if result:
                validate_output_using_regex_list(result, exp_result)
            filterd_msg = trace.wait_for_multi_filters(
                filters=WATCHDOG_EXPIRED_PAYLOAD,
                count=0,
                drop=True,
                timeout=60,
            )

        validate_expected_dlt_payloads_in_dlt_trace(filterd_msg, WATCHDOG_EXPIRED_PAYLOAD)

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Safety",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Safety reaction test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-61455",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "SFI_MONITORING"),
            },
        },
    )
    @skip("HWAbstractionTestClient should not be used on System Test by BMW. Check IDCEVODEV-337270 ")
    def test_003_verify_safety_reaction(self):
        """[SIT_Automated]  System enters in 'safe state' If temperature range exceeded 123 C (SoC)

        Steps:
        1. Increase the SOC temperature to 123 degrees C/ any other sensor to 100 degrees.
           Enter the below command in Sys Console to simulate the temperature.
           "echo -e '1\n1\n123000' | HWAbstractionClient --interface 4"
        2. Check IOC logs for the temperature set and critical temperature shutdown is initiated.
           - Req simulate trigger: 1
           - Req simulate temp: 123 , on sensor 3
           - Upgrading temp. level to 0 from 3 , 0 = SYS_OFF, 1 = HIGH, 2 = NORMAL, 3 = LOW
           - new pwm duty: 99
           - sensor ( 3 ) has 1230 C degrees (x10)
           - Initiating temp. shutdown!
           - disable 0 display
        """
        command = "echo -e '1\n1\n123000' | HWAbstractionClient --interface 4"
        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as trace:
            logger.info("Running echo cmd for temperature range exceeded test")
            self.test.mtee_target.execute_console_command(command, block=False)
            time.sleep(120)  # Target comes up after 2 min if shutdown was initiated due to over temperature
            self.test.mtee_target.resume_after_reboot()
            filterd_msg = trace.wait_for_multi_filters(
                filters=SAFETY_TEMP_PAYLOAD,
                count=0,
                drop=True,
                timeout=180,
            )
        validate_expected_dlt_payloads_in_dlt_trace(filterd_msg, SAFETY_TEMP_PAYLOAD)
        self.test.diagnostic_client.clear_single_dtc(0xA76312)

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Safety",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Safety reaction test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-52090",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "SFI_MONITORING"),
            },
        },
    )
    def test_004_verify_safety_reaction(self):
        """[SIT_Automated] Safety Manager watchdog - IOC | Verify MCU triggers safe state
        when any fault signaled from SFI

        Steps:
        1. Install audio-dsp-prebuild-mcipctest ipk file
        2. Send the below command on SOC Serial console to set FAULT_SAFETY_WATCHDOG fault in SFI.
          "mcipc_test -s 0 -t 0 -c22 -d00030001 -D4 -m1 -P1 -l1"
        3. Validate below keywords are found in the command response.
          "mcipc_sendmessage:successful", "[normal received]", "0x00,0x03,0x00,0x00,"
        4. Validate below payloads are observed in the IOC dlt.
          - [SM] change value, 1 -> 0 , id 0
          - [SM] change value, 1 -> 0 , id 1
          - [SM] change value, 1 -> 0 , id 2
          - [SAFESTATE MGR] Detected safety violation, reason  5  .*
        """

        if not self.ipk_checked:
            raise SkipTest(
                f"Skipping this test because the required IPKs, {required_target_packages}, "
                "weren't installed successfully!"
            )

        command = "mcipc_test -s 0 -t 0 -c22 -d00030001 -D4 -m1 -P1 -l1"
        exp_result = ["mcipc_sendmessage:successful", "[normal received]", "0x00,0x03,0x00,0x00,"]
        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as trace:
            result = self.test.mtee_target.execute_console_command(command, block=True)
            if result is not None:
                validate_output(result, exp_result)
            filterd_msg = trace.wait_for_multi_filters(
                filters=SAFETY_FAULT_SIGNALED_PAYLOAD,
                count=0,
                drop=True,
                timeout=60,
            )
        validate_expected_dlt_payloads_in_dlt_trace(filterd_msg, SAFETY_FAULT_SIGNALED_PAYLOAD)

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Safety",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Safety manager test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-24348",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "SFI_MONITORING"),
            },
        },
    )
    @skip(
        "Test not applicable for SP21 (IDCEVODEV-465171). Also skipped for SP25 while"
        "test ticket in maintenance (IDCEVODEV-465171)"
    )
    def test_005_verify_safety_reaction(self):
        """[SIT_Automated] Verify MCU enable display based on initial control display E2E message from SFI
        Steps:
            1 - Start MCU DLT trace and Reboot the target.
            2 - Verify 1st display enabled related payload appears around or before 450ms after reboot.
            2 - Verify MCU DLT logs to make sure system has restarted and displays are enabled.
                Expected Payloads:
                -System has been started!
                -[SM] change state
                -[SAFESTATE MGR] Enable  0  display
                -[SAFESTATE MGR] Enable  1  display
                -[SAFESTATE MGR] Enable  2  display
            # ToDo - With the current setup, display validation is not a part of test right now
            # ToDo - but will in the future when required setups are ready.
        """
        display_enabled_1st_payload = SAFETY_MCU_DISPLAY_ENABLE[2]["payload_decoded"]

        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as mcu_trace:
            logger.info("Rebooting target to validate display state")
            self.test.mtee_target.reboot(prefer_softreboot=False)
            mcu_filtered_trace = mcu_trace.wait_for_multi_filters(
                filters=SAFETY_MCU_DISPLAY_ENABLE,
                count=0,
                timeout=90,
            )
            for filtered_message in mcu_filtered_trace:
                match = display_enabled_1st_payload.search(filtered_message.payload_decoded)
                if match:
                    logger.debug(f"Found display enabled 1st payload: {filtered_message.payload_decoded}")
                    time_taken_in_seconds = filtered_message.tmsp
                    time_taken_in_ms = float(time_taken_in_seconds) * 1000
                    logger.info(f"Time taken for display enabled 1st payload- {time_taken_in_ms} ms")
                    assert_true(float(time_taken_in_ms) <= 450, "Displays are not enabled in 450ms after reboot")

        validate_expected_dlt_payloads_in_dlt_trace(mcu_filtered_trace, SAFETY_MCU_DISPLAY_ENABLE, "MCU Logs")
        self.test.apinext_target.wait_for_boot_completed_flag(180)

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Safety",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Safety reaction test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-71564",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "MCU_EXTERNAL_INTEGRITY"),
            },
        },
    )
    def test_006_verify_safety_reaction(self):
        """[SIT_Automated] Verify safety reaction when external watchdog communication is interrupted
        Inject a fault to stop communication from external watchdog
        and verify MCU triggers safety reaction ( Displays OFF)
        Steps:
            - Rebooting the target to make sure previous fault related cases are not impacting this case.
            - Start MCU DLT trace and interrupt the communication between MCU and external monitor component
              SFI/ External Watchdog by using below command
              CMD: "echo -e -n '\\x01\\x00\\x00\\x0C\\x00' > /dev/ipc12"
        Expected Results:
            - From MCU DLT traces verify that system is rebooted and watchdog reset initialized.
            # ToDo - With the current setup, display validation is not a part of test right now.
            # ToDo - Display validation will be added when required setups are available.
        """
        self.hardware_revision = self.test.mtee_target.options.hardware_revision
        logger.info(f"Current hardware version- {self.hardware_revision}")
        if "C" not in self.hardware_revision:
            raise SkipTest("Skipping test as it requires Sample C hardware version")
        self.test.mtee_target.reboot(prefer_softreboot=False)
        self.test.mtee_target._recover_ssh(record_failure=False)
        self.test.apinext_target.wait_for_boot_completed_flag(180)
        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as mcu_trace:
            logger.info("Running echo cmd to inject safety reaction")
            self.trigger_fault_command_on_target(SAFETY_REACTION_TRIGGER_CMD)
            self.test.mtee_target._recover_ssh(record_failure=False)
            mcu_filtered_trace = mcu_trace.wait_for_multi_filters(
                filters=WATCHDOG_RESET_PAYLOAD,
                count=0,
                timeout=120,
            )

        validate_expected_dlt_payloads_in_dlt_trace(mcu_filtered_trace, WATCHDOG_RESET_PAYLOAD, "MCU Logs")

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="MCU SFI Echo test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-8471",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "MCU_SFI"),
            },
        },
    )
    def test_005_mcu_sfi_echo_loopback_test(self):
        """[SIT_Automated] INC Communication MCU - SFI -Echo test
        Steps:
            - Start MCU DLT trace on target
            - Trigger a loopback test between MCU and SFI
                cmd - "echo -e -n '\\x01\\x00\\x00\\x01\\x00\\x64\\x00\\x00\\x00\\x60' > /dev/ipc12"
            - In MCU DLT Logs, validate echo test passed.
                MCU logs must contain payload - "echo test passed"
        """
        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker, filters=[("FS3I", None)]) as trace:
            logger.info("Trigger echo command to raise a loopback test")
            result = self.test.mtee_target.execute_command(LOOPBACK_TEST_CMD)
            assert_process_returncode(
                0, result.returncode, msg="Command '{}' failed\n{}\n".format(LOOPBACK_TEST_CMD, result)
            )
            filter_dlt_messages = trace.wait_for(
                attrs={"payload_decoded": LOOPBACK_ECHO_TEST_PASSED_PATTERN}, timeout=45, raise_on_timeout=False
            )
            for ioc_msg in filter_dlt_messages:
                matches = LOOPBACK_ECHO_TEST_PASSED_PATTERN.search(ioc_msg.payload_decoded)
                if matches:
                    logger.info(f"Match found: '{matches}'")
                    break
            else:
                logger.info(f"Expected DLT Payload -{LOOPBACK_ECHO_TEST_PASSED_PATTERN.pattern} not found in MCU logs")
                raise AssertionError(
                    f"Expected DTL payload -{LOOPBACK_ECHO_TEST_PASSED_PATTERN.pattern} not found in MCU logs"
                )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Safety",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Safety reaction test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-182945",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "MCU_EXTERNAL_INTEGRITY"),
            },
        },
    )
    @skipIf(target.has_capability(TE.target.hardware.rse26), "Test not applicable for this ECU")
    @skipIf(target.has_capability(TE.target.hardware.cde), "Test not applicable for this ECU")
    @skipIf("C" not in hw_revision, "Skipping test as it requires Sample C hardware version")
    def test_006_mcu_sfi_the_safety_uart_functional_safety_test(self):
        """[SIT_Automated] Verify SFI and MCU uses the Safety UART for functional safety reasons.
        Steps:
            1. Start traces and Reboot the target
            2. Check MCU refresh the watchdog timer from safety task every 30ms.
            3. Calculate the Number of periodic messages received ( Log "[IPC] stats: RX") between two timestamps
        Expected Outcome:
            - ensure that "MCU refresh the watchdog" payload is received after every 30ms .
            - ensure that "[IPC] stats: RX" periodic messages is received after every 5sec
        """
        # Capture DLTContext, Rebooting the target and validate watchdog timer from safety task should be not same
        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as mcu_trace:
            self.test.mtee_target.reboot(prefer_softreboot=False)
            self.test.mtee_target._recover_ssh(record_failure=False)
            mcu_filtered_trace = mcu_trace.wait_for_multi_filters(
                filters=SFI_MCU_SAFETY_UART,
                count=0,
                timeout=180,
            )
        self.test.apinext_target.wait_for_boot_completed_flag(240)
        self.watchdog_timer, _ = self.get_timestamp_and_payload_value_from_dlt_traces(
            traces=mcu_filtered_trace,
            payload=SFI_MCU_SAFETY_UART[0],
        )

        assert_true(
            all(map(lambda x: x == self.watchdog_timer[0], self.watchdog_timer)),
            f"Expected refresh time = 30ms. Actual refresh time values = {self.watchdog_timer}",
        )
        # Calculate the Number of periodic messages received between two timestamps
        _, self.rx_timestamp = self.get_timestamp_and_payload_value_from_dlt_traces(
            traces=mcu_filtered_trace,
            payload=SFI_MCU_SAFETY_UART[1],
        )
        assert_true(
            self.periodic_messages_validation(self.rx_timestamp, 5),
            f"Expected timestamp diff = 5 Sec. Actual timestamp values = {self.rx_timestamp}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Safety",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Safety reaction test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-182959",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "MCU_EXTERNAL_INTEGRITY"),
            },
        },
    )
    @skipIf(
        "B" in hw_revision
        or target.has_capability(TE.target.hardware.rse26)
        or target.has_capability(TE.target.hardware.cde),
        "Skipping test as it requires IDCevo C sample hardware version",
    )
    def test_007_verify_no_periodic_logs_on_watchdog_failure(self):
        """[SIT_Automated] Verify Trigger Safety Watchdog failure and Check no Periodic logs on MCU DLT
        Steps:
            1. "audio-dsp-prebuild-mcipctest" ipk must be installed
            2. Do a reboot with KL30 off and on (hard reboot).
            3. Check if MCU refresh watchdog timer from safety task every 30ms using DLT logs.
            4. Trigger a FAULT_SAFETY_WATCHDOG fault in SFI using command,
                "mcipc_test -s 0 -t 0 -c22 -d000C0001 -D4 -m1 -P1 -l1"
            5. Verify if the heartbeat message is DLT is missed for more than 100ms.
        """
        if not self.ipk_checked:
            raise SkipTest(
                f"Skipping this test because the required IPKs, {required_target_packages}, "
                "weren't installed successfully!"
            )

        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as mcu_trace:
            self.test.mtee_target.reboot(prefer_softreboot=False)
            mcu_filtered_trace = mcu_trace.wait_for_multi_filters(
                filters=SYSTEM_START_AND_WATCHDOG_TIMER_FILTER,
                count=0,
                drop=True,
                timeout=180,
            )

        self.watchdog_timer, _ = self.get_timestamp_and_payload_value_from_dlt_traces(
            traces=mcu_filtered_trace,
            payload=SYSTEM_START_AND_WATCHDOG_TIMER_FILTER[1],
        )

        assert_true(
            all(map(lambda x: x == self.watchdog_timer[0], self.watchdog_timer)),
            f"Expected refresh time = 30ms. Actual refresh time values = {self.watchdog_timer}",
        )

        self.test.mtee_target.execute_command("chmod +x /var/data")
        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as mcu_trace:
            self.test.mtee_target.execute_console_command(MCIPC_HW_FAULT_CMD, block=True)
            mcu_filtered_trace = mcu_trace.wait_for(
                attrs=WATCHDOG_HEARTBEAT_FAILURE_FILTER[0],
                count=0,
                drop=True,
                timeout=180,
                raise_on_timeout=False,
            )
            self.test.mtee_target._recover_ssh(record_failure=False)
        validate_expected_dlt_payloads_in_dlt_trace(
            mcu_filtered_trace,
            WATCHDOG_HEARTBEAT_FAILURE_FILTER,
            "MCU Logs",
        )

    @metadata(
        testsuite=["BAT", "SI", "IDCEVO-SP25"],
        component="tee_idcevo",
        domain="Safety",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Safety reaction test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-13235",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "MCU_INTERNAL_INTEGRITY"),
            },
        },
    )
    def test_008_verify_safety_reaction(self):
        """[SIT_Automated] Verify ECC checks for RAM | single bit ECC error for SRAML
        Steps:
            1.Enter the below Command for SFI Listen test.
                "echo -e -n '\\x01\\x00\\x00\\x07\\x00\\x01' > /dev/ipc12"
            2.Verify no reboot happened
            3.Check the IOC DLT traces for single_bit_ecc_payload payload
        Expected Results:
            For Step-2 - Ensure target is alive
            For Step-3 - Ensure expected payload mentioned in single_bit_ecc_payload is found in IOC DLT traces
        """
        single_bit_ecc_payload = [
            {"apid": "TEST", "payload_decoded": re.compile(r"Successful call for ecc test:  1")},
            {"apid": "SAFE", "payload_decoded": re.compile(r"\[ECC\] Recognized Single-Bit ECC error for SRAML")},
            {"apid": "CORE", "payload_decoded": re.compile(r"ECC Fault")},
        ]
        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as trace:
            self.test.mtee_target.execute_command(SINGLE_BIT_ECC_CMD)
            filterd_msg = trace.wait_for_multi_filters(
                filters=single_bit_ecc_payload,
                count=3,
                drop=True,
                timeout=60,
            )

        assert_true(lf.is_alive(), "ECU not alive after issuing echo single bit ecc command")
        validate_expected_dlt_payloads_in_dlt_trace(filterd_msg, single_bit_ecc_payload)

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="Safety",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Safety reaction test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-27725",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "MCU_INTERNAL_INTEGRITY"),
            },
        },
    )
    @skipIf(not target.has_capability(TE.target.hardware.idcevo), "Test not applicable for this ECU")
    def test_009_space_protection_from_safety_memory_context(self):
        """
        [SIT_Automated] Verify MCU RAM integrity | Space protection from safety memory context
        Steps:
            1.Execute cmd in var "SPACE_PROTECTION_CMD" to trigger space protection.
            2.Verify target is rebooted and check for expected payloads in IOC DLT Traces
        Expected Results:
            Validate reboot payloads mentioned in a list "safety_protection_reset_patterns"
            are found after space protection trigger
        """
        safety_protection_reset_patterns = [
            {"payload_decoded": re.compile(r".*System has been started!.*")},
            {"payload_decoded": re.compile(r".*Bus Fault.*")},
            {"payload_decoded": re.compile(r".*Recognized Wake Up: unrecoverable MPU access violation.*")},
        ]
        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as trace:
            self.trigger_fault_command_on_target(SPACE_PROTECTION_CMD)
            self.test.mtee_target._recover_ssh(record_failure=False)
            filterd_msg = trace.wait_for_multi_filters(
                filters=safety_protection_reset_patterns,
                count=0,
                drop=True,
                timeout=120,
            )
        self.verify_target_wakeup_post_crash()
        validate_expected_dlt_payloads_in_dlt_trace(filterd_msg, safety_protection_reset_patterns, "IOC Logs")

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="Safety",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Safety reaction test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-61448",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "MCU_INTERNAL_INTEGRITY"),
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["rse26", "cde"]), "This test isn't supported by this ECU!")
    def test_010_verify_reset_wakeup_reason(self):
        """[SIT_Automated] Verify MCU performs a reset in case of core test failure with Wakeup reason
        Steps:
          1. Execute the below Command to perform failure for core tests -
             "echo -e -n '\\x01\\x00\\x00\\x0D\\x00' > /dev/ipc12"
          2. Check the Wakeup reason on IOC DLT logs after restart
          3. Check the Wakeup reason on SOC DLT logs after restart.
        Expected Payloads:
            [For Step-2]:
            Ensure the expected payload mentioned in "mcu_payload_after_sc_st_reset_dict " is found in IOC DLT Traces.
            [For Step-3]:
            Ensure the expected payload mentioned in "soc_payload_after_sc_st_reset_dict " is found in SOC DLT Traces.
        """
        mcu_payload_after_sc_st_reset_dict = [
            {"apid": "SYST", "ctid": "", "payload_decoded": re.compile(r".*System has been started.*")},
            {"apid": "", "ctid": "", "payload_decoded": re.compile(r".*\[SCST\].*Last test:35.*")},
            {"apid": "", "ctid": "", "payload_decoded": re.compile(r".*\[SCST\].*Reset.*")},
            {
                "apid": "IOLI",
                "ctid": "",
                "payload_decoded": re.compile(r".*Recognized Wake Up: Self Core Test failure.*"),
            },
        ]

        soc_payload_after_sc_st_reset_dict = [
            {
                "apid": "HIPC",
                "ctid": "HWAb",
                "payload_decoded": re.compile(
                    r".*INC_WAKEUP_REASON:.*WakeupReasonRequestMessage:.*Message Count: 2.*Command Length: 5.*"
                ),
            },
            {
                "apid": "IOLI",
                "ctid": "HWAb",
                "payload_decoded": re.compile(
                    r".*WakeupReasonResponseMessage:.*Wakeup Reason:.*WAKEUP_REASON_IC_SAFETY_VIOLATION_RESET_BLANK.*"
                ),
            },
            {
                "apid": "IOLI",
                "ctid": "HWAb",
                "payload_decoded": re.compile(
                    r".*setWakeUpReason.*WAKEUP_REASON_IC_SAFETY_VIOLATION_RESET_BLANK\(28\).*"
                ),
            },
        ]
        try:
            with DLTContext(self.test.mtee_target.connectors.dlt.broker) as soc_trace:
                with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as mcu_trace:
                    self.trigger_fault_command_on_target(SAFETY_WAKEUP_REASON_CMD)
                    self.test.mtee_target._recover_ssh(record_failure=False)
                    mcu_filtered_trace = mcu_trace.wait_for_multi_filters(
                        filters=mcu_payload_after_sc_st_reset_dict,
                        count=4,
                        timeout=60,
                    )
                soc_filtered_trace = soc_trace.wait_for_multi_filters(
                    filters=soc_payload_after_sc_st_reset_dict,
                    count=3,
                    timeout=60,
                )
            validate_expected_dlt_payloads_in_dlt_trace(
                mcu_filtered_trace, mcu_payload_after_sc_st_reset_dict, "MCU Logs"
            )
            validate_expected_dlt_payloads_in_dlt_trace(
                soc_filtered_trace, soc_payload_after_sc_st_reset_dict, "SOC Logs"
            )
        finally:
            if not lf.is_alive():
                logger.info("Waking up target from the shutdown state")
                self.test.mtee_target.wakeup_from_sleep()
                lf.setup_keepalive()
                self.test.mtee_target.resume_after_reboot()

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Safety",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Safety reaction test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-27726",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "MCU_INTERNAL_INTEGRITY"),
            },
        },
    )
    @skipIf(target.has_capability(TE.target.hardware.rse26), "Test not applicable for this ECU")
    @skipIf(target.has_capability(TE.target.hardware.cde), "Test not applicable for this ECU")
    def test_011_verify_iar_stack_protection(self):
        """
        [SIT_Automated] Verify Safety Mechanism MCU RAM integrity | IAR stack protection
        Steps:
            1. Enter the below Command for IAR stack protection.
                "echo -e -n '\\x01\\00\\x00\\x09\\x00\\x02' > /dev/ipc12"
        Expected Outcome:
            - Verify reboot has happened
            - Validate payloads mentioned in a list- "wakeup_mcu_payloads_pattern"
                and "safety_violation_soc_payloads_pattern" are present in MCU and SOC logs.
        """
        wakeup_mcu_payloads_pattern = [
            {"payload_decoded": re.compile(r".*System has been started.*")},
            {"payload_decoded": re.compile(r".*Recognized Wake Up.*unrecoverable IAR stack protection violation.*")},
        ]
        safety_violation_soc_payloads_pattern = [
            {"payload_decoded": re.compile(r".*INC_WAKEUP_REASON.*WakeupReasonRequestMessage.*Count.*Length.*")},
            {
                "payload_decoded": re.compile(
                    r".*WakeupReasonResponseMessage.*Wakeup Reason.*WAKEUP_REASON_IC_SAFETY_VIOLATION_RESET_BLANK.*"
                )
            },
            {"payload_decoded": re.compile(r".*setWakeUpReason.*WAKEUP_REASON_IC_SAFETY_VIOLATION_RESET_BLANK.*")},
        ]
        try:
            logger.info("Running echo cmd for IAR stack protection: IAR_STACK_PROTECTION")
            with DLTContext(self.test.mtee_target.connectors.dlt.broker) as soc_trace:
                with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as mcu_trace:
                    self.trigger_fault_command_on_target(IAR_STACK_PROTECTION)
                    self.test.mtee_target._recover_ssh(record_failure=False)
                    mcu_msg = mcu_trace.wait_for_multi_filters(
                        filters=wakeup_mcu_payloads_pattern,
                        skip=True,
                        count=2,
                        drop=True,
                        timeout=60,
                    )
                soc_msg = soc_trace.wait_for_multi_filters(
                    filters=safety_violation_soc_payloads_pattern,
                    skip=True,
                    count=3,
                    drop=True,
                    timeout=120,
                )
            validate_expected_dlt_payloads_in_dlt_trace(mcu_msg, wakeup_mcu_payloads_pattern, "MCU logs")
            validate_expected_dlt_payloads_in_dlt_trace(soc_msg, safety_violation_soc_payloads_pattern, "SOC logs")
        finally:
            if not lf.is_alive():
                logger.info("Waking up target from the shutdown state")
                self.test.mtee_target.wakeup_from_sleep()
                lf.setup_keepalive()
                self.test.mtee_target.resume_after_reboot()

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Safety",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Safety reaction test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-13043",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "MCU_INTERNAL_INTEGRITY"),
            },
        },
    )
    @skipIf(not target.has_capability(TE.target.hardware.idcevo), "Test not applicable for this ECU")
    def test_012_verify_emulate_change_of_register_scg_spllcsr_with_reset_type_soft(self):
        """
        [SIT_Automated] Verify emulate change of register: SCG_SPLLCSR with RESET_TYPE_SOFT
        Steps:
            1.Execute Command to Emulate Change of register: SCG_SPLLCSR
            2.Verify that the target has rebooted and check for expected payloads in IOC
            DLT Traces
        Expected Results:
            for step 2:
            1. Validate payloads mentioned in the list "reset_type_soft_payloads_pattern"
            are present in ioc traces.
            2. Expected at least one of the payloads from the list "wakeup_recognized_payloads_pattern"
            to be present in ioc traces
        """
        wakeup_recognized_payloads_validation = False
        reset_type_soft_payloads_pattern = [
            {"payload_decoded": re.compile(r".*Successful call for regcheck test:.*4 , reset type.*2.*")},
            {"payload_decoded": re.compile(r".*System has been started!.*")},
        ]

        wakeup_recognized_payloads_pattern = [
            {"payload_decoded": re.compile(r".*Recognized Wake Up: IOC Watchdog reset.*")},
            {"payload_decoded": re.compile(r".*Recognized Wake Up: register supervision violation.*")},
        ]
        logger.info("Running echo cmd for emulate change of register: SCG_SPLLCSR_CMD")
        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as trace:
            self.trigger_fault_command_on_target(SCG_SPLLCSR_CMD)
            self.test.mtee_target._recover_ssh(record_failure=False)
            reset_type_filter_msg = trace.wait_for_multi_filters(
                filters=reset_type_soft_payloads_pattern,
                count=2,
                drop=True,
                timeout=90,
            )
            wakeup_recognized_filterd_msg = trace.wait_for_multi_filters(
                filters=wakeup_recognized_payloads_pattern,
                count=0,
                drop=True,
                timeout=120,
            )
        for ioc_msg in wakeup_recognized_filterd_msg:
            if any(
                re.match(ioc_regex["payload_decoded"], ioc_msg.payload_decoded)
                for ioc_regex in wakeup_recognized_payloads_pattern
            ):
                logger.info(f"Messages found on DLT : '{ioc_msg.payload_decoded}'")
                wakeup_recognized_payloads_validation = True
                break
        self.verify_target_wakeup_post_crash()
        validate_expected_dlt_payloads_in_dlt_trace(
            reset_type_filter_msg, reset_type_soft_payloads_pattern, "IOC Logs"
        )
        assert_true(
            wakeup_recognized_payloads_validation,
            f"Expected at least one of the payloads from the list {wakeup_recognized_payloads_pattern}\n"
            "to be present, but none were found.",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Safety",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Safety reaction test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-13239",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "MCU_INTERNAL_INTEGRITY"),
            },
        },
    )
    @skipIf(not target.has_capability(TE.target.hardware.idcevo), "Test not applicable for this ECU")
    def test_013_verify_ecc_for_ram_and_sramu(self):
        """
        [SIT_Automated] Verify ECC checks for RAM | multibit ECC error for SRAMU
        Steps:
            1. Enter the below Command for SFI Listen test.
              "echo -e -n '\\x01\\x00\\x00\\x07\\x00\\x04' > /dev/ipc12"
        Expected Outcome:
            1. Validate payloads mentioned in list "ess_test_and_fault_payloads_pattern" are present to
            ensure Multibit ECC error.
            2. Verify no unwanted reboot happened.
        """
        ess_test_and_fault_payloads_pattern = [
            {"payload_decoded": re.compile(r".*Successful call for ecc test: .*4.*")},
            {"payload_decoded": re.compile(r".*System has been started!.*")},
            {"payload_decoded": re.compile(r".*Fault occur .* ms after MCU startup.*")},
            {"payload_decoded": re.compile(r".*Address of code where fault occur 0x.*")},
            {"payload_decoded": re.compile(r".*Return address of faulty function call was 0x.*")},
            {"payload_decoded": re.compile(r".*R0.*-.* 0x 7.*")},
            {"payload_decoded": re.compile(r".*R1.*- .*0x 0.*")},
            {"payload_decoded": re.compile(r".*R2.*- 0x 0.*")},
            {"payload_decoded": re.compile(r".*R3.* - 0x 30.*")},
            {"payload_decoded": re.compile(r".*R12.*- 0x.*")},
            {"payload_decoded": re.compile(r".*PSR.*- 0x 16777216.*")},
            {"payload_decoded": re.compile(r".*ACTLR / LMFAR - 0x.*")},
            {"payload_decoded": re.compile(r".*DFSR / LMFATR - 0x.*")},
            {"payload_decoded": re.compile(r".*AFSR - 0x.*")},
            {"payload_decoded": re.compile(r".*MPU IAddress - 0x.*")},
            {"payload_decoded": re.compile(r".*MPU DAddress - 0x.*")},
            {"payload_decoded": re.compile(r".*MPU CurPrio - 0x.*")},
            {"payload_decoded": re.compile(r".*Recognized Wake Up: unrecoverable ECC fault for SRAMU memory.*")},
        ]
        with DLTContext(self.test.mtee_target.connectors.ioc_dlt.broker) as trace:
            self.trigger_fault_command_on_target(MULTIBIT_ECC_ERROR_FOR_SRAMU)
            self.test.mtee_target._recover_ssh(record_failure=False)
            filtered_msg = trace.wait_for_multi_filters(
                filters=ess_test_and_fault_payloads_pattern,
                count=0,
                drop=True,
                timeout=120,
            )
        self.verify_target_wakeup_post_crash()
        validate_expected_dlt_payloads_in_dlt_trace(filtered_msg, ess_test_and_fault_payloads_pattern)
        target_status = ensure_application_target_for_specific_timeout(self.test.mtee_target)
        assert_true(target_status, "Unexpected reboots occurred after ECC checks. This was not expected")
