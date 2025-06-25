from si_test_apinext.util.monkey_utils import MonkeyRunnerTest, CreateMonkeyFile
from si_test_apinext.testing.test_base import TestBase
from si_test_apinext.testing.test_utils import setup_activity


class TestMonkey:

    mtee_log_plugin = True

    @classmethod
    def setup_class(cls):
        # TestBase is a singleton class to re-use appium driver and target vars
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def test_000_validate_monkey_packages(self):
        """Validate Packages which are being tested"""
        monkey_file = CreateMonkeyFile(test_target=self.test)
        list_errors = monkey_file.validate_packages()
        if any(list_errors):
            nr_monkey_interaction_per_package = 500
            monkey_file.write_to_file(nr_monkey_interaction_per_package)
            raise AssertionError(list_errors)

    @setup_activity
    def test_001_monkey_stress(self):
        """Monkey stress testing"""
        monkey_stress = MonkeyRunnerTest(test_target=self.test)
        monkey_stress.start_monkey_test()
