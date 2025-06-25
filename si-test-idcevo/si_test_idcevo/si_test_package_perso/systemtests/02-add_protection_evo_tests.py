# Copyright (C) 2024-2025. BMW Group. All rights reserved.
import configparser
import logging
import time
from pathlib import Path

from mtee.metric import MetricLogger
from mtee.testing.connectors.connector_dlt import DLTContext

from mtee.testing.tools import assert_true, metadata
from si_test_idcevo.si_test_helpers import test_helpers as utils
from si_test_idcevo.si_test_helpers.android_helpers import ensure_launcher_page
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.apinext_target_handlers import LIST_MAIN_DISPLAY_ID
from si_test_idcevo.si_test_helpers.pages.idcevo.perso_page import PersoBMWIDPage as Perso
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)
metric_logger = MetricLogger()

DISPLAY_ID = LIST_MAIN_DISPLAY_ID["idcevo"]
ENABLED = True
DISABLED = False


class TestPersoAddKeyProtectionEvo:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(enable_appium=True)
        cls.test.apinext_target.wait_for_boot_completed_flag()
        wait_for_application_target(cls.test.mtee_target)

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    @classmethod
    def validate_key_fob_found(cls):
        logger.debug("validate_key_fob_found")
        keyfob_element = Perso.get_element(cls.test.driver, Perso.KEY_FOB_SEARCH_LABEL)
        if keyfob_element is None:
            return False
        else:
            return True

    @classmethod
    def validate_key_fob_linked(cls):
        logger.debug("validate_key_fob_found")
        keyfob_linked_element = Perso.get_element(cls.test.driver, Perso.KEY_FOB_LINKED_LABEL)
        if keyfob_linked_element is None:
            logger.debug("Failed to Link keyfob")
            return False
        else:
            logger.debug("Keyfob Linked with success")
            return True

    @classmethod
    def activate_key_protection(cls):
        logger.debug("activate_key_protection")
        time.sleep(2)
        is_keyfob_present = cls.validate_key_fob_found()
        if is_keyfob_present:
            cls.press_keyfob_element(cls.test, DISABLED)
        else:
            logger.debug("KeyFob was not FOUND!")
            # TODO: Validate if keyfob was already linked before
            cls.press_keyfob_element(cls.test, ENABLED)

    @classmethod
    def track_add_protection_kpi(cls, add_protection_filters, event):
        logger.debug("track_add_protection_kpi")
        with DLTContext(cls.test.mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as trace:
            try:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                time.sleep(2)
                cls.test.take_apinext_target_screenshot(
                    cls.test.results_dir, f"{timestamp}_trigger_kpi_tracking", DISPLAY_ID
                )

                logger.debug("Trigger event for KPIs")
                event()

                # Extract all patterns here
                list_of_expected_payloads = [
                    ({"payload_decoded": value["pattern"]}) for key, value in add_protection_filters.items()
                ]

                logger.debug("Filtering DLT logs for KPIs")
                dlt_msgs = trace.wait_for_multi_filters(
                    filters=list_of_expected_payloads,
                    drop=True,
                    count=0,
                    timeout=120,
                )
                if not dlt_msgs:
                    raise ValueError("Failed to collect DLT message")
                for msg in dlt_msgs:
                    logger.info(f"DLT logs found parsed message: {msg}")
                    for key, value in add_protection_filters.items():
                        match = value["pattern"].search(msg.payload_decoded)

                        if match:
                            logger.debug(f"Found Add protection log: {key}")
                            # Send collected KPI Metrics to Grafana
                            metric_logger.publish(
                                {
                                    "name": key,
                                    "kpi_name": value["metric"],
                                    "value": msg.payload_decoded,
                                }
                            )
            except Exception as error:
                error_msg = f"Appium session failed with '{error}'"
                logger.error(error_msg)

    @classmethod
    def press_keyfob_element(cls, test, is_enabled):
        logger.debug("Search icon_keyfob")
        icon_keyfob_element = Perso.get_element(test.driver, Perso.KEY_FOB_ICON)
        if icon_keyfob_element is None:
            logger.debug("Failed to get icon_keyfob")
        else:
            logger.debug("Search icon_keyfob success")
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            test.take_apinext_target_screenshot(test.results_dir, f"{timestamp}_before_click_keyfob", DISPLAY_ID)
            icon_keyfob_element.click()
            time.sleep(1)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            test.take_apinext_target_screenshot(test.results_dir, f"{timestamp}_after_click_keyfob", DISPLAY_ID)

            is_keyfob_linked = cls.validate_key_fob_linked()

            if is_enabled is False:
                logger.debug("Assert that toggle was just enabled")
                assert_true(is_keyfob_linked is ENABLED, "Failed to validate if Keyfob was just enabled")
            else:
                logger.debug("Assert that toggle was just disabled")
                assert_true(is_keyfob_linked is DISABLED, "Failed to validate if Keyfob was just disabled")

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-perso-traas"],
        component="None",
        domain="Performance",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "PERSO_ADD_KEYFOB"),
            },
        },
    )
    def test_001_user_key_rec(self):
        """
        001 - [SIT_Automated] Testing perso Key Recognition

        Steps:
            1. Open Perso app
            2. Wait for Foreground User Avatar to appear
            3. Click on Foreground User Avatar
            4. Check if Key Recognition tab is present
            5. Click on Key Recognition tab

        Expected outcome:
            1. All elements are available and accessible
            2. Fails if only Guest in the system
        """

        ensure_launcher_page(self.test)
        Perso.open_settings(self.test)
        Perso.open_key_rec_tab(self.test)

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-perso-traas"],
        component="None",
        domain="Performance",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "PERSO_ADD_KEYFOB"),
            },
        },
    )
    def test_002_keyfob_link(self):
        """
        002 - [SIT_Automated] Testing perso Key link when one keyfob found

        Steps:
            1. Open Perso app
            2. Click on "Active user"
            3. Click KeyRec tab
            4. Click on Keyfob Icon found
            5. Validate Keyfob is linked

        Expected outcome:
            We are able to link a keyfob
        """

        ensure_launcher_page(self.test)
        Perso.open_settings(self.test)
        Perso.open_key_rec_tab(self.test)
        # Track the DLT logs here for all layers
        self.track_add_protection_kpi(Perso.ADD_PROTECTION_DLT_KPI, lambda: self.activate_key_protection())
        self.validate_key_fob_linked()
