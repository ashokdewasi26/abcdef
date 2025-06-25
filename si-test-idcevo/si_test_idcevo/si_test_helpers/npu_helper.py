# Copyright (C) 2024. BMW CTW PT. All rights reserved.

import logging
import re

from mtee.testing.tools import (
    assert_false,
    assert_process_returncode,
)


logger = logging.getLogger(__name__)

ENN_SUCCESS_MSGS = ["Golden Matched", "TEST SUCCESS", "PASSED"]


def execute_model_with_enn_64(test_instance, model, input_data, golden_data, threshold=0, profile_summary=False):
    """
    Run EnnTest_64 executable with specified parameters
    :param model: .nnc file to use as model
    :param input_data: .bin file with input data
    :param golden_data: .bin file with golden data
    :param threshold: threshold for the execution
    :return stdout: output of EnnTest_64 execution
    """
    test_instance.mtee_target.execute_command("chmod +x EnnTest_64", cwd="/data/vendor/enn/")

    cmd = f"./EnnTest_64 --model {model} --input {input_data} --golden {golden_data} --threshold {threshold}"
    if profile_summary:
        cmd += " --profile SUMMARY"

    stdout, stderr, return_code = test_instance.mtee_target.execute_command(cmd, cwd="/data/vendor/enn/")

    assert_process_returncode(
        0, return_code, f"Failed to execute EnnTest_64 with the following command: {cmd}, Returned error: {stderr}"
    )
    return stdout


def validate_enn_output(enntest_output, expected_output_msgs):
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


def retrieve_fps_from_output(stdout):
    """
    Retrieve fps from EnnTest_64 output
    :param stdout: Output from EnnTest_64
    :type stdout: str
    :return fps: returns the fps from the output or False if failed to get fps
    """
    execution_perf_pattern = re.compile(r".*Execution Performance : \[ (.*?) \] fps.*")

    match = re.search(execution_perf_pattern, stdout)
    if match:
        fps = float(match.group(1))
    else:
        fps = False
        logger.debug(f"Failed to get fps from EnnTest_64 output: {stdout}")
    return fps


def execute_model_with_enn_and_get_fps(test_instance, model, input_data, golden_data, threshold, iter):
    """
    Execute enn_sample_external for npu inception models and get fps from output
    :param threshold: Threshold for the test
    :type threshold: float
    :param iter: Number of iterations
    :type iter: int
    :return fps: returns the fps from the output or False if failed to get fps
    """
    cmd = (
        f"./EnnTest_64 --model {model} --input {input_data} --golden {golden_data} --threshold {threshold}"
        f" --iter {iter}"
    )
    stdout, stderr, return_code = test_instance.mtee_target.execute_command(cmd, cwd="/data/vendor/enn/")

    assert_process_returncode(
        0, return_code, f"Failed to execute EnnTest_64 with the following command: {cmd}, Returned error: {stderr}"
    )

    return retrieve_fps_from_output(stdout)


def set_npu_exynos_properties(test_instance, mqos_set_level, scaling_max_freq, scaling_min_freq):
    """
    Set mqos_set_level and scaling_max_freq
    :param mqos_set_level: Set level for MQOS
    :type mqos_set_level: int
    :param scaling_max_freq: Maximum frequency for scaling
    :type scaling_max_freq: int
    """

    test_instance.mtee_target.execute_command(
        f"echo {mqos_set_level} > /sys/devices/platform/npu_exynos/mqos_set_level"
    )
    test_instance.mtee_target.execute_command(
        f"echo {scaling_max_freq} > /sys/devices/platform/npu_exynos/scaling_max_freq"
    )
    test_instance.mtee_target.execute_command(
        f"echo {scaling_min_freq} > /sys/devices/platform/npu_exynos/scaling_min_freq"
    )
    logger.info(f"Set mqos_set_level to {mqos_set_level} and scaling_max_freq to {scaling_max_freq}")


