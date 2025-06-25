from pathlib import Path

from si_test_apinext.testing.test_base import TestBase
from si_test_apinext.util.monkey_utils import CreateMonkeyFile, MonkeyRunnerTest


class TestMonkey:
    ref_files_dir = Path(Path(__file__).parent / "ref_files")
    mtee_log_plugin = True
    nr_monkey_interaction_per_package = 500

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()

    @classmethod
    def teardown_class(cls):
        cls.test.quit_driver()

    def test_001_monkey_stress(self):
        """Monkey stress testing with newly generated script"""
        monkey_file = CreateMonkeyFile(test_target=self.test, ref_files=self.ref_files_dir)
        monkey_file.write_to_file(self.nr_monkey_interaction_per_package)
        monkey_stress = MonkeyRunnerTest(test_target=self.test, ref_files=monkey_file.monkey_script_name)
        monkey_stress.start_monkey_test()
