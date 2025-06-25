# Copyright (C) 2024. BMW CTW PT. All rights reserved.
import logging
import os
import re

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.support.target_share import TargetShare as TargetShareMTEE
from mtee_apinext.targets import TargetShare as TargetShareAPINEXT

from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class TestModule2Demo:
    @classmethod
    def setup_class(cls):
        cls.node0_target = TargetShareMTEE().target  # Instantiate the Node0 TargetShare class
        cls.apinext_target = TargetShareAPINEXT().target  # Instantiate the Android TargetShare class

        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

    def test_001_idcevo_os_information(self):
        """Check the OS information of the target"""
        return_stdout, _, _ = self.node0_target.execute_command("cat /etc/os-release")
        logger.info(f"OS-release Output: {return_stdout}")

    def test_002_validate_boot_kernel_complete(self):
        """Check if the target has booted completely"""

        dlt_filters = [
            {"apid": "SYS", "ctid": "JOUR", "payload_decoded": re.compile(r".*MARKER KPI - kernel_init Done.*")},
        ]
        with DLTContext(self.node0_target.connectors.dlt.broker, filters=[("SYS", "JOUR")]) as trace:
            self.node0_target.reboot(prefer_softreboot=False)
            dlt_msgs = trace.wait_for_multi_filters(
                filters=dlt_filters,
                drop=True,
                count=0,
                timeout=60,
            )
            for dlt_msg in dlt_msgs:
                logger.info(f"DLT Message: {dlt_msg.payload_decoded}")

    def test_003_android_boot_complete(self):
        """Check if the Android boot is complete"""

        self.test.apinext_target.wait_for_boot_completed_flag()
        file_name = os.path.join(self.test.results_dir, "screenshot_android.png")
        self.test.apinext_target.take_screenshot(file_name)
