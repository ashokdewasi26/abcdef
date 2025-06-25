# Copyright (C) 2025. CTW PT. All rights reserved.
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from unittest import skipIf

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from si_test_idcevo.si_test_helpers.dltlyse_utils import DltlyseCustomHandler, _collect_dltlyse_plugin_package_dirs

logger = logging.getLogger(__name__)


class DLTlysePluginPostTest(object):

    __test__ = True

    target = TargetShare().target

    @classmethod
    def setup_class(cls):
        cls.plugins_list = ["DLTMsgInterestPluginCustom"]
        cls.package_names = ["dltlyse_plugins_gen22"]
        cls.package_path = str(Path(Path(__file__).parent.absolute().parent, "dltlyse_plugins"))
        logger.info("Package path: %s", cls.package_path)

        cls.result_dir = cls.target.options.result_dir
        cls.dlt_trace_file = os.path.join(cls.result_dir, "idcevo_full_trace.dlt")
        cls.timeout = 60

    def create_temporary_copy(self, path, temp_name="idcevo.dlt"):
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, temp_name)
        shutil.copy2(path, temp_path)
        return [temp_path]

    @skipIf(not target.has_capability(TE.test_bench.rack), "Skip the test for rack")
    def test_001_custom_dltlyse_plugin(self):
        """Test custom DLTlyse plugin

        This test only allows to run dltlyse plugins like DLTMsgInterestPluginCustom
        """

        plugins_dirs = _collect_dltlyse_plugin_package_dirs(
            plugins_dirs=[self.package_path],
            package_names=self.package_names,
        )
        plugins_dirs.append(self.package_path)

        temp_dlt_trace_file = self.create_temporary_copy(self.dlt_trace_file)

        dltlyse_proc = DltlyseCustomHandler(
            plugins=self.plugins_list,
            plugins_dir=plugins_dirs,
            dlt_trace_file=temp_dlt_trace_file,
            work_dir=self.result_dir,
        )

        try:
            output_process = dltlyse_proc.start_dltlyse()
            if re.search("Errors found on lifecycle", output_process, re.IGNORECASE):
                raise AssertionError("Errors found, please check the dltlyse plugins for details")
        finally:
            dltlyse_proc.stop_dltlyse()
            return

    def test_002_check_wakeup_reason(self):
        """Check wakeup reason appears on CSV file generated in the previous test"""
        message_pattern = re.compile(r".*WAKEUP_REASON.*")
        csv_file = os.path.join(self.result_dir, "extracted_files/dlt_msgs_interest_custom.csv")
        logger.info("CSV file path: %s", csv_file)
        with open(csv_file, "r") as file:
            for line in file:
                if message_pattern.match(line):
                    return
        raise AssertionError("Wakeup reason not found in CSV file")
