# Copyright (C) 2023. BMW CTW PT. All rights reserved.
"""Neural processing hardware resources tests"""
import configparser
import logging
import os
import re
import subprocess
import time

from pathlib import Path
from unittest import skipIf
from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import (
    assert_equal,
    assert_false,
    assert_greater,
    assert_process_returncode,
    assert_true,
    metadata,
    run_command,
)
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.linux_commands_handlers import LinuxCommandsHandler
from si_test_idcevo.si_test_helpers.npu_helper import extract_and_upload_model
from si_test_idcevo.si_test_helpers.test_helpers import skip_unsupported_ecus
from validation_utils.utils import CommandError, TimeoutError

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
target = TargetShare().target
hw_revision = target.options.hardware_revision

c_sample_2nnm_model_path = Path(os.sep) / "resources" / "2nnms_C-sample.tar.gz"
enntest64_path = Path(os.sep) / "resources" / "EnnTest_64.tar.gz"
delegatepackage = Path(os.sep) / "resources" / "delegatePackage.tar.gz"
large_network_c_sample_path = Path(os.sep) / "resources" / "large_network_C-sample.tar.gz"
npu_resources_path = Path(os.sep) / "resources" / "npu_hw_resources_tool.tar.gz"
matmul_model = Path(os.sep) / "resources" / "matmul_model.tar.gz"
mobile_c_sample_path = Path(os.sep) / "resources" / "mobile_C-sample.tar.gz"
model_2nnm_path = Path(os.sep) / "resources" / "2NNMsExecute.tar.gz"
npu_dsp_model_c_sample_path = Path(os.sep) / "resources" / "NPU_DSP_Model.tar.gz"
npu_mv2_resources_path = Path(os.sep) / "resources" / "npu_mv2_deeplab.tar.gz"
preemption_path = Path(os.sep) / "resources" / "preemption_models.tar.gz"
software_upgrade_path = Path(os.sep) / "resources" / "software_upgrade.tar.gz"
spotfixer_sample_path = Path(os.sep) / "resources" / "Spotfixer-sample.tar.gz"

NPU_SUCCESS_MSG = "[SUCCESS] Result is matched with golden out"
ENN_SUCCESS_MSGS = ["Golden Matched", "TEST SUCCESS"]

EXECUTION_PERF_PATTERN = re.compile(r".*Execution Performance : \[ (.*?) \] fps.*")
DELEGATE_APP_SUCCESS_MSGS = [
    "DelegateBackend: Initialized Samsung Delegate",
    "DelegateBackend: LIST OF DELEGATES",
    "DelegateBackend: Initialized Tflite Interpreter",
    "GOLDEN Match? true",
]

HIGH_FREQUENCY = 866000
LOW_FREQUENCY = 267000
SUCCESS_COUNT = 100

ENN_SAMPLE_EXTERNAL_FILE = "/vendor/bin/enn_sample_external"
NPU_IV3_PATH = "/data/vendor/enn/models/NPU_IV3"
NPU_MOBILENET_PATH = "/data/vendor/enn/models/NPU_mobilenet"
NNM_MODELS_EXPECTED_OUTPUT = [
    "/data/vendor/enn/models/NPU_IV3/NPU_InceptionV3.nnc",
    "/data/vendor/enn/models/NPU_mobilenet/NPU_mobile.nnc",
    "Executing model 0",
    "Executing model 1",
    "[SUCCESS] Result is matched with golden out",
]
ENNTEST_PATH = "/tmp/preemption_models/preemption/EnnTest_64"
PREEMPT_MODEL_PATH = "./models/NPU_InceptionV3/NPU_InceptionV3_preemption.nnc"
PREEMPT_INPUT_PATH = "./models/NPU_InceptionV3/NPU_InceptionV3_input_data.bin"
PREEMPT_GOLDEN_PATH = "./models/NPU_InceptionV3/NPU_InceptionV3_golden_data.bin"


