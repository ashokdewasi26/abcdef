# Copyright (C) 2023. BMW CTW PT. All rights reserved.
import os
import tarfile

from mtee.testing.tools import assert_false, assert_true


class LinuxCommandsHandler(object):
    def __init__(self, target, logger):
        self.target = target
        self.logger = logger
        self.uname = "uname -a"
        self.vmStop = "echo 3 > /proc/nk/vmstop"
        self.vmStart = "echo 3 > /proc/nk/vmstart"

    def search_features_in_kernel_configuration(self, features_list: list) -> list:
        """
        Search for specific features in a kernel configuration file.
        The following linux command will be executed for each pattern:
        e.g: "zcat /proc/config.gz | grep -q <pattern>"

        :param features_list: features list to be search in kernel config file.
        :type features_list: list.
        :returns: empty list if all features are found, otherwise returns the list of
        features which were not found.
        :rtype: list of strings.
        """
        return_list = []

        self.logger.info(f"Checking list: {features_list}")
        for feature in features_list:
            return_stdout, _, return_code = self.target.execute_command(f'zcat /proc/config.gz | grep -q "{feature}"')
            self.logger.debug(f"return_stdout: {return_stdout} for pattern: {feature}")
            if return_code != 0:
                return_list.append(feature)

        return return_list

    def extract_tar(self, tar_full_path, subdir="/tmp"):
        """Find and extract tar ball into subdir

        :param tar_full_path: Full path to the tar ball
        :type tar_full_path: Path.
        :param subdir: Directory where to extract the tar ball (will be created if doesn't exists)
        :type tar_full_path: Path.
        """
        self.logger.info(f"Extracting {tar_full_path} to {subdir}")
        os.makedirs(subdir, exist_ok=True)
        with tarfile.open(name=tar_full_path) as tar_handler:
            tar_handler.extractall(subdir)

    def validate_output_android_console(self, result, expected_output_list):
        """
        Validate received response from apinext target
        :param ProcessResult result: Actual response from apinext Target
        :param list expected_output_list: Expected output string
        """
        for expected in expected_output_list:
            if expected not in result:
                return False
        return True

    def verify_switch_to_android(self):
        """
        Verifies whether serial console is switched successfully to android console
        """
        output = self.target.execute_console_command(self.uname).stdout
        is_switched = "android" in output.lower()
        return is_switched

    def verify_switch_to_node0(self):
        """
        Verifies whether serial console is switched successfully to node console
        """
        output = self.target.execute_console_command(self.uname).stdout
        is_switched = "linux" in output.lower()
        return is_switched

    def verify_standalone_start_ivi(self):
        """
        Trigger vmstart command and verify standalone start to IVI console
        """
        try:
            output = self.target.execute_command(self.vmStart)
            output = output.stdout if output.returncode == 0 else output.stderr
            self.logger.debug(f"Command executed on linux: {self.vmStart}, {output}")
            assert_true(self.verify_switch_to_node0(), "Not able to access android and node0 console after start IVI")
        except Exception as e:
            raise Exception(f"Failed to verify standalone stop of IVI. Error: {e}")

    def verify_standalone_stop_ivi(self):
        """
        Trigger vmstop command and verify standalone stop to IVI console
        """
        try:
            output = self.target.execute_command(self.vmStop)
            output = output.stdout if output.returncode == 0 else output.stderr
            self.logger.debug(f"Command executed on linux: {self.vmStop}, {output}")
            assert_false(self.verify_switch_to_android(), "Able to access android console which shouldn't happen.")
        except Exception as e:
            raise Exception(f"Unable to perform standalone stop of IVI. Got exception: {e}")
        finally:
            self.target.reboot()