def execute_and_validate_large_network_model(test_instance, model_path):
    """
    Path creation, execution and validation of large network model
    :param str model_path: base path of folder where model files are present
    """
    large_network_nnc_path = f"{model_path}/large_network/large_network_O2_SingleCore.nnc"
    large_network_input_path = f"{model_path}/large_network/NPU_large_network_input_data.bin"
    large_network_golden_path = f"{model_path}/large_network/NPU_large_network_golden_data.bin"
    large_network_output = execute_model_with_enn_64(
        test_instance,
        large_network_nnc_path,
        large_network_input_path,
        large_network_golden_path,
        0.2,
    )
    validate_enn_output(large_network_output, ENN_SUCCESS_MSGS)


def execute_and_validate_gru_model(test_instance, model_path):
    """
    Path creation, execution and validation of gru model
    :param str model_path: base path of folder where model files are present
    """
    gru_nnc_path = f"{model_path}/GRU/GRU_O2_SingleCore.nnc"
    gru_input_path = f"{model_path}/GRU/NPU_GRU_input_data_0.bin {model_path}/GRU/NPU_GRU_input_data_1.bin"
    gru_golden_path = f"{model_path}/GRU/NPU_GRU_golden_data.bin"
    gru_output = execute_model_with_enn_64(test_instance, gru_nnc_path, gru_input_path, gru_golden_path, 0.2)
    validate_enn_output(gru_output, ENN_SUCCESS_MSGS)


def execute_and_validate_drowsiness_model(test_instance, model_path):
    """
    Path creation, execution and validation of drowsiness model
    :param str model_path: base path of folder where model files are present
    """
    drowsiness_nnc_path = f"{model_path}/drowsiness/drowsiness-2_O2_SingleCore.nnc"
    drowsiness_input_path = (
        f"{model_path}/drowsiness/NPU_drowsiness-2_input_data_0.bin "
        f"{model_path}/drowsiness/NPU_drowsiness-2_input_data_1.bin "
        f"{model_path}/drowsiness/NPU_drowsiness-2_input_data_2.bin"
    )
    drowsiness_golden_path = (
        f"{model_path}/drowsiness/NPU_drowsiness-2_golden_data_0.bin "
        f"{model_path}/drowsiness/NPU_drowsiness-2_golden_data_1.bin"
    )
    drowsiness_output = execute_model_with_enn_64(
        test_instance,
        drowsiness_nnc_path,
        drowsiness_input_path,
        drowsiness_golden_path,
        0.2,
    )
    validate_enn_output(drowsiness_output, ENN_SUCCESS_MSGS)


def execute_model_with_enntest_on_android(test_instance, model, input_data, golden_data, threshold_value=0.0):
    """
    Run EnnTest_v2_service with specified parameters
    :param model: .nnc file to use as a model
    :param input_data: .bin file with input data
    :param golden_data: .bin file with golden data
    :param threshold_value: threshold for the execution
    :return stdout: output of EnnTest_v2_service execution
    """
    cmd = f"EnnTest_v2_service --model {model} --input {input_data} --golden {golden_data}"
    if threshold_value > 0:
        cmd += f" --threshold {threshold_value}"
    enntest_output = test_instance.apinext_target.execute_command(cmd)
    logger.debug(f"Output of model - {enntest_output}")
    return enntest_output


def fetch_model_load_time(load_time_reg, exe_stdout):
    """
    Fetch model load time from enn load model test report

    :param regex load_time_reg: Regex to fetch model load time.
    :param str exe_stdout: enn test execution output
    :return str match_found: model load time value
    """
    match_found = None
    matches = load_time_reg.search(exe_stdout)
    if matches:
        match_found = matches.group(1)
        logger.info(f"Model upload time: '{match_found}'")
    return match_found


def extract_and_upload_model(test_context, tar_path, root_path, folder_path, folder_name):
    """
    Extracts a tar file and uploads the contents to the target device.

    :param tar_path: The path to the tar file to be extracted.
    :param str root_path: The name of the model path to be created.
    :param folder_path: The path to the folder containing the files to be uploaded.
    :param folder_name: The name of the folder to be created on the target device.
    """
    test_context.linux_helpers.extract_tar(tar_path)
    model_path = f"{root_path}/{folder_name}"
    if not test_context.test.mtee_target.isdir(model_path):
        test_context.test.mtee_target.mkdir(model_path, parents=True)
    test_context.test.mtee_target.upload(f"{folder_path}", model_path)
    test_context.test.mtee_target.chmod(model_path, 0o777, recursive=True)
    return model_path