class TestsNPUHardwareResources(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(root=True, disable_dmverity=True)
        cls.linux_helpers = LinuxCommandsHandler(cls.test.mtee_target, logger)
        cls.base_path = "/data/vendor/enn"
        cls.var_root_path = "/var/data/vendor/enn"

        cls.test.mtee_target.remount()
        if not cls.test.mtee_target.exists(cls.base_path):
            cls.test.mtee_target.execute_command(f"mkdir -p {cls.base_path}", expected_return_code=0)
        cls.linux_helpers.extract_tar(enntest64_path)
        run_command(["chmod", "0775", "tmp/EnnTest/EnnTest_64"])
        cls.test.mtee_target.upload("/tmp/EnnTest_64/EnnTest_64", f"{cls.base_path}/EnnTest_64")
        cls.test.mtee_target.chmod(f"{cls.base_path}/EnnTest_64", 0o777)

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def setup(self):
        self.test.mtee_target.remount()

    def teardown(self):
        self.test.mtee_target._recover_ssh(record_failure=False)

        # Delete all sub folders inside /data/vendor/enn
        self.test.mtee_target.execute_command(f"rm -rf {self.base_path}/*/", expected_return_code=0)

    def remove_enn_x86_prop_file(self):
        """
        Removing enn_x86_prop file from /home/root/ directory except for C samples
        """
        if "C" not in self.test.mtee_target.options.hardware_revision:
            cmd = "rm .enn_x86_prop"
            self.test.mtee_target.execute_command(cmd)

    def set_npu_exynos_properties(self, mqos_set_level, scaling_max_freq, scaling_min_freq):
        """
        Set mqos_set_level and scaling_max_freq
        :param mqos_set_level: Set level for MQOS
        :type mqos_set_level: int
        :param scaling_max_freq: Maximum frequency for scaling
        :type scaling_max_freq: int
        """

        self.test.mtee_target.execute_command(
            f"echo {mqos_set_level} > /sys/devices/platform/npu_exynos/mqos_set_level"
        )
        self.test.mtee_target.execute_command(
            f"echo {scaling_max_freq} > /sys/devices/platform/npu_exynos/scaling_max_freq"
        )
        self.test.mtee_target.execute_command(
            f"echo {scaling_min_freq} > /sys/devices/platform/npu_exynos/scaling_min_freq"
        )
        logger.info(f"Set mqos_set_level to {mqos_set_level} and scaling_max_freq to {scaling_max_freq}")

    def retrieve_fps_from_output(self, stdout):
        """
        Retrieve fps from EnnTest_64 output

        :param stdout: Output from EnnTest_64
        :type stdout: str
        :return fps: returns the fps from the output or False if failed to get fps
        """
        match = re.search(EXECUTION_PERF_PATTERN, stdout)
        if match:
            fps = float(match.group(1))
        else:
            fps = False
            logger.debug(f"Failed to get fps from EnnTest_64 output: {stdout}")
        return fps

    def execute_npu_mobile_and_get_fps(self, threshold, iter):
        """
        Execute enn_sample_external for npu mobile models and get fps from output

        :param threshold: Threshold for the test
        :type threshold: float
        :param iter: Number of iterations
        :type iter: int
        :return fps: returns the fps from the output or False if failed to get fps
        """
        stdout, stderr, returncode = self.test.mtee_target.execute_command(
            "./EnnTest_64 --model /data/vendor/enn/QoS_models/NPU_mobile.nnc"
            " --input /data/vendor/enn/QoS_models/NPU_mobile_input_data.bin"
            " --golden /data/vendor/enn/QoS_models/NPU_mobile_golden_data.bin"
            f" --threshold {threshold} --iter {iter}",
            cwd="/data/vendor/enn/",
            timeout=60,
        )

        assert_process_returncode(0, returncode, f"Failed to execute enn_sample_external, error: {stderr}")

        return self.retrieve_fps_from_output(stdout)

    def execute_model_with_enntest_64(self, model, input_data, golden_data, threshold=None):
        """
        Run EnnTest_64 executable with specified parameters

        :param model: .nnc file to use as model
        :param input_data: .bin file with input data
        :param golden_data: .bin file with golden data
        :param threshold: threshold for the execution
        :return stdout: output of EnnTest_64 execution
        """
        self.test.mtee_target.execute_command("chmod +x EnnTest_64", cwd="/data/vendor/enn/")

        cmd = f"./EnnTest_64 --model {model} --input {input_data} --golden {golden_data}"
        if threshold:
            cmd += f" --threshold {threshold}"

        stdout, stderr, return_code = self.test.mtee_target.execute_command(cmd, cwd="/data/vendor/enn/")

        assert_process_returncode(
            0, return_code, f"Failed to execute EnnTest_64 with the following command: {cmd}, Returned error: {stderr}"
        )
        return stdout

    def validate_enn_output(self, enntest_output, expected_output_msgs):
        """
        Validate the output of EnnTest_64 execution by checking expected success keywords
        :param enntest_output: Output of EnnTest_64 execution
        :param expected_output_msgs: Expected list of success keywords
        """
        missing_messages = []
        for message in expected_output_msgs:
            if message not in enntest_output:
                missing_messages.append(message)

        assert_false(
            missing_messages,
            f"Failed to find '{missing_messages}' message(s) in model's execution output. "
            f"Output found: {enntest_output}",
        )

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
        duplicates="IDCEVODEV-19072",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NNM_PROCESSING"),
                ],
            },
        },
    )
    @skipIf(not skip_unsupported_ecus(["idcevo"]), "This test isn't supported by this ECU!")
    def test_handle_preempt_processing(self):
        """
        [SIT_Automated] Verify system can able to handle preEmpt processing

        Steps:
            1 - Run following command to make the system RW and EXEC:
                # mount -o remount,rw /var/data
                # mount -o remount,exec /var/data
            2 - Copy all model files to /data/vendor/enn/models
            3 - copy Enntest_64 present in Enntest_64.zip
            4 - Run EnnTest_64 executable and validate output

        Note: This Test Case performs differently accordingly with the sample version (B-sample & C-sample)
        """
        self.test.mtee_target._clean_target = False
        self.test.mtee_target.remount()
        self.test.mtee_target.user_data.remount_as_exec()

        self.test.mtee_target.execute_command(f"mkdir -p {self.base_path}/models", expected_return_code=0)

        self.linux_helpers.extract_tar(preemption_path)

        self.test.mtee_target.upload("/tmp/preemption_models/preemption/NPU_InceptionV3", f"{self.base_path}/models/")
        self.test.mtee_target.upload(ENNTEST_PATH, f"{self.base_path}/EnnTest_64")
        self.test.mtee_target.execute_command("chmod 0777 EnnTest_64", cwd=self.base_path)

        logger.info("Running EnnTest_64")
        enntest_stdout, stderr, return_code = self.test.mtee_target.execute_command(
            f"./EnnTest_64 --multi_thread "
            f'"1 --model {PREEMPT_MODEL_PATH} --input {PREEMPT_INPUT_PATH} --golden '
            f'{PREEMPT_GOLDEN_PATH} --iter 10 --priority 112" '
            f'"2 --model {PREEMPT_MODEL_PATH} --input {PREEMPT_INPUT_PATH} --golden '
            f'{PREEMPT_GOLDEN_PATH} --iter 10 --priority 203" '
            f'"3 --model {PREEMPT_MODEL_PATH} --input {PREEMPT_INPUT_PATH} --golden '
            f'{PREEMPT_GOLDEN_PATH} --iter 10 --priority 112"',
            cwd=self.base_path,
        )

        logger.debug(f"Return of ./EnnTest_64: \n {enntest_stdout}")

        assert_process_returncode(0, return_code, f"Failed to execute EnnTest_64, error: {stderr}")
        assert_true("Golden Matched" in enntest_stdout, "Test failed. Output is missing the 'Golden Match'")
        assert_true("TEST SUCCESS" in enntest_stdout, "Test failed. Output is missing the 'TEST SUCCESS'")

        result = None
        try:
            cmd = "cat /sys/kernel/debug/npu/fw-report"
            result = self.test.mtee_target.execute_command(cmd, timeout=120)
            assert_true("preempt" in result.stdout, "Error while finding preempt keyword under fw-report")
        except (CommandError, TimeoutError) as err:
            logger.debug(f"Timeout reached while executing the preempt command - {err}")
        except AssertionError as ae:
            logger.error(f"Assertion error: {ae}")

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
        duplicates="IDCEVODEV-186265",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NPU_HW_RESOURCES_DETERMINISTIC_BEHAVIOUR"),
                ],
            },
        },
    )
    @skipIf(not target.has_capability(TE.target.hardware.idcevo), "Test not applicable for this ECU")
    def test_001_hardware_resources_application_domain(self):
        """
        [SIT_Automated] [NPU]HW resources - Application Domain

        Steps:
            1 - Remount target
            2 - Install apk based on HW revision.
            3 - Create dir /data/local/tmp/delegate in android target.
            4 - Push the model files into the target.
            5 - Enable executable permission to delegate folder.
            6 - Set required permissions to org.samsung_slsi.delegate_demo package.
            7 - Run model command and look for expected output.

        :return:
        """
        model_path = "/data/local/tmp/delegate"
        self.linux_helpers.extract_tar(delegatepackage)
        if "B" in hw_revision:
            apk_to_install = "/tmp/delegatePackage/app-debug.apk"
        else:
            apk_to_install = "/tmp/delegatePackage/EnnDelegate_EVT2.apk"
        result = self.test.apinext_target.install_apk(apk_to_install)
        assert_true("Success" in result.stdout.decode("utf-8"), "The apk was not installed successfully!")

        self.test.apinext_target.execute_command(f"mkdir -p {model_path}")
        self.test.apinext_target.push_as_current_user("/tmp/delegatePackage/data/", model_path)
        self.test.apinext_target.execute_command(f"chmod -R 777 {model_path}/")

        package_name = "org.samsung_slsi.delegate_demo"
        self.test.apinext_target.execute_command(f"appops set --uid {package_name} MANAGE_EXTERNAL_STORAGE allow")
        self.test.apinext_target.execute_command(f"appops set --uid {package_name} READ_EXTERNAL_STORAGE allow")
        self.test.apinext_target.execute_command(f"appops set --uid {package_name} WRITE_EXTERNAL_STORAGE allow")

        cmd = (
            "am start -S -n org.samsung_slsi.delegate_demo/org.samsung_slsi.delegate_demo.frontend.MainActivity"
            f" --es --model {model_path}/data/mobilenet_v2_1.0_224.tflite"
            f" --es --input {model_path}/data/banana_224.input"
            f" --es --golden {model_path}/data/banana_v2_1.0_224.output"
            " --es --threshold 0.1"
        )
        logcat_file_path = Path(self.test.results_dir) / "logcat_output.txt"
        logcat_command = ["adb", "logcat", "-s", "Logger"]
        with open(logcat_file_path, "w") as log_file:
            logcat_process = subprocess.Popen(logcat_command, stdout=log_file)
            try:
                result = self.test.apinext_target.execute_command(cmd)
                logger.debug(f"Application Domain result: {result}")
                time.sleep(10)
            finally:
                logcat_process.terminate()
                logcat_process.wait()
        logger.info("Logcat and command outputs have been saved to %s", logcat_file_path)
        with open(logcat_file_path, "r", encoding="latin-1") as logcat_data:
            logcat_output = logcat_data.read()
        self.validate_enn_output(logcat_output, DELEGATE_APP_SUCCESS_MSGS)

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
        duplicates="IDCEVODEV-30977",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NPU_HW_RESOURCES_DETERMINISTIC_BEHAVIOUR"),
                ],
            },
        },
    )
    def test_002_hardware_resources_config(self):
        """
        [SIT_Automated] [NPU] Configuration of the HW resources - Deterministic Behavior

        Steps:
            1 - Remount system for Read and Write permissions
            2 - Push enn_sample_external to /data and add permissions to execute
            3 - Push NPU mobile files to /data/vendor/enn/models/NPU_mobile
            4 - Export Neural Network (NN) lib path
            5 - Execute enn_sample_external
            6 - Check output result for 100 matches of "[SUCCESS] Result is matched with golden out"
        """

        self.linux_helpers.extract_tar(mobile_c_sample_path)
        self.linux_helpers.extract_tar(npu_resources_path)

        logger.info("Creating folder structure on target")
        self.test.mtee_target.execute_command("mkdir -p /data/vendor/enn/models/NPU_mobile", expected_return_code=0)

        if self.test.mtee_target.options.hardware_revision.startswith("B"):
            self.test.mtee_target.upload("/tmp/models", "/data/vendor/enn/models/NPU_mobile")
        else:
            self.test.mtee_target.upload("/tmp/mobile_C-sample/mobile", "/data/vendor/enn/models/NPU_mobile")

        logger.info("Uploading enn models and executable to target")
        self.test.mtee_target.upload("/tmp/enn_node0/enn_sample_external", "/data/enn_sample_external")

        self.test.mtee_target.execute_command("export LD_LIBRARY_PATH=/data/vendor/enn/libs:$LD_LIBRAARY_PATH")

        self.test.mtee_target.execute_command("chmod +x enn_sample_external", cwd="/data")
        stdout, stderr, returncode = self.test.mtee_target.execute_command("./enn_sample_external", cwd="/data")
        logger.debug(f"Command output: \n{stdout}, stderr: \n{stderr}")

        assert_process_returncode(0, returncode, "Failed to execute enn_sample_external.")
        assert_true(NPU_SUCCESS_MSG in stdout, f"Test failed. Output is missing the success message:{NPU_SUCCESS_MSG}")
        assert_true(
            stdout.count(NPU_SUCCESS_MSG) == SUCCESS_COUNT,
            f"Expected to find {SUCCESS_COUNT} success messages instead found {stdout.count(NPU_SUCCESS_MSG)}",
        )

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
        duplicates="IDCEVODEV-45726",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "QOS_MANAGEMENT"),
                ],
            },
        },
    )
    @skipIf(
        target.has_capability(TE.target.hardware.idcevo) and "C" not in hw_revision,
        "Skipping test as it can only be ran in IDCEVO C samples.",
    )
    def test_003_qos_management_mobilenet(self):
        """[SIT_Automated] Verify QOS management - Mobilenet

        Steps:
            1 - Run following command to make the system RW:
                # mount -o remount,rw /
            2 - Push models files to /data/vendor/enn/QoS_models/:
            3 - Push EnnTest_64 to /data/vendor/enn & enable permission:
            4 - Set mqos_set_level to 1 and scaling_max_freq to 267000:
                # echo 1 > /sys/devices/platform/npu_exynos/mqos_set_level
                # echo 267000 > /sys/devices/platform/npu_exynos/scaling_max_freq
            5 - run using enntest_64 by giving argument as --model, --input, --golden, --threshold & --iter as below:
                # ./EnnTest_64 --model /data/vendor/enn/QoS_models/NPU_mobile.nnc
                  --input /data/vendor/enn/QoS_models/NPU_mobile_input_data.bin
                  --golden /data/vendor/enn/QoS_models/NPU_mobile_golden_data.bin --threshold 0.1 --iter 100
            6 - Reboot the target
            7 - Set mqos_set_level to 2 and scaling_max_freq to 866000:
                # echo 2 > /sys/devices/platform/npu_exynos/mqos_set_level
                # echo 866000 > /sys/devices/platform/npu_exynos/scaling_max_freq
            8 - run using enntest_64 by giving argument as --model, --input, --golden, --threshold & --iter as below:
                # ./EnnTest_64 --model /data/vendor/enn/QoS_models/NPU_mobile.nnc
                  --input /data/vendor/enn/QoS_models/NPU_mobile_input_data.bin
                  --golden /data/vendor/enn/QoS_models/NPU_mobile_golden_data.bin --threshold 0.1 --iter 100
            9 - Compare the execution performance(fps) of step 5(LOW) and step 8(HIGH).
                if fps for High>Low, QoS is working as expected
        """

        self.linux_helpers.extract_tar(mobile_c_sample_path)
        self.linux_helpers.extract_tar(npu_resources_path)

        result = run_command(["ls", "-R", "/tmp"])
        logger.debug(f"Content of /tmp: \n{result.stdout}")

        logger.info("Creating models folder structure on target")
        self.test.mtee_target.execute_command("mkdir -p /data/vendor/enn/QoS_models", expected_return_code=0)

        logger.info("Uploading enn models and executable to target")
        if self.test.mtee_target.options.hardware_revision.startswith("B"):
            self.test.mtee_target.upload(Path(os.sep) / "tmp/models", "/data/vendor/enn/QoS_models")
        else:
            self.test.mtee_target.upload("/tmp/mobile_C-sample/mobile", "/data/vendor/enn/QoS_models")
        self.set_npu_exynos_properties(1, LOW_FREQUENCY, LOW_FREQUENCY)
        low_fps = self.execute_npu_mobile_and_get_fps(0.1, 100)
        logger.debug(f"Low execution performance fps: {low_fps}")

        self.set_npu_exynos_properties(2, HIGH_FREQUENCY, HIGH_FREQUENCY)
        high_fps = self.execute_npu_mobile_and_get_fps(0.1, 100)
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
        testsuite=["BAT", "domain", "SI", "IDCEVO-SP21"],
        component="tee_idcevo",
        domain="System Software",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-30980",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "OPERATORS_LAYERS_UPGRADE"),
                ],
            },
        },
    )
    def test_004_operators_layers(self):
        """
        [SIT_Automated] Operators layers upgrade

        Steps:
            1 - Remount target system
            2 - Extract models data and create folder structure on target
            2 - Push models files to /data/vendor/enn/large_model/:
                C samples -> large_network_C-sample.tar.gz
                B samples -> software_upgrade.tar.gz
            3 - Push EnnTest_64 to /data/vendor/enn & enable permission:
            4 - run using enntest_64 by giving argument as --model, --input & --golden as below:
                # ./EnnTest_64 --model /data/vendor/enn/large_model/large_network_O1_SingleCore.nnc
                    --input /data/vendor/enn/large_model/NPU_large_network_input_data.bin
                    --golden /data/vendor/enn/large_model/NPU_large_network_golden_data.bin --threshold 0.1
            5 - Check the result for golden match
        """

        logger.info("Creating folder structure on target")
        self.test.mtee_target.execute_command("mkdir -p /data/vendor/enn/large_model/", expected_return_code=0)

        logger.info("Upload models based on sample version")
        if self.test.mtee_target.options.hardware_revision.startswith("B"):
            self.linux_helpers.extract_tar(software_upgrade_path)
            model_file = "large_network_O1_SingleCore.nnc"
            self.test.mtee_target.upload(Path(os.sep) / "tmp/GPU_MODELS", "/data/vendor/enn/large_model")
        else:
            self.linux_helpers.extract_tar(large_network_c_sample_path)
            model_file = "large_network_O2_SingleCore.nnc"
            self.test.mtee_target.upload(
                Path(os.sep) / "tmp/large_network_C-sample/large_network/large_network", "/data/vendor/enn/large_model"
            )

        enntest_output = self.execute_model_with_enntest_64(
            f"{self.base_path}/large_model/{model_file}",
            f"{self.base_path}/large_model/NPU_large_network_input_data.bin",
            f"{self.base_path}/large_model/NPU_large_network_golden_data.bin",
            threshold=0.1,
        )
        self.validate_enn_output(enntest_output, ENN_SUCCESS_MSGS)

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
        duplicates="IDCEVODEV-19069",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NNM_SCHEDULING"),
                ],
            },
        },
    )
    def test_005_processing_2nnm_models_simultaneously(self):
        """
        [SIT_Automated] processing of 2NNM models run simultaneously based on scheduling

        Steps:
            1. Prepare model (nnc and bin) to test 2NNM functionality
            2. Enable adb using command,
                "getprop persist.vendor.usb.config"
                "setprop persist.vendor.usb.config adb"
            3. Reboot the target
            4. In the windows console, run the push.bat file to create all required directories
            and push all the models to the respective folders
            5. Run the 'enn_sample_external' model and validate the output.
        """
        self.test.apinext_target.execute_command("test -e /cache/tmpfs || mkdir /cache/tmpfs")
        self.test.apinext_target.execute_command("mount -t tmpfs tmpfs_ovl /cache/tmpfs")
        self.test.apinext_target.execute_command("mkdir /cache/tmpfs/upper")
        self.test.apinext_target.execute_command("mkdir /cache/tmpfs/work")
        self.test.apinext_target.execute_command(
            "mount -t overlay vendor_ovl -o lowerdir=/vendor,upperdir=/cache/tmpfs/upper,"
            "workdir=/cache/tmpfs/work /vendor"
        )

        if self.test.mtee_target.options.hardware_revision.startswith("C"):
            self.linux_helpers.extract_tar(c_sample_2nnm_model_path)
            npu_inceptionv3_path = (
                "/tmp/2nnms_C-sample/2nnms/2NNMsExecute/sample_model/v920/NPU_IV3/NPU_InceptionV3.nnc"
            )
            golden_data_npu_path = (
                "/tmp/2nnms_C-sample/2nnms/2NNMsExecute/sample_model/v920/NPU_IV3/NPU_InceptionV3_golden_data.bin"
            )
            input_data_npu_path = (
                "/tmp/2nnms_C-sample/2nnms/2NNMsExecute/sample_model/v920/NPU_IV3/NPU_InceptionV3_input_data.bin"
            )
            npu_mobile_path = "/tmp/2nnms_C-sample/2nnms/2NNMsExecute/sample_model/v920/mobile/NPU_mobile.nnc"
            golden_data_mobile_path = (
                "/tmp/2nnms_C-sample/2nnms/2NNMsExecute/sample_model/v920/mobile/NPU_mobile_golden_data.bin"
            )
            input_data_mobile_path = (
                "/tmp/2nnms_C-sample/2nnms/2NNMsExecute/sample_model/v920/mobile/NPU_mobile_input_data.bin"
            )
            enn_sample_external_path = "/tmp/2nnms_C-sample/2nnms/2NNMsExecute/enn_sample_external"
        else:
            self.linux_helpers.extract_tar(model_2nnm_path)
            npu_inceptionv3_path = "/tmp/2NNMsExecute/sample_model/v920/NPU_IV3/NPU_InceptionV3.nnc"
            golden_data_npu_path = "/tmp/2NNMsExecute/sample_model/v920/NPU_IV3/NPU_InceptionV3_golden_data.bin"
            input_data_npu_path = "/tmp/2NNMsExecute/sample_model/v920/NPU_IV3/NPU_InceptionV3_input_data.bin"
            npu_mobile_path = "/tmp/2NNMsExecute/sample_model/v920/mobile/NPU_mobile.nnc"
            golden_data_mobile_path = "/tmp/2NNMsExecute/sample_model/v920/mobile/NPU_mobile_golden_data.bin"
            input_data_mobile_path = "/tmp/2NNMsExecute/sample_model/v920/mobile/NPU_mobile_input_data.bin"
            enn_sample_external_path = "/tmp/2NNMsExecute/enn_sample_external"

        self.test.apinext_target.execute_command(f"mkdir -p {NPU_IV3_PATH}")
        self.test.apinext_target.execute_command(f"mkdir -p {NPU_MOBILENET_PATH}")

        self.test.apinext_target.execute_adb_command(
            [
                "push",
                npu_inceptionv3_path,
                NPU_IV3_PATH,
            ],
        )
        self.test.apinext_target.execute_adb_command(
            [
                "push",
                golden_data_npu_path,
                NPU_IV3_PATH,
            ],
        )
        self.test.apinext_target.execute_adb_command(
            [
                "push",
                input_data_npu_path,
                NPU_IV3_PATH,
            ],
        )
        self.test.apinext_target.execute_adb_command(
            [
                "push",
                npu_mobile_path,
                NPU_MOBILENET_PATH,
            ],
        )
        self.test.apinext_target.execute_adb_command(
            [
                "push",
                golden_data_mobile_path,
                NPU_MOBILENET_PATH,
            ],
        )
        self.test.apinext_target.execute_adb_command(
            [
                "push",
                input_data_mobile_path,
                NPU_MOBILENET_PATH,
            ],
        )

        self.test.apinext_target.execute_command("sync")
        self.test.apinext_target.execute_adb_command(
            [
                "push",
                enn_sample_external_path,
                "/vendor/bin/",
            ],
        )

        self.test.apinext_target.execute_command(f"chmod +x {ENN_SAMPLE_EXTERNAL_FILE}")
        result = self.test.apinext_target.execute_command(ENN_SAMPLE_EXTERNAL_FILE)
        logger.debug(f"Output of enn_sample_external model - {result}")
        match = self.linux_helpers.validate_output_android_console(result, NNM_MODELS_EXPECTED_OUTPUT)

        assert_true(match, f"Failed to validate expected output, got output - {result}")

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
        duplicates="IDCEVODEV-45543",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "DEDICATED_CU_PROCESSING"),
                ],
            },
        },
    )
    def test_006_dsp_support_nnm(self):
        """[SIT_Automated] Verify DSP-Support for processing NNM

        Note: To prevent unexpected failures, this test should always be executed AFTER the test
        '[SIT_Automated] processing of 2NNM models run simultaneously based on scheduling'

        Steps:
            1 - Run following command to make the system RW:
                # mount -o remount,rw /
            2 - Extract and upload model files on target
            3 - Run the Enn command and check output of EnnTest_64 for "Golden Matched" & "TEST SUCCESS"
            4 - Check output for "(+) NpuUserDriver::OpenSubGraph()"
        """
        npu_driver_pattern = re.compile(
            r".*\(\+\) NpuUserDriver::OpenSubGraph\(\), model_id\(.*\), op_list_id\(.*\).*"
        )
        self.test.mtee_target.user_data.remount_as_exec()
        folder_path = "/tmp/NPU_DSP_Model"
        folder_name = "NPU_DSP_Model"
        root_path = f"{self.var_root_path}/models"

        model_path = extract_and_upload_model(self, npu_dsp_model_c_sample_path, root_path, folder_path, folder_name)

        nnm_model_path = f"{model_path}/NPU_DSP_Model_O2_SingleCore.nnc"
        nnm_input_data_path = f"{model_path}/SPyTorchNet_input_data.bin"
        nnm_golden_data_path = f"{model_path}/SPyTorchNet_golden_data.bin"
        enntest_output = self.execute_model_with_enntest_64(nnm_model_path, nnm_input_data_path, nnm_golden_data_path)
        self.validate_enn_output(enntest_output, ENN_SUCCESS_MSGS)

        npu_driver_found = re.search(npu_driver_pattern, enntest_output)
        logger.debug(f"Found NpuUserDriver::OpenSubGraph information: {npu_driver_found}")
        assert_true(npu_driver_found, "Test failed. Output is missing NpuUserDriver::OpenSubGraph information")

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
        duplicates="IDCEVODEV-11863",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "VMACHINE_DOMAIN_SUPPORT"),
                ],
            },
        },
    )
    def test_007_virtualization_support_multiple_npu(self):
        """
        [SIT_Automated] Virtualization support-mutiple NPU support from node0

        Steps:
            1 - Remount target
            2 - Create /data/vendor/enn/, if non-existent
            3 - Upload EnnTest_64 executable to /data/vendor/enn, if non-existent
            3 - Extract and upload correct nnc model and data, depending on hardware revision
            4 - Run EnnTest_64 executable and validate output
        """

        self.linux_helpers.extract_tar(spotfixer_sample_path)
        self.test.mtee_target.upload("/tmp/Spotfixer", f"{self.base_path}/spotfixer")

        spotfixer_model_path = f"{self.base_path}/spotfixer/spotfixer__SingleCore.nnc"
        spotfixer_input_data_path = f"{self.base_path}/spotfixer/MCD_27_PhotoEditor_SpotFixer_input_data.bin"
        spotfixer_golden_data_path = f"{self.base_path}/spotfixer/MCD_27_PhotoEditor_SpotFixer_golden_data.bin"

        enntest_output = self.execute_model_with_enntest_64(
            spotfixer_model_path, spotfixer_input_data_path, spotfixer_golden_data_path, threshold=0.027
        )
        self.validate_enn_output(enntest_output, ENN_SUCCESS_MSGS)

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
        duplicates="IDCEVODEV-246468",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NNM_OPERATORS_LAYERS_ADDITIONAL"),
                ],
            },
        },
    )
    def test_008_matmul_operator_on_npu(self):
        """
        [SIT_Automated] Matmul Operator on NPU

        Steps:
            1 - Create /data/vendor/enn/, if non-existent
            2 - Upload EnnTest_64 executable to /data/vendor/enn, if non-existent
            3 - Extract and upload model data.
            4 - Check output of EnnTest_64 for "Golden Matched" & "TEST SUCCESS"
        """

        self.linux_helpers.extract_tar(matmul_model)
        self.test.mtee_target.upload("/tmp/matmul_model", f"{self.base_path}/matmul")

        matmul_model_path = f"{self.base_path}/matmul/matmul_sample_O2_SingleCore.nnc"
        matmul_input_data_path = f"{self.base_path}/matmul/data_Q_in.bin"
        matmul_golden_data_path = f"{self.base_path}/matmul/NPU_matmul_sample_golden_data.bin"

        enntest_output = self.execute_model_with_enntest_64(
            matmul_model_path, matmul_input_data_path, matmul_golden_data_path
        )
        self.validate_enn_output(enntest_output, ENN_SUCCESS_MSGS)

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
        duplicates="IDCEVODEV-186284",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": [
                    config.get("FEATURES", "NNM_PROCESSING"),
                    config.get("FEATURES", "NNM_SCHEDULING"),
                ],
            },
        },
    )
    def test_009_processing_2nnm_4nnm_8nnm_models_simultaneously(self):
        """
        [SIT_Automated] Verify Processing of 2NNM/4NNM/8NNM simultaneously
        Pre-condition:
            - Run following command to make the system RW:
                # mount -o remount,rw /var/data
        Steps:
            1 - Push models files to /var/data/vendor/enn/models
            2 - Push enn_sample_8nnms to /data/vendor/enn & enable permission
            3 - Update LD_LIBRARY_PATH in the target.
            4 - Execute enn_sample_8nnms
            5 - Check the return of the executable for test success status
        Expected outcome:
            - Check for below Results match:
                 Result is matched with golden out
        """
        nnm_model_path = Path(os.sep) / "resources" / "8nnm_models.tar.gz"

        self.test.mtee_target.remount()
        self.test.mtee_target.user_data.remount_as_exec()
        if not os.path.exists("tmp/8nnm_models/nnm_models"):
            self.linux_helpers.extract_tar(nnm_model_path)

        model_path = f"{self.var_root_path}/models"
        self.test.mtee_target.mkdir(model_path, parents=True)
        self.test.mtee_target.upload("/tmp/8nnm_models/nnm_models", model_path)

        enn_path = f"{self.base_path}/enn_test"
        self.test.mtee_target.mkdir(enn_path, parents=True)
        self.test.mtee_target.upload("/tmp/8nnm_models/nnm_models/enn_test", enn_path)

        self.test.mtee_target.chmod(enn_path, 0o777, recursive=True)

        self.test.mtee_target.execute_command("export LD_LIBRARY_PATH=/data/vendor/enn/libs:$LD_LIBRARY_PATH")

        cmd = "./enn_sample_8nnms"
        enntest_output, _, _ = self.test.mtee_target.execute_command(cmd, cwd=enn_path)
        assert_equal(
            8,
            enntest_output.count(NPU_SUCCESS_MSG),
            f"2NNM_4NNM_8NNM model execution was not successfull for 8 times \n"
            f"Actual success count: {enntest_output.count(NPU_SUCCESS_MSG)}",
        )
