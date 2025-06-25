# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Generate metric extractors artifact"""
import configparser
import json
import logging
import os
from pathlib import Path

from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from si_test_idcevo import METRIC_EXTRACTOR_ARTIFACT_PATH
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target


config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")
logger = logging.getLogger(__name__)

# Extractors file path
METRIC_EXTRACTORS_DEFINITION_FILEPATH = Path(os.sep) / "resources" / "android_metric_extractors.json"
METRIC_EXTRACTORS_DEFINITION_FILEPATH_TRAAS = Path(
    "/ws/repos/si-test-idcevo/si_test_idcevo/si_test_data/android_metric_extractors.json"
)


class TestsMetricExtractor(object):
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class(skip_setup_apinext=True)
        wait_for_application_target(cls.test.mtee_target)

        if cls.test.mtee_target.has_capability(TE.test_bench.rack):
            cls.metric_extractor_config_path = METRIC_EXTRACTORS_DEFINITION_FILEPATH_TRAAS
        else:
            cls.metric_extractor_config_path = METRIC_EXTRACTORS_DEFINITION_FILEPATH

    def test_generate_metric_extractor(self):
        """[SIT_Automated] Generate test artifact containing metrics info
        Steps:
            - Run metric extractor tool to extract metric files, excluding the whitelisted.
        Expected Outcome:
            - Metric files are generated
        """
        # Debug fs was disabled for IDCevo so it will not be present.
        whitelist = ["node0 bootlog"]
        self.test.mtee_target.extract_metric_artifacts(
            extractors_definition_filepath=self.metric_extractor_config_path
        )
        metric_extractor_dir = Path(self.test.mtee_target.options.result_dir) / METRIC_EXTRACTOR_ARTIFACT_PATH
        assert metric_extractor_dir.exists(), "Metric artifacts directory was not generated!"
        with open(self.metric_extractor_config_path, "r") as file:
            json_content = file.read()
        metric_extractors_dict = json.loads(json_content)
        metric_extractors = [
            extractor for extractor in metric_extractors_dict["extractors"] if extractor["name"] not in whitelist
        ]
        expected_file_names = {extractor["output_file"] for extractor in metric_extractors}

        actual_file_names = {file.name for file in metric_extractor_dir.glob("*")}

        missing_files = expected_file_names - actual_file_names

        assert (
            not missing_files
        ), f"Failed to generate all the expected metric artifacts! Missing files: {', '.join(missing_files)}"
