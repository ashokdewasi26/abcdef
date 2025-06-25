# Copyright (C) 2025. BMW CTW PT. All rights reserved.
"""Spider tests - SomeIP connection check tests"""
import logging

from mtee.testing.tools import metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target


logger = logging.getLogger(__name__)

SOME_IP_OUTPUT_SIZE = 11


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
class TestSomeIPConnectionCheck(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(root=True)
        cls.test.apinext_target.wait_for_boot_completed_flag()
        wait_for_application_target(cls.test.mtee_target)

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    @metadata(test_case_id="ABPI-611787")
    def test_001_someip_connection_check(self):
        """
        [SIT_Automated] Verify that SOMEIP EnhancedTestabilityClient runs as expected

        - Pre-condition
            - vnet32_0 properly configured

        - Expected result
            - SOMEIP network works as expected
        """
        try:
            res = (
                self.test.apinext_target.execute_command(["EnhancedTestabilityClient"], privileged=True)
                .stdout.strip()
                .decode("utf-8")
            )
            logger.debug(f"Result:\n{res}")
            assert SOME_IP_OUTPUT_SIZE == len(res.split("\n")), "SomeIP wasn't able to communicate 10 packets"
            for i in range(1, SOME_IP_OUTPUT_SIZE):
                assert (
                    f"Received echoUINT8 with the responseValue: {i} (requestValue was {i})" in res
                ), f"Request {i} was not received"
        except Exception as err:
            raise RuntimeError(f"Something went wrong when executing command on IDCevo Android.\nError log: {err}")
