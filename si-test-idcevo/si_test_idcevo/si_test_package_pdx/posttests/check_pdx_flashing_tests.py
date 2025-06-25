# Copyright (C) 2024. CTW PT. All rights reserved.
"""Esys Execution Check post test"""
import glob
import logging
from pathlib import Path

from mtee.testing.tools import assert_equal, assert_not_equal, metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase

logger = logging.getLogger(__name__)


@metadata(testsuite=["BAT", "SI", "SI-long", "SI-long-idle", "SI-short", "PDX-stress", "IDCEVO-SP21"], domain="SWINT")
class EsysExecutionPostTest(object):
    """Esys Execution Post Tests"""

    __test__ = True

    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        cls.executed_tal_path = Path(cls.test.mtee_target.options.result_dir) / "*/ExecutedTAL"
        cls.matches = glob.glob(str(cls.executed_tal_path))

    def test_check_for_errors_on_esys_folder(self):
        """
        Test Intended to find failures on esys executions
        In some cases esys return code is 0, however flashing can not be succeded.
        """
        files_with_errors = []
        files_with_failures = []
        no_files_found = 0
        for path in self.matches:
            logger.info(f"Looking into {path}, defined as esys data dir")
            # Validate that Executed TAL files exist
            esys_files = glob.glob(f"{path}/**/*Finished*", recursive=True)
            if len(esys_files) == 0:
                no_files_found += 1
                logger.info(f"No executed TAL files were found, path {format(path)} must be wrong!")
                continue

            error_file_path = glob.glob(f"{path}/**/*Error*", recursive=True)
            if error_file_path:
                files_with_errors.append(error_file_path)
                logger.info(f"File found with errors: {error_file_path}")

            failure_file_path = glob.glob(f"{path}/**/*Fail*", recursive=True)
            if failure_file_path:
                files_with_failures.append(failure_file_path)
                logger.info(f"File found with failures: {failure_file_path}")

        assert_equal(len(files_with_errors), 0, "There is Execution with Errors on esys")
        assert_equal(len(files_with_failures), 0, "There is Execution with Failures on esys")
        assert_not_equal(no_files_found, len(self.matches), "No executed TAL files were found")
