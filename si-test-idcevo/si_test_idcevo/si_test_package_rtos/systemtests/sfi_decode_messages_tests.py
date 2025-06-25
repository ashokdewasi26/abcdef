# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Check for SFI messages and decode them"""
import configparser
import logging
import os
import re
from itertools import pairwise
from pathlib import Path

from mtee.testing.tools import assert_equal, assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.dlt_logs_handlers import (
    decode_dlt_file_with_fibex,
    generate_new_dlt_file_with_upcoming_messages,
)
from si_test_idcevo.si_test_helpers.file_path_helpers import create_custom_results_dir


# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

SFI_FIBEX_FILE = "/images/Flashbins/IDCEvo-Artifacts/bins/sfi/{0}_sample/IDCevo_SFI.xml"

VALUES_REGEX = re.compile(r"Value\d:\s+(\d+)")
START_TEXT_REGEX = re.compile(r"\[Log Trace Test\]\: Trace Text")
TRACE_VALUE_REGEX = re.compile(r"\[Log Trace Test\]\: Trace Value:  (?P<value>\d*)")

SFI_LOGS = [
    re.compile(r"APIX PHY PCU OTP Revision:\s+0"),
    re.compile(r"SM-ControlDisplayState Channel E2E State Tx Count:"),
    re.compile(r"SM-SfiSafetyState Channel E2E State Tx Count:"),
]
# This just gives enough time to catch 2 or more test sequences for the SFI
DLT_TIME_WINDOW = 30

# Each test sequence has 4 msgs, we expect to decode 2 test sequences
# meaning that at least 8 msgs need to be decoded
MIN_SEQUENCES_TO_BE_TESTED = 2
MIN_DECODED_MSGS = MIN_SEQUENCES_TO_BE_TESTED * 4

SFI_ECUID = "SFIS"


