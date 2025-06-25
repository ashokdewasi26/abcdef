# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Test reboot using nsg_control"""
import logging

from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import metadata
from si_test_idcevo.si_test_helpers.reboot_handlers import reboot_using_serial, wait_for_application_target

logger = logging.getLogger(__name__)


@metadata(
    testsuite=["SI", "SI-long", "IDCEVO-SP21"],
    domain="IDCEvo Test",
    testtype="Requirements-based test",
    traceability={""},
)
class TestRebootViaNSG(object):
    mtee_target = TargetShare().target

    def test_001_reboot_nsg_serial(self):
        """Check if target can be rebooted via nsg serially
        Steps:
         - Call nsg_control --requestRestart through SERIAL to reboot target
         - Close SSH connection during reboot
         - Restore SSH connection
         - Wait for application.target is active

         Expected result:
            All steps are successfully performed
        """
        reboot_using_serial(self.mtee_target)
        self.mtee_target.resume_after_reboot(skip_ready_checks=False)
        wait_for_application_target(self.mtee_target)

    def test_002_reboot_nsg_ssh(self):
        """Check if target can be rebooted via nsg by SSH
        Steps:
         - Call nsg_control --requestRestart through SSH to reboot target
         - Close SSH connection during reboot
         - Restore SSH connection
         - Wait for application.target is active

         Expected result:
            All steps are successfully performed
        """
        self.mtee_target.reboot(check_target=True)
