# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Multi coding tests"""
import configparser
import glob
import logging
import os
from pathlib import Path

from gen22_helpers.pdx_utils import PDXUtils
from mtee.testing.tools import metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.coding_helpers import install_coding_fa, pdx_setup_class
from si_test_idcevo.si_test_helpers.file_path_helpers import create_custom_results_dir
from si_test_idcevo.si_test_helpers.pdx_helpers import (
    pdx_teardown,
    perform_mirror_pdx_flash,
)
from si_test_idcevo.si_test_helpers.reboot_handlers import (
    wait_for_application_target,
)
from tee.target_common import VehicleCondition

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)


class TestMultiCoding:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        wait_for_application_target(cls.test.mtee_target)
        cls.target_name = cls.test.mtee_target.options.target
        cls.tal_filter = f"/resources/TAL_filter_{cls.target_name}.xml"
        cls.generation = "25"
        cls.pdx, cls.svk_all = pdx_setup_class(cls.test, cls.target_name)
        logistics_dir = cls.test.mtee_target.options.esys_data_dir
        cls.pdx_utils = PDXUtils(target_type="IDCEVO-25", ks_filter="IDCEVO", logistics_dir=logistics_dir)

    def perform_pdx_flash(self):
        """Perform PDX flash"""
        test_result_dir = create_custom_results_dir("multi_coding", self.test.mtee_target.options.result_dir)

        self.test.vcar_manager.send("ActivationWireExtDiag.informationExtDiag.statusActivationWireOBD=1")
        self.test.mtee_target.switch_vehicle_to_state(VehicleCondition.PRUEFEN_ANALYSE_DIAGNOSE)

        data = (
            test_result_dir,
            self.test.mtee_target.options.vin,
            self.generation,
            self.test.mtee_target.options.vehicle_order,
            self.test.mtee_target.options.target_type,
            self.pdx,
            self.svk_all,
            self.test.mtee_target.options.vehicle_type,
            self.tal_filter,
            self.test.mtee_target.options.target_ecu_uid,
        )
        perform_mirror_pdx_flash(*data)

    @metadata(
        testsuite=["SI-multi-coding-na"],
        component="tee_idcevo",
        domain="IDCEvo Test",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
    )
    def test_001_na_multicoding(self):
        """Multi coding NA

        Steps:
            1. Collect all coding features available
            2. Perform PDX flash
            3. Install all coding features

        Expected Outcome:
            1. Coding is successful for all files.
        """
        vehicle_orders = glob.glob(os.path.join(os.sep, "resources", "multi_coding", "NA", "*.xml"))
        logger.info("Found the following vehicle orders: %s", vehicle_orders)

        self.perform_pdx_flash()

        failed_coding_features = install_coding_fa(self.test, vehicle_orders)

        assert not failed_coding_features, (
            f"Failed to install coding features: {failed_coding_features}. ",
            "Please check logs for more information",
        )

        pdx_teardown(self.test, self.pdx_utils, "test_001_na_multicoding")

    @metadata(
        testsuite=["SI-multi-coding-g"],
        component="tee_idcevo",
        domain="IDCEvo Test",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
    )
    def test_002_g_multicoding(self):
        """Multi coding G line

        Steps:
            1. Collect all coding features available
            2. Perform PDX flash
            3. Install all coding features

        Expected Outcome:
            1. Coding is successful for all files.
        """
        vehicle_orders = glob.glob(os.path.join(os.sep, "resources", "multi_coding", "G", "*.xml"))
        logger.info("Found the following vehicle orders: %s", vehicle_orders)

        self.perform_pdx_flash()

        failed_coding_features = install_coding_fa(self.test, vehicle_orders)

        assert not failed_coding_features, (
            f"Failed to install coding features: {failed_coding_features}. ",
            "Please check logs for more information",
        )

        pdx_teardown(self.test, self.pdx_utils, "test_002_g_multicoding")

    @metadata(
        testsuite=["SI-multi-coding-sp21-u"],
        component="tee_idcevo",
        domain="IDCEvo Test",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
    )
    def test_003_sp21_u_multicoding(self):
        """Multi coding SP21 U line

        Steps:
            1. Collect all coding features available
            2. Perform PDX flash (Temporarly disabled, ticket IDCEVODEV-303361)
            3. Install all coding features

        Expected Outcome:
            1. Coding is successful for all files.
        """
        vehicle_orders = glob.glob(os.path.join(os.sep, "resources", "multi_coding", "SP21-U", "*.xml"))
        logger.info("Found the following vehicle orders: %s", vehicle_orders)

        failed_coding_features = install_coding_fa(self.test, vehicle_orders, enable_doip_protocol=False)

        assert not failed_coding_features, (
            f"Failed to install coding features: {failed_coding_features}. ",
            "Please check logs for more information",
        )

        pdx_teardown(self.test, self.pdx_utils, "test_003_u_multicoding")
