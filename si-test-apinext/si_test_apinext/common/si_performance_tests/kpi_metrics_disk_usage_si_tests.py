# Copyright (C) 2022 CTW PT. All rights reserved.
"""Test disk usage during idle"""
import logging

from mtee.testing.support.target_share import TargetShare
from mtee.testing.test_environment import require_environment, TEST_ENVIRONMENT

from si_test_apinext.util.system_stats import TargetSystemStats

target = TargetShare().target
logger = logging.getLogger(__name__)
system_stats = TargetSystemStats()


@require_environment(TEST_ENVIRONMENT.target.hardware)
class TestDiskUsagePerformance(object):
    @classmethod
    def setup_class(cls):
        """Setup class"""
        cls.target_type = target.options.target

    @classmethod
    def teardown_class(cls):
        """Teardown class"""
        pass

    def test_001_read_disk_usage(self):
        """Test used to read disk usage from target"""
        logger.debug("Execution of read disk usage test")
        system_stats.disk_usage_metric_collect_publish("disk_partitioning")
