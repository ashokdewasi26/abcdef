# Copyright (C) 2024. CTW PT. All rights reserved.
"""Input config file for DLT KPIs metric collection for CDE

    *All parameters are mandatory!*

    Each entry has a name and a set of parameters associated with it:

    - "pattern": The regex to search on the DLT payload

    - "type": We have two possibilities:
            * "regex_group" - Use regex.group to extract KPI from payload
            * "msg_tmsp" - Get DLT msg timestamp

    - "metric": This is the metric's output name, meaning,
                the name or ID of the metric to be presented on the output files like 'metrics.json'
                and Grafana list of available metrics named 'KPI name'
        We configure this name on MetricsOutputName class on the si-test-idcevo/si_test_idcevo/__init__.py file,
        please add there your entry first.
            i.e. # class MetricsOutputName:
                    NODE0_PID_1_TEST = "node0_pid1_kpi_msg_processed_time"

    - "apid": DLT APP_ID

    - "ctid": DLT CONTEXT_ID

    Note: Each KPI will be collected and outputted to 'METRICS_FILE_NAME' csv file.
    There is the possibility to match this to a requirement value on kpi_threshold_config.py,
    and validate that in a pass/fail way with a post test. For this, create a
    test on si_test_package_performance/posttests/match_generic_kpis_tests.py with the proper
    traceability metadata and the metric name.

    Further down is the documentation on the GENERIC_MULTI_MARKERS_KPI_CONFIG
"""
import re

from si_test_idcevo import MetricsOutputName

METRICS_FILE_NAME = "generic_dlt_kpis.csv"


GENERIC_DLT_KPI_CONFIG = {
    "Node0 PID 1 test": {
        "pattern": re.compile(r"(\d+.\d+[0-9])\skernel\: MARKER KPI - kernel_init Done"),
        "type": "regex_group",
        "metric": MetricsOutputName.NODE0_PID_1_TEST,
        "apid": "SYS",
        "ctid": "JOUR",
    },
    "Vsome IP routing ready test": {
        "pattern": re.compile(r"MARKER KPI NET4 SOME/IP Routing Ready"),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.VSOME_IP_ROUTING_READY_TEST,
        "apid": "VSIP",
        "ctid": "VSIP",
    },
    "Kernel start": {
        "pattern": re.compile(r"(\d+.\d+[0-9])\skernel\: MARKER KPI - start_kernel"),
        "type": "regex_group",
        "metric": MetricsOutputName.KERNEL_START,
        "apid": "SYS",
        "ctid": "JOUR",
    },
    "First UDP NM3 ": {
        "pattern": re.compile(r"First UDP NM3 message received"),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.FIRST_UDP_MESSAGE_RECEIVED,
        "apid": "UNM3",
        "ctid": "KPI",
    },
}

"""Input config file for DLT Multi Marker KPIs metric collection

    *All parameters are mandatory!*
    *All used KPI markers must be included in GENERIC_DLT_KPI_CONFIG dictionary!*

    Each GENERIC_MULTI_MARKERS_KPI_CONFIG entry must contain the following parameters:

    - "kpi_1": Name of the first KPI marker (must also exist in GENERIC_DLT_KPI_CONFIG dictionary)

    - "kpi_2": Name of the first KPI marker (must also exist in GENERIC_DLT_KPI_CONFIG dictionary)

    - "metric": Multi Marker KPI metric name"

    Since the metrics will use metric logger, it will be necessary to specify:
    - "key": "node0_pid1_kpi" (context of the metric)
    - "tag": "msg_processed_time" (specific name for each kpi)
    The kpi name at the end will be processed joining both.
    i.e. 'node0_pid1_kpi_msg_processed_time'

    The metric will calculate the time elapsed since kpi1 until kpi2 doing (kpi2 - kpi1)

    Note: Each KPI will be collected and outputted to 'METRICS_FILE_NAME' csv file.
    There is the possibility to match this to a requirement value on kpi_threshold_config.py,
    and validate that in a pass/fail way with a post test. For this, create a
    test on si_test_package_performance/posttests/match_generic_kpis_tests.py with the proper
    traceability metadata and the metric name.
"""
GENERIC_MULTI_MARKERS_KPI_CONFIG = {
    "Boot Node0 Kernel": {
        "kpi_1": "Kernel start",
        "kpi_2": "Node0 PID 1 test",
        "metric": MetricsOutputName.NODE0_KERNEL_BOOT_DURATION,
    },
}
