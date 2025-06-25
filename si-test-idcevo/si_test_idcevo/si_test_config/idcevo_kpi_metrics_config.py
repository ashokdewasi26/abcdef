# Copyright (C) 2023. CTW PT. All rights reserved.
"""Input config file for DLT KPIs metric collection for IDCEVO

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

DEFAULT_MULTIPLE_REBOOTS = "25"


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
    "Early Cluster Initialized": {
        "pattern": re.compile(r"MARKER Early-cluster application is initialized."),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.EARLY_CLUSTER_INIT,
        "apid": "EARL",
        "ctid": "KPI",
    },
    "Early Cluster First Image": {
        "pattern": re.compile(r"MARKER First image shown."),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.EARLY_CLUSTER_FIRST_IMAGE,
        "apid": "EARL",
        "ctid": "KPI",
    },
    "Early Cluster Full Content": {
        "pattern": re.compile(r"MARKER Full content shown."),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.EARLY_CLUSTER_FULL_CONTENT,
        "apid": "EARL",
        "ctid": "KPI",
    },
    "Full Cluster Available": {
        "pattern": re.compile(r"Cluster-App-Ready!"),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.FULL_CLUSTER_AVAILABLE,
        "apid": "ALD",
        "ctid": "LCAT",
    },
    "Deadreckoning Position calculated after cold boot": {
        "pattern": re.compile(r"MARKER KPI Positioning component has been started from cold boot"),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.DEADRECKONING_POS_CALC_AFTER_COLD_BOOT,
        "apid": "NAVD",
        "ctid": "KPI#",
    },
    "Interior light available": {
        "pattern": re.compile(r"MARKER KPI IL1 interior light available"),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.INTERIOR_LIGHT_AVAILABLE,
        "apid": "LGHT",
        "ctid": "LTID",
    },
    "Interior light caf loaded": {
        "pattern": re.compile(r"MARKER KPI IL2 interior light caf loaded"),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.INTERIOR_LIGHT_CAF_LOADED,
        "apid": "LGHT",
        "ctid": "LTML",
    },
    "Android kernel start": {
        "pattern": re.compile(r"(\d+.\d+[0-9])\s\[0\]\:Booting Linux on physical CPU 0x0000000000"),
        "type": "regex_group",
        "metric": MetricsOutputName.ANDROID_KERNEL_START,
        "apid": "ALD",
        "ctid": "KRNL",
    },
    "Android PID 1 test": {
        "pattern": re.compile(r"(\d+.\d+[0-9])\s\[1\]\:Run /init as init process"),
        "type": "regex_group",
        "metric": MetricsOutputName.ANDROID_PID_1_TEST,
        "apid": "ALD",
        "ctid": "KRNL",
    },
    "Android Boot Animation Start": {
        "pattern": re.compile(r"(\d+.\d+[0-9])\sinit\[1\]\:starting service 'bootanim'..."),
        "type": "regex_group",
        "metric": MetricsOutputName.ANDROID_BOOT_ANIMATION_START,
        "apid": "ALD",
        "ctid": "KRNL",
    },
    "Android Boot Animation End": {
        "pattern": re.compile(r"(\d+.\d+[0-9])\sinit\[1\]\:Service 'bootanim' \(pid .*\) exited with status.*"),
        "type": "regex_group",
        "metric": MetricsOutputName.ANDROID_BOOT_ANIMATION_END,
        "apid": "ALD",
        "ctid": "KRNL",
    },
    "Android Launcher All Widgets Drawn": {
        "pattern": re.compile(r"\[launcher-app\].*#KPI\|\d+\|KEY_STATE_ALL_WIDGETS_DRAWN\|([0-9]*(\.[0-9]+)?)\|.*"),
        "type": "regex_group",
        "metric": MetricsOutputName.ANDROID_LAUNCHER_ALL_WIDGETS_DRAWN,
        "apid": "ALD",
        "ctid": "LCAT",
    },
    "CID Ready Show Content": {
        "pattern": re.compile(r"CID Attribute ReadyShowContent updated 0 -> 1"),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.CID_READY_SHOW_CONTENT,
        "apid": "DISS",
        "ctid": "CID",
    },
    "PHUD Driver Ready Show Content": {
        "pattern": re.compile(r"PHUD-0 Attribute ReadyShowContent updated 0 -> 1"),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.PHUD_DRIVER_READY_SHOW_CONTENT,
        "apid": "DISS",
        "ctid": "PHUD",
    },
    "Account Protections Service": {
        "pattern": re.compile(r"#ACCOUNTPROTECTIONS #SVC #AccountProtectionsService\[[0-9]+\]\:onCreate\(\)"),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.ACCOUNT_PROTECTIONS_SVC,
        "apid": "ALD",
        "ctid": "LCAT",
    },
    "Account Protections Proxy": {
        "pattern": re.compile(
            r"#ACCOUNTPROTECTIONS #HAL #ACCOUNTPROTECTIONPROVIDER\[[0-9]+\]\:AccountProtections Service is available."
        ),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.ACCOUNT_PROTECTIONS_PROXY,
        "apid": "ALD",
        "ctid": "LCAT",
    },
    "Account Data Proxy": {
        "pattern": re.compile(r"#ACCOUNTDATA #HAL #ACCOUNTDATAPROVIDER\[[0-9]+\]\:AccountData Service is available."),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.ACCOUNT_DATA_PROXY,
        "apid": "ALD",
        "ctid": "LCAT",
    },
    "User Accounts Proxy": {
        "pattern": re.compile(r"#ACCOUNTDATA #HAL #USERACCOUNTS\[[0-9]+\]\:UserAccounts Service is available."),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.USER_ACCOUNTS_PROXY,
        "apid": "ALD",
        "ctid": "LCAT",
    },
    "Digital Key Proxy": {
        "pattern": re.compile(r"#ACCOUNTPROTECTIONS #HAL #DIGITALKEY\[[0-9]+\]\:DigitalKey Service is available."),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.DIGITALKEY_PROXY,
        "apid": "ALD",
        "ctid": "LCAT",
    },
    "Account Data Subscription": {
        "pattern": re.compile(
            r"#ACCOUNTDATA #HAL\[[0-9]+\]\:Error on DataChanged Broadcast susbcription. Callstatus: 0"
        ),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.ACCOUNT_DATA_SUBSCRIPTION,
        "apid": "ALD",
        "ctid": "LCAT",
    },
    "Account Protections Subscription": {
        "pattern": re.compile(
            r".*#IAccountProtectionsServiceImpl\[[0-9]+\]\:Subscribing.*Protections List.*result: true"
        ),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.ACCOUNT_PROTECTIONS_SUBSCRIPTION,
        "apid": "ALD",
        "ctid": "LCAT",
    },
    "Initial user detection": {
        "pattern": re.compile(r".*Checking Pia Profile and the UserId mapped to it"),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.INITIAL_USER_DETECTION,
        "apid": "ALD",
        "ctid": "LCAT",
    },
    "First UDP NM3 ": {
        "pattern": re.compile(r"First UDP NM3 message received"),
        "type": "msg_tmsp",
        "metric": MetricsOutputName.FIRST_UDP_MESSAGE_RECEIVED,
        "apid": "UNM3",
        "ctid": "KPI",
    },
    "DSP Boot Duration ": {
        "pattern": re.compile(
            r"adsp_logger\[\d+\]\:\[.*\] \[core0\]\[count\d+\]\[hifi_core\]\[\s+(\d+.\d+)\]MARKER KPI ADSP: audio framework boot complete!"  # noqa: E501
        ),
        "type": "regex_group",
        "metric": MetricsOutputName.DSP_BOOT_DURATION,
        "apid": "ALD",
        "ctid": "LCAT",
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
    "Android Kernel Boot Duration": {
        "kpi_1": "Android kernel start",
        "kpi_2": "Android PID 1 test",
        "metric": MetricsOutputName.ANDROID_KERNEL_BOOT_DURATION,
    },
    "Android Boot Animation Duration": {
        "kpi_1": "Android Boot Animation Start",
        "kpi_2": "Android Boot Animation End",
        "metric": MetricsOutputName.ANDROID_BOOT_ANIMATION_DURATION,
    },
}

"""Input config file for DLT KPIs multiple reboots metric collection

    *All parameters are mandatory!*

    Each entry has a name and a set of parameters associated with it:

    - "pattern": The regex to search on the DLT payload

    - "type": We have two possibilities:
            * "regex_group" - Use regex.group to extract KPI from payload
            * "msg_tmsp" - Get DLT msg timestamp

    Since the metrics will be using metric logger, we need to specify:
    - "key": "node0_pid1_kpi" (context of the metric)
    - "tag": "msg_processed_time" (specific name for each kpi)
    The kpi name at the end will be processed joining both.
    i.e. 'node0_pid1_kpi_msg_processed_time'

    - "apid": DLT APP_ID

    - "ctid": DLT CONTEXT_ID

    - "reboots": Number of times to collect this KPI.
    ALL KPIs in list will be collected max(reboots) times

    Note: Each KPI will be collected and outputted to 'METRICS_FILE_NAME' csv file.
    These are "dummy" KPIs, not requested to be collected more than once, implemented for testing and reference
"""
MULTIPLE_REBOOTS_DLT_KPI_CONFIG = {
    key: {**value, "reboots": DEFAULT_MULTIPLE_REBOOTS} for key, value in GENERIC_DLT_KPI_CONFIG.items()
}

MULTIPLE_REBOOTS_DLT_KPI_CONFIG["Node0 PID 1 test"]["reboots"] = "50"
