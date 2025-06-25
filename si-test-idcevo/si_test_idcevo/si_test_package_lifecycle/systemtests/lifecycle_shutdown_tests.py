# Copyright (C) 2024. BMW Car IT. All rights reserved.
import configparser
import logging
import os
import re
import time
from pathlib import Path
from unittest import skipIf

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import assert_equal, assert_false, assert_true, metadata, run_command
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.dlt_logs_handlers import validate_expected_dlt_payloads_in_dlt_trace
from si_test_idcevo.si_test_helpers.dmverity_helpers import disable_dm_verity
from si_test_idcevo.si_test_helpers.reboot_handlers import (
    reboot_and_wait_for_android_target,
    wait_for_application_target,
    wakeup_from_sleep_and_restore_vehicle_state,
)
from si_test_idcevo.si_test_helpers.test_helpers import skip_unsupported_ecus

from tee.target_common import FuncPN, VehicleCondition
from tee.tools.diagnosis import DiagClient
from tee.tools.dlt_helper import set_udp_broadcast_buffer_storage_time
from tee.tools.lifecycle import LifecycleFunctions
from validation_utils.utils import TimeoutCondition

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
lf = LifecycleFunctions()
target = TargetShare().target
target_type = target.options.target

PRUEFEN_ECU_POWER_DOWN_FILTER = [
    {"payload_decoded": re.compile(r".*Current PWF.* PRUEFEN.*")},
    {"payload_decoded": re.compile(r".*mal_cb_is_powerdownmode.*true.*")},
    {"payload_decoded": re.compile(r".*Dropping all the PNs.*PowerDownMode*")},
    {"payload_decoded": re.compile(r".*ShutdownType.*NormalShutdown.*")},
]

WUP_COUNTER_PATTERN = re.compile(r"setWupCounter\((\d+)\)")

WAKEUP_TRIGGER_DICT = [
    {"payload_decoded": re.compile(r"setWupCounter\((\d+)\)")},
    {"payload_decoded": re.compile(r".*WAKEUP_REASON_ETHERNET_ACTIVE.*")},
]

ERROR_RESET_CMD = "nsm_control --r 1"
PRUEFEN_AND_ERROR_RESET_FILTER = [
    {"payload_decoded": re.compile(r".*WAKEUP_REASON_ERROR_RESET.*")},
    {"payload_decoded": re.compile(r".*Current PWF.* PRUEFEN.*Previous PWF.*PRUEFEN")},
    {"payload_decoded": re.compile(r".*SHUTDOWN_ERROR_RESET.*")},
    {"payload_decoded": re.compile(r".*NsmNodeState_FastShutdown.*")},
]


