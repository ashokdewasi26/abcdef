# Copyright (C) 2024. BMW Car IT GmbH. All rights reserved.
"""
Helpers for RSU compatibility test
"""

import logging
import time

from mtee.testing.test_environment import require_environment, TEST_ENVIRONMENT as TE
from mtee.testing.tools import assert_process_returncode, TimeoutCondition
from tee.target_common import VehicleCondition
from tee.tools.diagnosis import DiagClient
from tee.tools.lifecycle import LifecycleFunctions

try:
    from validation_utils.utils import TimeoutError
except ModuleNotFoundError:
    from node0_ssh_client.tools import TimeoutError

logger = logging.getLogger(__name__)


@require_environment(TE.target.hardware.idc23)
class RSUHelper:
    def __init__(self, target):
        self.target = target
        self.diag_client = DiagClient(self.target.diagnostic_address, self.target.ecu_diagnostic_id)

    def clear_dtc_and_activate_container(self):
        """Clearing DTCs and starting node1 container"""
        self.diag_client.clear_dtc()
        self.diag_client.ecu_reset()
        self.target.reset_connector_dlt_state()
        self.target.wait_for_reboot()
        self.target.wait_for_nsm_fully_operational()
        logger.info("Activating node1 container in case container has changed...")
        command = ("setenforce", "0")
        result = self.target.execute_command(command)
        assert_process_returncode(0, result, f"Execution of command '{command}' failed")
        self.target.execute_command_container(container="node1", args=["lxc-attach", "node1"])

    def clear_coredumps(self):
        """Clearing coredumps folder and provisioning the testrack"""
        logger.info("Clearing coredumps")
        command = ("rm", "-rf", "/var/data/node0/health/coredumper/dumps/*")
        result = self.target.execute_command(command)
        assert_process_returncode(0, result, f"Execution of command '{command}' failed")
        self.diag_client.steuern_provisioning()
        time.sleep(5)

    def wait_for_target_to_sleep(self, timeout):
        """Wait for testrack to go to sleep after RSU.
        :param timeout: Max wait time to check if target is asleep
        """
        lf = LifecycleFunctions()
        timeout_condition = TimeoutCondition(timeout)
        try:
            while timeout_condition():
                if not lf.is_alive():
                    logger.info("Will wake up target now...")
                    self.target.set_vehicle_lifecycle_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
                    return
                time.sleep(1)
        except TimeoutError:
            logger.error("Target is still awake after %s seconds.", timeout)
