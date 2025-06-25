# Copyright (C) 2023. BMW Car IT GmbH. All rights reserved.
"""Interrupt shutdown test"""
import json
import logging
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from unittest import skipIf

from diagnose.hsfz import HsfzError
from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE, require_environment
from mtee.testing.tools import assert_true, metadata
from mtee.tools.utils import StopWatch
from tee.target_common import VehicleCondition
from tee.tools.diagnosis import DiagClient
from tee.tools.lifecycle import LifecycleFunctions

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name
target = TargetShare().target
diagnostic_client = DiagClient(target.diagnostic_address, target.ecu_diagnostic_id)
lifecycle_manager = LifecycleFunctions()

TEST_ENVIRONMENT = (TE.target.hardware.idcevo,)
DIAGNOSE_SLEEP_SECONDS: Tuple[int, ...] = (8, 16)
INTERRUPTED_SHUTDOWN_SLEEP_MIN_SECONDS: int = 1
INTERRUPTED_SHUTDOWN_SLEEP_MAX_SECONDS: int = 60

TracebackInfo = str
ExceptionTraceback = Tuple[Exception, TracebackInfo]


class InterruptedShutdownTestResult:
    def __init__(
        self,
        interrupt_sleep_seconds: int,
        session_states: Dict[int, Union[bool, ExceptionTraceback]],
        test_elapsed_time: float = -1,
        unknown_exception: Optional[ExceptionTraceback] = None,
        reboot_exception: Optional[ExceptionTraceback] = None,
    ):
        self.interrupt_sleep_seconds = interrupt_sleep_seconds
        self.session_states = session_states
        self.test_elapsed_time = test_elapsed_time
        self.unknown_exception = unknown_exception
        self.reboot_exception = reboot_exception

    def _exception_traceback_str(self, error: Optional[ExceptionTraceback] = None) -> str:
        if not error:
            return ""

        exception, traceback_info = error
        return f"{type(exception).__name__} - {str(exception)}, traceback: {traceback_info}"

    def is_pass(self) -> bool:
        if not self.session_states:
            return False
        if not any(value for value in self.session_states.values()):
            return False

        return not self.unknown_exception and not self.reboot_exception

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interrupt_sleep_seconds": self.interrupt_sleep_seconds,
            "diagnose_ping_stats": {
                key: value if isinstance(value, bool) else self._exception_traceback_str(value)
                for key, value in self.session_states.items()
            },
            "test_elapsed_time": self.test_elapsed_time,
            "unknown_exception": self._exception_traceback_str(self.unknown_exception),
            "reboot_exception": self._exception_traceback_str(self.reboot_exception),
        }

    def __repr__(self):
        return str(self.to_dict())


class InterruptShutdownTestReport:
    def __init__(self, test_report_path: Optional[Path] = None) -> None:
        self.test_results: List[InterruptedShutdownTestResult] = []

    def append(self, test_result: InterruptedShutdownTestResult) -> None:
        self.test_results.append(test_result)

    def is_pass(self) -> bool:
        return all(result.is_pass() for result in self.test_results)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pass": self.is_pass(),
            "test_elapsed_time_all": sum(test_result.test_elapsed_time for test_result in self.test_results),
            "num_success_tests": sum(int(test_result.is_pass()) for test_result in self.test_results),
            "num_failed_tests": sum(int(not test_result.is_pass()) for test_result in self.test_results),
            "details": {result.interrupt_sleep_seconds: result.to_dict() for result in self.test_results},
        }

    def write_report(self, test_report_path: Optional[Path] = None) -> None:
        test_report_path = test_report_path or (
            Path(target.options.result_dir)
            / "test_case_reports"
            / "interrupted_shutdown_test"
            / "test_001_interrupted_shutdown.json"
        )

        logger.info("Write test report for interrupted-shutdown test to %s", test_report_path)
        test_report_path.parent.mkdir(exist_ok=True, parents=True)
        test_report_path.write_text(json.dumps(self.to_dict(), indent=4))

    def __repr__(self):
        return str(self.to_dict())


