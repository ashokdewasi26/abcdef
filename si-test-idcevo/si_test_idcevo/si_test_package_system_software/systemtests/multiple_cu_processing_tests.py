# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Multiple CU support for processing NNMs tests"""
import configparser
import logging
import os

from pathlib import Path
from mtee.testing.tools import assert_process_returncode, assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.linux_commands_handlers import LinuxCommandsHandler

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)


class TestsMultipleCuProcessing(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)
        cls.linux_helpers = LinuxCommandsHandler(cls.test.mtee_target, logger)

        cls.base_path = "/var/data/vendor/enn"

    def teardown(self):
        # Delete all sub folders inside /data/vendor/enn and var/data/vendor/enn
        self.test.mtee_target.execute_command(f"rm -rf {self.base_path}/*/")

    def extract_c_samples_models(self, module_file_path):
        """Extract models for C samples and define parameters for executable."""
        self.linux_helpers.extract_tar(module_file_path)
        self.test.mtee_target.upload("/tmp/SPytorch_model", os.path.join(self.base_path, "models"))
        self.model_file_path = os.path.join("./models/multi_unified_resize_O2_SingleCore.nnc")
        self.input_file_path = os.path.join("./models/SPyTorchNet_input_data_fp32.bin")
        self.golden_file_path = (
            "./models/SPyTorchNet_golden_data0_fp32.bin "
            "./models/SPyTorchNet_golden_data1_fp32.bin "
            "./models/SPyTorchNet_golden_data2_fp32.bin "
            "./models/SPyTorchNet_golden_data3_fp32.bin "
            "./models/SPyTorchNet_golden_data4_fp32.bin"
        )
        self.threshold = "0.001"

    def build_model_command(self):
        """Define the command to be executed with the corrects arguments."""
        cmd = f"./EnnTest_64 --model {self.model_file_path} --input {self.input_file_path} "
        cmd += f"--golden {self.golden_file_path} --threshold {self.threshold}"
        return cmd

    @metadata(
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-50133",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "HW_UTILIZATION_MULTIPLE_CU_PROCESSING"),
                ],
            },
        },
    )
    def test_001_alexnet_gpu(self):
        """
        [SIT_Automated] [NPU]Multiple CU support for processing NNMs-test_alexnet_GPU

        Steps:
            1 - Run following command to make the system RW:
                # mount -o remount,rw /
            2 - Push models files to /var/data/vendor/enn/models
            3 - Push EnnTest_64 to /var/data/vendor/enn & enable permission
            4 - Execute EnnTest_64
            5 - Check the return of the executable for test success status
        """
        enntest64_path = Path(os.sep) / "resources" / "EnnTest_64.tar.gz"
        spytorchnet_path = Path(os.sep) / "resources" / "SPytorch_model.tar.gz"
        self.test.mtee_target._clean_target = False
        self.test.mtee_target.user_data.remount_as_exec()

        logger.info("Creating folder structure on target")
        result = self.test.mtee_target.execute_command(f"mkdir -p {self.base_path}")
        assert_process_returncode(0, result, f"Failed to create folder structure {self.base_path}")
        self.test.mtee_target.execute_command(f"mkdir -p {self.base_path}/models")

        logger.info("Extracting models")
        self.linux_helpers.extract_tar(enntest64_path)
        self.extract_c_samples_models(spytorchnet_path)

        logger.info("Uploading executable to target and change permissions")
        self.test.mtee_target.upload("/tmp/EnnTest_64/EnnTest_64", f"{self.base_path}/EnnTest_64")
        self.test.mtee_target.execute_command("chmod 0777 EnnTest_64", cwd=self.base_path)

        cmd = self.build_model_command()
        stdout, stderr, return_code = self.test.mtee_target.execute_command(
            cmd,
            cwd=self.base_path,
        )

        logger.debug(f"Return of ./EnnTest_64: \n{stdout}")

        assert_process_returncode(0, return_code, f"Failed to execute EnnTest_64, error: {stderr}")
        assert_true("Golden Matched" in stdout, 'Test failed. Output is missing the "Golden Match" on output')
        assert_true("TEST SUCCESS" in stdout, 'Test failed. Output is missing the "TEST SUCCESS" on output')
