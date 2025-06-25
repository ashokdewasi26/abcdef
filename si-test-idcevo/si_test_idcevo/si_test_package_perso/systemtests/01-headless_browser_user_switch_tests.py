# Copyright (C) 2025. CTW. All rights reserved.
import configparser
import logging
import os
import re
import time
from unittest import skip

from appium.webdriver.common.appiumby import AppiumBy
from mtee.metric import MetricLogger
from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.tools import metadata
from si_test_idcevo.si_test_helpers.android_helpers import ensure_launcher_page
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import Element
from si_test_idcevo.si_test_helpers.pages.idcevo.perso_page import PersoBMWIDPage as Perso
import si_test_idcevo.si_test_helpers.test_helpers as utils  # noqa: AZ100
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target
from si_test_idcevo.si_test_helpers.traas.traas_helpers import TRAASHelper

from pathlib import Path  # noqa: AZ100
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC  # noqa: AZ100 N812

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
metric_logger = MetricLogger()
logger = logging.getLogger(__name__)

QR_CODE_URL = Element(By.XPATH, "//*[contains(@content-desc, 'https')]")
# Use cases for perso tests to be displayed on reporting
# {"use_case": <None(test did not run), False(test failed), True(test pass)>}
USE_CASES = {
    "provisioning": None,
    "qr_code_generated": None,
    "redirect_with_qr_code": None,
    "login_with_valid_credentials": None,
    "redirect_to_user_account": None,
    "user_session_remains_active": None,
}


