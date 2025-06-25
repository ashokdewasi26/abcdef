# Copyright (C) 2024. BMW CTW PT. All rights reserved.
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase


class TestAdbLogcat:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

    def test_adb_logcat(self):
        logcat_command = self.test.apinext_target.execute_adb_command(["logcat", "--max-count=1"])
        assert len(logcat_command.stdout) > 0, "The logcat command should produce output"