class TestShutdown:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()

        # Issue "IDCEVODEV-412517" is causing setup level failures for CDE jobs.
        # For CDE LC job, as apinext setup is not needed as of now,
        # Below is a workaround and will be removed once this defect is fixed.
        if "cde" in target_type:
            cls.test.setup_base_class(skip_setup_apinext=True)
        else:
            cls.test.setup_base_class()

        cls.diagnostic_client = DiagClient(
            cls.test.mtee_target.diagnostic_address, cls.test.mtee_target.ecu_diagnostic_id
        )

    @classmethod
    def teardown_class(cls):
        """set defaults"""
        cls.test.teardown_base_class()
        cls.test.mtee_target.reboot(prefer_softreboot=False)
        cls.test.mtee_target.wait_for_nsm_fully_operational()

    def teardown(self):
        """Restores target into awake state and FAHREN if target ends the test asleep"""
        self.test.mtee_target._recover_ssh(record_failure=False)
        lf.set_default_vehicle_state()
        if not lf.is_alive():
            logger.debug("Sleeping after completed test, rebooting ...")
            lf.wakeup_target()
            self.test.mtee_target.wait_for_nsm_fully_operational()
            assert_true(
                lf.is_alive(),
                "Failing to restore initial state in PWF Living Driving tests - Target is not alive after test",
            )

    def restore_target_and_abort_test_if_not_alive(self):
        """Restores target if not alive after LC operations and aborts the test.
        Raise: AssertionError and reboots the target if found asleep.
        """
        if not lf.is_alive():
            logger.debug("Rebooting the Target, since target didn't wakeup from sleep")
            reboot_and_wait_for_android_target(self.test, prefer_softreboot=False)
            raise AssertionError(
                "Aborting the Test since target didn't wakeup from sleep after LC operation. ",
                "Rebooting the target and waiting for application mode.....",
            )

    def enable_and_validate_fpn(self):
        """Verify ECU stays alive with FPN enabled."""
        enable_fernwarntung_ecu_fpn_filter = [
            {
                "payload_decoded": re.compile(
                    r"NodeState: NsmNodeState_FullyOperational, NmState: ReadySleepState, "
                    r"Bpn: Standfunktionen, Fpn: 0x8"
                )
            },
            {
                "payload_decoded": re.compile(
                    r"^NetworkManagementUDPFullNW: readySleepState, BPN: KOM_STANDFUNKTIONEN_KUNDE_NICHT_IM_FZG,"
                    r"req\./active FPN: 0x[0-9A-Fa-f]{5}:0x[0-9A-Fa-f]{5}$"
                )
            },
            {"payload_decoded": re.compile(r".*set attribute FunctionalPartialNetworkStatus to 0x8")},
            {"payload_decoded": re.compile(r".*set attribute BasePartialNetworkStatus to KOM_KEINE_KOMMUNIKATION")},
        ]

        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
            lf.set_vcar_func_pn(FuncPN.FERNWARTUNG)
            assert_true(lf.is_alive(), "ECU is not alive with FPN enabled")

            dlt_msgs = trace.wait_for_multi_filters(
                filters=enable_fernwarntung_ecu_fpn_filter,
                count=0,
                timeout=60,
            )

        validate_expected_dlt_payloads_in_dlt_trace(
            dlt_msgs,
            enable_fernwarntung_ecu_fpn_filter,
            "SOC logs",
        )

    def disable_and_validate_fpn(self):
        """Verify ECU shutdown when FPN is disabled."""
        disable_fernwarntung_ecu_fpn_filter = [
            {"payload_decoded": re.compile(r"Changed ShutdownEventType:\sPostpone =>\sNormalShutdown")},
            {"payload_decoded": re.compile(r"Received VMControlCommand \[POWER_OFF\]")},
            {"payload_decoded": re.compile(r"setPowerState=SHUTDOWN_PREPARE")},
            {"payload_decoded": re.compile(r"^Changed VmState:\sRunning =>\sPoweringOff")},
            {"payload_decoded": re.compile(r"setPowerState=SHUTDOWN_START")},
            {"payload_decoded": re.compile(r"Changed HyperState:\sRunning =>\sPoweringOff")},
            {"payload_decoded": re.compile(r"Changed HyperState:\sPoweringOff =>\sOff")},
            {"payload_decoded": re.compile(r"Changed VmState:\sPoweringOff =>\sOff")},
            {"payload_decoded": re.compile(r"Changed NmState:\sReadySleepState =>\sPrepareBusSleepMode")},
            {"payload_decoded": re.compile(r"Changed NmState:\sPrepareBusSleepMode =>\sBusSleepMode")},
            {"payload_decoded": re.compile(r"Received prepareShutdownFinished")},
            {"payload_decoded": re.compile(r"\[SystemShutdown\] Powering off")},
            {"payload_decoded": re.compile(r"start unit: poweroff.service")},
        ]

        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
            lf.set_vcar_func_pn(0)
            lf.stop_keepalive()
            lf.ecu_to_enter_sleep(timeout=30)
            assert_false(lf.is_alive(), "ECU is alive with FPN disabled")

            dlt_msgs = trace.wait_for_multi_filters(
                filters=disable_fernwarntung_ecu_fpn_filter,
                count=0,
                timeout=180,
            )

        validate_expected_dlt_payloads_in_dlt_trace(
            dlt_msgs,
            disable_fernwarntung_ecu_fpn_filter,
            "SOC logs",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI", "SI-lifecycle", "ACM"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-10849",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "FORCED_POWER_OFF"),
                    config.get("FEATURES", "PLANT_DIAGNOSTIC_FUNCTIONS"),
                    config.get("FEATURES", "POWER_DOWN_MODE_ECU_MODES_SUPPORT"),
                    config.get("FEATURES", "SHUTDOWN_MODE_ECU_MODES_SUPPORT"),
                ],
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["rse26", "cde"]), "This test isn't supported by this ECU!")
    def test_001_power_down_ecu_mode(self):
        """
        [SIT_Automated] ECU mode: Power Down using diagnostics

        Steps:
        1. Trigger PRUEFEN_ANALYSE_DIAGNOSE vehicle state.
        2. Trigger 11 41 diag job to enable power down mode
        3. Trigger PARKEN_BN_IO/STANFUNCTIONEN
        4. Verify using DLT logs
        """
        try:
            with DLTContext(self.test.mtee_target.connectors.dlt.broker) as dlt_detector:
                self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
                self.diagnostic_client.ecu_powerdown()
                self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PARKEN_BN_IO)
                dlt_msgs = dlt_detector.wait_for_multi_filters(
                    filters=PRUEFEN_ECU_POWER_DOWN_FILTER,
                    timeout=60,
                    drop=True,
                    count=0,
                )
                validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, PRUEFEN_ECU_POWER_DOWN_FILTER, "EVO Logs")
        finally:
            wakeup_from_sleep_and_restore_vehicle_state(self.test)

    @metadata(
        testsuite=["BAT", "domain", "SI", "SI-lifecycle", "ACM"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-9010",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "STARTUP"),
                    config.get("FEATURES", "STARTUP_WAKEUP_BY_WAKEUP_PULSE"),
                    config.get("FEATURES", "STARTUP_TRIGGER_BY_WAKEUP_LINE"),
                ],
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["rse26", "cde"]), "This test isn't supported by this ECU!")
    def test_002_verify_ecu_startup_after_wup_trigger(self):
        """
        [SIT_Automated] Startup using Wakeup trigger
        Steps:
            1- Reboot the device and collect the WUPCounter value via SOC DLTContext
            2- Switch to PARKEN State as a precondition for wakeup trigger action.
            3- Start SOC DLT trace and switch to PRUEFEN State.
            4- Ensure WUPCounter and WAKEUP_REASON payloads are found after switching to PRUEFEN State
            5- Make sure WUPCounter is increased by 1 when compared with value captured at step1.
        """
        wup_counter_before_wake_up = None
        wup_counter_after_wake_up = None
        # Rebooting DUT to fetch WUP Counter
        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as reboot_traces:
            self.test.mtee_target.reboot(prefer_softreboot=False)
            filter_dlt_messages = reboot_traces.wait_for(
                attrs=WAKEUP_TRIGGER_DICT[0], timeout=180, raise_on_timeout=False
            )
        self.test.mtee_target._recover_ssh(record_failure=False)
        self.test.apinext_target.wait_for_boot_completed_flag(240)

        # Extracting WUP Counter value from SOC traces.
        for soc_msg in filter_dlt_messages:
            matches = WUP_COUNTER_PATTERN.search(soc_msg.payload_decoded)
            if matches:
                wup_counter_before_wake_up = matches.group(1)
                logger.info(f"Wup counter before wake up: '{wup_counter_before_wake_up}'")
                break

        # Switch to PARKEN State as a precondition for wakeup trigger action.
        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PARKEN_BN_IO)
        lf.stop_keepalive()
        lf.ecu_to_enter_sleep(timeout=80)
        time.sleep(10)

        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as pruefen_traces:
            lf.setup_keepalive()
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
            lf.wakeup_target(wait_for_serial_reboot=False)
            wake_up_reason_filter = pruefen_traces.wait_for_multi_filters(
                filters=WAKEUP_TRIGGER_DICT,
                count=0,
                drop=True,
                timeout=180,
            )

        # Extracting WUP Counter value after wakeup triggered.
        for soc_msg in wake_up_reason_filter:
            logger.info(f"DLT payloads: '{soc_msg.payload_decoded}'")
            matches = WUP_COUNTER_PATTERN.search(soc_msg.payload_decoded)
            if matches:
                wup_counter_after_wake_up = matches.group(1)
                logger.info(f"Wup counter after wake up: '{wup_counter_after_wake_up}'")
                break

        validate_expected_dlt_payloads_in_dlt_trace(wake_up_reason_filter, WAKEUP_TRIGGER_DICT, "SOC Logs")

        assert_equal(
            int(wup_counter_before_wake_up) + 1,
            int(wup_counter_after_wake_up),
            "WupCounter didn't increased by 1 after wakeup.",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI", "SI-lifecycle", "ACM"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-9001",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "SHUTDOWN"),
                    config.get("FEATURES", "SHUTDOWN_ECU_RESET"),
                    config.get("FEATURES", "RECOVERY_SHUTDOWN"),
                ],
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["rse26", "cde"]), "This test isn't supported by this ECU!")
    def test_003_verify_system_shutdown_with_error_reset(self):
        """
        [SIT_Automated] Verify System Shutdown with Error reset
        Steps:
        1. Trigger PRUEFEN_ANALYSE_DIAGNOSE.
        2. Trigger error reset using the command,
            "nsg_control --r 1"
        3. Validate using DLT logs.
        """
        disable_dm_verity()
        set_udp_broadcast_buffer_storage_time(10)
        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
            self.test.mtee_target.execute_command(ERROR_RESET_CMD)
            dlt_msgs = trace.wait_for_multi_filters(
                filters=PRUEFEN_AND_ERROR_RESET_FILTER,
                drop=True,
                count=0,
            )
        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, PRUEFEN_AND_ERROR_RESET_FILTER, "EVO logs")

    @metadata(
        testsuite=["BAT", "domain", "SI", "SI-lifecycle"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-88667",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "STARTUP_FIRST_SWITCH_TO_POWER"),
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["idcevo", "cde"]), "This test isn't supported by this ECU!")
    def test_004_verify_first_switch_to_power_startup(self):
        """
        [SIT_Automated] Verify first Switch to power Startup
        Steps:
            1. Start DLT traces and reboot the target
            2. Change vehicle status to PRUEFEN ANALYSE DIAGNOSE
            3. Capture a screenshot and check the file size.
            4. Set target to default vehicle state

        Expected Outcome:
            For step 2:
                - Ensure that expected payload mentioned in the list -"pad_pattern" are found in DLT traces.
                - Ensure that target is in application mode to make sure linux booted
            For step 3:
                - Ensure Android VM is up and file size is not 0.
        """
        pad_pattern = {"payload_decoded": re.compile(r".*PowerStateMachine input: pwf is: DIAGNOSE.*")}
        try:
            with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
                self.test.mtee_target.reboot(prefer_softreboot=False)
                self.test.mtee_target.wait_for_nsm_fully_operational()
                self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
                dlt_msgs = trace.wait_for(pad_pattern, count=1, timeout=60)
            validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, [pad_pattern], "SOC logs")

            assert_true(
                wait_for_application_target(self.test.mtee_target, timeout=180),
                "Target is not up after switching to PAD. Waited for 180 seconds.",
            )

            self.test.apinext_target.wait_for_boot_completed_flag()
            file_path = os.path.join(self.test.results_dir, "screenshot_android.png")
            self.test.apinext_target.take_screenshot(file_path)
            screenshot_file_size, _, _ = run_command(f"stat -c %s {file_path}", shell=True)
            assert_true(
                int(screenshot_file_size) != 0, f"Actual file size is {screenshot_file_size}. 0 size not expected"
            )
            self.restore_target_and_abort_test_if_not_alive()
        finally:
            lf.set_default_vehicle_state()

    @metadata(
        testsuite=["BAT", "domain", "SI", "SI-lifecycle"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-88247",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "CONTROL_AND_COORDINATE_NODE_STARTUP"),
                    config.get("FEATURES", "RECOVERY_SHUTDOWN"),
                    config.get("FEATURES", "SHUTDOWN_ECU_RESET"),
                ],
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["idcevo", "cde"]), "This test isn't supported by this ECU!")
    def test_005_verify_system_reset_nsm_reset(self):
        """
        [SIT_Automated] Verify System reset using application NSM reset
        Steps:
        1. Trigger NSM Application reset using reboot
        Expected Results:
        1. Ensure that expected payload mentioned in the list -"nsm_application_reset_payload" are found in DLT traces.
        2. Verify presence of the marker files in "/run/bootmode/"
        """
        nsm_application_reset_payload = [
            {"payload_decoded": re.compile(r".*PowerStateMachine input: pwf is: DIAGNOSE.*")},
            {"payload_decoded": re.compile(r"SHUTDOWN_APPLICATION_RESET\(5\)")},
            {"payload_decoded": re.compile(r".*NsmNodeState_FullyOperational.*5.*=>.*NsmNodeState_FastShutdown 8.*")},
            {"payload_decoded": re.compile(r".*NSM: Starting Collective Timeout for shutdown type FAST.*")},
            {"payload_decoded": re.compile(r"setWakeUpReasonWAKEUP_REASON_APPLICATION\(8\)")},
            {"payload_decoded": re.compile(r".*Current Boot Mode: Application.*")},
            {"payload_decoded": re.compile(r".*application.target.*")},
            {"payload_decoded": re.compile(r".*late.target.*")},
        ]
        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
        time.sleep(10)
        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as dlt_trace:
            self.test.mtee_target.reboot(prefer_softreboot=True)
            dlt_msgs = dlt_trace.wait_for_multi_filters(
                filters=nsm_application_reset_payload,
                count=0,
                drop=True,
                timeout=240,
            )
        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, nsm_application_reset_payload, "SOC logs")
        self.test.mtee_target._recover_ssh(record_failure=False)

        is_marker_file = self.test.mtee_target.exists("/run/bootmode/application")
        assert_true(is_marker_file, "Unable to create application marker file in path '/run/bootmode/'")

    @metadata(
        testsuite=["BAT", "SI", "SI-lifecycle"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-87081",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "STARTUP"),
                    config.get("FEATURES", "STARTUP_WAKEUP_BY_WAKEUP_PULSE"),
                ],
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["idcevo", "rse26"]), "This test isn't supported by this ECU!")
    def test_006_verify_ecu_startup_after_wup_trigger(self):
        """
        [SIT_Automated] Verify ECU Startup using valid BPN with an external WUP trigger
        Steps:
            1- Switch to PARKEN State as a precondition for WUP action
            2- Start SOC DLT traces and trigger a WUP action
            3- Start SOC DLT traces and switch to PRUEFEN State.
        Expected Results:
            for step 2:
                Validate payloads mentioned in list "wake_up_response_pattern" is present to ensure wakeup reason.
                If not, reboot the target and abort the test.
            for step 3:
                Valiate payloads mentioned in list "pad_pattern" is present to ensure target received valid BPN PAD.
        """
        disable_dm_verity()
        set_udp_broadcast_buffer_storage_time(10)
        wake_up_response_pattern = [
            {
                "apid": "HWAb",
                "ctid": "IOLI",
                "payload_decoded": re.compile(
                    r".*wakeupReasonResponseMessage:.*Wakeup Reason:.*WAKEUP_REASON_ETHERNET_ACTIVE\(4\).*",
                    re.IGNORECASE,
                ),
            }
        ]

        pad_pattern = [
            {
                "apid": "NSG",
                "ctid": "LCMG",
                "payload_decoded": re.compile(r"PowerStateMachine input.*pwf is: DIAGNOSE"),
            },
            {
                "apid": "NSG",
                "ctid": "NSG",
                "payload_decoded": re.compile(
                    r"Changed NodeState: NsmNodeState_BaseRunning => NsmNodeState_FullyRunning.*"
                ),
            },
            {
                "apid": "NSG",
                "ctid": "NSG",
                "payload_decoded": re.compile(
                    r"NmState: ReadySleepState.*Bpn: PruefenAnalyseDiagnose.*Pwf: DIAGNOSE.*"
                ),
            },
        ]

        # Switch to PARKEN State as a precondition for wakeup trigger action.
        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PARKEN_BN_IO)
        lf.stop_keepalive()
        lf.ecu_to_enter_sleep(timeout=80)
        time.sleep(10)

        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as traces:
            self.test.mtee_target.wakeup_from_sleep()
            lf.setup_keepalive()
            msg_filter = traces.wait_for(
                attrs=wake_up_response_pattern[0],
                count=1,
                drop=True,
                timeout=90,
                raise_on_timeout=False,
            )
        validate_expected_dlt_payloads_in_dlt_trace(msg_filter, wake_up_response_pattern, "SOC logs")

        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as traces:
            lf.setup_keepalive()
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
            lf.wakeup_target(wait_for_serial_reboot=False)
            msg_filter = traces.wait_for_multi_filters(
                filters=pad_pattern,
                count=0,
                drop=True,
                timeout=240,
            )
        self.restore_target_and_abort_test_if_not_alive()
        validate_expected_dlt_payloads_in_dlt_trace(msg_filter, pad_pattern, "SOC logs")

    @metadata(
        testsuite=["BAT", "SI", "SI-lifecycle"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-87014",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "NETWORK_MANAGEMENT_ETHERNET_BASE"),
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["idcevo", "rse26"]), "This test isn't supported by this ECU!")
    def test_007_ecu_remains_up_with_bpn_kom_wohnen(self):
        """
        [SIT_Automated] Verify ECU Remains up with BPN KOM_WOHNEN
        Pre_condition:
            1.Switch vehicle state to PRUEFEN_ANALYSE_DIAGNOSE
        Steps:
            1.Start SOC traces and switch to WOHNEN
        Expected Outcome:
            Ensure that expected WOHNEN payload
            mentioned in the list -"wohnen_soc_pattern" are found in DLT traces.
        """
        wohnen_soc_pattern = [
            {"payload_decoded": re.compile(r".*pwf is: WOHNEN.*")},
            {
                "payload_decoded": re.compile(
                    r".*NsmNodeState_FullyOperational, NmState: ReadySleepState, Bpn: Wohnen.*"
                )
            },
        ]
        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.WOHNEN)
            dlt_msgs = trace.wait_for_multi_filters(
                filters=wohnen_soc_pattern,
                drop=True,
                count=0,
                timeout=15,
            )
        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, wohnen_soc_pattern, "soc logs")

    @metadata(
        testsuite=["BAT", "SI", "SI-Lifecycle"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-86996",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NETWORK_MANAGEMENT_ETHERNET_BASE"),
                    config.get("FEATURES", "VM_LIFECYCLE_CONTROL"),
                ],
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["idcevo", "rse26"]), "This test isn't supported by this ECU!")
    def test_008_transit_between_pwf_states(self):
        """
        [SIT_Automated] Verify Shutdown behavior when PWF state transition from Wohnen to Standfunktionen
        Steps:
            1. Start DLT traces and switch powerstate to PAD
            2. Start DLT traces and switch powerstate to WOHNEN
            3. Start DLT traces and switch powerstate to Standfunktionen
        Expected Results:
            1. Target stays alive in PAD power state
            2. Target stays alive in WOHNEN state and ensure 'wohen_pwf_filter' payload are found in DLT logs
            3. Target should go to shutdown state and ensure 'standfunk_pwf_filter' payload are found in DLT logs
        """
        wohen_pwf_filter = [
            {"payload_decoded": re.compile(r".*set attribute BasePartialNetworkStatus to KOM_WOHNEN")},
            {"payload_decoded": re.compile(r".*PowerStateMachine input: pwf is: WOHNEN.*")},
            {"payload_decoded": re.compile(r'.*setPowerStateAttribute: distribute powerState: "(.*?)"')},
            {"payload_decoded": re.compile(r"Changed ShutdownState:\s StartUp => Running")},
        ]

        standfunk_pwf_filter = [
            {"payload_decoded": re.compile(r".*set attribute BasePartialNetworkStatus to KOM_KEINE_KOMMUNIKATION.*")},
            {"payload_decoded": re.compile(r".*PowerStateMachine input: pwf is: STANDFUNKTIONEN.*")},
            {
                "payload_decoded": re.compile(
                    r".*setPowerStateAttribute: distribute powerState: .*SHUTDOWN_MODE_USER_OFF.*"
                )
            },
            {"payload_decoded": re.compile(r"Changed NmState: PrepareBusSleepMode => BusSleepMode.*")},
            {
                "payload_decoded": re.compile(
                    r"^Changed NodeState: NsmNodeState_ShuttingDown => " r"NsmNodeState_Shutdown,$"
                )
            },
        ]

        self.test.mtee_target.set_vehicle_lifecycle_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
        try:
            with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
                self.test.mtee_target.set_vehicle_lifecycle_state(VehicleCondition.WOHNEN)
                dlt_msgs = trace.wait_for_multi_filters(
                    filters=wohen_pwf_filter,
                    drop=True,
                    count=0,
                    timeout=10,
                    skip=True,
                )
                assert_true(lf.is_alive(), "Ecu not alive in WOHNEN")

            validate_expected_dlt_payloads_in_dlt_trace(
                dlt_msgs,
                wohen_pwf_filter,
                "SOC logs",
            )

            with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
                self.test.mtee_target.set_vehicle_lifecycle_state(VehicleCondition.STANDFUNKTIONEN_KUNDE_NICHT_IM_FZG)
                lf.stop_keepalive()
                lf.ecu_to_enter_sleep(timeout=30)
                assert_false(lf.is_alive(), "Ecu is alive in STANDFUNKTIONEN_KUNDE_NICHT_IM_FZG")

                dlt_msgs = trace.wait_for_multi_filters(
                    filters=standfunk_pwf_filter,
                    count=0,
                    timeout=60,
                )

            validate_expected_dlt_payloads_in_dlt_trace(
                dlt_msgs,
                standfunk_pwf_filter,
                "SOC logs",
            )
        finally:
            wakeup_from_sleep_and_restore_vehicle_state(self.test)

    @metadata(
        testsuite=["BAT", "SI", "SI-Lifecycle"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-87007",
        traceability={
            "FEATURE": [
                config.get("FEATURES", "NETWORK_MANAGEMENT_ETHERNET_BASE"),
                config.get("FEATURES", "VM_LIFECYCLE_CONTROL"),
            ],
        },
    )
    @skipIf(skip_unsupported_ecus(["idcevo", "rse26"]), "This test isn't supported by this ECU!")
    def test_009_verify_ecu_behavior_with_fpn(self):
        """
        [SIT_Automated] Verify System Behavior with or without FPN request
        Steps:
                1. Set Vehicle state to STANDFUNKTIONEN
                2. Set FPN to Fernwarntung
                3. Disable FPN to 0
        Expected outcome:
                1. Verify system stays alive as long as it receives corresponding FPN is Received
                2. Ensure that expected payload
                    mentioned in the list -"fernwarntung_ecu_fpn_filter found in DLT traces.
                3. Verify system shutdown once FPN is disabled and Ensure that expected payload
                    from disable_fernwarntung_ecu_fpn_filter are found in dlt logs
        """
        try:
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.STANDFUNKTIONEN_KUNDE_NICHT_IM_FZG)
            self.enable_and_validate_fpn()
            self.disable_and_validate_fpn()
        finally:
            wakeup_from_sleep_and_restore_vehicle_state(self.test)

    @metadata(
        testsuite=["BAT", "domain", "SI", "SI-lifecycle"],
        component="tee_idcevo",
        domain="Lifecycle/Powermgmt",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-87084",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "STARTUP_WAKEUP_BY_WAKEUP_PULSE"),
                    config.get("FEATURES", "VM_LIFECYCLE_CONTROL"),
                ],
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["idcevo", "rse26"]), "This test isn't supported by this ECU!")
    def test_010_verify_ecu_startup_using_fernwertung_fpn_after_wup_trigger(self):
        """
        [SIT_Automated] Verify ECU Startup using Fernwertung FPN with an external WUP trigger
        Steps:
            1- Switch to PARKEN State as a precondition for wakeup trigger action.
            2- Start SOC DLT trace and trigger a FPN Keine_Kommunikation (0x0h)
            3- Trigger a 500ms WUP using Umlaut setup in IPB rack
            4- Start SOC DLT trace and trigger a FPN Fernwertung (0x8h)
            5- Start SOC DLT trace and trigger a FPN Fernwertung (0x0h)
        Expected Results:
        [For Step-3]
            Verify Wakeup reason is set to WAKEUP_REASON_ETHERNET_ACTIVE
        [For Step-4]
            FunctionalPartialNetworkStatus set to 8 (Fernwertung)
        [For Step-5]
            FunctionalPartialNetworkStatus set to 0 (Keine_Kommunikation)
        """
        wakeup_reason_ethernet_payload = [
            {"payload_decoded": re.compile(r"setWakeUpReason.*WAKEUP_REASON_ETHERNET_ACTIVE\(4\).*")},
            {"payload_decoded": re.compile(r".*ApplicationState:.*Fpn:.*0x0.*")},
        ]
        enable_fernwarntung_ecu_fpn_filter = [
            {"payload_decoded": re.compile(r".*FunctionalPartialNetworkStatus.*to.*0x200008.*")},
            {"payload_decoded": re.compile(r".*ApplicationState:.*Fpn:.*0x200008.*")},
            {"payload_decoded": re.compile(r".*NsmNodeState_FullyOperational.*5.*")},
        ]
        disable_fernwarntung_ecu_fpn_filter = [
            {"payload_decoded": re.compile(r".*Changed.*NmState:.*ReadySleepState.*=>.*PrepareBusSleepMode.*")},
            {"payload_decoded": re.compile(r".*Changed.*NmState:.*PrepareBusSleepMode.*=>.*BusSleepMode.*")},
            {"payload_decoded": re.compile(r".*ApplicationState:.*Fpn:.*0x0.*")},
            {"payload_decoded": re.compile(r".*NetworkManagementState.*to.*prepareBusSleepState.*")},
            {"payload_decoded": re.compile(r".*NetworkManagementState.*to.*busSleepState.*")},
            {"payload_decoded": re.compile(r".*ShutdownType.*:.*SHUTDOWN_FULL_OFF.*")},
        ]
        try:
            # Switch to PARKEN State as a precondition for wakeup trigger action.
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PARKEN_BN_IO)

            with DLTContext(self.test.mtee_target.connectors.dlt.broker) as soc_trace:
                lf.set_vcar_func_pn(0)
                lf.stop_keepalive()
                lf.ecu_to_enter_sleep(timeout=30)
                assert_false(lf.is_alive(), "ECU is alive with FPN disabled")
                self.test.mtee_target.wakeup_from_sleep()
                lf.setup_keepalive()
                self.test.mtee_target.resume_after_reboot()
                dlt_msgs = soc_trace.wait_for_multi_filters(
                    filters=wakeup_reason_ethernet_payload,
                    count=2,
                    drop=True,
                    timeout=80,
                )
            validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, wakeup_reason_ethernet_payload, "SOC logs")

            timer = TimeoutCondition(60)
            match = False
            with DLTContext(self.test.mtee_target.connectors.dlt.broker) as soc_trace:
                lf.set_vcar_func_pn(FuncPN.FERNWARTUNG)
                while timer:
                    if lf.is_alive():
                        match = True
                        break
                    else:
                        time.sleep(2)
                assert_true(match, "ECU is not alive with FPN enabled")
                dlt_msgs = soc_trace.wait_for_multi_filters(
                    filters=enable_fernwarntung_ecu_fpn_filter,
                    count=3,
                    drop=True,
                    timeout=80,
                )
            validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, enable_fernwarntung_ecu_fpn_filter, "SOC logs")

            with DLTContext(self.test.mtee_target.connectors.dlt.broker) as soc_trace:
                lf.set_vcar_func_pn(0)
                lf.stop_keepalive()
                lf.ecu_to_enter_sleep(timeout=30)
                assert_false(lf.is_alive(), "ECU is alive with FPN disabled")
                dlt_msgs = soc_trace.wait_for_multi_filters(
                    filters=disable_fernwarntung_ecu_fpn_filter,
                    count=6,
                    drop=True,
                    timeout=80,
                )
            validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, disable_fernwarntung_ecu_fpn_filter, "SOC logs")
        finally:
            if not lf.is_alive():
                logger.info("Waking up target from FPN disabled state!")
                self.test.mtee_target.wakeup_from_sleep()
                lf.setup_keepalive()
