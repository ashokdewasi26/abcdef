# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Searches for GNSS messages in DLT log file."""
import configparser
import logging
import re
from pathlib import Path

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import assert_equal, assert_is_not_none, assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

TARGET_BASE_GNSS_HAL_LOG = [
    {
        "payload_decoded": re.compile(
            r"NAVD\[\d+\]:int Positioning::GNSSPositioningProducer::init\(\) : GnssPositioningProxy "
            r"sucessfully created for domain : local and instance : (\d)"
        )
    },
    {
        "payload_decoded": re.compile(
            r"NAVD\[\d+\]:int Positioning::VehicleCoding::getInstanceIdFlagValue\(int64_t &\) : Flag value : (\d)"
        )
    },
]


class TestsBaseGNSS(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(root=True)

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def divide_list_into_chunks(self, msgs, list_size=11):
        """
        Split list of msgs into chunks. By default the list will be divided into sublists with 10 elements each
        """
        for i in range(0, len(msgs), list_size):
            yield msgs[i : i + list_size]  # noqa: E203

    def validate_gnss_frequency(self, dlt_msgs):
        """
        Steps to validate frequency:
            - Limit the number of DLT messages found to have a total number divisible by ten
            - Split the DLT messages into sublists with ten messages
            - Get the first and last element of each sublist
            - Check if difference of timestamp between the two is one second with a deviation of one percent
        """
        frequency_time = 1000  # ms -> 1 second
        total_deviation = frequency_time * 0.01  # Deviation of 1%
        dlt_messages_chunk_size = 10

        split_dlt_msgs = list(self.divide_list_into_chunks(dlt_msgs, dlt_messages_chunk_size))

        for sublist_dlt_msg in split_dlt_msgs:
            if len(sublist_dlt_msg) < dlt_messages_chunk_size:
                continue
            pattern = re.compile(r"NAVD\[\d+\]:GNSSTime : SysTime=(\d+), Timestamp=(?P<timestamp>\d*),.*")
            first_match = pattern.search(sublist_dlt_msg[0].payload_decoded)
            last_match = pattern.search(sublist_dlt_msg[-1].payload_decoded)
            if first_match and last_match:
                initial_timestamp = first_match.groupdict().get("timestamp")
                final_timestamp = last_match.groupdict().get("timestamp")
                time_difference = int(final_timestamp) - int(initial_timestamp)
                assert_true(
                    frequency_time - total_deviation <= time_difference <= frequency_time + total_deviation,
                    "Failed to validate GNSS frequency to be 10HZ. The time difference between the first and last"
                    f" DLT messages in the following subset is {time_difference} milliseconds when it should be"
                    f" between {int(frequency_time - total_deviation)} and {int(frequency_time + total_deviation)}"
                    " milliseconds:\n" + "\n".join([str(msg.payload_decoded) for msg in sublist_dlt_msg]),
                )

    def get_instance_and_flag_value_from_base_gnss_hal(self, target_base_gnss_hal_patterns):
        """
        get instance and flag value from base GNSS HAL from DLT logs
        :param target_base_gnss_hal_patterns: Target GNSS HAL DLT log pattern.
        """
        instance_value = flag_value = None
        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as trace:
            self.test.apinext_target.execute_command(["stop", "navsens-hal-1_0"], privileged=True)
            self.test.apinext_target.execute_command(["start", "navsens-hal-1_0"], privileged=True)
            dlt_msgs = trace.wait_for_multi_filters(
                filters=target_base_gnss_hal_patterns,
                drop=True,
                count=0,
                timeout=60,
            )

        if not dlt_msgs:
            raise ValueError("Failed to collect DLT message")
        for msg in dlt_msgs:
            for index, pattern in enumerate(target_base_gnss_hal_patterns):
                match = pattern["payload_decoded"].search(msg.payload_decoded)
                if match:
                    if index == 0:
                        instance_value = int(match.group(1))
                    elif index == 1:
                        flag_value = int(match.group(1))
                else:
                    logger.info(f"DLT logs are not found as per pattern {target_base_gnss_hal_patterns}")
        return flag_value, instance_value

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Navigation ROW",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-23076",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "DEAD_RECKONING_POSITIONING"),
            },
        },
    )
    def test_001_verify_base_gnss_hal(self):
        """
        [SIT_Automated] BMW_IDCEvo_I290 _Base GNSS HAL subscribes to dead reckoning service interface
        Steps:
            - Start DLT traces and run below two GNSS_HAL commands
                - stop navsens-hal-1_0
                - start navsens-hal-1_0
            - Ensure payload mentioned in dict "target_base_gnss_hal_log" are found in DLT traces
            - Fetch Flag value and Instance value from the traces.
            - If flag value is in range 1-4, Instance value must be equal to Flag value.
              Else instance value should be 3.
        """
        flag_value, instance_value = self.get_instance_and_flag_value_from_base_gnss_hal(TARGET_BASE_GNSS_HAL_LOG)

        logger.debug(f"Instance value : {instance_value} \n Flag Value: {flag_value}")
        assert_is_not_none(
            instance_value and flag_value,
            f"DLT logs are not found as per pattern : {TARGET_BASE_GNSS_HAL_LOG}",
        )
        if flag_value in range(1, 5):
            assert_equal(
                flag_value,
                instance_value,
                f"Instance value must be equal to Flag value."
                f"Actual Instance value- {instance_value} and actual flag value - {flag_value}",
            )
        else:
            assert_equal(
                3,
                instance_value,
                "Instance value must be equal to 3.\n"
                f"Actual Instance value- {instance_value} Expected Instance value- 3",
            )

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="Navigation ROW",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-23093",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "GNSS_LOGS"),
            },
        },
    )
    def test_002_verify_gnss_log_frequency(self):
        """
        [SIT_Automated] BMW_IDCEvo_I290 _ GNSS input log frequency is set to 10 Hz.
        Steps:
            1. Check instance value of GNSS HAL. If it is not 3, set it to 3.
            2. Execute below commands
                - stop navsens-hal-1_0
                - start navsens-hal-1_0
            3. Start DLT trace to search GNSS input log frequency messages.
        Expected Outcome:
            1. GNSS input log frequency is set to 10 Hz.

        Implementation notes:
            The method we implemented to validate the GNSS frequency divides the DLT messages into chunks of
            10 messages each. We then get the first and last element of each chunk and check the "Timestamp"
            field of the message. To check if the frequency is 10Hz, we validate the difference between the
            first and last timestamps is 1 second, with a deviation of 0.01 seconds. Here is an example:

            First message of the chunk:
                - NAVD[3756]:GNSSTime : SysTime=56006, Timestamp=56005, Year=2025, Month=3,
                  Day=6, Hour=11, Min=54, Sec=37, Ms=439, Scale=0, Vb=511

            Last message of the chunk:
                - NAVD[3756]:GNSSTime : SysTime=57007, Timestamp=57105, Year=2025, Month=3,
                  Day=6, Hour=11, Min=54, Sec=38, Ms=539, Scale=0, Vb=511

            Time elapsed between the first and last message:
                Last message timestamp - First message timestamp = 57005ms - 56005ms = 1000ms = 1sec = 10Hz
        """
        gnss_filters = {
            "apid": "ALD",
            "ctid": "LCAT",
            "payload_decoded": re.compile(r"NAVD\[\d+\]:GNSSTime : SysTime=(\d+), Timestamp=(\d+),.*"),
        }
        gnss_id_read_command = self.test.mtee_target.execute_command(
            "devcoding read ANDROID_GNSS_POSITIONING_INST_ID", expected_return_code=0
        )
        if gnss_id_read_command != 3:
            self.test.mtee_target.execute_command(
                "devcoding write ANDROID_GNSS_POSITIONING_INST_ID 3", expected_return_code=0
            )
            self.test.mtee_target.reboot()
            wait_for_application_target(self.test.mtee_target)

            gnss_id_read_command = self.test.mtee_target.execute_command(
                "devcoding read ANDROID_GNSS_POSITIONING_INST_ID", expected_return_code=0
            )
            match = re.search(r"idc_evo_gnss_deadreckoning\s*{\s*(\d+)", gnss_id_read_command.stdout)
            assert match, "Failed to get Android GNSS Positioning ID"

            gnss_id_value = match.group(1)
            assert gnss_id_value == "3", "Failed to set ANDROID_GNSS_POSITIONING_INST_ID to 3"
            logger.info("Successfully set ANDROID_GNSS_POSITIONING_INST_ID to 3")

        self.test.apinext_target.execute_command(["stop", "navsens-hal-1_0"], privileged=True)
        self.test.apinext_target.execute_command(["start", "navsens-hal-1_0"], privileged=True)

        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as trace:
            dlt_msgs = trace.wait_for(
                gnss_filters,
                timeout=10 * 60,
                drop=True,
                raise_on_timeout=False,
                count=0,
            )

            assert_true(len(dlt_msgs) > 10, "Not enough messages found on DLT to validate GNSS frequency")

            self.validate_gnss_frequency(dlt_msgs)
