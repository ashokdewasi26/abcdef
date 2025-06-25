import logging
import time
from unittest import skip
from unittest.case import SkipTest
from mtee.testing.test_environment import TEST_ENVIRONMENT

from mtee.testing.tools import metadata
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from si_test_apinext.mini.pages.connectivity_page import ConnectivityPage as Connect
from si_test_apinext.mini.pages.launcher_page import LauncherPage as Launcher
from si_test_apinext.mini.pages.media_page import MediaPage as Media
from si_test_apinext.mini.pages.navigation_page import NavigationPage as Navi
from si_test_apinext.mini.pages.perso_page import PersoPage as Perso
from si_test_apinext.testing.test_base import TestBase
import si_test_apinext.util.driver_utils as utils
from si_test_apinext.util.global_steps import GlobalSteps
from si_test_apinext.util.screenshot_utils import capture_screenshot

logger = logging.getLogger(__name__)


@metadata(testsuite=["SI"])
class TestUser:

    mtee_log_plugin = True
    create_using_appium = True
    user_name = "USER"
    user_id = None
    previous_user_name = None
    previous_user_id = None
    test = None

    @classmethod
    def setup_class(cls):

        # TestBase is a singleton class to re-use appium driver and target vars
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        if not cls.test.apinext_target:
            cls.test.setup_apinext_target()
        cls.connectivity_external = cls.test.apinext_target.check_internet_connectivity()

        cls.test.quit_driver()
        time.sleep(10)
        utils.remove_appium_apk(cls.test.apinext_target)
        time.sleep(20)

        cls.previous_user_id = cls.test.apinext_target.get_current_user_id()
        cls.previous_user_name = Perso.get_current_user_name()
        cls.user_id = cls.test.apinext_target.create_user(cls.user_name)
        cls.test.apinext_target.skip_user_setup_wizard(cls.user_id)
        cls.test.apinext_target.switch_user(cls.user_id)

        time.sleep(30)
        # Reset driver to start appium session with new user
        cls.test.setup_driver()
        time.sleep(10)
        Launcher.turn_on_bluetooth()

    @classmethod
    def teardown_class(cls):
        if Perso.check_user_present(cls.user_name):
            cls.test.apinext_target.switch_user(cls.previous_user_id)
            cls.test.apinext_target.delete_user(cls.user_id)

        cls.test.quit_driver()
        time.sleep(10)
        utils.remove_appium_apk(cls.test.apinext_target)
        time.sleep(30)

    def test_001_create_user(self):
        """
        Create new user

        *Background information*

        This test case verifies the following functionality of HLF IDC22PM-1156:
        * In this test case, it's created a new user using adb commands.

        Note:
        * It's used adb commands to add user, because appium tool do not allow install appium as service apk,
        this means if appium apk installed using Driver (Default user), the apk access will be restricted to Driver.
        * To mitigate this issue, it's created a new user, then installed appium tool to be accessible for all users.

        This test case verifies the following set of requirements:
        * ABPI-5660 (Create User on headunit and place a username)

        *Steps*
        1. Create new user
        2. Switch to user created
        3. Verify current user is the created user
        """
        Perso.start_activity()
        current_id = self.test.apinext_target.get_current_user_id()
        assert current_id == self.user_id, "Create user-Unexpected user_id : %s " % current_id

    @utils.gather_info_on_fail
    def test_002_new_user_press_launcher(self):
        """
        New user verify Launcher content

        *Background information*

        This test case verifies the following functionality of HLF IDC22PM-1156:
        * In this test case, it's verified the content on Launcher is available for new user.

        This test case verifies the following set of requirements:
        * ABPI-49116 (Open App with new user selected)

        *Steps*
        1. Verify new user is selected
        2. Validate that Main Menu Bar on BMW launcher has the following buttons for new user:
            - Menu (MENU)
            - Media (MEDIA)
            - Telephony (TEL)
            - Navigation (NAV)
        3. For each button:
            - Click button
            - Validate that opened button functionality
            - Go to Home
        """
        assert (
            self.test.apinext_target.get_current_user_id() == self.user_id
        ), "Unexpected user_id for test launcher content"

        Launcher.open_all_apps_search_from_home()
        Launcher.go_to_home()

        home_menu_button = self.test.driver.find_element(*Launcher.OVERLAY_HOME_BUTTON)
        GlobalSteps.click_button_and_expect_elem(self.test.wb, home_menu_button, Launcher.RECYCLER_APPS_ID, 2)
        capture_screenshot(test=self.test, test_name="open_menu")
        Launcher.go_to_home()

        media_button = self.test.driver.find_element(*Media.OVERLAY_MEDIA_BUTTON)
        GlobalSteps.click_button_and_expect_elem(self.test.wb, media_button, Media.get_media_element_id(), 2)
        capture_screenshot(test=self.test, test_name="open_media")
        Launcher.go_to_home()

        tel_button = self.test.driver.find_element(*Connect.OVERLAY_CONN_BUTTON)
        GlobalSteps.click_button_and_expect_elem(self.test.wb, tel_button, Connect.CONN_DISC_FRAG_ID, 2)
        capture_screenshot(test=self.test, test_name="open_tel")
        Launcher.go_to_home()

        if self.test.mtee_target.has_capability(TEST_ENVIRONMENT.test_bench.farm):
            logger.info("Navigation test case is skipped because it is not applicable on Mini Standalone Worker")
        else:
            nav_button = self.test.driver.find_element(*Navi.OVERLAY_NAV_BUTTON)
            nav_button.click()
            # Wait till the navigation app opens after clicking nav button
            time.sleep(5)
            capture_screenshot(test=self.test, test_name="open_nav")
            main_map = self.test.driver.find_elements(*Navi.NAV_MAIN_INFO_VIEW)
            assert main_map, "Failed to open navigation after clicking nav button"

    @utils.gather_info_on_fail
    def test_003_switch_previous_user(self):
        """
        Switch active user on headunit

        *Background information*

        This test case verifies the following functionality of HLF IDC22PM-1156:
        * In this test case, it's switch from created user to default user "Driver".

        This test case verifies the following set of requirements:
        * ABPI-5662 (Active user can be switched on headunit)

        *Steps*
        1. Click on "Switch  driver profile" button
        2. Wait for list users be displayed
        3. Click on previous user "Driver"
        4. Wait until textbox be displayed, which allow activate user selected
        5. Click on "Activate" button
        6. Wait until launcher be present
        7. Verify current user is previous user "Driver"
        """
        Perso.launch_switch_user_screen()
        self.test.wb.until(
            ec.visibility_of_element_located(Perso.LIST_PROFILES_ID), message="Unable to find List Users"
        )
        user = Perso.get_current_active_user()
        current_user = user.replace(" ", "")
        assert current_user == self.user_name, "Switch Back User-Unexpected user_id : %s" % current_user
        try:
            previous_user = self.test.driver.find_element(
                By.XPATH,
                "//*[@resource-id='com.bmwgroup.idnext.perso:id/standard_card_header']//*[@text='{}']".format(
                    "D R I V E R"
                ),
            )
        except NoSuchElementException:
            pre_user_name = " ".join(self.previous_user_name.upper())
            logger.info("Profile name element not found. Checking one more with name: %s", pre_user_name)
            previous_user = self.test.driver.find_element(
                By.XPATH,
                "//*[@resource-id='com.bmwgroup.idnext.perso:id/accountList']//*[@text='{}']".format(pre_user_name),
            )
        logger.info("Previous User : %s", previous_user)
        previous_user.click()
        self.test.wb.until(
            ec.visibility_of_element_located(Perso.ACTIVATE_NEW_PROFILE_ID),
            message="Unable to find Activate Button",
        )
        activate_button = self.test.driver.find_element(*Perso.ACTIVATE_NEW_PROFILE_ID)
        location = activate_button.location_in_view
        self.test.apinext_target.send_tap_event(location["x"], location["y"])
        if self.test.driver:
            # self.driver.stop_recording_screen() # Temporary in case of need to record a video
            self.test.driver.quit()
            self.test.driver = None
        time.sleep(10)
        utils.remove_appium_apk(self.test.apinext_target)
        time.sleep(20)

        self.test.setup_driver()
        Perso.launch_switch_user_screen()
        prev_user = Perso.get_current_active_user()
        assert prev_user == "D R I V E R", "We are not on Previous : %s" % prev_user

    @skip("Test is skipped due to provisioning funcionallity not fully working - see ABPI-94474")
    @utils.gather_info_on_fail
    def test_004_delete_created_user(self):
        """
        Delete user on headunit

        *Background information*

        This test case verifies the following functionality of HLF IDC22PM-1156:
        * In this test case, it's deleted created user on headunit.

        This test case verifies the following set of requirements:
        * ABPI-5661 (User can be deleted by customer on headunit)

        *Steps*
        1. Restart Perso Main activity
        2. Click on "Settings" button
        3. Wait for "Manage Profiles" be displayed
        4. Click on "Manage Profiles" button
        5. Wait for User created be displayed
        6. Click on "Remove" Button
        7. Wait until textbox be displayed, which allow accept removal
        8. Click on "Remove Now" button
        9. Verify user deleted is not present in available users
        """
        # self.driver.start_recording_screen() # Temporary in case of need to record a video

        if not self.connectivity_external:
            raise SkipTest("Skipping Delete user on headunit test because target is offline")

        Perso.start_activity()

        settings_button = self.test.wb.until(
            ec.element_to_be_clickable(Perso.SETTINGS_PROFILE_ID),
            message="Unable to find Settings Button after restart",
        )
        settings_button.click()

        self.test.wb.until(
            ec.visibility_of_element_located(Perso.MANAGE_PROFILES_ID),
            message="Unable to Manage Profiles Button",
        )
        manage_user = self.test.driver.find_element(
            By.XPATH, "//*[@resource-id='{}']//*[@text='Manage profiles']".format(Perso.MANAGE_PROFILES_ID.selector)
        )
        manage_user.click()
        self.test.wb.until(
            ec.visibility_of_element_located(Perso.PANEL_PROFILE_ID),
            message="Unable to find List Profiles",
        )
        panel_button = self.test.driver.find_element(
            By.XPATH,
            "//*[@resource-id='{}']//*[@text='{}']/..".format(Perso.PANEL_PROFILE_ID.selector, self.user_name),
        )
        remove_button = panel_button.find_element(*Perso.REMOVE_BUTTON_ID)
        remove_button.click()
        accept_remove_button = self.test.wb.until(ec.visibility_of_element_located(Perso.ACCEPT_REMOVE_BUTTON_ID))
        accept_remove_button.click()
        assert not Perso.check_user_present(self.user_name), "Delete user fails, user still present"

    @skip("Test is skipped due to provisioning funcionallity not fully working - see ABPI-114069")
    @utils.gather_info_on_fail
    def test_005_validate_offline_buttons(self):
        """
        Validate offline target has no backend connection

        *Background information*

        From HU22DM-11783, we learned that we should not be able to go to Setting in offline state (which is happening
        when testing in testfarm env)

        TEMPORARY behavior: Perso buttons are enabled, but after clicking on them we get
         a no backend connection message.
         To deal with the temporary behavior the test will pass if the button is not enabled, or
         if the button is enabled and there is a 'no backend connection message'

        This test case verifies the following set of requirements:
        * ABPI-5661

        *Steps*
        1. Restart Perso Main activity
        2. Validate target is offline
        3. Validate 'Add BMW ID' button is not enabled, or step 4.
        4. If 'Add BMW ID' button is enabled:
        5.      Validate offline target message is displayed
        """

        if self.connectivity_external:
            raise SkipTest("Skipping Validate offline buttons test because target is online")

        Perso.start_activity()

        button = self.test.driver.find_element(*Perso.ADD_BMW_ID)
        error_msg = []
        if not button.is_displayed():
            return True
        if button.get_attribute("enabled") != "true":
            error_msg.append(
                f"\tButton {Perso.ADD_BMW_ID.selector} is unexpectedly not enabled: {button.get_attribute('enabled')}"
            )
        if button.get_attribute("clickable") != "true":
            error_msg.append(
                f"\tButton {Perso.ADD_BMW_ID.selector} is unexpectedly not clickable: "
                + f"{button.get_attribute('clickable')}"
            )
        total_error_msg = "\n".join(error_msg)
        if total_error_msg:
            raise AssertionError(total_error_msg)

        explanation = GlobalSteps.click_button_and_expect_elem(self.test.wb, button, Perso.DIALOG_EXPLANATION_ID)

        assert explanation.text in [
            "No connection to BMW ConnectedDrive could be established. Please try again later.",
            "An error occurred whilst logging in. Please try again later.",
        ], f"Unexpected message: '{explanation.text}'"
