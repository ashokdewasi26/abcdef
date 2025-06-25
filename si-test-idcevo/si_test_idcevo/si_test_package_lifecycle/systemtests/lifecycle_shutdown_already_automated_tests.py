# Copyright (C) 2025. BMW Car IT. All rights reserved.
import configparser
import logging
import re
import time
from pathlib import Path
from unittest import skipIf

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.dlt_logs_handlers import validate_expected_dlt_payloads_in_dlt_trace
from si_test_idcevo.si_test_helpers.reboot_handlers import (
    wait_for_application_target,
    wakeup_from_sleep_and_restore_vehicle_state,
)
from si_test_idcevo.si_test_helpers.test_helpers import skip_unsupported_ecus
from tee.target_common import VehicleCondition
from tee.tools.lifecycle import LifecycleFunctions


config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
lf = LifecycleFunctions()
target = TargetShare().target
target_type = target.options.target


class TestLifeCycleShutdown:
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

    @classmethod
    def teardown_class(cls):
        """set defaults"""
        cls.test.teardown_base_class()
        cls.test.mtee_target.reboot()
        cls.test.mtee_target.wait_for_nsm_fully_operational()

    def teardown(self):
        """Restores target into awake state and FAHREN if target ends the test asleep"""
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
        duplicates="IDCEVODEV-9020",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "SHUTDOWN"),
                    config.get("FEATURES", "ECU_MODES_SUPPORT"),
                    config.get("FEATURES", "NETWORK_MANAGEMENT"),
                    config.get("FEATURES", "NETWORK_MANAGEMENT_ETHERNET_BASE"),
                    config.get("FEATURES", "CUSTOMER_SHUTDOWN"),
                    config.get("FEATURES", "ECU_MODES_SUPPORT_APPLICATION_MODE"),
                    config.get("FEATURES", "SHUTDOWN_MODE_ECU_MODES_SUPPORT"),
                ],
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["rse26", "cde"]), "This test isn't supported by this ECU!")
    def test_001_verify_shutdown_behavior_with_pwf_05_pad_to_standfunktionen(self):
        """
        [SIT_Automated] Verify Shutdown behavior with PWF_05_PAD_to_STANDFUNKTIONEN
        Steps:
            1. Start DLT traces and switch to PAD PWF state
            2. Start DLT traces and switch to Standfunktion PWF state
        Expected Outcome:
            1. For step-1 -
            a. Ensure that expected payload mentioned in the below lists -"pad_soc_pattern" are found.
            b. Verify Display Comes up
            2. For step-2 -
            a. Ensure that expected payload mentioned in the below lists -"standfunktionen_soc_pattern" are found .
        """
        pad_soc_pattern = [
            {"payload_decoded": re.compile(r".*PowerStateMachine input: pwf is: DIAGNOSE.*")},
        ]
        standfunktionen_soc_pattern = [
            {"payload_decoded": re.compile(r".*pwf is: STANDFUNKTIONEN.*")},
            {"payload_decoded": re.compile(r".*powerState: SHUTDOWN_MODE_USER_OFF.*")},
            {"payload_decoded": re.compile(r".*Bpn: Standfunktionen.*")},
            {"payload_decoded": re.compile(r".*KOM_KEINE_KOMMUNIKATION.*")},
            {"payload_decoded": re.compile(r".*Changed Pwf: STANDFUNKTIONEN => INVALID.*")},
            {"payload_decoded": re.compile(r".*Changed NmState: ReadySleepState => PrepareBusSleepMode.*")},
            {"payload_decoded": re.compile(r".*Changed NmState: PrepareBusSleepMode => BusSleepMode.*")},
            {"payload_decoded": re.compile(r".*NetworkManagementServer.*prepareBusSleepState.*")},
            {"payload_decoded": re.compile(r".*NetworkManagementServer.*busSleepState.*")},
            {"payload_decoded": re.compile(r".*ShutdownType.*")},
            {"payload_decoded": re.compile(r".*NsmNodeState_ShuttingDown.*")},
        ]
        # Trigger PWF state to PAD as a precondition
        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as dlt_traces:
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
            dlt_msgs = dlt_traces.wait_for(
                attrs=pad_soc_pattern[0],
                count=1,
                drop=True,
                timeout=180,
                raise_on_timeout=False,
            )
        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, pad_soc_pattern, "SOC Logs")
        assert_true(
            wait_for_application_target(self.test.mtee_target, timeout=180),
            "Target is not up after switching to PAD. Waited for 180 seconds.",
        )
        # Trigger PWF state to Standfunktion
        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as dlt_traces:
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.WOHNEN)
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.STANDFUNKTIONEN_KUNDE_NICHT_IM_FZG)
            lf.stop_keepalive()
            lf.ecu_to_enter_sleep(timeout=80)
            dlt_msgs = dlt_traces.wait_for_multi_filters(
                filters=standfunktionen_soc_pattern,
                count=0,
                drop=True,
                timeout=60,
            )
        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, standfunktionen_soc_pattern, "SOC logs")

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
        duplicates="IDCEVODEV-32392",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "SHUTDOWN"),
                    config.get("FEATURES", "ECU_MODES_SUPPORT"),
                    config.get("FEATURES", "CUSTOMER_SHUTDOWN"),
                    config.get("FEATURES", "ECU_MODES_SUPPORT_APPLICATION_MODE"),
                ],
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["rse26", "cde"]), "This test isn't supported by this ECU!")
    def test_002_verify_shutdown_behavior_with_pwf_wohnen_to_parken(self):
        """
        [SIT_Automated] Validate ECU shutdown with PWF transition Wohnen_to_Parken
        Steps:
            1. Start SOC traces and switch to WOHNEN
            2. Start SOC traces and switch to PARKEN
        Expected Outcome:
            1. Ensure that expected WOHNEN payload
               mentioned in the list -"wohnen_soc_pattern" are found in DLT traces.
            2. Ensure that expected PARKEN payload
               mentioned in the list -"parken_soc_pattern" are found in DLT traces.
        """
        wohnen_soc_pattern = [
            {"payload_decoded": re.compile(r".*pwf is: WOHNEN.*")},
            {"payload_decoded": re.compile(r".*mal_cb_lcm_powerstate_detailed: ENTERTAINMENT.*")},
            {"payload_decoded": re.compile(r".*distribute powerState: ENTERTAINMENT_MODE_USER_ON.*")},
        ]
        parken_soc_pattern = [
            {"payload_decoded": re.compile(r".*PowerStateMachine transition: Entertainment => ShutdownMode.*")},
            {"payload_decoded": re.compile(r".*mal_cb_lcm_powerstate_detailed: SHUTDOWN_MODE.*")},
            {"payload_decoded": re.compile(r".*powerState: SHUTDOWN_MODE_USER_OFF.*")},
            {"payload_decoded": re.compile(r".*NmState: PrepareBusSleepMode => BusSleepMode.*")},
            {"payload_decoded": re.compile(r".*VmNmState: PrepareBusSleepMode => BusSleepMode.*")},
            {"payload_decoded": re.compile(r".*powerState: SLEEP_MODE_ALL_OFF.*")},
        ]
        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
            self.test.diagnostic_client.ecu_reset()
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.WOHNEN)

            dlt_msgs = trace.wait_for_multi_filters(
                filters=wohnen_soc_pattern,
                drop=True,
                count=0,
                timeout=60,
                skip=True,
            )
        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, wohnen_soc_pattern, "soc logs")
        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PARKEN_BN_IO)
            lf.stop_keepalive()
            lf.nm3_stop_sending_all()
            lf.ecu_to_enter_sleep(timeout=80)
            time.sleep(10)
            dlt_msgs = trace.wait_for_multi_filters(
                filters=parken_soc_pattern,
                drop=True,
                count=0,
                timeout=180,
                skip=True,
            )
        lf.setup_keepalive()
        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, parken_soc_pattern, "soc logs")

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
        duplicates="IDCEVODEV-9016",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "SHUTDOWN"),
                    config.get("FEATURES", "ECU_MODES_SUPPORT"),
                    config.get("FEATURES", "NETWORK_MANAGEMENT"),
                    config.get("FEATURES", "NETWORK_MANAGEMENT_ETHERNET_BASE"),
                    config.get("FEATURES", "CUSTOMER_SHUTDOWN"),
                    config.get("FEATURES", "ECU_MODES_SUPPORT_APPLICATION_MODE"),
                    config.get("FEATURES", "SHUTDOWN_MODE_ECU_MODES_SUPPORT"),
                ],
            },
        },
    )
    @skipIf(skip_unsupported_ecus(["rse26", "cde"]), "This test isn't supported by this ECU!")
    def test_003_verify_shutdown_behaviour(self):
        """
        [SIT_Automated] Verify Shutdown behavior with PWF_02_Wohnen_to_Standfunktionen
        Steps:
            1. Start DLT Traces and trigger WOHNEN vehicle state.
            2. Start DLT Traces and trigger STANDFUNKTIONEN_KUNDE_NICHT_IM_FZG vehicle state.

        Expected Outcome:
            - From step 1 ensure that expected payload mentioned in the list -
                "wohnen_pattern" are found in DLT traces.
            - From step 2 ensure that expected payload mentioned in the list -
               "standfunktionen_pattern" are found in DLT traces.
        """
        wohnen_pattern = [
            {"payload_decoded": re.compile(r".*PowerStateMachine.*pwf is.*WOHNEN.*")},
            {"payload_decoded": re.compile(r".*BasePartialNetworkStatus.*KOM_WOHNEN.*")},
            {"payload_decoded": re.compile(r".*powerState.*ENTERTAINMENT_MODE_USER_ON.*")},
            {
                "payload_decoded": re.compile(
                    r".*NodeState: NsmNodeState_FullyOperational.*NmState: ReadySleepState.*Bpn: WOHNEN.*"
                )
            },
        ]
        standfunktionen_pattern = [
            {"payload_decoded": re.compile(r".*PowerStateMachine.*STANDFUNKTIONEN.*")},
            {"payload_decoded": re.compile(r".*distribute powerState.*SHUTDOWN_MODE_USER_OFF.*")},
            {
                "payload_decoded": re.compile(
                    r".*ApplicationState.*NsmNodeState_FullyOperational.*ReadySleepState.*Standfunktionen.*"
                )
            },
            {
                "payload_decoded": re.compile(
                    r".*NetworkManagementServer.*unknown BasePartialNetwork setting to KOM_KEINE_KOMMUNIKATION.*"
                )
            },
            {"payload_decoded": re.compile(r".*Changed Pwf.*STANDFUNKTIONEN.*INVALID.*")},
            {"payload_decoded": re.compile(r".*NetworkManagementState.*prepareBusSleepState.*")},
            {"payload_decoded": re.compile(r".*NetworkManagementState.*busSleepState.*")},
            {"payload_decoded": re.compile(r".*ShutdownTypeNormal.*")},
            {
                "payload_decoded": re.compile(
                    r".*SHUTDOWN_FULL_OFF.*Sending prepareShutdown with maximum Standby Time: 0.*"
                )
            },
            {
                "payload_decoded": re.compile(
                    r".*Changed NodeState.*NsmNodeState_ShuttingDown.*NsmNodeState_Shutdown.*"
                )
            },
        ]
        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.WOHNEN)
            dlt_msgs = trace.wait_for_multi_filters(
                filters=wohnen_pattern,
                drop=True,
                count=0,
                timeout=60,
                skip=True,
            )
        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, wohnen_pattern, "SOC logs")

        with DLTContext(self.test.mtee_target.connectors.dlt.broker) as trace:
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.STANDFUNKTIONEN_KUNDE_NICHT_IM_FZG)
            lf.stop_keepalive()
            lf.ecu_to_enter_sleep(timeout=80)
            dlt_msgs = trace.wait_for_multi_filters(
                filters=standfunktionen_pattern,
                drop=True,
                count=0,
                timeout=60,
                skip=True,
            )
        validate_expected_dlt_payloads_in_dlt_trace(dlt_msgs, standfunktionen_pattern, "SOC logs")
