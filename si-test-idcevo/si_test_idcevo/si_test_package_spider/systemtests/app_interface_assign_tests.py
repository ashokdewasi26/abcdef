# Copyright (C) 2025. BMW CTW PT. All rights reserved.
"""Spider tests - FlexCon app-interface mapping tests"""
import logging
import time
from pathlib import Path
from unittest import skip

from mtee.testing.tools import SkipTest, assert_true, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.linux_commands_handlers import LinuxCommandsHandler
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target


logger = logging.getLogger(__name__)

BMW_APPSTORE_PACKAGE = "com.bmwgroup.apinext.appstore"

SPIDER_WEB_SERVICE = "com.bmwgroup.apinext.spiderwebservices.data.service.SpiderWebService"

SPIDER_WEB_SERVICE_APKS = [
    "spiderwebservices-vlan77-debug.apk",
    "spiderwebservices-vlan80-debug.apk",
    "spiderwebservices-vlan87-debug.apk",
    "spiderwebservices-vlan97-debug.apk",
    "spiderwebservices-vlan107-debug.apk",
]

TELEMATICS_NETWORKS = [
    "eth0.77",
    "eth0.80",
    "eth0.87",
    "eth0.97",
    "eth0.107",
]

TEST_SET = {
    "vlan77": {"apk": SPIDER_WEB_SERVICE_APKS[0], "interface": TELEMATICS_NETWORKS[0]},
    "vlan80": {"apk": SPIDER_WEB_SERVICE_APKS[1], "interface": TELEMATICS_NETWORKS[1]},
    "vlan87": {"apk": SPIDER_WEB_SERVICE_APKS[2], "interface": TELEMATICS_NETWORKS[2]},
    "vlan97": {"apk": SPIDER_WEB_SERVICE_APKS[3], "interface": TELEMATICS_NETWORKS[3]},
    "vlan107": {"apk": SPIDER_WEB_SERVICE_APKS[4], "interface": TELEMATICS_NETWORKS[4]},
}

APKS_PATH = Path("/ws/repos/si-test-idcevo/si_test_idcevo/si_test_data/spider_flexcon_app.tar.gz")


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
class TestFlexConInterfaceMapping(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(root=True)
        cls.linux_helpers = LinuxCommandsHandler(cls.test.mtee_target, logger)
        cls.test.apinext_target.wait_for_boot_completed_flag()
        wait_for_application_target(cls.test.mtee_target)

        # install required apk's for the test
        try:
            # extract apks
            cls.linux_helpers.extract_tar(APKS_PATH)

            cls.current_ecu = cls.test.mtee_target.options.target.lower()
            if "idcevo" not in cls.current_ecu:
                raise RuntimeError(f"Not IDCEvo: was {cls.current_ecu}")
            # Install all services via ADB
            for apk_file in SPIDER_WEB_SERVICE_APKS:
                apk_path = Path("/tmp", apk_file).resolve()
                cls.test.apinext_target.install_apk(apk_path, install_flags=["-i", BMW_APPSTORE_PACKAGE, "-r"])
            # This delay is to sure that the TelematicsService executed and included all the installed APKs correctly
            time.sleep(5)
        except Exception as err:
            raise SkipTest(f"Something went wrong while setting up APKs for test cases. Skipping...\n{err}")

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def dumpsys(self, package_name, arg):
        """Use dumpsys to output information about service"""
        result = self.test.apinext_target.execute_command(
            f"dumpsys activity service {package_name} {arg}"
        ).stdout.decode("utf-8")
        # Remove first 2 lines and return
        # Dumpsys always returns 2 extra lines before the actual content
        return result.split("\n", 2)[2]

    def start_service(self, package_name, service):
        """Start foreground service"""
        result = self.test.apinext_target.execute_command(
            f"am start-foreground-service {package_name}/{service}", privileged=True
        ).stdout.decode("utf-8")
        time.sleep(5)
        if "Error" in result:
            raise Exception(f"{result} when trying to start service.")

    def fail_message(self, test_set_vlan):
        """Returns the failed message for a giving interface"""
        return f"Fail in assign {TEST_SET[test_set_vlan]['interface']} to {TEST_SET[test_set_vlan]['apk']}"

    def do_evaluate_app_interface_mapping(self, interface_name, apk_file):
        """Evaluate mapping of a given interface"""
        apk_path = Path("/tmp", apk_file).resolve()
        package_name = self.test.apinext_target.get_pkg_name_from_apk(apk_path)
        logger.debug(f"Validating {package_name} to {interface_name} mapping")

        self.start_service(package_name, SPIDER_WEB_SERVICE)

        current_interface_result = self.dumpsys(package_name, "getCurrentInterface")
        logger.debug("Current_interface_result: " + current_interface_result)
        if interface_name not in current_interface_result:
            logger.debug(f"{current_interface_result} does not match expected result: {interface_name}")
            return False

        return True

    def test_001_validate_eth0_77_mapping(self):
        """[SIT_Automated] Validate vlan77 mapping"""
        test_set_vlan = "vlan77"
        assert_true(
            self.do_evaluate_app_interface_mapping(
                TEST_SET[test_set_vlan]["interface"], TEST_SET[test_set_vlan]["apk"]
            ),
            self.fail_message(test_set_vlan),
        )

    def test_002_validate_eth0_80_mapping(self):
        """[SIT_Automated] Validate vlan80 mapping"""
        test_set_vlan = "vlan80"
        assert_true(
            self.do_evaluate_app_interface_mapping(
                TEST_SET[test_set_vlan]["interface"], TEST_SET[test_set_vlan]["apk"]
            ),
            self.fail_message(test_set_vlan),
        )

    @skip("This test checks ICON WIFI connectivity. Currently CTW TRAAS racks doesn't have that implemented.")
    def test_003_validate_eth0_87_mapping(self):
        """[SIT_Automated] Validate vlan87 mapping"""
        test_set_vlan = "vlan87"
        assert_true(
            self.do_evaluate_app_interface_mapping(
                TEST_SET[test_set_vlan]["interface"], TEST_SET[test_set_vlan]["apk"]
            ),
            self.fail_message(test_set_vlan),
        )

    def test_004_validate_eth0_97_mapping(self):
        """[SIT_Automated] Validate vlan97 mapping"""
        test_set_vlan = "vlan97"
        assert_true(
            self.do_evaluate_app_interface_mapping(
                TEST_SET[test_set_vlan]["interface"], TEST_SET[test_set_vlan]["apk"]
            ),
            self.fail_message(test_set_vlan),
        )

    def test_005_validate_eth0_107_mapping(self):
        """[SIT_Automated] Validate vlan107 mapping"""
        test_set_vlan = "vlan107"
        assert_true(
            self.do_evaluate_app_interface_mapping(
                TEST_SET[test_set_vlan]["interface"], TEST_SET[test_set_vlan]["apk"]
            ),
            self.fail_message(test_set_vlan),
        )
