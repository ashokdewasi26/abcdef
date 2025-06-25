# Copyright (C) 2023. BMW Car IT GmbH. All rights reserved.
"""
The module tests PDX flashing use cases
"""
import glob
import logging
from pathlib import Path

from mtee.testing.support.target_share import TargetShare as TargetShareMTEE
from mtee.testing.tools import assert_process_returncode, assert_true, metadata, run_command
from mtee_idcevo.pre_test_validator import PreTestVerification
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from tee.const import SFA_FEATURE_IDS
from tee.target_common import VehicleCondition
from tee.tools.secure_modes import SecureECUMode
from tee.tools.sfa_utils import SFAHandler
from validation_utils.utils import TimeoutCondition

logger = logging.getLogger(__name__)
generation = "25"


@metadata(
    testsuite=["PDX", "PDX-flash-everything"],
    duration="long",
    traceability={"SIT_DomainTests": {"JIRA": ["IDCEVODEV-12013"]}},
)
class TestGen25PDX:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        # For idcevo, its value is "idcevo"; for rse26, its value is "rse26"
        target_type = cls.test.mtee_target.options.target
        # Set up pdx-required variablees
        cls.pdx = glob.glob(f"/images/pdx/{target_type.upper()}_*.pdx")[0]
        cls.svk_all = cls.test.mtee_target.pdx_svt_file
        logger.info("Use SVT file %s", cls.svk_all)
        cls.feature_id = SFA_FEATURE_IDS["SFA_INTERNAL_DEBUG_ACCESS_DLT_EXTERNAL_TRACING_ID"]
        cls.sfa_handler_object = SFAHandler(cls.test.mtee_target)

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def is_application_mode(self, timeout):
        command = ["systemctl", "is-active", "application.target"]
        timer = TimeoutCondition(timeout)
        while timer:
            return_stdout, _, return_code = self.test.mtee_target.execute_command(command)
            if return_code == 0 and return_stdout == "active":
                return True
        else:
            return False

    def setup(self):
        self.test.take_apinext_target_screenshot(
            results_dir=self.test.results_dir, file_name="Before_pdx_mirror_flashing.png"
        )
        logger.info("Vcar: statusActivationWireOBD=1")
        TargetShareMTEE().vcar_manager.send("ActivationWireExtDiag.informationExtDiag.statusActivationWireOBD=1")
        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)

    def teardown(self):
        logger.debug("Activate engineering mode")
        secure_mode_object = SecureECUMode(self.test.mtee_target)
        secure_mode_object.switch_mode("ENGINEERING")
        self.test.mtee_target._connect_to_target()
        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.FAHREN)
        logger.debug("Ensure already in application mode after pdx flashing")
        assert_true(self.is_application_mode(timeout=120), "Not in application mode after flashing")
        logger.debug("Enable adb after pdx flashing and validate adb is enabled")
        self.test.mtee_target.enable_adb()
        assert_true(PreTestVerification(self.test.mtee_target))
        self.test.take_apinext_target_screenshot(
            results_dir=self.test.results_dir, file_name="After_pdx_mirror_flashing.png"
        )

    def login_via_esys_certificates_check(self, cmd):
        """
        Adds E-sys certificate authentication for flashing
        param: cmd (str): Flashing command
        raises: AssertionError if certificates not found
        """
        cetificate = "/opt/esysdata/persistency_backup/Esys_NCD_key.p12"
        use_certificates = Path(cetificate).exists()
        if use_certificates:
            logger.info("Using certificate for Esys coding- %s", cetificate)
            cmd += [
                "--use-certificate",
                "--certificate",
                cetificate,
            ]
            return cmd
        else:
            raise AssertionError(f"No Certificate found for Esys coding at path:{cetificate}. Aborting the test.")

    @metadata(testsuite="PDX-flash-everything")
    def test_001_pdx_uds_flash(self):
        """Test PDX UDS flash

        **Pre-conditions**
            Vehicle condition set to PAD

        **Required Steps**
            - Extract PDX tar, requires release PDX
            - Import PDX container
            - Create TAL for flashing using SVK all data
            - Execute TAL and flash PDX
            - Switch back to ENGINEERING mode

        **Expected outcome**
            - PDX flashing successful
        """
        test_result_dir = Path(self.test.mtee_target.options.result_dir) / "test_001_pdx_uds_flash"
        test_result_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "pdx-flash",
            "--results",
            test_result_dir,
            "--context",
            "FullFlash",
            "--vin",
            self.test.mtee_target.options.vin,
            "--generation",
            generation,
            "--fa",
            self.test.mtee_target.options.vehicle_order,
            "--target-ecu",
            self.test.mtee_target.options.target_type,
            "--pdx",
            self.pdx,
            "--svk-soll",
            self.svk_all,
            "--vehicle-type",
            self.test.mtee_target.options.vehicle_type,
            "--tal-filter",
            "/resources/TAL_filter_idcevo.xml",
            "--no-begu-mc",
            "--direct-connection",
        ]
        cmd = self.login_via_esys_certificates_check(cmd)
        try:
            timeout = 3600
            logger.info("Waiting for full PDX flash to finish. Timeout: %s", timeout)
            result = run_command(cmd, timeout=timeout)
            logger.debug("Full PDX flash results: %s", result)
            assert_process_returncode(0, result, "PDX flash failed. See logs for details.")
            logger.info("Full PDX flash is finished.")
        finally:
            # remove PSDZdata folder from results
            result = run_command(["rm", "-rf", test_result_dir / "psdzdata"])
            logger.debug("Cleanup psdz data results: %s", result)

    @metadata(testsuite="PDX-flash-everything")
    def test_002_pdx_mirror_flash(self):
        """Test PDX Mirror flash

        **Pre-conditions**
            Vehicle condition set to PAD

        **Required Steps**
            - Extract PDX tar, requires release PDX
            - Import PDX container
            - Create TAL for flashing using SVK all data
            - Execute TAL and flash PDX
            - Switch back to ENGINEERING mode

        **Expected outcome**
            - PDX flashing successful
        """
        test_result_dir = Path(self.test.mtee_target.options.result_dir) / "test_002_pdx_mirror_flash"
        test_result_dir.mkdir(parents=True, exist_ok=True)
        target_ecu_uid = self.test.mtee_target.options.target_ecu_uid

        cmd = [
            "pdx-flash",
            "--results",
            test_result_dir,
            "--context",
            "FullFlashMirror",
            "--vin",
            self.test.mtee_target.options.vin,
            "--generation",
            generation,
            "--fa",
            self.test.mtee_target.options.vehicle_order,
            "--target-ecu",
            self.test.mtee_target.options.target_type,
            "--pdx",
            self.pdx,
            "--svk-soll",
            self.svk_all,
            "--vehicle-type",
            self.test.mtee_target.options.vehicle_type,
            "--tal-filter",
            "/resources/TAL_filter_idcevo.xml",
            "--no-begu-mc",
            "--direct-connection",
            "--use-mirror-protocol",
            "--auth-method-mirror-protocol",
            "SIGNED_TOKEN",
            "--target-ecu-uid",
            target_ecu_uid,
        ]
        cmd = self.login_via_esys_certificates_check(cmd)
        try:
            timeout = 3600
            logger.info("Waiting for full PDX flash to finish. Timeout: %s", timeout)
            result = run_command(cmd, timeout=timeout)
            logger.debug("Full PDX flash results: %s", result)
            assert_process_returncode(0, result, "PDX flash failed. See logs for details.")
            logger.info("Full PDX flash is finished.")
        finally:
            # remove PSDZdata folder from results
            result = run_command(["rm", "-rf", test_result_dir / "psdzdata"])
            logger.debug("Cleanup psdz data results: %s", result)
