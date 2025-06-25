# Copyright (C) 2023. BMW CTW PT. All rights reserved.
import logging
import os
import tempfile

from unittest import skipIf
from mtee.testing.tools import metadata
from nose import SkipTest
from nose.tools import assert_equal

from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.test_helpers import skip_unsupported_ecus

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


@metadata(testsuite=["SI", "SI-android"])
class TestAdbEssential:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def test_adb_shell(self):
        echo_command = self.test.apinext_target.execute_command(["echo", "1"])
        assert echo_command.stdout.startswith(b"1"), "The shell echo command should output 1"

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

    @skipIf(skip_unsupported_ecus(["cde", "rse26"]), "This test isn't supported by this ECU!")
    def test_01_turn_on_bluetooth_via_adb_command(self):
        """
        Connects the bluetooth via adb command
        Note:
            The test when executed, performs the correct actions and returns the expected output.
            However, the correspondent UI component does not change, which indicates the test might be changing Android
            properties without changing BMW (the car) properties.As such, this test will need to be modified once the
            UI is in a more stable phase of development.
        """
        bluetooth_state = self.test.get_bluetooth_state_via_adb_command()
        if bluetooth_state == 0:
            self.test.turn_on_bluetooth_via_adb_commands()
            bluetooth_state = self.test.get_bluetooth_state_via_adb_command()
        assert_equal(bluetooth_state, 1, "Bluetooth is disable:{}".format(bluetooth_state))

    @skipIf(skip_unsupported_ecus(["cde", "rse26"]), "This test isn't supported by this ECU!")
    def test_02_turn_off_bluetooth_via_adb_commands(self):
        """
        Disconnects the bluetooth via adb command
        Note:
            The test when executed, performs the correct actions and returns the expected output.
            However, the correspondent UI component does not change, which indicates the test might be changing Android
            properties without changing BMW (the car) properties.As such, this test will need to be modified once the
            UI is in a more stable phase of development.
        """
        bluetooth_state = self.test.get_bluetooth_state_via_adb_command()
        if bluetooth_state != 0:
            self.test.turn_off_bluetooth_via_adb_commands()
            bluetooth_state = self.test.get_bluetooth_state_via_adb_command()
        assert_equal(bluetooth_state, 0, "Unable to disconnect Bluetooth:{}".format(bluetooth_state))

    @skipIf(skip_unsupported_ecus(["cde", "rse26"]), "This test isn't supported by this ECU!")
    def test_03_turn_on_wifi_via_adb_commands(self):
        """
        Connects the wifi via adb command
        Note:
            The test when executed, performs the correct actions and returns the expected output.
            However, the correspondent UI component does not change, which indicates the test might be changing Android
            properties without changing BMW (the car) properties.As such, this test will need to be modified once the
            UI is in a more stable phase of development.
        """
        wifi_state = self.test.get_wifi_state_via_adb_commands()
        if wifi_state == 0:
            self.test.turn_on_wifi_via_adb_commands()
            wifi_state = self.test.get_wifi_state_via_adb_commands()
        assert_equal(wifi_state, 1, "Wifi is disable:{}".format(wifi_state))

    @skipIf(skip_unsupported_ecus(["cde", "rse26"]), "This test isn't supported by this ECU!")
    def test_04_turn_off_wifi_via_adb_commands(self):
        """
        Disconnects the wifi via adb command
        Note:
            The test when executed, performs the correct actions and returns the expected output.
            However, the correspondent UI component does not change, which indicates the test might be changing Android
            properties without changing BMW (the car) properties.As such, this test will need to be modified once the
            UI is in a more stable phase of development.
        """
        wifi_state = self.test.get_wifi_state_via_adb_commands()
        if wifi_state != 0:
            self.test.turn_off_wifi_via_adb_commands()
            wifi_state = self.test.get_wifi_state_via_adb_commands()
        assert_equal(wifi_state, 0, "Unable to disconnect Wifi:{}".format(wifi_state))
