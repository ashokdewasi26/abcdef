# Copyright (C) 2023. BMW Car IT GmbH. All rights reserved.
"""PDX flashing Tests"""

import logging
import os
import sh
import time  # noqa: AZ100

from gen22_helpers.pdx_utils import PDXUtils
from mtee.metric import MetricLogger
from mtee.testing.tools import assert_equal, assert_true, metadata, run_command
from si_test_idcevo.si_test_helpers.android_helpers import wait_for_all_widgets_drawn
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.coding_helpers import pdx_setup_class
from si_test_idcevo.si_test_helpers.dmverity_helpers import disable_dm_verity
from si_test_idcevo.si_test_helpers.file_path_helpers import create_custom_results_dir
from si_test_idcevo.si_test_helpers.pdx_helpers import (
    check_missing_mandatory_swes_in_svk,
    generate_tal,
    perform_mirror_pdx_flash,
    retrieve_svk,
)
from si_test_idcevo.si_test_helpers.reboot_handlers import (
    wait_for_application_target,
)
from tee.target_common import VehicleCondition
from tee.tools.secure_modes import SecureECUMode
from tee.tools.sfa_utils import SFAHandler
from validation_utils.utils import TimeoutCondition

logger = logging.getLogger(__name__)
metric_logger = MetricLogger()

NUM_PDX_FLASH_ITERATIONS = 15


