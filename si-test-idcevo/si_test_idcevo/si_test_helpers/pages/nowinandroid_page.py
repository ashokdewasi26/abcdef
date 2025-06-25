import os
import tarfile
import time

from pathlib import Path
from selenium.webdriver.common.by import By

import si_test_idcevo.si_test_helpers.test_helpers as utils

from si_test_idcevo.si_test_helpers.dmverity_helpers import run_command_on_host
from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage, Element


class NowInAndroidPage(BasePage):
    COMMON_NAME = "NowInAndroid"
    PACKAGE_NAME = "com.google.samples.apps.nowinandroid.demo"
    PACKAGE_ACTIVITY = "com.google.samples.apps.nowinandroid.MainActivity"
    INSTALL_FILES_PATH = Path(os.sep) / "resources" / "nowinandroid_config_files.tar.gz"
    EXTRACTED_FILES_PATH = Path(os.sep) / "tmp" / "NowInAndroid"

    SWIPE_BOTTOM_TO_TOP = 'input swipe "1720" "1000" "1720" "500" "500"'
    SWIPE_TOP_TO_BOTTOM = 'input swipe "1720" "500" "1720" "1000" "500"'

    RESET_GFX_STATS = f"dumpsys gfxinfo {PACKAGE_NAME} reset"
    READ_GFX_STATS = f"dumpsys gfxinfo {PACKAGE_NAME}"

    DONE_ID = Element(By.XPATH, "//*[contains(@text,'Done')]")
    PREFERENCE_IDS = {
        Element(By.XPATH, "//*[contains(@text,'Performance')]"),
        Element(By.XPATH, "//*[contains(@text,'UI')]"),
        Element(By.XPATH, "//*[contains(@text,'Compose')]"),
    }

    @classmethod
    def perform_scroll(cls, direction, count):
        """
        Perform 'count' number of scrolls in the given direction:
        - 'up' scrolls up to reveal content above the current page.
        - 'down' scrolls down to reveal content below the current page.

        Waits 3 seconds between scrolls.
        """

        if direction == "up":
            cmd = cls.SWIPE_TOP_TO_BOTTOM
        elif direction == "down":
            cmd = cls.SWIPE_BOTTOM_TO_TOP
        else:
            raise ValueError("Invalid direction for scrolling. Use 'up' or 'down'.")

        for _ in range(count):
            cls.start_activity(cmd=cmd)
            time.sleep(3)

    @classmethod
    def open_app(cls, test):
        """Open the NowInAndroid application."""
        cls.start_activity()
        time.sleep(15)
        test.take_apinext_target_screenshot(test.results_dir, "app_opened_for_benchmark")

    @classmethod
    def click_preferences_and_close_prompt(cls, test):
        """Click on topic preferences and close the prompt."""
        try:
            for preference in cls.PREFERENCE_IDS:
                element = cls.check_visibility_of_element(preference, web_driver_timeout=10)
                element.click()
            utils.get_screenshot_and_dump(test, test.results_dir, "all_preferences_selected")
            cls.click(cls.DONE_ID)
        except Exception as e:
            raise RuntimeError(f"Error while choosing NIA topic preferences: {e}")

    @classmethod
    def execute_performance_benchmark(cls, test):
        """Execute the performance benchmark on the NowInAndroid app and save GFX statistics

        Steps:
        1. Sleep for 3 seconds for stability
        2. Reset GFX statistics
        3. Perform two down scrolls
        4. Perform two up scrolls
        5. Return GFX statistics
        """
        time.sleep(3)
        test.apinext_target.execute_command(cls.RESET_GFX_STATS)
        cls.perform_scroll(direction="down", count=2)
        cls.perform_scroll(direction="up", count=2)
        return str(test.apinext_target.execute_command(cls.READ_GFX_STATS))

    @classmethod
    def install_apk_and_upload_data(cls, test):
        """Install the NowInAndroid APK and upload the test data to the target

        Steps:
        1. Root the target
        2. Extract the tar data and install the APK in android
        3. Clear the app data to ensure a clean state
        4. Find the user and group owner of the app data
        5. Give the app permission to post notifications
        6. Start the app for the first time to generate initial app data
        7. Force stop the app
        8. Upload the test data to the target and change the owner of the data
        9. Unroot the target
        """
        run_command_on_host(["adb", "root"])

        os.makedirs(cls.EXTRACTED_FILES_PATH, exist_ok=True)
        with tarfile.open(name=cls.INSTALL_FILES_PATH) as tar_handler:
            tar_handler.extractall(cls.EXTRACTED_FILES_PATH)
        test.apinext_target.install_apk("/tmp/NowInAndroid/NowInAndroid.apk")

        test.apinext_target.execute_command(f"pm clear {cls.PACKAGE_NAME}")

        user_id = str(test.apinext_target.execute_command("am get-current-user")).strip()
        appdata_path = f"/data/user/{user_id}/com.google.samples.apps.nowinandroid.demo"
        user_group_cmd = f"ls -l {appdata_path} | grep code_cache"
        output = test.apinext_target.execute_command(user_group_cmd)
        user = output.split()[2]
        group = output.split()[3]

        grant_command = f"pm grant --user {user_id} {cls.PACKAGE_NAME} android.permission.POST_NOTIFICATIONS"
        test.apinext_target.execute_command(grant_command)

        cls.start_activity()
        test.take_apinext_target_screenshot(test.results_dir, "first_app_start")
        time.sleep(5)
        test.force_stop_package(["com.google.samples.apps.nowinandroid.demo"])
        time.sleep(3)

        for subdir in Path("/tmp/NowInAndroid").iterdir():
            if subdir.is_dir():
                test.apinext_target.push_as_current_user(subdir, appdata_path)
                test.apinext_target.execute_command("sync")
                test.apinext_target.execute_command(f"chown -R {user}:{group} {appdata_path}/{subdir.name}")

        run_command_on_host(["adb", "unroot"])
