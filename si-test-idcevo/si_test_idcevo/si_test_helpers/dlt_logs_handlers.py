# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Helper class to parse messages from DLT log."""

import csv
import logging
import os
import re
import time

from dlt.dlt_broker import DLTBroker
from dlt_non_verbose.dlt_non_verbose import DltNonVerbose
from mtee.testing.tools import assert_equal
from pydlt import DltFileWriter

logger = logging.getLogger(__name__)


def generate_new_dlt_file_with_upcoming_messages(target, filename="new_dlt_trace.dlt", timeout=20):
    """Generate a new dlt file with upcoming msg within the next "timeout" seconds

    :param target: TEE target
    :type target: Target
    :param filename: Name for the new dlt file, defaults to "new_dlt_trace.dlt"
    :type filename: str, optional
    :param timeout: Time to collect the DLT msg to the new file, defaults to 20
    :type timeout: int, optional
    """
    ip_address = target.get_dlt_server_address()
    broker = DLTBroker(
        ip_address,
        filename=filename,
        enable_dlt_time=True,
        enable_filter_set_ack=True,
        ignore_filter_set_ack_timeout=True,
    )
    broker.start()
    time.sleep(timeout)
    broker.stop()


def decode_dlt_file_with_fibex(fibexfile, dlt_file, decoded_dlt_file=None, ecuid=None):
    """Decode messages from dlt file given an fibex file

    To decode the messages the Fibex file need to be provided. The messages decoded will be
    returned has a list. Additionally we can filter to decode msgs only for a specific ECUID.

    **Important**
    Be careful not to try to decode the full dlt trace, this is intended to decode small dlt files.

    :param fibexfile: Path to the fibex file
    :type fibexfile: Path
    :param dlt_file: Path to the dlt file to decode msgs
    :type dlt_file: Path
    :param decoded_dlt_file: Path for the new dlt file to be created with decoded messages
    :type decoded_dlt_file: Path, optional
    :param ecuid: Filter dlt msgs by ecuid, defaults to None
    :type ecuid: Str, optional

    :return: List of the decoded messages
    :rtype: List
    """
    non_verbose_dlt = DltNonVerbose()
    non_verbose_dlt.parse_fibex_file(fibexfile)

    decoded_messages = []
    with DltFileWriter(decoded_dlt_file, append=True) as file:

        for msg in non_verbose_dlt.read_dlt_file(dlt_file):
            if ecuid:
                if msg.std_header.ecu_id == ecuid:
                    decoded_msg = non_verbose_dlt.decode_message(msg)
                    decoded_messages.append(decoded_msg)

                    if decoded_dlt_file:
                        file.write_message(decoded_msg)
            else:
                decoded_msg = non_verbose_dlt.decode_message(msg)
                decoded_messages.append(decoded_msg)

                if decoded_dlt_file:
                    file.write_message(decoded_msg)

    return decoded_messages


def validate_expected_dlt_payloads_in_dlt_trace(
    filtered_dlt_messages, payload_msg_to_validate, type_of_log="MCU Logs"
):
    """This function searches expected payloads in filtered DTL trace logs supplied as an argument.
    :param list filtered_dlt_messages: DLT Context filtered messages captured during trace
    :param list payload_msg_to_validate: Expected payloads to be searched in traced logs
        for ex - [{apid_1, ctid_1, payload_1},..., {apid_n, ctid_n, payload_n}]
    :param str type_of_log: Type of trace logs. It can ebe either MCU OR SOC type
    """
    dlt_msgs = []
    list_of_expected_payloads = [(dict_items["payload_decoded"]) for dict_items in payload_msg_to_validate]
    for ioc_msg in filtered_dlt_messages:
        for ioc_regex in list_of_expected_payloads:
            matches = ioc_regex.search(ioc_msg.payload_decoded)
            if matches:
                logger.info(f"Trace logs - {ioc_msg.payload_decoded}")
                logger.info(f"Match Found: '{matches}'")
                matched_found = matches.group(0)
                if matched_found not in dlt_msgs:
                    dlt_msgs.append(matched_found)
        if len(dlt_msgs) == len(payload_msg_to_validate):
            logger.info(f"Expected Payload - {dlt_msgs} found in {type_of_log}")
            return True

    assert_equal(
        len(dlt_msgs),
        len(payload_msg_to_validate),
        f"List of expected payloads - {list_of_expected_payloads}. Actual Payloads found- {dlt_msgs}",
    )


class DLTLogsHandler(object):
    def __init__(self, logger, files_path):
        self.logger = logger
        self.files_path = files_path

    def add_dlt_msg_to_dict(self, row, logs_found, csv_file):
        """
        Adds a specific DLT message payload and respective lifecycle to dict 'logs_found'.
        :param row: dlt message.
        :param logs_found: dict containing the target DLT logs found:
            dict key: DLT message payload
            dict item: list containg the lifecycles in which the message payload was found.
        :param csv_file: "dlt_msgs_of_interest.csv" file path.
        :return: adds DLT message payload and lifecycle to 'logs_found' dict.
        """

        if row["payload"] not in logs_found:
            logs_found[row["payload"]] = []

        # lifecycle folder is located on the penultimate position ([-2]) of the file path
        # (e.g. [..., 'extracted_files', 'Lifecycles', '02', 'dlt_msgs_of_interest.csv'])
        current_lifecycle = csv_file.split(os.sep)[-2]

        if current_lifecycle not in logs_found[row["payload"]]:
            logs_found[row["payload"]].append(current_lifecycle)

        return logs_found

    def parse_dlt_logs(self, settings, detailed_payload=False):
        """
        Used to parse DLT log messages.
        :param settings: dict containing configurations needed for each SearchDLTLogs test.
        It corresponds to the items format of DLT_LOG_VERIFICATION dict.
        :param detailed_payload: when enabled, it returns the full payloads found in the DLT logs.
        :return: dict with dlt logs found.
            dict key: regex pattern (str).
            dict item: list containing the lifecyles in which the regex pattern was found.
        """

        logs_found = {}
        for csv_file in self.files_path:
            with open(csv_file) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    for filter in range(len(settings["apid"])):
                        if (
                            (row["apid"] == settings["apid"][filter])
                            and (row["ctid"] == settings["ctid"][filter])
                            or not (settings["apid"][filter] and settings["ctid"][filter])
                        ):
                            for pattern in settings["pattern"][filter]:
                                if re.search(re.compile(pattern), row["payload"]):
                                    logs_found = self.add_dlt_msg_to_dict(row, logs_found, csv_file)
        if detailed_payload:
            return logs_found

        return self.process_dlt_logs_found(settings["pattern"], logs_found)

    def process_dlt_logs_found(self, pattern_list, logs_found):
        """
        Verifies if target DLT logs were found in all lifecycles.
        :param pattern_list: list containing the target regex patterns
        :param logs_found: dict containing the target DLT logs found:
            dict key: DLT message payload
            dict item: list containg the lifecycles in which the message payload was found.
        :return: adds DLT message payload and lifecycle to 'logs_found' dict.
        """
        logs_found_sorted = {}
        for list in range(len(pattern_list)):
            for pattern in pattern_list[list]:
                matching_items = []
                for pattern_found, list_lifecycles_found in logs_found.items():
                    if re.search(pattern, pattern_found):
                        for lifecycle in list_lifecycles_found:
                            matching_items.append(lifecycle)
                        logs_found_sorted[pattern] = sorted(set(matching_items))

                if pattern not in logs_found_sorted:
                    logs_found_sorted[pattern] = []

        return logs_found_sorted