class TestsSFINonVerboseDLT(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

        cls.results_dir = create_custom_results_dir("sfi_tests", cls.test.mtee_target.options.result_dir)

        cls.dlt_subset = os.path.join(cls.results_dir, "sfi_test_messages_new_broker.dlt")
        cls.sfi_dlt_decoded = os.path.join(cls.results_dir, "sfi_test_messages_non_verbose.dlt")
        cls.sfis_decoded_dlt = os.path.join(cls.results_dir, "sfis_decoded_dlt_file.dlt")
        cls.sfi_fibexfile = ""
        cls.sfi_decoded_messages = []

        cls.current_payload = ""
        cls.log_trace_sequence_index = 0
        cls.started_log_trace_test = False
        cls.current_log_trace_value = None
        cls.previous_log_trace_value = None
        cls.number_of_sequences_tested = 0

        cls.set_sfi_fibex_file()
        cls.sfi_log_check = False
        cls.sfi_log_timestamp = []
        cls.sfi_log_counter = 0

    @classmethod
    def fibex_exists(cls, variant):
        """
        Check if the fibex file exists for the given variant
        """
        cls.sfi_fibexfile = SFI_FIBEX_FILE.format(variant)
        return os.path.exists(cls.sfi_fibexfile)

    @classmethod
    def set_sfi_fibex_file(cls):
        """
        Set the SFI fibex file based on the hardware revision.

        This method removes the number from the hardware revision (e.g., B1 -> b),
        then attempts to find a valid fibex file by decrementing the letter until
        a folder is found or the letter is less than 'a'.

        Raises:
            FileNotFoundError: If no valid folder is found for the hardware revision.
        """
        pattern = r"[0-9]"
        # Remove the number from the hardware revision. Ex: B1 -> b
        hardware_variant = re.sub(pattern, "", cls.test.mtee_target.options.hardware_revision).lower()
        logger.debug(f"Original Hardware variant: {hardware_variant}")

        # Decrease letter until folder is found,
        # this is a workaround for the fibex file not being found in the original folder
        while not cls.fibex_exists(hardware_variant) and hardware_variant >= "a":
            hardware_variant = chr(ord(hardware_variant) - 1)
            logger.debug(f"Original fibex file not found, trying with: {hardware_variant}")

        if hardware_variant < "a":
            raise FileNotFoundError("No valid Fibex File found for the hardware revision.")

        logger.debug(f"Using SFI fibex filepath: {cls.sfi_fibexfile}")

    def check_all_elements_of_list_are_equal(self, list):
        """Check if all elements in a list are the same

        :param list: List containing the values to test
        :type list: List
        :return: True if all are the same or False if not
        :rtype: Bool
        """
        return all(i == list[0] for i in list)

    def search_sfi_start_text(self):
        """Search for the start of SFI Log Trace Test on current payload

        :return: True if current payload marks the start of the SFI Log Trace Test or False if not
        :rtype: Bool
        """
        if START_TEXT_REGEX.match(self.current_payload):
            logger.debug(f"Found message SFI start {self.current_payload}")
            self.log_trace_sequence_index += 1
            self.started_log_trace_test = True
            return True

        return False

    def get_current_log_trace_value(self):
        """Extracts the trace value from current payload"""
        match = TRACE_VALUE_REGEX.match(self.current_payload)
        self.current_log_trace_value = int(match.group("value"))

    def find_all_trace_values_in_payload(self):
        """Find all trace values on current payload

        :return: List of values found on current payload
        :rtype: List
        """
        return VALUES_REGEX.findall(self.current_payload)

    def search_display_and_safety_sfi_logs(self):
        """Search for display and safety related logs in current payload and ensures they appear in sequence.
        This functions ensures that payloads mentioned in list "SFI_LOGS" appears in sequence.

        :return: True if current payload matches the payload mentioned in SFI_LOGS or False if not
        :rtype: Bool
        """
        if self.sfi_log_counter == len(SFI_LOGS):
            self.sfi_log_check = True
        elif SFI_LOGS[self.sfi_log_counter].search(self.current_payload):
            logger.debug(f"Found message -  {self.current_payload}")
            self.sfi_log_counter += 1
            return True

    def check_all_msgs_timestamp_are_sequencial_or_equal(self, timestamp_list):
        """Check if all elements in a list are in incremental sequence or matches with the adjacent item.

        :param timestamp_list: List containing the values to test
        :type timestamp_list: List
        :return: True if all are in incremental sequence or same and False if not
        :rtype: Bool
        """
        logger.info(f"Matched Payload Timestamps -  {self.sfi_log_timestamp}")
        if all(a <= b for a, b in pairwise(timestamp_list)):
            return True
        else:
            return False

    def set_counters_for_next_set_of_traces(self):
        """This function resets / increments the counters for next bunch of SFI logs"""
        self.log_trace_sequence_index = 0
        self.started_log_trace_test = False
        self.previous_log_trace_value = self.current_log_trace_value
        self.number_of_sequences_tested += 1
        self.sfi_log_counter = 0
        self.sfi_log_check = False
        self.sfi_log_timestamp = []

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-26686",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "RTOS_SFI_DLT_LOGS"),
            },
        },
    )
    def test_001_decode_dlt_sfi_log_trace_test(self):
        """[SIT_Automated] Decode the SFI traces - Non Verbose

        Steps:
            1 - Create new DLT file with a 'DLT_TIME_WINDOW' seconds of messages (Currently using 30s of dlt msgs)
            2 - Load SFI fibex file to Non-Verbose DLT
            3 - Decode messages and write the one's with "SFIS" ECU ID to a new DLT file
            4 - Iterate all "SFIS" messages and find SFI Log Trace Test
            5 - Iterate by each Log Trace sequence and check values are as expected
                - Find first message of sequence
                - Find trace value
                - Find all other values and see if they are the same
                - Repeat and check if next trace value is incremented by one from previous

        Expected Result:
            - Messages are successfully decoded with SFI FIBEX file
            - SFI Log Trace Test sequence is found and all values are parsed and are equal
            - Values from the next Log Trace Test are incremented by one from previous
            - At least 2 Log Trace Test sequence were found
        """
        logger.info("Starting SFI trace non-verbose test")

        logger.info(f"Generate new dlt file for the upcoming messages in the next {DLT_TIME_WINDOW}s")
        generate_new_dlt_file_with_upcoming_messages(self.test.mtee_target, self.dlt_subset, DLT_TIME_WINDOW)

        self.sfi_decoded_messages = decode_dlt_file_with_fibex(
            self.sfi_fibexfile, self.dlt_subset, self.sfi_dlt_decoded, ecuid=SFI_ECUID
        )
        assert_true(
            len(self.sfi_decoded_messages) >= MIN_DECODED_MSGS,
            f"Unable to decode enough messages. Decoded only {len(self.sfi_decoded_messages)} msgs.",
        )

        for msg in self.sfi_decoded_messages:
            self.current_payload = msg.payload._to_str()

            if not self.started_log_trace_test:
                self.search_sfi_start_text()

            else:
                if self.log_trace_sequence_index == 1:
                    self.get_current_log_trace_value()

                    if self.previous_log_trace_value is not None:
                        assert_equal(
                            self.previous_log_trace_value + 1,
                            self.current_log_trace_value,
                            f"Current log and trace value should be {self.previous_log_trace_value + 1}"
                            f" but is {self.current_log_trace_value}",
                        )

                    self.log_trace_sequence_index += 1
                    continue

                elif self.log_trace_sequence_index == 2 or self.log_trace_sequence_index == 3:
                    logger.debug(f"Searching values on payload: {self.current_payload}")
                    values = self.find_all_trace_values_in_payload()
                    assert_true(
                        len(values) >= 2,
                        f"Expected to parsed 2 or 4 values on payload: {self.current_payload}",
                    )
                    assert_true(
                        self.check_all_elements_of_list_are_equal(values),
                        f"Not all values are the same: {self.current_payload}",
                    )
                    assert_equal(
                        self.current_log_trace_value,
                        int(values[0]),
                        f"Current trace value is {self.current_log_trace_value}"
                        f" and Values are {values}, should be all the same",
                    )
                    self.log_trace_sequence_index += 1
                    continue

                else:
                    logger.debug("Log trace sequence completed")
                    self.log_trace_sequence_index = 0
                    self.started_log_trace_test = False
                    self.previous_log_trace_value = self.current_log_trace_value
                    self.number_of_sequences_tested += 1

        assert_true(
            self.number_of_sequences_tested >= 2,
            f"Expected to process 2 or more sequences, got only {MIN_SEQUENCES_TO_BE_TESTED}."
            f"Check the {self.sfi_dlt_decoded} for more details.",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="RTOS",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Safety reaction test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-8738",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "INTER_NODE_COMMUNICATION_SFI_LINUX_COMMUNICATION"),
                    config.get("FEATURES", "RTOS_SFI_DLT_LOGS"),
                ],
            },
        },
    )
    def test_002_route_sfi_logs_to_node0_dlt_infra_test(self):
        """[SIT_Automated] Routing SFI logs to Node0 DLT Infrastructure

        Steps:
            1 - Decode messages and write the one's with "SFIS" ECU ID to a new DLT file
            2 - Iterate all "SFIS" messages and find SFI Log Trace Test
            3 - Iterate by each Log Trace sequence and check values are as expected
                - Find first message of sequence
                - Find trace value
                - Find all other values and see if they are the same
                - Find Control Display and Safety State logs
                - Repeat and check if next trace value is incremented by one from previous

        Expected Result:
            - SFI Log Trace Test sequence is found and all values are parsed and are equal
            - Values from the next Log Trace Test are incremented by one from previous
            - SFI Log Trace Test sequence is as expected
            - At least 2 Log Trace Test sequence were found
        """
        # Decode messages and write the one's with "SFIS" ECU ID to a new DLT file
        self.sfi_decoded_messages = decode_dlt_file_with_fibex(
            self.sfi_fibexfile, self.dlt_subset, self.sfis_decoded_dlt, ecuid=SFI_ECUID
        )
        assert_true(
            len(self.sfi_decoded_messages) >= MIN_DECODED_MSGS,
            f"Unable to decode enough messages. Decoded only {len(self.sfi_decoded_messages)} msgs.",
        )
        # Iterating all "SFIS" messages and evaluating SFI Log Trace Test Sequence
        for msg in self.sfi_decoded_messages:
            self.current_payload = msg.payload._to_str()
            # Find first message of sequence and note the timestamp.
            if not self.started_log_trace_test:
                if self.search_sfi_start_text():
                    self.sfi_log_timestamp.append(msg.std_header.timestamp)
            else:
                if self.log_trace_sequence_index == 1:
                    self.get_current_log_trace_value()
                    if self.previous_log_trace_value is not None:
                        assert_equal(
                            self.previous_log_trace_value + 1,
                            self.current_log_trace_value,
                            f"Current log and trace value should be {self.previous_log_trace_value + 1}"
                            f" but is {self.current_log_trace_value}",
                        )
                    self.log_trace_sequence_index += 1
                    continue
                # Find second and third msg of sequence and note the timestamp.
                elif self.log_trace_sequence_index == 2 or self.log_trace_sequence_index == 3:
                    logger.debug(f"Searching values on payload: {self.current_payload}")
                    self.sfi_log_timestamp.append(msg.std_header.timestamp)
                    values = self.find_all_trace_values_in_payload()
                    assert_true(
                        len(values) >= 2,
                        f"Expected to parsed 2 or 4 values on payload: {self.current_payload}",
                    )
                    assert_true(
                        self.check_all_elements_of_list_are_equal(values),
                        f"Not all values are the same: {self.current_payload}",
                    )
                    assert_equal(
                        self.current_log_trace_value,
                        int(values[0]),
                        f"Current trace value is {self.current_log_trace_value}"
                        f" and Values are {values}, should be all the same",
                    )
                    self.log_trace_sequence_index += 1
                    continue

                # Ensures display and safety related payloads appears in a row and parallely note the timestamp
                elif not self.sfi_log_check:
                    if self.search_display_and_safety_sfi_logs():
                        self.sfi_log_timestamp.append(msg.std_header.timestamp)
                    continue

                # The below code will execute after one sequence is completed.
                # It ensures all payloads were in sequence and then resets/increments the counter for next sequence.
                # Note, we do check the sequence in the above steps too.
                # The below validation is a sort of second level of validation via timestamp
                else:
                    assert_true(
                        self.check_all_msgs_timestamp_are_sequencial_or_equal(self.sfi_log_timestamp),
                        "Payloads didn't appear in incremental sequence or at same timestamp."
                        f"Matched Payload Timestamps:{self.sfi_log_timestamp}.",
                    )
                    self.set_counters_for_next_set_of_traces()

        assert_true(
            self.number_of_sequences_tested >= 2,
            f"Expected to process 2 or more sequences, got only {self.number_of_sequences_tested}."
            f"Check the {self.sfi_dlt_decoded} for more details.",
        )