class TestPersoSwitchUser:
    @classmethod
    def setup_class(cls):
        cls.traas_helper = TRAASHelper()

        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(enable_appium=True, root=True)
        cls.test.apinext_target.wait_for_boot_completed_flag()
        wait_for_application_target(cls.test.mtee_target)

        cls.chrome_driver = None
        cls.username = "marcelo.lopes@ctw.bmwgroup.com"
        cls.password = "TRAAS_ctw_idcevo25"

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def validate_app_requirements(self):
        """Check requirements for the BMW ID app
        Steps:
            1 - Retrieve app version
            2 - Check provisioning on the IDCEVO and ICON
        """
        result = self.test.apinext_target.execute_adb_command(
            ["shell", "dumpsys", "package", Perso.PACKAGE_NAME, "|", "grep", "versionName"]
        )
        result_output = result.stdout.decode("utf-8")
        logger.info(f"BMW ID app version: {result_output}")
        with open(os.path.join(self.test.mtee_target.options.result_dir, "perso_app_version.txt"), "w") as f:
            f.write(result_output.strip())

        USE_CASES["provisioning"] = False
        if self.check_provisioning():
            logger.info("Rack provisioning is OK")
        else:
            logger.error("Rack provisioning is NOT OK... Triggering OTA provisioning")
            self.traas_helper.trigger_diag_job("icon", "31 01 A0 7A")
            time.sleep(30)
            self.test.mtee_target.reboot(prefer_softreboot=False)
            if not self.check_provisioning():
                logger.error("OTA provisioning failed")
                raise RuntimeError("OTA provisioning failed")
        USE_CASES["provisioning"] = True

    def check_provisioning(self):
        """Check provisioning on the IDCEVO and ICON"""
        # Check if the app is provisioned on the IDCEVO & ICON
        provisioning_file = "/var/data/telematics/pers/tel_provisioningd/provisioningd/data/provisioning-files"
        # Check ICON provisioning
        result_icon = self.traas_helper.execute_command_icon(
            f"ls {provisioning_file}",
        )
        logger.info(f"ICON provisioning result: {result_icon.stdout.decode('utf-8')}")
        # Check IDCEVO provisioning
        result_idcevo = self.test.mtee_target.execute_command(
            f"ls {provisioning_file}",
        )
        logger.info(f"IDCEVO provisioning result: {result_idcevo.stdout}")
        return bool(result_icon.returncode == 0 and result_idcevo.returncode == 0)

    def starting_perso_app(self):
        """Starts the BMWID app"""
        logger.info("Starting BMWID app")
        Perso.start_activity()
        time.sleep(2)
        dumpsys_activities = self.test.apinext_target.execute_command(["dumpsys activity activities"])
        if Perso.PACKAGE_NAME not in dumpsys_activities:
            self.test.apinext_target.execute_command("input keyevent 4")  # Could be overlay and need to go back
            time.sleep(2)
            Perso.start_activity()
            time.sleep(2)

    def click_add_profile_button(self):
        """Clicks on the add profile button"""
        logger.info("Adding new user profile")
        try:
            add_profile_button = self.test.driver.find_element(
                by=AppiumBy.ANDROID_UIAUTOMATOR, value='new UiSelector().resourceId("ItemAddProfileOnList")'
            )
            add_profile_button.click()
        except NoSuchElementException:
            self.test.take_apinext_target_screenshot(self.test.results_dir, "item_add_not_found")
            time.sleep(10)
            add_profile_button = self.test.driver.find_element(
                by=AppiumBy.ANDROID_UIAUTOMATOR, value='new UiSelector().resourceId("ItemAddProfileOnList")'
            )
            add_profile_button.click()
        logger.info("Add profile button clicked")
        time.sleep(4)

    def headless_browser_setup(self):
        """Setup for headless browser"""
        logger.info("Setting up headless browser")
        chrome_options = webdriver.ChromeOptions()
        chrome_options.binary_location = "/opt/google/chrome/chrome"  # Path to the Chromium binary
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--no-sandbox")  # Bypass OS security model
        chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
        chrome_options.add_argument("--incognito")

        self.chrome_driver = webdriver.Chrome(options=chrome_options)
        logger.info("Headless browser setup complete")

    def submit_bmw_credentials(self, qr_code_url):
        """Submit BMW credentials with headless browser"""
        logger.info("Submitting BMW credentials with headless browser")
        # Open the target website
        self.chrome_driver.get(f"{qr_code_url}")

        self.chrome_driver.save_screenshot(f"{self.test.results_dir}/bmw_login_page.png")

        # Wait for the username field to load, then input the credentials
        WebDriverWait(self.chrome_driver, 10).until(EC.visibility_of_element_located((By.ID, "email"))).send_keys(
            self.username
        )
        self.chrome_driver.save_screenshot(f"{self.test.results_dir}/email_entered.png")
        continue_button = self.chrome_driver.find_element(By.XPATH, '//button[text()="Continue"]')
        continue_button.click()

        WebDriverWait(self.chrome_driver, 10).until(EC.visibility_of_element_located((By.ID, "password"))).send_keys(
            self.password
        )
        self.chrome_driver.save_screenshot(f"{self.test.results_dir}/password_entered.png")
        logger.info("Credential going to be submitted")

        login_button = self.chrome_driver.find_element(By.XPATH, '//button[text()="Login"]')
        login_button.click()
        logger.info("BMW credentials submitted!")

    def retrieve_account_id(self):
        """Retrieve account ID from the DLT logs"""
        logger.info("Retrieving account ID from DLT logs")
        account_id = None
        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[("ALD", "LCAT")]) as trace:
            regex_pattern = re.compile(
                r".*DeviceSignOnStatus changed: {.status = SUCCESS, .accountId = \"(?P<account_id>\S*)\", .*",
            )
            dlt_filters = [
                {"apid": "ALD", "ctid": "LCAT", "payload_decoded": regex_pattern},
            ]
            dlt_msgs = trace.wait_for_multi_filters(
                filters=dlt_filters,
                drop=True,
                count=0,
                timeout=60,
            )
            if dlt_msgs:
                account_id = regex_pattern.search(dlt_msgs[0].payload_decoded).group("account_id")
                logger.info(f"Account ID found: {account_id}")
        return account_id

    def get_qr_code_url(self):
        """Extract URL from QR code"""
        logger.info("Extracting QR code URL")
        qr_code_element = self.test.driver.find_element(*QR_CODE_URL)
        qr_code_url = qr_code_element.get_attribute("content-desc")
        logger.info(f"QR code URL found: {qr_code_url}")
        return qr_code_url

    @utils.gather_info_on_fail
    @metadata(
        testsuite=["BAT", "SI", "SI-android", "SI-performance"],
        component="None",
        domain="Performance",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-84838",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "PERSO_USER_SWITCH"),
            },
        },
    )
    def test_001_add_new_user(self):
        """
        001 - [SIT_Automated] Add a new user using BMWID

        Steps:
            - Ensure we start from launcher page or the "Home page"
            - Open BMWID app
            - List current activities and check perso app is present
            - Find and click on plus sign (+) to add new user
            - Wait some time for pop up to load
            - Extract link from QR code
            - Close main appium session with IDCevo (since new user creation process could break it)
            - Open an instance of a headless browser (chromium)
            - Go to QR code link on the browser
            - Insert BMW account into the browser form
            - Wait for on boarding activity to appear

        Note:
            Screenshots are taking a long the way of the steps

        Expected outcome:
            - We are able to add a new user
            - Onboarding activity is found after new user created
        """
        ensure_launcher_page(self.test)

        self.validate_app_requirements()

        self.starting_perso_app()
        self.test.take_apinext_target_screenshot(self.test.results_dir, "perso_app_home")
        logger.info("BMW ID app started")

        self.click_add_profile_button()

        self.test.take_apinext_target_screenshot(self.test.results_dir, "qr_code_popup")

        # QR Code is Generated for User log in
        try:
            qr_code_url = self.get_qr_code_url()
            USE_CASES["qr_code_generated"] = True
        except Exception:
            USE_CASES["qr_code_generated"] = False
            raise AssertionError("Error generating QR code")

        # close appium because changing user will break the session
        self.test.teardown_appium()
        self.headless_browser_setup()

        account_id = None
        try:
            # When user scan QRCode, it's redirect to Login page on the user phone
            try:
                self.submit_bmw_credentials(qr_code_url)
                USE_CASES["redirect_with_qr_code"] = True
            except Exception:
                USE_CASES["redirect_with_qr_code"] = False
                raise Exception("Cannot submit credentials to BMW login page")
            # User can successfully log in with valid credentials
            try:
                account_id = self.retrieve_account_id()
                if not account_id:
                    raise
                USE_CASES["login_with_valid_credentials"] = True
            except Exception:
                USE_CASES["login_with_valid_credentials"] = False
                raise Exception("User login failed... Failed to get account id from DLT")
            self.test.take_apinext_target_screenshot(self.test.results_dir, "new_user")
        except Exception as e:
            raise AssertionError(e)
        finally:
            # Close the WebDriver
            time.sleep(3)  # Optional: view result for a few seconds before closing
            self.chrome_driver.quit()

        # Checking if onboard page was initiated
        dumpsys_activities = self.test.apinext_target.execute_command(
            ["dumpsys activity activities | grep -E 'ResumedActivity'"]
        )
        onboard_activity = "com.bmwgroup.idnext.perso/.app.ui.onboardingstart.view.OnboardingStartActivity"
        self.test.take_apinext_target_screenshot(self.test.results_dir, "onboard_activity")
        logger.info(f"List of activities: {dumpsys_activities}")
        # User is redirected to the Account where the user was logging in
        if onboard_activity in dumpsys_activities:
            USE_CASES["redirect_to_user_account"] = True
        else:
            USE_CASES["redirect_to_user_account"] = False
            raise AssertionError("BMW OnBoard page was not loaded")

        # Check if new user was created
        user_id, error_msg = Perso.check_user(self.test, account_id)
        if bool(user_id):
            USE_CASES["user_session_remains_active"] = True
        else:
            USE_CASES["user_session_remains_active"] = False
            raise AssertionError(error_msg)

    @skip("This test is only needed for sanity checks")
    def test_002_access_to_browser(self):
        """002 - Headless browser sanity check
        Steps:
            - Instance a new headless browser (chrome-linux)
            - Open URL to a practice-test-login
            - Insert user and password
            - Parse login message

        Expected Outcome:
            Login is successful
        """

        chrome_options = webdriver.ChromeOptions()
        chrome_options.binary_location = "/opt/google/chrome/chrome"  # Path to the Chromium binary
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--no-sandbox")  # Bypass OS security model
        chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
        chrome_options.add_argument("--incognito")

        # Define the login credentials
        username = "student"
        password = "Password123"

        driver = webdriver.Chrome(options=chrome_options)
        try:
            # Open the target website
            driver.get("https://practicetestautomation.com/practice-test-login/")
            driver.save_screenshot(f"{self.test.results_dir}/practice_screenshot.png")
            logger.info("URL fetch success")
            # Wait for the username field to load, then input the credentials
            WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "username"))).send_keys(username)
            WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "password"))).send_keys(password)
            logger.info("Credential going to be submitted")
            driver.save_screenshot(f"{self.test.results_dir}/credentials_screenshot.png")

            # Submit the form
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "submit"))).click()

            # Check if login was successful by looking for a confirmation element
            success_message = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//h1[contains(text(), 'Logged In Successfully')]"))
            )
            driver.save_screenshot(f"{self.test.results_dir}/submitted_screenshot.png")

            # If the element is found, logger.info confirmation
            if success_message:
                logger.info("Logged in successfully!")
            else:
                RuntimeError("Login failed.")

        except Exception as e:
            logger.info(f"An error occurred: {e}")
        finally:
            driver.quit()

    def test_003_provisioning(self):
        """003 - [PERSO_USE_CASE] Provisioning is enable"""
        utils.check_use_case(
            USE_CASES,
            "provisioning",
            "Provisioning is not enable. Please check 'Add a new user using BMWID' test for more details",
        )

    def test_004_qr_code_generated(self):
        """004 - [PERSO_USE_CASE] QR Code is Generated for User log in"""
        utils.check_use_case(
            USE_CASES,
            "qr_code_generated",
            "QR code was not generated. Please check 'Add a new user using BMWID' test for more details",
        )

    def test_005_redirect_with_qr_code(self):
        """005 - [PERSO_USE_CASE] When user scan QRCode, it's redirect to login page on the user phone"""
        utils.check_use_case(
            USE_CASES,
            "redirect_with_qr_code",
            "After scan the QR code, BMW login page was not loaded. "
            "Please check 'Add a new user using BMWID' test for more details",
        )

    def test_006_login_with_valid_credentials(self):
        """006 - [PERSO_USE_CASE] User can successfully log in with valid credentials"""
        utils.check_use_case(
            USE_CASES,
            "login_with_valid_credentials",
            "User log in failed. Please check 'Add a new user using BMWID' test for more details",
        )

    def test_007_redirect_to_user_account(self):
        """007 - [PERSO_USE_CASE] User is redirected to the Account where the user was logging in"""
        utils.check_use_case(
            USE_CASES,
            "redirect_to_user_account",
            "After login, user was not redirected to the account. "
            "Please check 'Add a new user using BMWID' test for more details",
        )

    def test_008_user_session_remains_active(self):
        """008 - [PERSO_USE_CASE] User session remains active as expected"""
        utils.check_use_case(
            USE_CASES,
            "user_session_remains_active",
            "User account does not remains active after login. "
            "Please check 'Add a new user using BMWID' test for more details",
        )
