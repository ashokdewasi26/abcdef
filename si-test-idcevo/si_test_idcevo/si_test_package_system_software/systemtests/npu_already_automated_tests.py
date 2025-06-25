# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""
System Software already automated tests - NPU.

These tests were previously automated in the domain's repositories.
This file brings them into our codebase, where they have been adapted to align with our testing standards.
"""
import configparser
import logging
import os
import time
from pathlib import Path
from unittest import skipIf

from mtee.testing.test_environment import TEST_ENVIRONMENT as TE, require_environment, require_environment_setup
from mtee.testing.tools import (
    assert_greater,
    assert_process_returncode,
    assert_true,
    metadata,
)
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.dmverity_helpers import disable_dm_verity
from si_test_idcevo.si_test_helpers.linux_commands_handlers import LinuxCommandsHandler
from si_test_idcevo.si_test_helpers.npu_helper import (
    ENN_SUCCESS_MSGS,
    execute_model_with_enn_64,
    execute_model_with_enn_and_get_fps,
    set_npu_exynos_properties,
    validate_enn_output,
)

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
required_target_packages = ["devmem2", "virtio-utils"]

TEST_ENVIRONMENT = (TE.target.hardware.idcevo,)
HW_ACCELERATION = Path(os.sep) / "resources" / "HW_acceleration.tar.gz"
NPU_MOBILE_PATH = Path(os.sep) / "resources" / "NPU_mobile.tar.gz"

HIGH_FREQUENCY = 866000
LOW_FREQUENCY = 267000


@require_environment(*TEST_ENVIRONMENT)
class TestsSystemSwNpu(object):
    test = TestBase.get_instance()
    test.setup_base_class()
    hw_revision = test.mtee_target.options.hardware_revision

    @classmethod
    @require_environment_setup(*TEST_ENVIRONMENT)
    def setup_class(cls):
        disable_dm_verity()

        cls.high_frequency = HIGH_FREQUENCY
        cls.low_frequency = LOW_FREQUENCY
        cls.enn_success_msgs = ENN_SUCCESS_MSGS

        cls.base_path = "/data/vendor/enn"
        cls.var_root_path = "/var/data/vendor/enn"
        enntest64_path = Path(os.sep) / "resources" / "EnnTest_64.tar.gz"
        cls.linux_helpers = LinuxCommandsHandler(cls.test.mtee_target, logger)
        disable_dm_verity()

        cls.test.mtee_target.remount()
        if not cls.test.mtee_target.exists(cls.var_root_path):
            cls.test.mtee_target.execute_command(f"mkdir -p {cls.var_root_path}", expected_return_code=0)

        if not cls.test.mtee_target.exists(cls.base_path):
            cls.test.mtee_target.execute_command(f"mkdir -p {cls.base_path}", expected_return_code=0)

        cls.linux_helpers.extract_tar(enntest64_path)
        cls.test.mtee_target.upload("/tmp/EnnTest_64/EnnTest_64", f"{cls.base_path}/EnnTest_64")
        cls.test.mtee_target.chmod(f"{cls.base_path}/EnnTest_64", 0o777)

    def teardown(self):
        # Delete all sub folders inside /data/vendor/enn and var/data/vendor/enn
        self.test.mtee_target.execute_command(f"rm -rf {self.base_path}/*/")
        self.test.mtee_target.execute_command(f"rm -rf {self.var_root_path}/*/")

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
        duplicates="IDCEVODEV-30986",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NNM_OPERATORS_LAYERS"),
                ],
            },
        },
    )
    def test_001_hw_acceleration_for_nnm_processing(self):
        """
        [SIT_Automated] [NPU]Support for full HW acceleration-NPU for NNM processing

        Steps:
            1 - Create /data/vendor/enn/models/nnm_processing, if non-existent
            2 - Extract and upload correct nnc model and data, depending on hardware revision
            3 - Upload EnnTest_64 executable to /data/vendor/enn, if non-existent
            4 - Run EnnTest_64 executable and validate output

        """
        self.linux_helpers.extract_tar(HW_ACCELERATION)
        model_path = f"{self.base_path}/models/nnm_processing"
        self.test.mtee_target.mkdir(model_path, parents=True)
        if self.test.mtee_target.options.hardware_revision.startswith("B"):
            self.test.mtee_target.upload("/tmp/HW_acceleration/nnm_processing/B_sample", model_path)
        else:
            self.test.mtee_target.upload("/tmp/HW_acceleration/nnm_processing/C_sample", model_path)

        self.test.mtee_target.chmod(model_path, 0o777, recursive=True)
        nnm_model_path = f"{model_path}/NPU_mobile.nnc"
        nnm_input_data_path = f"{model_path}/NPU_mobile_input_data.bin"
        nnm_golden_data_path = f"{model_path}/NPU_mobile_golden_data.bin"
        enntest_output = execute_model_with_enn_64(
            self.test, nnm_model_path, nnm_input_data_path, nnm_golden_data_path, 0.1
        )
        validate_enn_output(enntest_output, self.enn_success_msgs)

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
        duplicates="IDCEVODEV-30987",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NNM_OPERATORS_LAYERS"),
                ],
            },
        },
    )
    def test_002_hw_acceleration_for_8bit_quatized_nnm(self):
        """
        [SIT_Automated] [NPU]Support for full HW acceleration-8bit Quatized NNM

        Steps:
            1 - Create /data/vendor/enn/models/8bit_nnm, if non-existent
            2 - Extract and upload correct nnc model and data, depending on hardware revision
            3 - Upload EnnTest_64 executable to /data/vendor/enn, if non-existent
            4 - Run EnnTest_64 executable and validate output
        """
        if not os.path.exists("tmp/HW_acceleration"):
            self.linux_helpers.extract_tar(HW_ACCELERATION)
        model_path = f"{self.base_path}/models/8bit_nnm"
        self.test.mtee_target.mkdir(model_path, parents=True)
        if self.test.mtee_target.options.hardware_revision.startswith("B"):
            self.test.mtee_target.upload("/tmp/HW_acceleration/8bit_nnm/B_sample", model_path)
        else:
            self.test.mtee_target.upload("/tmp/HW_acceleration/8bit_nnm/C_sample", model_path)

        self.test.mtee_target.chmod(model_path, 0o777, recursive=True)
        nnm_model_path = f"{model_path}/NPU_mobile.nnc"
        nnm_input_data_path = f"{model_path}/NPU_mobile_input_data.bin"
        nnm_golden_data_path = f"{model_path}/NPU_mobile_golden_data.bin"
        enntest_output = execute_model_with_enn_64(
            self.test, nnm_model_path, nnm_input_data_path, nnm_golden_data_path, 0.1
        )
        validate_enn_output(enntest_output, self.enn_success_msgs)

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
        duplicates="IDCEVODEV-30988",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NNM_OPERATORS_LAYERS"),
                ],
            },
        },
    )
    def test_003_hw_acceleration_for_16bit_quatized_nnm(self):
        """
        [SIT_Automated] [NPU]Support for full HW acceleration-16bit Quatized NNM

        Steps:
            1 - Create /data/vendor/enn/models/16bit_nnm, if non-existent
            2 - Extract and upload correct nnc model and data, depending on hardware revision
            3 - Upload EnnTest_64 executable to /data/vendor/enn, if non-existent
            4 - Run EnnTest_64 executable and validate output
        """
        if not os.path.exists("tmp/HW_acceleration"):
            self.linux_helpers.extract_tar(HW_ACCELERATION)
        model_path = f"{self.base_path}/models/16bit_nnm"
        self.test.mtee_target.mkdir(model_path, parents=True)
        if self.test.mtee_target.options.hardware_revision.startswith("B"):
            self.test.mtee_target.upload("/tmp/HW_acceleration/16bit_nnm/B_sample", model_path)
        else:
            self.test.mtee_target.upload("/tmp/HW_acceleration/16bit_nnm/C_sample", model_path)

        self.test.mtee_target.chmod(model_path, 0o777, recursive=True)
        nnm_model_path = f"{model_path}/NPU_mobile.nnc"
        nnm_input_data_path = f"{model_path}/NPU_mobile_input_data.bin"
        nnm_golden_data_path = f"{model_path}/NPU_mobile_golden_data.bin"
        enntest_output = execute_model_with_enn_64(
            self.test, nnm_model_path, nnm_input_data_path, nnm_golden_data_path, 0.1
        )
        validate_enn_output(enntest_output, self.enn_success_msgs)

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
        duplicates="IDCEVODEV-18692",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NNM_PROCESSING"),
                ],
            },
        },
    )
    def test_004_system_support_for_loading_and_preparing_the_nnms(self):
        """
        [SIT_Automated] System support for loading and preparing the NNMs for processing in the CU
        Steps:
            1 - Create /data/vendor/enn/models/NPU_mobile, if non-existent
            2 - Upload EnnTest_64 executable to /data/vendor/enn, if non-existent
            3 - Extract and upload correct nnc model and data, depending on hardware revision
            4 - Update LD_LIBRARY_PATH in the target.
            5 - Run EnnTest_64 executable and validate output
        """
        self.linux_helpers.extract_tar(NPU_MOBILE_PATH)
        model_path = f"{self.base_path}/models/NPU_mobile"
        self.test.mtee_target.mkdir(model_path, parents=True)
        if self.test.mtee_target.options.hardware_revision.startswith("B"):
            self.test.mtee_target.upload("/tmp/NPU_mobile/B_sample/NPU_mobile", model_path)
        else:
            self.test.mtee_target.upload("/tmp/NPU_mobile/C_sample/NPU_mobile", model_path)
        self.test.mtee_target.execute_command("export LD_LIBRARY_PATH=/data/vendor/enn/libs:$LD_LIBRAARY_PATH")

        nnm_model_path = f"{model_path}/NPU_mobile.nnc"
        nnm_input_data_path = f"{model_path}/NPU_mobile_input_data.bin"
        nnm_golden_data_path = f"{model_path}/NPU_mobile_golden_data.bin"

        enntest_output = execute_model_with_enn_64(
            self.test, nnm_model_path, nnm_input_data_path, nnm_golden_data_path, 0.1
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
        duplicates="IDCEVODEV-45729",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "QOS_MANAGEMENT"),
                ],
            },
        },
    )
    @skipIf(
        test.mtee_target.has_capability(TE.target.hardware.idcevo) and "C" not in hw_revision,
        "Skipping test as it can only be ran in IDCEVO C samples.",
    )
    def test_005_qos_management_npu_iv3(self):
        """[SIT_Automated] Verify QOS management - NPU_IV3
        Steps:
            1 - Push models files to /data/vendor/enn/QoS_models/:
            2 - Push EnnTest_64 to /data/vendor/enn & enable permission:
            3 - Set mqos_set_level to 1 and scaling_max_freq to 267000:
                # echo 1 > /sys/devices/platform/npu_exynos/mqos_set_level
                # echo 267000 > /sys/devices/platform/npu_exynos/scaling_max_freq
            4 - run using enntest_64 by giving argument as --model, --input, --golden, --threshold & --iter as below:
                # ./EnnTest_64 --model /data/vendor/enn/QoS_models/NPU_InceptionV3.nnc
                  --input /data/vendor/enn/QoS_models/NPU_InceptionV3_input_data.bin
                  --golden /data/vendor/enn/QoS_models/NPU_InceptionV3_golden_data.bin --threshold 0.1 --iter 100
            5 - Reboot the target
            6 - Set mqos_set_level to 2 and scaling_max_freq to 866000:
                # echo 2 > /sys/devices/platform/npu_exynos/mqos_set_level
                # echo 866000 > /sys/devices/platform/npu_exynos/scaling_max_freq
            7 - run using enntest_64 by giving argument as --model, --input, --golden, --threshold & --iter as below:
                # ./EnnTest_64 --model /data/vendor/enn/QoS_models/NPU_InceptionV3.nnc
                  --input /data/vendor/enn/QoS_models/NPU_InceptionV3_input_data.bin
                  --golden /data/vendor/enn/QoS_models/NPU_InceptionV3_golden_data.bin --threshold 0.1 --iter 100
            8 - Compare the execution performance(fps) of step 5(LOW) and step 8(HIGH).
                if fps for High>Low, QoS is working as expected
        """
        qos_inception_c_sample_path = Path(os.sep) / "resources" / "Qos_Inception_C-sample.tar.gz"
        self.linux_helpers.extract_tar(qos_inception_c_sample_path)

        logger.info("Creating models folder structure on target")
        model_path = f"{self.base_path}/Qos_models"
        self.test.mtee_target.mkdir(model_path, parents=True)

        logger.info("Uploading enn models and executable to target")
        self.test.mtee_target.upload("/tmp/Qos_Inception_C-sample/Qos_Inception", model_path)

        self.test.mtee_target.chmod(model_path, 0o777, recursive=True)
        # Adding Sleep to ensure the previous action won't affect the low frequency test
        time.sleep(2)
        inception_model_path = f"{model_path}/NPU_InceptionV3.nnc"
        inception_input_data_path = f"{model_path}/NPU_InceptionV3_input_data.bin"
        inception_golden_data_path = f"{model_path}/NPU_InceptionV3_golden_data.bin"

        set_npu_exynos_properties(self.test, 1, LOW_FREQUENCY, LOW_FREQUENCY)
        low_fps = execute_model_with_enn_and_get_fps(
            self.test, inception_model_path, inception_input_data_path, inception_golden_data_path, 0.1, 100
        )
        logger.debug(f"Low execution performance fps: {low_fps}")

        set_npu_exynos_properties(self.test, 2, HIGH_FREQUENCY, HIGH_FREQUENCY)
        high_fps = execute_model_with_enn_and_get_fps(
            self.test, inception_model_path, inception_input_data_path, inception_golden_data_path, 0.1, 100
        )
        logger.debug(f"High execution performance fps: {high_fps}")

        assert_true(low_fps, "Error on getting fps for low execution performance.")
        assert_true(high_fps, "Error on getting fps for high execution performance.")
        assert_greater(
            high_fps,
            low_fps,
            "QoS is not working as expected."
            f"High execution performance fps: {high_fps}."
            f"Low execution performance fps: {low_fps}.",
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
        duplicates="IDCEVODEV-47602",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "GENERAL_CPU_PROCESSING"),
                ],
            },
        },
    )
    def test_006_support_processing_nmm(self):
        """
        [SIT_Automated] general CPU processing: Support for processing NNM on the CPU of the SoC- mobilenet Model

        Steps:
            1 - Run following command to make the system RW & EXCE:
                # mount -o remount,rw /var/data && mount -o remount,exec /var/data
            2 - Copy models to /data/vendor/enn/
            3 - Copy EnnTest_64 to /data/vendor/enn/ & enable permission
            4 - Run the executable as follows:
                "./EnnTest_64 --model ./models/NPU_mobile.nnc --input ./models/NPU_mobile_input_data.bin --golden
                ./models/NPU_mobile_golden_data.bin --threshold 0.1 --profile SUMMARY"
        """
        self.test.mtee_target._clean_target = False
        self.test.mtee_target.user_data.remount_as_exec()
        self.test.mtee_target.remount()
        mobilenet_sample_path = Path(os.sep) / "resources" / "mobilenet.tar.gz"

        logger.info("Creating folder structure on target")
        result = self.test.mtee_target.execute_command(f"mkdir -p {self.base_path}")
        assert_process_returncode(0, result, f"Failed to create folder structure {self.base_path}")
        self.test.mtee_target.execute_command(f"mkdir -p {self.base_path}/models")

        logger.info("Extracting models")
        self.linux_helpers.extract_tar(mobilenet_sample_path)
        if self.test.mtee_target.options.hardware_revision.startswith("B"):
            self.test.mtee_target.upload(
                "/tmp/mobilenet/mobile_B-sample",
                os.path.join(self.base_path, "models"),
            )
        else:
            self.test.mtee_target.upload(
                "/tmp/mobilenet/mobile_C-sample",
                os.path.join(self.base_path, "models"),
            )
        model_file_path = os.path.join(self.base_path, "models/NPU_mobile.nnc")
        input_file_path = os.path.join(self.base_path, "models/NPU_mobile_input_data.bin")
        golden_file_path = os.path.join(self.base_path, "models/NPU_mobile_golden_data.bin")

        enntest_output = execute_model_with_enn_64(self.test, model_file_path, input_file_path, golden_file_path, 0.1)
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
        duplicates="IDCEVODEV-10354",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "HW_UTILIZATION_MULTIPLE_CU_PROCESSING"),
                ],
            },
        },
    )
    def test_007_multiple_cu_support_for_mobilenet_model(self):
        """
        [SIT_Automated] [NPU]Multiple CU support GPU for processing NNMs - mobilenet model
        Steps:
            1 - Create /data/vendor/enn/models/models, if non-existent
            2 - Extract and upload correct mobilenet model and data, depending on hardware revision
            3 - Upload EnnTest_64 executable to /data/vendor/enn, if non-existent
            4 - Run EnnTest_64 executable and validate output
        """
        mobilenet_path = Path(os.sep) / "resources" / "mobilenet_multiple_cu_support.tar.gz"
        if not os.path.exists("tmp/mobilenet_multiple_cu_support"):
            self.linux_helpers.extract_tar(mobilenet_path)
        model_path = f"{self.base_path}/models"
        self.test.mtee_target.mkdir(model_path, parents=True)
        if self.test.mtee_target.options.hardware_revision.startswith("B"):
            self.test.mtee_target.upload("/tmp/mobilenet_multiple_cu_support/B_Sample", model_path)
        else:
            self.test.mtee_target.upload("/tmp/mobilenet_multiple_cu_support/C_Sample", model_path)

        self.test.mtee_target.chmod(model_path, 0o777, recursive=True)
        nnm_model_path = f"{model_path}/NPU_mobile.nnc"
        nnm_input_data_path = f"{model_path}/NPU_mobile_input_data.bin"
        nnm_golden_data_path = f"{model_path}/NPU_mobile_golden_data.bin"
        enntest_output = execute_model_with_enn_64(
            self.test, nnm_model_path, nnm_input_data_path, nnm_golden_data_path, 0.1
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
        duplicates="IDCEVODEV-30981",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "QOS_MANAGEMENT"),
                ],
            },
        },
    )
    @skipIf(
        test.mtee_target.has_capability(TE.target.hardware.idcevo) and "C" not in hw_revision,
        "Skipping test as it can only be ran in IDCEVO C samples.",
    )
    def test_008_qos_management_large_network(self):
        """[SIT_Automated][NPU]QOS management - Large Network
        Steps:
        1 - Push models files to /data/vendor/enn/Qos_large_network/:
        2 - Push EnnTest_64 to /data/vendor/enn & enable permission:
        3 - Set mqos_set_level to 1 and scaling_max_freq to 267000 and trigger commands:
                # echo 1 > /sys/devices/platform/npu_exynos/mqos_set_level
                # echo 267000 > /sys/devices/platform/npu_exynos/scaling_max_freq
        4 - run using enntest_64 by giving argument as --model, --input, --golden, --threshold & --iter as below:
                # ./EnnTest_64 --model /data/vendor/enn/Qos_large_network/large_network_O1_SingleCore.nnc
                  --input /data/vendor/enn/Qos_large_network/NPU_large_network_input_data.bin
                  --golden /data/vendor/enn/Qos_large_network/NPU_large_network_golden_data.bin
                  --threshold 0.1 --iter 100
        5 - Reboot the target
        6 - Set mqos_set_level to 2 and scaling_max_freq to 866000:
            # echo 2 > /sys/devices/platform/npu_exynos/mqos_set_level
            # echo 866000 > /sys/devices/platform/npu_exynos/scaling_max_freq
        7 - run using enntest_64 by giving argument as --model, --input, --golden, --threshold & --iter as below:
            # ./EnnTest_64 --model /data/vendor/enn/QoS_models/large_network_O1_SingleCore.nnc
              --input /data/vendor/enn/QoS_models/NPU_large_network_input_data.bin
              --golden /data/vendor/enn/QoS_models/NPU_large_network_golden_data.bin --threshold 0.1 --iter 100
        8 - Compare the execution performance(fps) of step 5(LOW) and step 8(HIGH).
            if fps for High>Low, QoS is working as expected
        """
        qos_large_network_c_sample_path = Path(os.sep) / "resources" / "QOS_large_network_C-sample.tar.gz"
        self.linux_helpers.extract_tar(qos_large_network_c_sample_path)

        logger.info("Creating models folder structure on target")
        model_path = f"{self.base_path}/Qos_large_network"
        self.test.mtee_target.mkdir(model_path, parents=True)
        logger.info("Uploading enn models and executable to target")
        self.test.mtee_target.upload("/tmp/QOS_large_network_C-sample/large_network", model_path)

        self.test.mtee_target.chmod(model_path, 0o777, recursive=True)
        # Adding Sleep to ensure the previous action won't affect the low frequency test
        time.sleep(2)
        large_network_model_path = f"{model_path}/large_network_O1_SingleCore.nnc"
        large_network_golden_path = f"{model_path}/NPU_large_network_golden_data.bin"
        large_network_input_path = f"{model_path}/NPU_large_network_input_data.bin"

        set_npu_exynos_properties(self.test, 1, self.low_frequency, LOW_FREQUENCY)
        low_fps = execute_model_with_enn_and_get_fps(
            self.test, large_network_model_path, large_network_input_path, large_network_golden_path, 0.1, 100
        )
        logger.debug(f"Low execution performance fps: {low_fps}")

        set_npu_exynos_properties(self.test, 2, self.high_frequency, self.high_frequency)
        high_fps = execute_model_with_enn_and_get_fps(
            self.test, large_network_model_path, large_network_input_path, large_network_golden_path, 0.1, 100
        )
        logger.debug(f"High execution performance fps: {high_fps}")

        assert_true(low_fps, "Error on getting fps for low execution performance.")
        assert_true(high_fps, "Error on getting fps for high execution performance.")
        assert_greater(
            high_fps,
            low_fps,
            "QoS large network model is not working as expected."
            f"High execution performance fps: {high_fps}."
            f"Low execution performance fps: {low_fps}.",
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
        duplicates="IDCEVODEV-10353",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DEDICATED_CU_PROCESSING"),
                ],
            },
        },
    )
    def test_009_cu_support_for_nnm(self):
        """
        [SIT_Automated] Dedicated CU support for processing NNMs
        Steps:
            1. create a path mkdir -p  /var/data/vendor/enn/
            2. upload the models to the path /var/data/vendor/enn/
            3. Chmod 0777 Enn test_64
            4. ./EnnTest_64 --model ./models/NPU_mobile.nnc --input ./models/NPU_mobile_input_data.bin
             --golden ./models/NPU_mobile_golden_data.bin --threshold 0.1
        """
        if not os.path.exists("tmp/NPU_mobile"):
            self.linux_helpers.extract_tar(NPU_MOBILE_PATH)
        model_path = f"{self.base_path}/models/NPU_mobile"
        self.test.mtee_target.mkdir(model_path, parents=True)
        if self.test.mtee_target.options.hardware_revision.startswith("B"):
            self.test.mtee_target.upload("/tmp/NPU_mobile/B_sample/NPU_mobile", model_path)
        else:
            self.test.mtee_target.upload("/tmp/NPU_mobile/C_sample/NPU_mobile", model_path)

        self.test.mtee_target.chmod(model_path, 0o777, recursive=True)
        nnm_model_path = f"{model_path}/NPU_mobile.nnc"
        nnm_input_data_path = f"{model_path}/NPU_mobile_input_data.bin"
        nnm_golden_data_path = f"{model_path}/NPU_mobile_golden_data.bin"
        enn_test_output = execute_model_with_enn_64(
            self.test, nnm_model_path, nnm_input_data_path, nnm_golden_data_path, 0.1
        )
        validate_enn_output(enn_test_output, ENN_SUCCESS_MSGS)

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
        duplicates="IDCEVODEV-19070",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NNM_SCHEDULING"),
                ],
            },
        },
    )
    def test_010_processing_4nnm_models_simultaneously(self):
        """
        [SIT_Automated] Processing of 4NNM simultaneously
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
        logger.info("Extracting models")
        sample_4nnm_processing_model_path = Path(os.sep) / "resources" / "sample_4nnm_processing.tar.gz"
        self.linux_helpers.extract_tar(sample_4nnm_processing_model_path)

        if self.test.mtee_target.options.hardware_revision.startswith("B"):
            self.test.mtee_target.upload(
                "/tmp/sample_4nnm_processing/sample_4nnm_b_processing", f"{self.base_path}/models"
            )
        else:
            self.test.mtee_target.upload(
                "/tmp/sample_4nnm_processing/sample_4nnm_c_processing", f"{self.base_path}/models"
            )

        logger.info("Uploading executable to target and change permissions")
        self.test.mtee_target.upload(
            "/tmp/sample_4nnm_processing/enn_sample_external", f"{self.base_path}/enn_sample_external"
        )
        self.test.mtee_target.chmod(f"{self.base_path}/enn_sample_external", 0o777, recursive=True)
        enntest_output, stderr, return_code = self.test.mtee_target.execute_command(
            "./enn_sample_external",
            cwd=self.base_path,
        )

        logger.debug(f"Return of ./enn_sample_external: \n{enntest_output}")
        assert_process_returncode(0, return_code, f"Failed to execute EnnTest_64, error: {stderr}")
        assert_true(
            "Result is matched with golden out" in enntest_output, "Test failed. Output is missing the expected Output"
        )
