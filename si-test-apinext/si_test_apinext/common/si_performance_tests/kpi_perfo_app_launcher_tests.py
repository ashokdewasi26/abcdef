# Copyright (C) 2022 CTW PT. All rights reserved.
"""Test to call the perfo-app-launcher script that generates a csv with all the relevant measurements"""
import logging
import os

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import require_environment, TEST_ENVIRONMENT
from mtee.testing.tools import run_command, check_process_returncode

target = TargetShare().target
logger = logging.getLogger(__name__)


@require_environment(TEST_ENVIRONMENT.target.hardware, TEST_ENVIRONMENT.target.hardware.idc23)
class TestPerfoAppLauncher(object):
    """Perfo App Launcher tests"""

    def compile_c_binary_files(self):

        compile_c_file_1 = [
            "gcc",
            "-Wall",
            "/workspace/mtee_test_scripts/helpers/computestats.c",
            "-o",
            "/workspace/mtee_test_scripts/helpers/perfo-computestats",
            "-lm",
        ]

        result = run_command(compile_c_file_1, check=True)
        check_process_returncode(0, result, "Compile C file 1: {} command failed {}".format(compile_c_file_1, result))
        logger.info("Output from the compile_c_file_1 call: %s", result)

        compile_c_file_2 = [
            "gcc",
            "-Wall",
            "/workspace/mtee_test_scripts/helpers/computestatsf.c",
            "-o",
            "/workspace/mtee_test_scripts/helpers/perfo-computestatsf",
            "-lm",
        ]

        result = run_command(compile_c_file_2, check=True)
        check_process_returncode(0, result, "Compile C file 2: {} command failed {}".format(compile_c_file_2, result))
        logger.info("Output from the compile_c_file_2 call: %s", result)

    @classmethod
    def setup_class(cls):
        """Setup class"""
        pass

    @classmethod
    def teardown_class(cls):
        """Teardown class"""
        target.screendump("test_001_call_perfo_app_launcher", screens="CID", publish=True)

    def test_001_call_perfo_app_launcher(self):
        """Test to call the perfo-app-launcher script"""

        logger.info("Start of perfo-app-launcher script")
        output_folder_path = os.path.join(target.options.result_dir, "extracted_files")

        self.compile_c_binary_files()

        perfo_script_cmd = [
            "/workspace/mtee_test_scripts/helpers/perfo-app-launcher",
            "-a",
            "50",
            "-r",
            str(output_folder_path),
        ]

        # The timeout must be large because the average time to execute the script completely,
        # in IDC23, is about 2.5 hours
        result = run_command(perfo_script_cmd, check=True, timeout=9000)
        check_process_returncode(0, result, "perfo-app-launcher command failed {}".format(result))
        logger.debug("Output from the perfo-app-launcher script call: %s", result)
        logger.info("End of perfo-app-launcher")
