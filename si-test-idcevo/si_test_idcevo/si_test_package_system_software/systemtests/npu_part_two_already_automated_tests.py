# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""
System Software already automated tests - NPU.

These tests were previously automated in the domain's repositories.
This file brings them into our codebase, where they have been adapted to align with our testing standards.
"""
import configparser
import logging
import os
import re
import time
from pathlib import Path
from unittest import skipIf


from mtee.testing.test_environment import TEST_ENVIRONMENT as TE, require_environment, require_environment_setup
from mtee.testing.tools import (
    assert_equal,
    assert_is_not_none,
    assert_true,
    metadata,
)
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.dmverity_helpers import disable_dm_verity
from si_test_idcevo.si_test_helpers.linux_commands_handlers import LinuxCommandsHandler
from si_test_idcevo.si_test_helpers.npu_helper import (
    ENN_SUCCESS_MSGS,
    execute_and_validate_drowsiness_model,
    execute_and_validate_gru_model,
    execute_and_validate_large_network_model,
    execute_model_with_enn_64,
    execute_model_with_enntest_on_android,
    extract_and_upload_model,
    fetch_model_load_time,
    validate_enn_output,
)

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
required_target_packages = ["devmem2", "virtio-utils"]


TEST_ENVIRONMENT = (TE.target.hardware.idcevo,)
NPU_MOBILE_PATH = Path(os.sep) / "resources" / "NPU_mobile.tar.gz"

SEC_MODEL_LOAD_REG = re.compile(r"2nd model load = (\d\d+\s*\[µs])")


@require_environment(*TEST_ENVIRONMENT)
class TestsSystemSwNpuPart2(object):
    test = TestBase.get_instance()
    test.setup_base_class()
    hw_revision = test.mtee_target.options.hardware_revision

    @classmethod
    @require_environment_setup(*TEST_ENVIRONMENT)
    def setup_class(cls):

        disable_dm_verity()

        enntest64_path = Path(os.sep) / "resources" / "EnnTest_64.tar.gz"
        cls.base_path = "/data/vendor/enn"
        cls.var_root_path = "/var/data/vendor/enn"

        cls.linux_helpers = LinuxCommandsHandler(cls.test.mtee_target, logger)

        cls.test.mtee_target.remount()

        if not cls.test.mtee_target.exists(cls.var_root_path):
            cls.test.mtee_target.execute_command(f"mkdir -p {cls.var_root_path}", expected_return_code=0)

        if not cls.test.mtee_target.exists(cls.base_path):
            cls.test.mtee_target.execute_command(f"mkdir -p {cls.base_path}", expected_return_code=0)
        cls.linux_helpers.extract_tar(enntest64_path)
        cls.test.mtee_target.upload("/tmp/EnnTest_64/EnnTest_64", f"{cls.base_path}/EnnTest_64")
        cls.test.mtee_target.chmod(f"{cls.base_path}/EnnTest_64", 0o777)

    def setup(self):
        # Root the target
        if self.test.apinext_target.get_current_shell_user_id() != 0:
            self.test.apinext_target.execute_adb_command("root")
            assert (
                self.test.apinext_target.get_current_shell_user_id() == 0
            ), "The adb should run as root after adb root command"

    def teardown(self):

        self.test.mtee_target.execute_command(f"rm -rf {self.var_root_path}/*/")
        # Delete all sub folders inside /data/vendor/enn
        self.test.mtee_target.execute_command(f"rm -rf {self.base_path}/*/", expected_return_code=0)
        # Unroot the target
        if self.test.apinext_target.get_current_shell_user_id() == 0:
            self.test.apinext_target.execute_adb_command("unroot")
            assert (
                self.test.apinext_target.get_current_shell_user_id() != 0
            ), "The adb should run as non root after adb unroot command"

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-19073",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NNM_PROCESSING"),
                ],
            },
        },
    )
    def test_001_system_support_for_loading_and_preparing_the_nnms_multicore(self):
        """
        [SIT_Automated] [NPU] To verify system loading time
        Steps:
            1 - Extract and upload correct NPU model and data, depending on hardware revision
            2 - Upload enn_loadmodel test file and give executable permissions to this path and model paths
            3 - Run enn_loadmodel executable
            4 - Fetch 2nd model upload time and make sure it's available.
        """
        load_time_test_samples_path = Path(os.sep) / "resources" / "load_time_test_samples.tar.gz"

        self.linux_helpers.extract_tar(load_time_test_samples_path)
        model_path = f"{self.var_root_path}/models"
        self.test.mtee_target.mkdir(model_path, parents=True)
        if self.test.mtee_target.options.hardware_revision.startswith("B"):
            self.test.mtee_target.upload("/tmp/load_time_test_samples/b_sample", model_path)
        else:
            self.test.mtee_target.upload("/tmp/load_time_test_samples/c_sample", model_path)

        enn_path = f"{self.var_root_path}/enn_test"
        self.test.mtee_target.mkdir(enn_path, parents=True)
        self.test.mtee_target.upload("/tmp/load_time_test_samples/enn_test", enn_path)
        self.test.mtee_target.chmod(enn_path, 0o777, recursive=True)
        self.test.mtee_target.chmod(model_path, 0o777, recursive=True)

        cmd = "./enn_loadmodel"
        stdout, _, _ = self.test.mtee_target.execute_command(cmd, cwd=enn_path, trim_log=False)
        sec_model_load_reg = re.compile(r"2nd model load = (\d\d+\s*\[µs])")

        sec_model_upload_time = fetch_model_load_time(sec_model_load_reg, stdout)
        assert_is_not_none(
            sec_model_upload_time,
            f"2nd model upload time did not match the expected regex pattern: {sec_model_load_reg.pattern}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-19071",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NNM_SCHEDULING"),
                ],
            },
        },
    )
    def test_002_processing_8nnm_models_simultaneously(self):
        """
        [SIT_Automated] Processing of 8NNM simultaneously
        Pre-condition:
            - Run following command to make the system RW:
                # mount -o remount,rw /var/data
        Steps:
            1 - Push models files to /var/data/vendor/enn/models
            2 - Push enn_sample_external to /var/data/vendor/enn & enable permission
            3 - Execute enn_sample_external
            4 - Check the return of the executable for test success status
        Expected outcome:
            - Check for below Results match:
                 Result is matched with golden out
        """
        nnm8_model_path = Path(os.sep) / "resources" / "8nnm_modules.tar.gz"
        if not os.path.exists("tmp/8nnm_model"):
            self.linux_helpers.extract_tar(nnm8_model_path)
        model_path = f"{self.var_root_path}/models"
        self.test.mtee_target.mkdir(model_path, parents=True)

        if self.test.mtee_target.options.hardware_revision.startswith("B"):
            self.test.mtee_target.upload("/tmp/8nnm_modules/b_sample", model_path)
        else:
            self.test.mtee_target.upload("/tmp/8nnm_modules/c_sample", model_path)

        enn_path = f"{self.var_root_path}/enn_test"
        self.test.mtee_target.mkdir(enn_path, parents=True)
        self.test.mtee_target.upload("/tmp/8nnm_modules/enn_test", enn_path)
        self.test.mtee_target.chmod(enn_path, 0o777, recursive=True)
        cmd = "./enn_sample_8nnms"
        enntest_output, _, _ = self.test.mtee_target.execute_command(cmd, cwd=enn_path)
        logger.debug(f"enntest_output : {enntest_output}")
        enntest_validation_pattern = r".*\[SUCCESS\] Result is matched with golden out.*"
        enntest_validation_pattern_count = len(re.findall(enntest_validation_pattern, enntest_output))
        assert_equal(
            8,
            enntest_validation_pattern_count,
            f"8NNM model execution was not successfull for 8 times \n"
            f"Actual success count: {enntest_validation_pattern_count}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-30985",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NNM_OPERATORS_LAYERS"),
                ],
            },
        },
    )
    def test_003_full_hw_acceleration_for_nnm_layer(self):
        """
        [SIT_Automated] Support for full HW acceleration-Support for NNM layers
        Steps:
            1. Run the following command: mount -o remount,exec /var/data
            2. Extract the tar.zip file
            3. create folders /var/data/vendor/enn/models/
            4. upload the model, input, golden files of large network model, gru model and drowsiness model
            5. Create the Enn command with multiple input and golden files in below format for large network model,
               gru model and drowsiness model:
                ./EnnTest_64 --model <modelpath> --input <path of input1> <path of input2> --golden <golden1 path>
                 <golden2 path> <golden 3 path> --threshold 0.2
            6. Run the Enn file for each model and Validate the output
        """
        hw_acc_nnm_layers = Path(os.sep) / "resources" / "hw_acc_nnm_layers.tar.gz"
        self.test.mtee_target.user_data.remount_as_exec()
        self.linux_helpers.extract_tar(hw_acc_nnm_layers)
        time.sleep(3)  # The size of tar.gz file is more than 85MB. It requires some time in extraction.

        model_path = f"{self.var_root_path}/models"
        self.test.mtee_target.mkdir(model_path, parents=True)
        self.test.mtee_target.upload("/tmp/hw_acc_nnm_layers", model_path)
        self.test.mtee_target.chmod(model_path, 0o777, recursive=True)

        execute_and_validate_large_network_model(self.test, model_path)
        execute_and_validate_gru_model(self.test, model_path)
        execute_and_validate_drowsiness_model(self.test, model_path)

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-45539",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DEDICATED_CU_PROCESSING"),
                ],
            },
        },
    )
    def test_004_hw_utilization_of_dedicated_cu_for_nnm_processing(self):
        """
        [SIT_Automated] hw-utilization Dedicated CU- for processing NNMs
        Steps:
            1. Run the following command: mount -o remount,exec /var/data
            2. Extract the tar.gz file
            3. create folder /var/data/vendor/enn/models/ in target
            4. Upload the extracted model files to target
            5. Run the Enn command and Validate the output
        """
        dedicated_cu_nnm_process_path = Path(os.sep) / "resources" / "DEDICATED_CU_NNM_PROCESS_PATH.tar.gz"
        self.test.mtee_target.user_data.remount_as_exec()
        self.linux_helpers.extract_tar(dedicated_cu_nnm_process_path)

        model_path = f"{self.var_root_path}/models"
        if not self.test.mtee_target.isdir(model_path):
            self.test.mtee_target.mkdir(model_path, parents=True)
        self.test.mtee_target.upload("/tmp/DEDICATED_CU_NNM_PROCESS_PATH", model_path)
        self.test.mtee_target.chmod(model_path, 0o777, recursive=True)

        model_file_path = f"{model_path}/spotfixer__SingleCore.nnc"
        input_file_path = f"{model_path}/MCD_27_PhotoEditor_SpotFixer_input_data.bin"
        golden_file_path = f"{model_path}/MCD_27_PhotoEditor_SpotFixer_golden_data.bin"
        threshold = "0.027"
        profile_summary = True
        enntest_output = execute_model_with_enn_64(
            self.test, model_file_path, input_file_path, golden_file_path, threshold, profile_summary
        )
        validate_enn_output(enntest_output, ENN_SUCCESS_MSGS)

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-186283",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NNM_PROCESSING"),
                ],
            },
        },
    )
    @skipIf("C" not in hw_revision, "Skipping test as it can only be ran in IDCEVO C samples.")
    def test_005_verify_system_loading_time(self):
        """
        [SIT_Automated] Verify TRS-To verify system loading time
        Steps:
            1. Run the following command: mount -o remount,exec /var/data
            2. Extract and upload correct NPU model and data
            3. Upload enn_loadmodel test file and give executable permissions to this path and model paths
            4. Update LD_LIBRARY_PATH in the target.
            5. Run executable file enn_loadmodel
            5. Fetch 2nd model upload time and make sure it's available.
        """
        model_loadtime_path = Path(os.sep) / "resources" / "model_loadtime.tar.gz"

        self.test.mtee_target.user_data.remount_as_exec()
        self.linux_helpers.extract_tar(model_loadtime_path)
        model_path = f"{self.var_root_path}/models"
        self.test.mtee_target.mkdir(model_path, parents=True)
        self.test.mtee_target.upload("/tmp/model_loadtime", model_path)

        enn_path = f"{self.var_root_path}/enn_test"
        self.test.mtee_target.mkdir(enn_path, parents=True)
        self.test.mtee_target.upload("/tmp/model_loadtime/enn_test", enn_path)

        self.test.mtee_target.chmod(model_path, 0o777, recursive=True)
        self.test.mtee_target.chmod(enn_path, 0o777, recursive=True)

        self.test.mtee_target.execute_command("export LD_LIBRARY_PATH=/data/vendor/enn/libs:$LD_LIBRAARY_PATH")

        cmd = "./enn_loadmodel"
        stdout, _, _ = self.test.mtee_target.execute_command(cmd, cwd=enn_path, trim_log=False)
        model_upload_time = fetch_model_load_time(SEC_MODEL_LOAD_REG, stdout)
        assert_is_not_none(
            model_upload_time,
            f"2nd model upload time did not match the expected regex pattern: {SEC_MODEL_LOAD_REG.pattern}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-11598",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "VIRTUALIZATION_SUPPORT_CU_VIRTUALIZATION"),
                ],
            },
        },
    )
    def test_006_virtualization_support_android_npu(self):
        """
        [SIT_Automated] NPU able to run alongside within Virtualization android environment.
        Steps:
            1. Setup: Remount target and Root the target
            2. Create /data/vendor/enn/models/npu_iv3, if not available
            3. Extract and upload correct nnc model and data
            4. Run EnnTest_v2_service and validate output
            5. Teardown: Unroot the target
        Expected Outcome:
            Android Module should run on target with Golden Matched and TEST SUCCESS
        """
        npu_model_file = ["mobile_O1_SingleCore.nnc", "NPU_mobile_golden_data.bin", "NPU_mobile_input_data.bin"]
        npu_model_path = Path(os.sep) / "resources" / "npumodel.tar.gz"

        npu_path = f"{self.base_path}/models/npu_iv3"
        self.test.apinext_target.execute_command(f"mkdir -p {npu_path}")
        if not os.path.exists("tmp/npumodel"):
            self.linux_helpers.extract_tar(npu_model_path)
        self.test.apinext_target.push_as_current_user(
            "/tmp/npumodel/sample_file",
            f"{npu_path}",
        )
        npu_path = f"{npu_path}/sample_file"
        result = self.test.apinext_target.execute_command(["ls", f"{npu_path}"])
        assert_true(
            self.linux_helpers.validate_output_android_console(result, npu_model_file),
            f"Model file are not available on {npu_path}",
        )
        nnm_model_path = f"{npu_path}/mobile_O1_SingleCore.nnc"
        nnm_input_data_path = f"{npu_path}/NPU_mobile_input_data.bin"
        nnm_golden_data_path = f"{npu_path}/NPU_mobile_golden_data.bin"
        npu_test_output = execute_model_with_enntest_on_android(
            self.test,
            model=nnm_model_path,
            input_data=nnm_input_data_path,
            golden_data=nnm_golden_data_path,
            threshold_value=0.1,
        )
        assert_true(
            self.linux_helpers.validate_output_android_console(npu_test_output, ENN_SUCCESS_MSGS),
            f"Failed to find SUCCESS in model's execution output.\nOutput found: {npu_test_output}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-45748",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "VIRTUALIZATION_SUPPORT_CU_VIRTUALIZATION"),
                ],
            },
        },
    )
    def test_007_npu_support_alexnet_model(self):
        """
        [SIT_Automated] [NPU]Virtualization support-CU NPU support from android. - Alexnet Model
        Steps:
            1 - Setup: Remount target and Root the target
            2 - Create /data/vendor/enn/models/alexenet, if not available.
            3 - Extract and upload correct nnc model and data, depending on hardware revision
            4 - Run EnnTest_v2_service and validate output
            5 - Teardown: Unroot the target
        Expected Outcome:
            Alexnet module should run on target with Golden Matched and TEST SUCCESS
        """

        alexnet_model_path = Path(os.sep) / "resources" / "alexnet.tar.gz"
        npu_alexnet_path = f"{self.base_path}/models/alexenet"

        alexnet_model_files = [
            "alexnet_O1_SingleCore.nnc",
            "NPU_alexnet_input_data.bin",
            "NPU_alexnet_golden_data.bin",
        ]

        self.test.apinext_target.execute_command(f"mkdir -p {npu_alexnet_path}")
        if not os.path.exists("tmp/alexnet"):
            self.linux_helpers.extract_tar(alexnet_model_path)

        if self.test.mtee_target.options.hardware_revision.startswith("B"):
            self.test.apinext_target.push_as_current_user(
                "/tmp/alexnet/b_sample/",
                f"{npu_alexnet_path}",
            )
            npu_alexnet_path = f"{npu_alexnet_path}/b_sample"
        else:
            self.test.apinext_target.push_as_current_user(
                "/tmp/alexnet/c_sample/",
                f"{npu_alexnet_path}",
            )
            npu_alexnet_path = f"{npu_alexnet_path}/c_sample"

        result = self.test.apinext_target.execute_command(["ls", f"{npu_alexnet_path}"])
        assert_true(
            self.linux_helpers.validate_output_android_console(result, alexnet_model_files),
            f"Model file are not available on {npu_alexnet_path}",
        )

        nnm_model_path = f"{npu_alexnet_path}/alexnet_O1_SingleCore.nnc"
        nnm_input_data_path = f"{npu_alexnet_path}/NPU_alexnet_input_data.bin"
        nnm_golden_data_path = f"{npu_alexnet_path}/NPU_alexnet_golden_data.bin"
        enntest_output = execute_model_with_enntest_on_android(
            self.test,
            model=nnm_model_path,
            input_data=nnm_input_data_path,
            golden_data=nnm_golden_data_path,
        )
        assert_true(
            self.linux_helpers.validate_output_android_console(enntest_output, ENN_SUCCESS_MSGS),
            f"Failed to find SUCCESS in model's execution output.\nOutput found: {enntest_output}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-45750",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "VIRTUALIZATION_SUPPORT_CU_VIRTUALIZATION"),
                ],
            },
        },
    )
    def test_008_npu_support_siamese_model(self):
        """
        [SIT_Automated] [NPU]Virtualization support-CU NPU support from android. - siamese Model
        Steps:
            1 - Setup: Remount target and Root the target
            2 - Create /data/vendor/enn/models/siamese, if not available.
            3 - Extract and upload correct nnc model and data, depending on hardware revision
            4 - Run EnnTest_v2_service and validate output
            5 - Teardown: Unroot the target
        Expected Outcome:
            siamese module should run on target with Golden Matched and TEST SUCCESS
        """
        siamese_model_files = [
            "mnist_siamese_O1_SingleCore.nnc",
            "NPU_mnist_siamese_input_data.bin",
            "NPU_mnist_siamese_golden_data.bin",
        ]
        npu_siamese_path = f"{self.base_path}/models/siamese"
        siamese_model_path = Path(os.sep) / "resources" / "siameseModule.tar.gz"

        self.test.apinext_target.execute_command(f"mkdir -p {npu_siamese_path}")
        if not os.path.exists("tmp/siameseModule"):
            self.linux_helpers.extract_tar(siamese_model_path)

        if self.test.mtee_target.options.hardware_revision.startswith("B"):
            self.test.apinext_target.push_as_current_user(
                "/tmp/siameseModule/b_sample/",
                f"{npu_siamese_path}",
            )
            npu_siamese_path = f"{npu_siamese_path}/b_sample"
        else:
            self.test.apinext_target.push_as_current_user(
                "/tmp/siameseModule/c_sample/",
                f"{npu_siamese_path}",
            )
            npu_siamese_path = f"{npu_siamese_path}/c_sample"

        result = self.test.apinext_target.execute_command(["ls", f"{npu_siamese_path}"])
        assert_true(
            self.linux_helpers.validate_output_android_console(result, siamese_model_files),
            f"Model file are not available on {npu_siamese_path}",
        )

        nnm_model_path = f"{npu_siamese_path}/mnist_siamese_O1_SingleCore.nnc"
        nnm_input_data_path = f"{npu_siamese_path}/NPU_mnist_siamese_input_data.bin"
        nnm_golden_data_path = f"{npu_siamese_path}/NPU_mnist_siamese_golden_data.bin"
        enntest_output = execute_model_with_enntest_on_android(
            self.test,
            model=nnm_model_path,
            input_data=nnm_input_data_path,
            golden_data=nnm_golden_data_path,
        )
        assert_true(
            self.linux_helpers.validate_output_android_console(enntest_output, ENN_SUCCESS_MSGS),
            f"Failed to find SUCCESS in model's execution output.\nOutput found: {enntest_output}",
        )

    @metadata(
        testsuite=["BAT", "domain", "SI"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-212242",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NNM_OPERATORS_LAYERS_ADDITIONAL"),
                ],
            },
        },
    )
    @skipIf(
        not (
            test.mtee_target.has_capability(TE.target.hardware.idcevo)
            and "C" in test.mtee_target.options.hardware_revision
        ),
        "Test not applicable for this ECU or it can only be run in IDCEVO C samples.",
    )
    def test_009_verify_support_for_matmul(self):
        """
        [SIT_Automated] Verify Add support for Matmul
        Steps:
            - Extract and upload matmul model files on target
            - Run the Enn command and Validate the output
        """
        matmul_model_path = Path(os.sep) / "resources" / "matmul_model_sample.tar.gz"
        folder_path = "/tmp/matmul_model_sample"
        folder_name = "matmul_model_sample"
        root_path = f"{self.var_root_path}/models"
        model_path = extract_and_upload_model(self, matmul_model_path, root_path, folder_path, folder_name)

        nnm_model_path = f"{model_path}/matmul_sample_O2_SingleCore.nnc"
        nnm_input_data_path = f"{model_path}/data_Q_in.bin"
        nnm_golden_data_path = f"{model_path}/NPU_matmul_sample_golden_data.bin"
        enn_test_output = execute_model_with_enn_64(
            self.test, nnm_model_path, nnm_input_data_path, nnm_golden_data_path
        )
        validate_enn_output(enn_test_output, ENN_SUCCESS_MSGS)
