# Copyright (C) 2022. BMW CTW PT. All rights reserved.
"""Target startup tests"""
import csv
import logging
import time
import traceback
import os

from diagnose.hsfz import HsfzError
from mtee.metric import MetricLogger
from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import require_environment, TEST_ENVIRONMENT
from mtee.testing.tools import (
    TimeoutCondition,
    assert_greater_equal,
    assert_true,
    assert_less_equal,
    assert_false,
)
from tee.tools.diagnosis import DiagClient

target = TargetShare().target
logger = logging.getLogger(__name__)
metric_logger = MetricLogger()
RESPONSE_PAYLOAD = 0
RESPONSE_TIMESTAMP = 1
RESPONSE_EXCEPTION_TRACEBACK = 2
TEST_CASE_ID = "sf_startup"
diagnostic_client = DiagClient(target.diagnostic_address, target.ecu_diagnostic_id)


@require_environment(TEST_ENVIRONMENT.target.hardware)
class TestSystemStartup(object):
    """Target startup tests"""

    def __init__(self):
        self.countdown_uds_request = None
        self.countdown_target_connected = None
        self.timeout_value_uds_request = {"bmt": 10.0, "mgu22": 35.0, "idc23": 35.0, "rse22": 35.0, "mars": 20.0}
        self.timeout_value_target_connected = {"bmt": 30.0, "mgu22": 40.0, "idc23": 40.0, "rse22": 40.0, "mars": 30.0}
        self.minimum_time = 2.0
        self.poll_interval = 1.0
        self.ecu_diagnostic_address = target.ecu_diagnostic_id
        self.target_key = target.options.target
        self.responses_log = []

    def check_minimum_elapsed_time(self, timestamp):
        """Calculate whether minimum time has elapsed"""
        time_diff = self.minimum_time - timestamp
        return False if time_diff > 0 else True

    def check_responses(self, test_cycle=None):
        """Check all responses to each request"""
        last_valid_response = None
        # Error message that details obtained responses or lack thereof
        error_msg = "Failure on test cycle {}: \n".format(test_cycle + 1) if test_cycle else ""
        for response in self.responses_log:
            if response[RESPONSE_PAYLOAD] is not None:
                last_valid_response = response
                # Error message if ECU responded before performing reset
                # And no other requests have been processed
                error_msg += """Expected valid response to RDBI_PING_SESSION_STATE UDS request between
{} - {} seconds after reset. But timestamp of last known response was: {} seconds
""".format(
                    self.minimum_time,
                    self.timeout_value_uds_request[self.target_key],
                    last_valid_response[RESPONSE_TIMESTAMP],
                )
            else:
                # Error message if ECU did not respond at all
                error_msg += "Failed to ping ECU via UDS at timestamp: {} seconds. Handled exception: {}".format(
                    response[RESPONSE_TIMESTAMP], response[RESPONSE_EXCEPTION_TRACEBACK]
                )
        # Check last valid response was received after reset
        if last_valid_response is not None:
            assert_greater_equal(last_valid_response[RESPONSE_TIMESTAMP], self.minimum_time, error_msg)
            assert_less_equal(
                last_valid_response[RESPONSE_TIMESTAMP], self.timeout_value_uds_request[self.target_key], error_msg
            )
        # No responses have been found
        else:
            if self.responses_log:
                final_error_msg = """ECU did not respond to any RDBI_PING_SESSION_STATE UDS requests triggered within
{} seconds after ECU Reset. List of failed attempts:
{}
""".format(
                    self.timeout_value_uds_request[self.target_key], error_msg
                )
            raise AssertionError(final_error_msg)

    def log_to_csv(self, test_case_id, metric_id, timing_secs):
        csv_dir = os.path.join(target.options.result_dir, "extracted_files")
        csv_path = os.path.join(csv_dir, "test_systemfunctions_startup.csv")
        csv_header = ["test_case_id", "metric_id", "timing_secs"]

        if not os.path.isdir(csv_dir):
            return

        with open(csv_path, mode="a") as csv_file:
            csv_writter = csv.DictWriter(csv_file, fieldnames=csv_header)
            if csv_file.tell() == 0:
                csv_writter.writeheader()
            csv_writter.writerow({csv_header[0]: test_case_id, csv_header[1]: metric_id, csv_header[2]: timing_secs})

    def perform_ecu_reset(self):
        """Trigger diagnosis ECU-Reset"""
        exception_trace_ecu_reset = None
        uds_request_error = None
        try:
            diagnostic_client.ecu_reset()
            uds_request_error = False
        except (OSError, EOFError, RuntimeError, HsfzError):
            exception_trace_ecu_reset = traceback.format_exc()
            uds_request_error = True
        return uds_request_error, exception_trace_ecu_reset

    def polling_uds_ping_session_state(self):
        """Perform RDBI_PING_SESSION_STATE (0x22 f1 00) every 1000ms until request is accepted"""
        # Start timeout mechanism
        self.countdown_uds_request = TimeoutCondition(self.timeout_value_uds_request[self.target_key])
        self.countdown_target_connected = TimeoutCondition(self.timeout_value_target_connected[self.target_key])
        self.responses_log = []
        while self.countdown_uds_request:
            ecu_response = None
            event_timestamp = None
            exception_trace_ping_session_state = None
            # After the first 2 seconds following ecu_reset, perform RDBI_PING_SESSION_STATE (0x22 f1 00)
            # every 1000ms until request is accepted, as per 10505691-000-02 Fahrzeugprogrammierung: FL497
            # and FL496
            if self.check_minimum_elapsed_time(self.countdown_uds_request.time_elapsed):
                try:
                    ecu_response = diagnostic_client.ping_session_state()
                    event_timestamp = self.countdown_uds_request.time_elapsed
                except (OSError, EOFError, RuntimeError, HsfzError):
                    exception_trace_ping_session_state = traceback.format_exc()
                    self.responses_log.append(
                        (ecu_response, self.countdown_uds_request.time_elapsed, exception_trace_ping_session_state)
                    )
                else:
                    self.responses_log.append((ecu_response, event_timestamp, exception_trace_ping_session_state))
                    # Wait until valid response is obtained
                    if self.responses_log[-1][RESPONSE_PAYLOAD] is not None:
                        return event_timestamp
                time.sleep(self.poll_interval)

    def wait_for_target_reachability_network(self):
        """Perform regular network ping"""
        while self.countdown_target_connected:
            # Get target reachability
            target_reachable = target.check_network()
            if target_reachable:
                target_reachable_timestamp = self.countdown_target_connected.time_elapsed
                return target_reachable, target_reachable_timestamp
            time.sleep(self.poll_interval)

    def tc_sequence(self, test_cycle=None):
        """Common test sequence for test_001"""
        error_msg_prepend = "[Test cycle {}]".format(test_cycle + 1) if test_cycle else ""
        metric_id_suffix = "_consecutive_reset{}".format(test_cycle) if test_cycle and (test_cycle > 0) else ""
        # Trigger diagnosis ECU-Reset
        uds_request_error, exception_trace_ecu_reset = self.perform_ecu_reset()
        assert_false(
            uds_request_error,
            "{} Failed to complete ECU Reset UDS request on test cycle. Traceback: {}".format(
                error_msg_prepend, exception_trace_ecu_reset
            ),
        )
        # Perform RDBI_PING_SESSION_STATE (0x22 f1 00) until request is accepted
        uds_request_accepted_timestamp = self.polling_uds_ping_session_state()

        metric_logger.publish(
            "test_case_id={} metric_id={}{} timing_secs={}".format(
                TEST_CASE_ID, "uds_startup", metric_id_suffix, uds_request_accepted_timestamp
            )
        )
        self.log_to_csv(TEST_CASE_ID, "uds_startup" + metric_id_suffix, uds_request_accepted_timestamp)

        # Wait until target is reachable, by performing regular network ping
        target_reachable, target_reachable_timestamp = self.wait_for_target_reachability_network()

        metric_logger.publish(
            "test_case_id={} metric_id={}{} timing_secs={}".format(
                TEST_CASE_ID, "target_reachable", metric_id_suffix, target_reachable_timestamp
            )
        )
        self.log_to_csv(TEST_CASE_ID, "target_reachable" + metric_id_suffix, target_reachable_timestamp)

        # Ensure UDS request has been accepted within time limit after ECU Reset
        self.check_responses(test_cycle)
        # Check if target is reachable within time limit after ECU Reset
        assert_true(
            target_reachable,
            "{} Network ping not successful within {} seconds after ECU Reset".format(
                error_msg_prepend, self.timeout_value_target_connected[self.target_key]
            ),
        )
        assert_less_equal(
            target_reachable_timestamp,
            self.timeout_value_target_connected[self.target_key],
            "{} Network ping was successful but exceeded limit of {} seconds after ECU Reset".format(
                error_msg_prepend, self.timeout_value_target_connected[self.target_key]
            ),
        )

    def setup(self):
        """Test case preparation"""
        target.prepare_for_reboot()

    def teardown(self):
        """Test case teardown"""
        target.resume_after_reboot()
        # Get target connection status via SSH
        connected_to_target = target.is_connected()
        # Check if target is connected via SSH
        assert_true(connected_to_target, "SSH session not established")

    def test_001_uds_startup_and_target_availability(self):
        """Check target UDS request acceptance, reachability and SSH connectivity after reset

        **Pre-conditions**
            N/A

        **Required Steps**
            #. Trigger diagnosis ECU-Reset
            #. Start timer
            #. Perform RDBI_PING_SESSION_STATE (0x22 f1 00) until request is accepted
            #. Stop timer once first response after reset (outcome of step 3) is received

        **Expected outcome**
            * Response (as per step 4) shall be received in no more than 5 seconds otherwise
                it is considered as a failure. Also, to avoid false positives, responses shall
                be ignored in the first 2 seconds after reset.

            * Target is pingable within next 30 seconds after restart.
            * Serial console shows a reset has been executed.

        .. note:: Currently, UDS request acceptance timeout might be set to higher values

                * MGU22, 35 seconds is the temporary timeout
                * IDC23, 35 seconds is the temporary timeout
        """
        self.tc_sequence()
