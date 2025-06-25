# Copyright (C) 2025. CTW PT. All rights reserved.
"""Extract Custom DLT messages of interest"""
import os
from pathlib import Path

from dltlyse_plugins_gen22.plugins_gen22.dlt_messages_of_interest import DLTMsgInterestPlugin

configs_path = Path(__file__).parent.absolute()


class DLTMsgInterestPluginCustom(DLTMsgInterestPlugin):
    """Extract Messages of Interest for DLT log for custom use case

    **Output Files**
        - `dlt_msgs_interest_staging.csv`: Logs with all messages of interest
    """

    def __init__(self):
        resources_path = configs_path / "data/dlt_list_of_interest_staging.csv"
        if not os.path.exists(resources_path):
            traas_path = Path("/ws/repos/si-test-idcevo/si_test_idcevo/si_test_package_demo/dltlyse_plugins/data")
            resources_path = traas_path / "dlt_list_of_interest_staging.csv"
        super().__init__(
            list_of_interest_path=[resources_path],
            msgs_of_interest_file="dlt_msgs_interest_custom.csv",
            general_csv=True,
            fail_when_found=False,
        )