@metadata(
    testsuite=["PDX", "PDX-flash-everything", "PDX-stress", "IDCEVO-SP21"],
    duration="long",
    traceability={"SIT_DomainTests": {"JIRA": ["IDCEVODEV-12013"]}},
)
class TestGen25PDXflash:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        wait_for_application_target(cls.test.mtee_target)
        cls.target_name = cls.test.mtee_target.options.target
        hw_variant = cls.test.mtee_target.options.hardware_variant
        cls.tal_filter = f"/resources/TAL_filter_{cls.target_name}.xml"
        cls.pdx, cls.svk_all = pdx_setup_class(cls.test, cls.target_name)
        logistics_dir = cls.test.mtee_target.options.esys_data_dir
        cls.pdx_utils = PDXUtils(target_type="IDCEVO-25", ks_filter="IDCEVO", logistics_dir=logistics_dir)
        if "idcevo" in cls.target_name and "SP21" in hw_variant:
            cls.generation = "EES21"
        else:
            cls.generation = cls.test.generation

        # Set up pdx-required variables
        logger.info("Use SVT file %s", cls.svk_all)
        cls.sfa_handler_object = SFAHandler(cls.test.mtee_target)
        cls.vlan68_proxy_ip = "160.48.249.119"

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def get_uptime(self):
        """Get ECU uptime"""
        ret = self.test.mtee_target.execute_command("cat /proc/uptime", shell=True)
        return float(ret.stdout.split()[0])

    def wait_for_application_target(self, timeout=130):
        """Wait for application target to be active with timeout (defaults to 130s)"""
        timeout_condition = TimeoutCondition(timeout)
        while timeout_condition:
            if self.is_application_mode():
                logger.info(f"Target into application after {timeout_condition.time_elapsed}s")
                metric_logger.publish(
                    {
                        "name": "node0_target",
                        "kpi_name": "application_boot_time",
                        "value": self.get_uptime(),
                    }
                )
                return True
            time.sleep(3)

    def is_application_mode(self):
        return_stdout, _, return_code = self.test.mtee_target.execute_command(
            ["systemctl", "is-active", "application.target"]
        )
        return return_code == 0 and return_stdout == "active"

    def pdx_pre_setup(self):
        """Setup for PDX flash iteration

        :return bool: True in case all actions are performed
        """
        logger.info("Vcar: statusActivationWireOBD=1")
        self.test.vcar_manager.send("ActivationWireExtDiag.informationExtDiag.statusActivationWireOBD=1")
        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
        return True

    def pdx_teardown(self, current_iteration):
        """Teardown for PDX flash iteration

        :return bool: True in case all actions are performed
        """
        svk_response_processed = retrieve_svk(self.test, self.pdx_utils, "PDX")
        missing_swes = check_missing_mandatory_swes_in_svk(self.test, svk_response_processed)
        if missing_swes:
            logger.debug(
                f"PDX flash failed in iteration {current_iteration}. The following mandatory SWE(s) "
                f"are not included in the SVK response: {missing_swes}"
            )
            return False

        logger.debug(f"Activate engineering mode in iteration: {current_iteration}")
        secure_mode_object = SecureECUMode(self.test.mtee_target)
        secure_mode_object.switch_mode("ENGINEERING")
        self.test.mtee_target._connect_to_target()
        if self.test.mtee_target.vehicle_state != VehicleCondition.FAHREN:
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.FAHREN)
        try:
            wait_for_all_widgets_drawn(self.test)
            self.test.take_apinext_target_screenshot(
                results_dir=self.test.results_dir, file_name=f"After_pdx_mirror_flashing_{current_iteration}.png"
            )
        except (sh.ErrorReturnCode_255, sh.TimeoutException) as exception:
            logger.debug(
                f"Teardown screenshot failed on iteration {current_iteration}, adb not working..."
                + f"Recovering reboot. Error msg: '{exception}'"
            )
        return True

    @metadata(testsuite=["PDX-stress", "IDCEVO-SP21"])
    def test_001_pdx_stress_flash(self):
        """Test PDX Mirror flash 15 times in a row

        **Pre-conditions**
            Vehicle condition set to PAD

        **Required Steps**
            - Extract PDX tar, requires release PDX
            - Import PDX container
            - Create TAL for flashing using SVK all data
            - Execute TAL and flash PDX
            - Switch back to ENGINEERING mode

        **Expected outcome**
            - 15x PDX in a row are flashed successfully
        """

        failed_pdx_flash_iteration = []
        for i in range(NUM_PDX_FLASH_ITERATIONS):
            pre_setup_fail_msg = "pdx_pre_setup failed"
            teardown_fail_msg = "pdx_teardown failed"
            try:
                pre_setup_fail_msg = "" if self.pdx_pre_setup() else pre_setup_fail_msg
                test_result_dir = create_custom_results_dir(
                    f"pdx_stress_{i}", self.test.mtee_target.options.result_dir
                )
                data = (
                    test_result_dir,
                    self.test.mtee_target.options.vin,
                    self.generation,
                    self.test.mtee_target.options.vehicle_order,
                    "rse26" if "rse26" in self.target_name else self.test.mtee_target.options.target_type,
                    self.pdx,
                    self.svk_all,
                    self.test.mtee_target.options.vehicle_type,
                    self.tal_filter,
                    self.test.mtee_target.options.target_ecu_uid,
                )
                perform_mirror_pdx_flash(*data)

                if not self.pdx_teardown(current_iteration=i):
                    failed_pdx_flash_iteration.append(i)

            except Exception as e:
                logger.debug(
                    f"Failed PDX flash in iteration {i}\n Pre setup fail message: '{pre_setup_fail_msg}'\n"
                    f"Teardown fail message: '{teardown_fail_msg}'\nThrown exception: {e}"
                )
                failed_pdx_flash_iteration.append(i)

        assert_true(
            len(failed_pdx_flash_iteration) == 0,
            f"PDX flash failed iterations: {failed_pdx_flash_iteration}. "
            f"Check debug logs and pdx_stress folder in results for details.",
        )

    @metadata(testsuite=["SI"])
    def test_002_rsu_flash(self):
        """RSU test

        **Pre-conditions**
            - Have PDX container
            - RSU flasher tool installed

        **Steps**
            - Set Vehicle condition to PAD
            - Generate TAL file
            - Execute RSU flash
            - Execute coding with esys
            - Set Vehicle condition to FAHREN

        **Expected outcome**
            - RSU flashing successful
            - Coding successful
        """

        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)
        rsu_timeout = 3000

        # Generate TAL file
        generated_tal_dir = os.path.join(self.test.mtee_target.options.esys_data_dir, "Logs", "TAL_test_rsu_flash")

        tal_file_path = generate_tal(
            target=self.test.mtee_target,
            tal_filter_path=self.tal_filter,
            timeout=360,
            tal_log_dir=generated_tal_dir,
            pdx_path=self.pdx,
            svk_file_path=self.svk_all,
        )

        logger.debug("tal_file_path: {}".format(tal_file_path))

        try:
            rsu_flash_cmd = [
                "rsu-flasher",
                "--pdx-path",
                self.pdx,
                "--tal-file-path",
                tal_file_path,
                "--target-type",
                self.test.mtee_target.options.target,
                "--vin",
                self.test.mtee_target.options.vin,
                "--http-server-ip",
                self.vlan68_proxy_ip,
                "--log-level",
                "DEBUG",
                "--result-dir",
                self.test.mtee_target.options.result_dir,
            ]

            logger.info("rsu_flash_cmd: {}".format(rsu_flash_cmd))

            # Disable ssh connection
            self.test.mtee_target.prepare_for_reboot()

            stdout, stderr, returncode = run_command(rsu_flash_cmd, timeout=rsu_timeout)
            logger.info(f"RSU flash results:\nstdout:{stdout}\n{stderr}")
            assert_equal(0, returncode, "RSU flash failed. See logs for details.")

            # Check if dm-verity is enabled
            return_stdout, _, _ = self.test.mtee_target.execute_command("cat /proc/cmdline")
            if "root=/dev/dm-0" in return_stdout:
                disable_dm_verity()

            # Enable ssh connections
            self.test.mtee_target.ssh.wait_for_ssh(self.test.mtee_target.get_address(), timeout=60)
            self.test.mtee_target._recover_ssh(record_failure=False)
            wait_for_application_target(self.test.mtee_target)

            logger.info("Coding the target")
            self.test.mtee_target.install_coding(enable_doip_protocol=True)
        finally:
            self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.FAHREN)