@require_environment(*TEST_ENVIRONMENT)
@metadata(testsuite=["SI-long", "SI-long-staging"])
class TestInterruptedShutdown:
    def _run_interrupted_shutdown(self, interrupt_sleep_seconds: int) -> InterruptedShutdownTestResult:
        logger.info("Run interrupted-shutdown test with interrupt_sleep_seconds=%s", interrupt_sleep_seconds)

        initial_vehicle_condition = target.vehicle_state
        try:
            target.log_to_dlt(f"INTERRUPTED_SHUTDOWN_TEST - {interrupt_sleep_seconds} - START")

            target.switch_vehicle_to_state(VehicleCondition.PARKEN_BN_IO)

            # 1. Trigger shutdown message
            lifecycle_manager.stop_keepalive()

            # 2. Sleep some seconds
            time.sleep(interrupt_sleep_seconds)

            # 3. Trigger run-up message
            lifecycle_manager.setup_keepalive()
            target.switch_vehicle_to_state(VehicleCondition.FAHREN)
            target.wakeup_from_sleep()

            # 4. Check with diagnose job
            session_states: Dict[int, Union[bool, ExceptionTraceback]] = {}
            current_seconds = 0
            for check_seconds in DIAGNOSE_SLEEP_SECONDS:
                sleep_seconds = check_seconds - current_seconds
                time.sleep(sleep_seconds)
                current_seconds += sleep_seconds

                try:
                    diagnostic_client.ping_session_state()
                    session_states[check_seconds] = True
                except (EOFError, HsfzError, OSError, RuntimeError) as err:
                    session_states[check_seconds] = (err, traceback.format_exc())

            test_result = InterruptedShutdownTestResult(
                interrupt_sleep_seconds=interrupt_sleep_seconds, session_states=session_states
            )

            target.log_to_dlt(f"INTERRUPTED_SHUTDOWN_TEST - {interrupt_sleep_seconds} - DONE")
        except Exception as err:
            test_result.unknown_exception = (err, traceback.format_exc())

            logger.exception(
                "Unknown error for interrupted-shutdown test with interrupt_sleep_seconds: %s, err: %s",
                interrupt_sleep_seconds,
                str(err),
            )
        finally:
            try:
                target.switch_vehicle_to_state(initial_vehicle_condition)
                target._connect_to_target()
                target.reboot()
            except Exception as err:
                test_result.reboot_exception = (err, traceback.format_exc())

                logger.exception(
                    "Reboot error for interrupted-shutdown test with interrupt_sleep_seconds: %s, err: %s",
                    interrupt_sleep_seconds,
                    str(err),
                )

        logger.info(
            "Interrupted-shutdown test result with sleep %s: %s, session_states: %s",
            test_result.interrupt_sleep_seconds,
            test_result.is_pass(),
            test_result.session_states,
        )

        return test_result

    @metadata(
        testsuite=["SI", "SI-long", "SI-android", "SI-long-staging"],
        domain="SI",
        traceability={""},
    )
    @skipIf(target.has_capability(TE.test_bench.rack), "Skip the test for rack")
    def test_001_interrupted_shutdown(self) -> None:
        """Interrupted-shutdown test

        **Pre-conditions**
            N/A

        **Required Steps**
            #. Set Vehicle Condition to Parken_BN_IO
            #. Halt Keep Alive routine on vCar
            #. Sleep N (1-60) seconds for each test
            #. Trigger a run-up signal
            #. Perform RDBI_PING_SESSION_STATE UDS request

        **Expected outcome**
            * No errors happen during the test

        **Output File**
            - `test_case_reports/interrupted_shutdown_test/test_001_interrupted_shutdown.json`
        """
        test_report = InterruptShutdownTestReport()

        for interrupt_sleep_seconds in range(
            INTERRUPTED_SHUTDOWN_SLEEP_MIN_SECONDS, INTERRUPTED_SHUTDOWN_SLEEP_MAX_SECONDS + 1
        ):
            with StopWatch() as test_watch:
                test_result = self._run_interrupted_shutdown(interrupt_sleep_seconds)

            test_result.test_elapsed_time = test_watch.duration
            test_report.append(test_result)

        test_report.write_report()
        assert_true(test_report.is_pass(), f"Interrupted-shutdown test error with\n{test_report}")
