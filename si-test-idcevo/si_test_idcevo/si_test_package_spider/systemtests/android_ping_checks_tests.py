# Copyright (C) 2025. BMW CTW PT. All rights reserved.
"""Spider tests - Android ping check tests"""
import logging

from mtee.testing.tools import metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target


logger = logging.getLogger(__name__)


@metadata(
    testsuite=["SI-spider-traas"],
    domain="Telematics",
    asil="None",
    duration="short",
    testtype="Requirement-based testing",
    testsetup="SW-Integration",
    categorization="functional",
    priority="1",
    traceability={
        "idcevo": {"SUBFEATURE": []},
    },
)
class TestAndroidPingChecks(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(root=True)
        cls.test.apinext_target.wait_for_boot_completed_flag()
        wait_for_application_target(cls.test.mtee_target)

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def test_001_android_ping_google(self):
        """
        [SIT_Automated] Android ping to google

        Steps:
            - Execute ping from idcevo android to google

        Expected outcome:
            - Successful ping to google
        """
        try:
            self.test.apinext_target.execute_command(
                ["ping", "-I", "eth0.77", "-c", "4", "-W", "1", "8.8.8.8"], privileged=True
            )
        except Exception as err:
            raise RuntimeError(f"Ping from IDCevo Android to google failed.\nError log: {err}")
