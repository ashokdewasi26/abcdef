# pylint: disable=missing-docstring,invalid-name,protected-access,no-self-use

import os
import tempfile
from unittest import skip

from nose import SkipTest
from si_test_apinext.testing.test_base import TestBase


class TestAdbEssential:

    mtee_log_plugin = True

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

    @classmethod
    def teardown_class(cls):
        cls.test.quit_driver()

    def test_adb_shell(self):
        echo_command = self.test.apinext_target.execute_adb_command(["shell", "echo", "1"])
        assert echo_command.stdout.startswith(b"1"), "The shell echo command should output 1"

    def test_adb_logcat(self):

        logcat_command = self.test.apinext_target.execute_adb_command(["logcat", "--max-count=1"])
        assert len(logcat_command.stdout) > 0, "The logcat command should produce output"

    @skip("Skip this test to prevent subsequent tests from being blocked - ABPI-181386")
    def test_adb_root_unroot(self):

        uid = self.test.apinext_target.get_current_shell_user_id()
        if uid == 0:
            raise SkipTest("Skipping 'adb root' test as the adbd is already running as root")

        self.test.apinext_target.execute_adb_command("root")
        assert (
            self.test.apinext_target.get_current_shell_user_id() == 0
        ), "The adbd should run as root after adb root command"

        self.test.apinext_target.execute_adb_command("unroot")
        assert (
            self.test.apinext_target.get_current_shell_user_id() != 0
        ), "The adbd should run as non root after adb unroot command"

    @skip("Skip this test to prevent subsequent tests from being blocked - ABPI-181386")
    def test_push_pull(self):

        with tempfile.NamedTemporaryFile() as tf:
            need_unroot = False
            if self.test.apinext_target.get_current_shell_user_id() != 0:
                self.test.apinext_target.execute_adb_command("root")
                assert (
                    self.test.apinext_target.get_current_shell_user_id() == 0
                ), "The adbd should run as root after adb root command"
                need_unroot = True

            push_command = self.test.apinext_target.execute_adb_command(["push", tf.name, "/storage"])
            assert b"1 file pushed" in push_command.stdout, "The push command should copy file to target"

            file_name = "/storage/" + os.path.basename(tf.name)
            with tempfile.TemporaryDirectory() as td:
                pull_command = self.test.apinext_target.execute_adb_command(["pull", file_name, td])
                assert b"1 file pulled" in pull_command.stdout, "The pull command should retrieve file from target"

            if need_unroot:
                self.test.apinext_target.execute_adb_command("unroot")
                assert (
                    self.test.apinext_target.get_current_shell_user_id() != 0
                ), "The adbd should run as non root after adb unroot command"
