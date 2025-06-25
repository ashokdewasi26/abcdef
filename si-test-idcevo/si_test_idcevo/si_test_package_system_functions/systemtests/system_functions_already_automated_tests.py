# Copyright (C) 2024. BMW Car IT. All rights reserved.
"""Already Automated System Functions Tests

These tests were previously automated and created in the domain's repositories.
This file brings them into our codebase,
where they have been adapted to align with our testing standards and updated as needed
"""
import binascii
import configparser
import logging
import re
from pathlib import Path

from mtee.testing.tools import assert_equal, assert_is_not_none, metadata

from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from validation_utils.utils import CommandError, TimeoutError

# Config parser reading data from config file.
config = configparser.ConfigParser()

config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

ECU_UID_PATTERN = re.compile(r".*Result:([a-zA-Z0-9]+).*")
REGISTRY_READ_TEST_COMMAND = r"echo -e '1\n1\nk\n0' | registryreadtest"


class TestEcuFunctions:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="System Functions",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-9919",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "HARDWARE_INFO"),
                    config.get("FEATURES", "ANDROID_STRONGBOX_BACKED_KEYSTORE"),
                ]
            },
        },
    )
    def test_001_read_ecu_uid(self):
        """[SIT_Automated] Read ECU UID
        Steps-
            - Run the command 'echo -e '1\n1\nk\n0' | registryreadtest' and get ECU UID
            - Validate the length of ECU UID
        Expected Outcome:
            - Ensure that ECU UID should be 16 bytes.
        """
        uid_number = None
        try:
            return_stdout, _, _ = self.test.mtee_target.execute_command(
                REGISTRY_READ_TEST_COMMAND,
                timeout=60,
            )
        except (CommandError, TimeoutError) as e:
            raise RuntimeError(f"Encountered the following error while executing command: {e}")

        matches = ECU_UID_PATTERN.search(return_stdout)
        if matches:
            uid_number = matches.group(1)
        assert_is_not_none(uid_number, f"After executing {REGISTRY_READ_TEST_COMMAND} ECU UID not found")
        length_of_uid_number = len(binascii.unhexlify(uid_number))

        assert_equal(
            str(length_of_uid_number),
            "16",
            f"Expected ECU UID should be 16 bytes. Actual: {length_of_uid_number}",
        )
