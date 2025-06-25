# Copyright (C) 2025. BMW CTW PT. All rights reserved.
"""Check that there are no SFI related error messages in idcevo_full_trace.dlt"""
import configparser
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from mtee.testing.tools import metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.dlt_logs_handlers import decode_dlt_file_with_fibex

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

SFI_FIBEX_FILE = "/images/Flashbins/IDCEvo-Artifacts/bins/sfi/{0}_sample/IDCevo_SFI.xml"

SFI_LOGS = [
    re.compile(r"Safety Fault Detected"),
    re.compile(r"\[SFI\] Reset requested for Display:"),
]


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
    duplicates="IDCEVODEV-431727",
    traceability={
        config.get("tests", "traceability"): {
            "FEATURE": config.get("FEATURES", "INTER_NODE_COMMUNICATION_SFI_LINUX_COMMUNICATION"),
        },
    },
)
class SFIErrorDltPostTest(object):
    __test__ = True

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)

        cls.original_result_dir = cls.test.mtee_target.options.result_dir

        cls.results_dir = cls.test.results_dir

        cls.full_dlt_path = os.path.join(cls.original_result_dir, "filtered_full_sfis.dlt")

        cls.full_dlt_decoded_path = os.path.join(cls.results_dir, "idcevo_full_trace_SFIS_decoded.dlt")

        cls.define_sfi_fibex_file()
        logger.info(f"Using SFI fibex filepath: {cls.sfi_fibexfile}")

        cls.error_messages = []

    @classmethod
    def format_msg_timestamp(cls, message):
        """
        Converts the timestamp from a message's header into a formatted string.

        Args:
            message: An object containing a 'str_header' attribute with 'seconds' and 'microseconds' fields.

        Returns:
            str: The formatted timestamp as "YYYY/MM/DD HH:MM:SS.microseconds".
        """
        return (
            datetime.fromtimestamp(message.str_header.seconds).strftime("%Y/%m/%d %H:%M:%S")
            + "."
            + str(message.str_header.microseconds).zfill(6)
        )

    @classmethod
    def fibex_exists(cls, variant):
        """
        Checks if the FIBEX file for a given variant exists.

        This method constructs the file path for the FIBEX file using the provided
        variant and checks if the file exists in the filesystem.

        Args:
            variant (str): The variant identifier used to format the FIBEX file path.

        Returns:
            bool: True if the FIBEX file exists, False otherwise.
        """
        cls.sfi_fibexfile = SFI_FIBEX_FILE.format(variant)
        return os.path.exists(cls.sfi_fibexfile)

    @classmethod
    def define_sfi_fibex_file(cls):
        """Define the SFI fibex file to be used on the test based on the hardware revision"""
        pattern = r"[0-9]"
        # Remove the number from the hardware revision. Ex: B1 -> b
        hardware_variant = re.sub(pattern, "", cls.test.mtee_target.options.hardware_revision).lower()
        logger.info(f"Original Hardware variant: {hardware_variant}")

        # Decrease letter until folder is found
        while not cls.fibex_exists(hardware_variant) and hardware_variant >= "a":
            hardware_variant = chr(ord(hardware_variant) - 1)
            logger.info(f"Original fibex file not found, trying with: {hardware_variant}")

        if hardware_variant < "a":
            logger.error("No valid folder found for the hardware revision.")
            return

        logger.debug(f"Using SFI fibex filepath: {cls.sfi_fibexfile}")

    def test_001_sfi_errors(self):
        """
        [SIT_Automated] Check that there are no SFI related error messages in idcevo_full_trace.dlt
        Steps:
            1 - Filter sfis dlt file
            2 - Decode DLT file with fibex file
            3 - Check if there are SFI related error messages
        Output:
            1 - Error messages found in idcevo_full_trace.dlt
        """
        logger.info("Decoding DLT file with fibex file")
        self.sfi_decoded_messages = decode_dlt_file_with_fibex(
            self.sfi_fibexfile, self.full_dlt_path, decoded_dlt_file=self.full_dlt_decoded_path
        )

        # Use SFI_LOGS regex to check if there are SFI related error messages
        for msg in self.sfi_decoded_messages:
            current_payload = msg.payload._to_str()
            if any(regex.search(current_payload) for regex in SFI_LOGS):
                current_tmsp = self.format_msg_timestamp(msg)
                self.error_messages.append(current_tmsp + " - " + current_payload)

        assert not self.error_messages, f"SFI error messages found in idcevo_full_trace.dlt: {self.error_messages}"
