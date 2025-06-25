import inspect
import json
import logging
import os
import re
import sh

from pathlib import Path  # noqa: AZ100
from Levenshtein import ratio
from mtee.testing.test_environment import TEST_ENVIRONMENT

from si_test_idcevo.si_test_helpers.android_helpers import ensure_launcher_page
from si_test_idcevo.si_test_helpers.apinext_target_handlers import IDCEvoApinextTargetHandler
from si_test_idcevo.si_test_helpers.appium_handler import IDCEvoAppiumHandler
from si_test_idcevo.si_test_helpers.dmverity_helpers import disable_dm_verity
from si_test_idcevo.si_test_helpers.file_path_helpers import get_calling_test
from si_test_idcevo.si_test_helpers.pages.idcevo.base_page import BasePage
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target

logger = logging.getLogger(__name__)

MINIMUM_RATIO_ACTIVITY = 0.8


class TestBase(IDCEvoApinextTargetHandler, IDCEvoAppiumHandler):
    """Test base singleton class

    This class is a singleton with multiple inheritance from IDCEvoApinextTargetHandler and IDCEvoAppiumHandler.
    The purpose of this class is to be reused by all IDC tests,
    to avoid having more than one apinext target and appium session handler.

    This class was meant to contain all the target instances required in test:
        - apinext target (aka android target)
        - mtee target (aka linux target)
        - vcar manager
        - diagnostic client
        - appium session
    """

    __instance__ = None

    def __init__(self) -> None:
        self.__apinext_target = None
        self.__results_dir = None
        self.__generation = None
        self.__build_branch = None
        self.vcar_manager = None
        self.activities_list = {}
        self.activities_file = ""
        self.rooted = False

    def __new__(cls):
        """Method to create singleton instance"""
        if not cls.__instance__:
            cls.__instance__ = super(TestBase, cls).__new__(cls)
        return cls.__instance__

    @staticmethod
    def get_instance():
        """Static method to fetch the current instance"""
        if not TestBase.__instance__:
            TestBase()
        return TestBase.__instance__

    @property
    def apinext_target(self):
        return self.__apinext_target

    @apinext_target.setter
    def apinext_target(self, value):
        self.__apinext_target = value
        BasePage.apinext_target = value

    @property
    def results_dir(self):
        return self.__results_dir

    @results_dir.setter
    def results_dir(self, value):
        self.__results_dir = value
        BasePage.results_dir = value

    @property
    def generation(self):
        return self.__generation

    @property
    def build_branch(self):
        return self.__build_branch

    def setup_base_class(self, root=False, enable_appium=False, disable_dmverity=False, skip_setup_apinext=False):
        if not self.apinext_target and not skip_setup_apinext:
            try:
                self.setup_apinext_target()
            except sh.TimeoutException:
                logger.error("Failed to setup apinext target. Adb device not available. Trying to recover...")
                if not self.mtee_target:
                    self.setup_target()
                self.mtee_target.reboot(prefer_softreboot=True)
                self.setup_apinext_target()
                wait_for_application_target(self.mtee_target)

        self.setup_vcar_manager()

        if not self.mtee_target:
            self.setup_target()
            self.mtee_target.reboot(prefer_softreboot=True)
            wait_for_application_target(self.mtee_target)

        if disable_dmverity:
            disable_dm_verity()

        if root and not self.rooted:
            self.apinext_target.root()
            self.rooted = True

        if enable_appium:
            self.setup_driver()

        # Get calling test name
        stack_inspect = inspect.stack()
        current_test_name = get_calling_test(stack_inspect)

        self.setup_results_dir(current_test_name)

        self.get_generation()

        self.get_build_branch()

        if self.apinext_target and not skip_setup_apinext:
            ensure_launcher_page(test=self)

            if not self.activities_list:
                self.set_activities_list()

    def teardown_base_class(self):
        if self.opened_session:
            self.teardown_appium()
        if self.rooted is True:
            try:
                self.apinext_target.wait_for_boot_completed_flag()
                self.apinext_target.unroot()
                self.rooted = False
            except Exception as err:
                logger.warning("Unroot failed: %s. Attempting recovery reboot and retrying unroot.", err)
                self.mtee_target.reboot(prefer_softreboot=True)
                wait_for_application_target(self.mtee_target)
                self.apinext_target.wait_for_boot_completed_flag()
                self.apinext_target.unroot()
                self.rooted = False

    def set_activities_list(self):
        """
        Launch monkey activity to collect all packages and activity with class android.intent.category.LAUNCHER

        Output:
            * List packages available on target
        """
        self.activities_file = os.path.join(
            self.mtee_target.options.result_dir, "extracted_files/android_activities.json"
        )
        monkey_file = self.apinext_target.execute_command(
            ["monkey", "-c android.intent.category.LAUNCHER --pct-syskeys 0 -v -v -v 0"]
        )
        pattern = re.compile(r"Using main activity\s(?P<activity>\S*).*from package\s(?P<package>[\w.]*)")
        monkey_lines = monkey_file.split("\n")
        for line in monkey_lines:
            match = pattern.search(line)
            if match:
                match_dict = match.groupdict()
                if "appium" not in match_dict.get("package"):
                    if match_dict.get("package") not in self.activities_list:
                        self.activities_list[match_dict.get("package")] = []
                    if match_dict.get("activity") not in self.activities_list[match_dict.get("package")]:
                        self.activities_list[match_dict.get("package")].append(match_dict.get("activity"))

        if self.activities_list:
            with open(Path(self.activities_file), "w") as outfile:
                json.dump(self.activities_list, outfile)

    def get_most_similar_activity(self, package_activity):
        """
        Get the most similar activity from the list of activities.
        Only accept the most similar activity if the ratio is greater than 0.8

        :param package_activity[str]: The package and activity to replace

        :return: The most similar activity
        """
        package_name = package_activity.split("/")[0]
        activity = package_activity.split("/")[1]

        most_similar_activity = ""
        max_ratio = 0

        if package_name in self.activities_list:
            similar_activities = self.activities_list[package_name]
            for similar_activity in similar_activities:
                ratio_activity = ratio(activity, similar_activity)
                logger.info(f"Ratio: {ratio_activity}, activity: {activity}, package: {package_name}")
                if ratio_activity > max_ratio and ratio_activity > MINIMUM_RATIO_ACTIVITY:
                    max_ratio = ratio_activity
                    most_similar_activity = similar_activity
                    logger.info(f"Most similar activity: '{most_similar_activity}' with a ratio of {max_ratio}")
        return most_similar_activity

    def get_generation(self):
        """
        Fetch the generation of the target and update generation property
        """
        generation = None
        if self.mtee_target.has_capability(TEST_ENVIRONMENT.service_pack.SP21):
            generation = "21"
        elif self.mtee_target.has_capability(TEST_ENVIRONMENT.service_pack.SP25):
            generation = "25"
        self.__generation = generation

    def get_build_branch(self):
        """
        Fetch the current build branch flashed on the target
        """
        build_branch = None
        command_output = self.mtee_target.execute_command("cat /etc/os-release")
        if 'VERSION="idcevo-mainline' in command_output.stdout:
            build_branch = "mainline"
        elif 'VERSION="idcevo-pu' in command_output.stdout:
            build_branch = "pu"
        elif "dirty" in command_output.stdout:
            build_branch = "dirty"
        self.__build_branch = build_branch
