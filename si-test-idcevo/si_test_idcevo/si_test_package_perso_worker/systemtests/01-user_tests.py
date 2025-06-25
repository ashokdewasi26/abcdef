# Copyright (C) 2024-2025. BMW Group. All rights reserved.
import configparser
import json
import logging
import time
from pathlib import Path
from unittest import skipIf

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT
from mtee.testing.tools import assert_true, metadata
from selenium.common.exceptions import NoSuchElementException

from si_test_idcevo.si_test_helpers import test_helpers as utils
from si_test_idcevo.si_test_helpers.android_helpers import ensure_launcher_page
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.apinext_target_handlers import LIST_MAIN_DISPLAY_ID
from si_test_idcevo.si_test_helpers.pages.idcevo.perso_page import PersoBMWIDPage as Perso
from si_test_idcevo.si_test_helpers.reboot_handlers import (
    reboot_and_wait_for_android_target,
    wait_for_application_target,
)
from validation_utils.utils import TimeoutCondition

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

target = TargetShare().target

# Get the vcar client
vcar = TargetShare().vcar_manager

DISPLAY_ID = LIST_MAIN_DISPLAY_ID["idcevo"]


@skipIf(
    target.has_capability(TEST_ENVIRONMENT.test_bench.rack),
    "Test class only applicable for standalone IDCevo",
)
class TestPersoSwitchUserEvo:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(enable_appium=False)

        # Setup the necessary simulation signals
        # Reboot to make sure values are used
        cls.send_vehicle_setup_signals()
        cls.send_profile_data()
        time.sleep(5)
        reboot_and_wait_for_android_target(cls.test)
        cls.test.setup_base_class(enable_appium=True, root=True)
        cls.test.apinext_target.wait_for_boot_completed_flag()
        wait_for_application_target(cls.test.mtee_target)
        time.sleep(30)

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    @classmethod
    def vcar_send(cls, payload):
        try:
            vcar.send(payload)
        except (RuntimeError, UnicodeDecodeError) as e:
            logger.info(f"Vcar error {e} sending {payload}")

    @classmethod
    def send_vehicle_setup_signals(cls):
        # From disabling emergency signals, valet mode
        # to potentially provisioning
        # quotes inside string must be escaped as in the example below:
        # vcar_command =
        # f"UserAccounts.accountsInfo.0 = \"Example\\\"Quoted\\\"String\""

        cls.vcar_send("DriverAttentionControlStatus.statusBreakRecommendation.recommendationStatus = 0")

        cls.vcar_send("AccountController.valetModeStatus.activated = 0")

        cls.vcar_send("AccountControllerBasic.valetModeStatus.activated = 0")

        # key fob setup:
        cls.vcar_send('DigitalKey.userguideURL = ""')
        # NFC_ONLY
        cls.vcar_send("DigitalKey.supportedDigitalKeyWirelessCapabilities = 0")
        # OP_TWO_KEY_FOBS
        cls.vcar_send("DigitalKey.ownerPairingAuthenticationMethod = 1")
        # INACTIVE_RESET
        cls.vcar_send("DigitalKey.digitalKeyFunctionState = 2")

    @classmethod
    def send_profile_data(cls):

        # Build getValues array here
        # givenName can be sent with:
        # status 5 - KEY_NOT_IN_SCHEMA
        # status 255 - SUCCESS
        cls.vcar_send("AccountDataProvider.getValues.status = 255")

        cls.vcar_send(
            'AccountDataProvider.getValues.data.0 = struct(0, 0, \
            char(0, 32, 1, 0, "perso/user/2/4/givenName"), \
            char(0, 32, 1, 0, "\\"Name1\\""), \
            unsigned(0, 32, 622185400))'
        )

        cls.vcar_send(
            'AccountDataProvider.getValues.data.1 = struct(0, 0, \
            char(0, 32, 1, 0, "locale/settings/1/0/language"), \
            char(0, 32, 1, 0, "4"), \
            unsigned(0, 32, 622185400))'
        )

        cls.vcar_send(
            'AccountDataProvider.getValues.data.2 = struct(0, 0, \
            char(0, 32, 1, 0, "locale/settings/1/0/unitDate"), \
            char(0, 32, 1, 0, "1"), \
            unsigned(0, 32, 622185400))'
        )

        cls.vcar_send(
            'AccountDataProvider.getValues.data.3 = struct(0, 0, \
            char(0, 32, 1, 0, "locale/settings/1/0/unitTime"), \
            char(0, 32, 1, 0, "2"), \
            unsigned(0, 32, 622185400))'
        )

        cls.vcar_send(
            "internal_AccountDataProvider.getValues.data = \
            array(0, 32, 0, 4, \
            AccountDataProvider.getValues.data.0, \
            AccountDataProvider.getValues.data.1, \
            AccountDataProvider.getValues.data.2, \
            AccountDataProvider.getValues.data.3)"
        )

        # This overrides the values above and sends empty array instead.
        # Delete this command to send the key values above
        cls.vcar_send(
            "internal_AccountDataProvider.getValues.data = \
            array(0, 32, 0, 0)"
        )

        # Create Account Info Dict
        account_info_0 = {
            "accessToken": "",
            "accountIdOnVehicle": "dummyid-0",
            "accountType": "LOCATION_DEFAULT",
            "piaProfileId": "PIA_PROFILE_GUEST",
            "pinnedLocations": [0],
            "username": "FIRST_ROW_DRIVER",
            "avatarType": 1,
            "mappingRoles": [],
        }

        account_info_1 = {
            "accessToken": "",
            "accountIdOnVehicle": "dummyid-1",
            "accountType": "LOCAL",
            "gcid": "",
            "piaProfileId": "PIA_PROFILE_1",
            "pinnedLocations": [],
            "username": "Local2",
            "avatarType": 1,
            "givenName": "name1",
            "mappingRoles": [2],
        }

        account_info_2 = {
            "accessToken": "",
            "accountIdOnVehicle": "dummyid-2",
            "accountType": "LOCATION_DEFAULT",
            "piaProfileId": "PIA_PROFILE_UNPERSONALIZED",
            "pinnedLocations": [2],
            "username": "FIRST_ROW_CODRIVER",
            "avatarType": 1,
            "givenName": "name2",
            "mappingRoles": [0],
        }

        account_info_3 = {
            "accessToken": "0123456789",
            "accountIdOnVehicle": "dummyid-3",
            "accountType": "CONNECTED",
            "gcid": "dummygcid-3",
            "piaProfileId": "PIA_PROFILE_2",
            "pinnedLocations": [],
            "username": "ctw123@bmwgroup.com",
            "avatarType": 1,
            "givenName": "name3",
            "mappingRoles": [0, 2],
            "mappingStatus": 40,
        }

        account_info_4 = {
            "accountIdOnVehicle": "dummyid-4",
            "accountType": "SHADOW",
            "gcid": "dummygcid-4",
            "piaProfileId": "PIA_PROFILE_4",
            "pinnedLocations": [],
            "username": "shadow5@bmwgroup.com",
            "avatarType": 1,
            "givenName": "name4",
            "shadowFirstName": "Robert",
            "shadowLastName": "Marley",
        }

        account_info_5 = {
            "accountIdOnVehicle": "dummyid-5",
            "accountType": "LOCATION_DEFAULT",
            "piaProfileId": "PIA_PROFILE_UNPERSONALIZED",
            "pinnedLocations": [1],
            "username": "FIRST_ROW_DRIVER",
        }

        account_info_6 = {
            "accountIdOnVehicle": "dummyid-6",
            "accountType": "LOCATION_DEFAULT",
            "piaProfileId": "PIA_PROFILE_UNPERSONALIZED",
            "pinnedLocations": [3],
            "username": "SECOND_ROW_DRIVER_SIDE",
        }

        account_info_7 = {
            "accountIdOnVehicle": "dummyid-7",
            "accountType": "LOCATION_DEFAULT",
            "piaProfileId": "PIA_PROFILE_UNPERSONALIZED",
            "pinnedLocations": [4],
            "username": "SECOND_ROW_MIDDLE",
        }

        account_info_8 = {
            "accountIdOnVehicle": "dummyid-8",
            "accountType": "LOCATION_DEFAULT",
            "piaProfileId": "PIA_PROFILE_UNPERSONALIZED",
            "pinnedLocations": [5],
            "username": "SECOND_ROW_CODRIVER_SIDE",
        }

        account_info_9 = {
            "accountIdOnVehicle": "dummyid-9",
            "accountType": "LOCATION_DEFAULT",
            "piaProfileId": "PIA_PROFILE_UNPERSONALIZED",
            "pinnedLocations": [6],
            "username": "THIRD_ROW_DRIVER_SIDE",
        }

        account_info_10 = {
            "accountIdOnVehicle": "dummyid-10",
            "accountType": "LOCATION_DEFAULT",
            "piaProfileId": "PIA_PROFILE_UNPERSONALIZED",
            "pinnedLocations": [7],
            "username": "THIRD_ROW_MIDDLE",
        }

        account_info_11 = {
            "accountIdOnVehicle": "dummyid-11",
            "accountType": "LOCATION_DEFAULT",
            "piaProfileId": "PIA_PROFILE_UNPERSONALIZED",
            "pinnedLocations": [8],
            "username": "THIRD_ROW_CODRIVER_SIDE",
        }

        account_info_12 = {
            "accessToken": "",
            "accountIdOnVehicle": "dummyid-12",
            "accountType": "LOCAL",
            "gcid": "",
            "piaProfileId": "PIA_PROFILE_0",
            "pinnedLocations": [],
            "username": "uname12",
            "givenName": "name12",
            "avatarType": 1,
            "mappingRoles": [2],
        }

        account_info_13 = {
            "accessToken": "9876543210",
            "accountIdOnVehicle": "dummyid-13",
            "accountType": "CONNECTED",
            "gcid": "dummygcid-13",
            "piaProfileId": "PIA_PROFILE_3",
            "pinnedLocations": [],
            "username": "ctw456@bmwgroup.com",
            "givenName": "name13",
            "mappingRoles": [2],
            "avatarType": 1,
            "mappingStatus": 0,
        }

        # Convert dictionaries to JSON strings
        # Escape double quotes by adding a backslash
        account_str_0 = json.dumps(account_info_0).replace('"', '\\"')
        account_str_1 = json.dumps(account_info_1).replace('"', '\\"')
        account_str_2 = json.dumps(account_info_2).replace('"', '\\"')
        account_str_3 = json.dumps(account_info_3).replace('"', '\\"')
        account_str_4 = json.dumps(account_info_4).replace('"', '\\"')
        account_str_5 = json.dumps(account_info_5).replace('"', '\\"')
        account_str_6 = json.dumps(account_info_6).replace('"', '\\"')
        account_str_7 = json.dumps(account_info_7).replace('"', '\\"')
        account_str_8 = json.dumps(account_info_8).replace('"', '\\"')
        account_str_9 = json.dumps(account_info_9).replace('"', '\\"')
        account_str_10 = json.dumps(account_info_10).replace('"', '\\"')
        account_str_11 = json.dumps(account_info_11).replace('"', '\\"')
        account_str_12 = json.dumps(account_info_12).replace('"', '\\"')
        account_str_13 = json.dumps(account_info_13).replace('"', '\\"')

        # The right way below, after vcar config is changed to have more
        # array positions:
        """
        vcar_command = f"UserAccounts.accountsInfo.1 = \"{account_str_1}\""
        vcar.send(vcar_command)

        vcar_command = f"UserAccounts.accountsInfo.2 = \"{account_str_2}\""
        vcar.send(vcar_command)

        vcar_command = f"UserAccounts.accountsInfo.3 = \"{account_str_3}\""
        vcar.send(vcar_command)

        vcar_command = f"UserAccounts.accountsInfo.4 = \"{account_str_4}\""
        vcar.send(vcar_command)
        """
        # For now, override intermediate variables and use directly the final
        # signal vcar python complaints on the response format, so it needs to
        # be inside try/except, when building the payload manually
        cls.vcar_send(
            f'internal_UserAccounts.accountsInfo = \
            array(0, 32, 0, 14, \
            char(0, 32, 1, 0, "{account_str_0}"), \
            char(0, 32, 1, 0, "{account_str_1}"), \
            char(0, 32, 1, 0, "{account_str_2}"), \
            char(0, 32, 1, 0, "{account_str_3}"), \
            char(0, 32, 1, 0, "{account_str_4}"), \
            char(0, 32, 1, 0, "{account_str_5}"), \
            char(0, 32, 1, 0, "{account_str_6}"), \
            char(0, 32, 1, 0, "{account_str_7}"), \
            char(0, 32, 1, 0, "{account_str_8}"), \
            char(0, 32, 1, 0, "{account_str_9}"), \
            char(0, 32, 1, 0, "{account_str_10}"), \
            char(0, 32, 1, 0, "{account_str_11}"), \
            char(0, 32, 1, 0, "{account_str_12}"), \
            char(0, 32, 1, 0, "{account_str_13}"))'
        )

        time.sleep(1)

        # For now, override intermediate variables and use directly the final
        # signal:
        cls.vcar_send(
            'internal_AccountController.availableAccounts = \
            array(0, 32, 0, 14, \
            char(0, 0, 1, 40, "dummyid-0"), \
            char(0, 0, 1, 40, "dummyid-1"), \
            char(0, 0, 1, 40, "dummyid-2"), \
            char(0, 0, 1, 40, "dummyid-3"), \
            char(0, 0, 1, 40, "dummyid-4"), \
            char(0, 0, 1, 40, "dummyid-5"), \
            char(0, 0, 1, 40, "dummyid-6"), \
            char(0, 0, 1, 40, "dummyid-7"), \
            char(0, 0, 1, 40, "dummyid-8"), \
            char(0, 0, 1, 40, "dummyid-9"), \
            char(0, 0, 1, 40, "dummyid-10"), \
            char(0, 0, 1, 40, "dummyid-11"), \
            char(0, 0, 1, 40, "dummyid-12"), \
            char(0, 0, 1, 40, "dummyid-13"))'
        )

        # To activate dummyid-1 account:
        time.sleep(1)
        cls.vcar_send('AccountController.sessions.0.accountId = "dummyid-1"')

        cls.vcar_send("AccountController.sessions.0.accountSessionStatus = 1")

        cls.vcar_send("AccountController.sessions.0.accountType = 10")

        cls.vcar_send('AccountController.sessions.0.gcid = ""')

        cls.vcar_send("AccountController.sessions.0.locationId = 0")

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["SI-android"],
        component="None",
        domain="Personalization",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "PERSO_USER_SWITCH"),
            },
        },
    )
    def test_001_add_user(self):
        """
        [SIT_Automated] Check user creation button

        Steps:
            1. Open Perso app
            2. Wait for Add Profile button to appear
            3. Click on Add Profile button

        Expected outcome:
            1. Add Profile button is available and accessible
        """

        ensure_launcher_page(self.test)
        Perso.start_activity()
        time.sleep(2)
        self.test.take_apinext_target_screenshot(self.test.results_dir, "001_perso_app", DISPLAY_ID)

        timeout_condition = TimeoutCondition(10)
        while timeout_condition:
            add_user_element = Perso.get_element(self.test.driver, Perso.ADD_PROFILE_BTN)
            if add_user_element is not None:
                break
            time.sleep(1)
        assert_true(add_user_element is not None, "Failed to get add_user_element")

        try:
            add_user_element.click()
            time.sleep(2)
            self.test.take_apinext_target_screenshot(self.test.results_dir, "001_add_user_element_click", DISPLAY_ID)
        except NoSuchElementException:
            logger.debug("add_user_element not found")
