# Copyright (C) 2024. BMW CTW PT. All rights reserved.
import logging
import os
from unittest import skipIf

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE, require_environment
from mtee.testing.tools import assert_true, metadata
from si_test_idcevo.si_test_helpers.csv_handlers import CSVHandler
from si_test_idcevo.si_test_helpers.dlt_helpers import seek_android_dlt_msg_with_conditions

target = TargetShare().target
requirements = (TE.feature.DLT, TE.target.hardware)
logger = logging.getLogger(__name__)

APID_FILTER = "ALD"
CTID_FILTER = "LCAT"
PAYLOAD_FILTER = r".*"

LIFECYCLES_PATH = os.path.join("extracted_files", "Lifecycles")
INPUT_CSV_FILE = "dlt_msgs_of_interest.csv"


@require_environment(*requirements)
@metadata(testsuite=["SI", "SI-long", "SI-android"])
class AndroidVerificationPostTest(object):
    """Android Verification Post Tests"""

    __test__ = True

    @classmethod
    def setup_class(cls):
        if target:
            lifecyle_full_path = os.path.join(target.options.result_dir, LIFECYCLES_PATH)

            csv_handler = CSVHandler(INPUT_CSV_FILE)
            # gets list containing all csv files path
            cls.files_path = csv_handler.get_csv_files_path(lifecyle_full_path)
            assert_true(TE.feature.android, "Android partitions are not flashed.")

    @skipIf(not target, "Test requires target.")
    @skipIf(
        not (target.has_capability(TE.target.hardware.idcevo)),
        "Test not applicable for this ECU",
    )
    def test_001_verify_android(self):
        """Checks any android DLT messages present"""
        msg = [".*"]
        seek_android_dlt_msg_with_conditions("ALD", "LCAT", msg, self.files_path)
