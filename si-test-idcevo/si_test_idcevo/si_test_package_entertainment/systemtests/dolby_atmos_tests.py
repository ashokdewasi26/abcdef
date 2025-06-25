# Copyright (C) 2025. BMW CTW PT. All rights reserved.
import configparser
import logging

import os
import re
from pathlib import Path

from mtee.testing.tools import assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.linux_commands_handlers import LinuxCommandsHandler

config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)


class TestDolbyAtmos:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.linux_helpers = LinuxCommandsHandler(cls.test.mtee_target, logger)

    @metadata(
        testsuite=["SI-Android"],
        component="tee_idcevo",
        domain="Entertainment",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-476784",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "DOLBY_ATMOS"),
            },
        },
    )
    def test_001_audio_manager_output_device_for_attributes(self):
        """
        [SIT_Automated][Entertainment][Dolby Atmos][SI] audio_manager_output_device_for_attributes-514-14-mixer (68)

        Steps:
            1. Extract DolbyCarExperienceTests.tar.gz
            2. Install the DolbyCarExperienceTests.apk
            3. Run the Dolby AudioManagerTest instrumented test

        Expected Outcome:
            - DolbyCarExperienceTests.apk is successfully installed
            - Instrumented test is successful
            - 'OK (1 test)' is found on the test output
        """
        dolbycar_tarball = Path(os.sep) / "resources" / "DolbyCarExperienceTests.tar.gz"
        self.linux_helpers.extract_tar(dolbycar_tarball)
        apk_to_install = "/tmp/DolbyCarExperienceTests.apk"

        self.test.apinext_target.install_apk(apk_to_install)
        result = self.test.apinext_target.execute_adb_command(
            [
                "shell",
                "am",
                "instrument",
                "-w",
                "-e",
                "class",
                "com.dolby.android.dcx.tests.AudioManagerTest#testOutputDevicesForAttributesForMixerArch",
                "-e",
                "outChannelMask",
                "514",
                "com.dolby.android.dcx.tests/androidx.test.runner.AndroidJUnitRunner",
            ]
        )
        logger.debug(result)
        ok_pattern = r"OK \(1 test\)"
        stdout_match = re.search(ok_pattern, result.stdout.decode("utf-8"))

        assert_true(
            stdout_match,
            "Instrumented test failed: 'OK (1 test)' not found in output. Check the device logs for more details.",
        )
