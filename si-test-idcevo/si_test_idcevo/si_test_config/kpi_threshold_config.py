import configparser
from pathlib import Path

from si_test_idcevo import MetricsOutputName

# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")

DEFAULT_DOMAIN = "IDCEvo Test"
DEFAULT_DOCSTRING = "This is a default docstring"

# All KPIs thresholds must have a traceability config defined, so every metric entry in ECU_SPECIFIC_KPI must also
# have an entry on TRACEABILITY_CONFIG
ECU_SPECIFIC_KPI = {
    "idcevo": {
        "master": {
            MetricsOutputName.NODE0_PID_1_TEST: 0.85,  # (seconds) File: kpi_pid1_node0_after_cold_boot_tests.py
            MetricsOutputName.VSOME_IP_ROUTING_READY_TEST: 1.3,
            # (seconds) File: vsome_ip_routing_node0_after_cold_boot_tests.py
            MetricsOutputName.UDS_AVAILABITY: 5,  # (seconds) File: kpi_uds_availability_tests.py
            MetricsOutputName.PRIO1_DIAG_AVAILABILITY: 5,  # (seconds) File: kpi_uds_availability_tests.py
            MetricsOutputName.NODE0_KERNEL_BOOT_DURATION: 0.45,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.EARLY_CLUSTER_FIRST_IMAGE: 4.0,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.FULL_CLUSTER_AVAILABLE: 23,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.DEADRECKONING_POS_CALC_AFTER_COLD_BOOT: 3,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.INTERIOR_LIGHT_AVAILABLE: 2.05,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.INTERIOR_LIGHT_CAF_LOADED: 2.05,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.ANDROID_KERNEL_BOOT_DURATION: 0.75,  # (seconds) File: generic_dlt_kpi_tests.py
        },
        "i330_stable": {
            MetricsOutputName.VSOME_IP_ROUTING_READY_TEST: 5.85,
            # (seconds) File: vsome_ip_routing_node0_after_cold_boot_tests.py
            MetricsOutputName.UDS_AVAILABITY: 22.5,  # (seconds) File: kpi_uds_availability_tests.py
            MetricsOutputName.PRIO1_DIAG_AVAILABILITY: 22.5,  # (seconds) File: kpi_uds_availability_tests.py
            MetricsOutputName.NODE0_KERNEL_BOOT_DURATION: 2.025,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.EARLY_CLUSTER_FIRST_IMAGE: 6.75,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.FULL_CLUSTER_AVAILABLE: 103.5,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.DEADRECKONING_POS_CALC_AFTER_COLD_BOOT: 13.5,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.INTERIOR_LIGHT_AVAILABLE: 9.225,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.INTERIOR_LIGHT_CAF_LOADED: 9.225,  # (seconds) File: generic_dlt_kpi_tests.py
        },
        "i350_stable": {
            MetricsOutputName.VSOME_IP_ROUTING_READY_TEST: 3.25,
            # (seconds) File: vsome_ip_routing_node0_after_cold_boot_tests.py
            MetricsOutputName.UDS_AVAILABITY: 12.5,  # (seconds) File: kpi_uds_availability_tests.py
            MetricsOutputName.PRIO1_DIAG_AVAILABILITY: 12.5,  # (seconds) File: kpi_uds_availability_tests.py
            MetricsOutputName.NODE0_KERNEL_BOOT_DURATION: 1.125,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.EARLY_CLUSTER_FIRST_IMAGE: 5.25,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.FULL_CLUSTER_AVAILABLE: 80.5,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.DEADRECKONING_POS_CALC_AFTER_COLD_BOOT: 10.5,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.INTERIOR_LIGHT_AVAILABLE: 7.79,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.INTERIOR_LIGHT_CAF_LOADED: 7.79,  # (seconds) File: generic_dlt_kpi_tests.py
        },
        "default_branch": {
            "default_kpi_threshold": 0.0,  # (seconds). Default value used when the desired target is not defined.
        },
    },
    "rse26": {
        "master": {
            MetricsOutputName.NODE0_PID_1_TEST: 0.85,  # (seconds) File: kpi_pid1_node0_after_cold_boot_tests.py
            MetricsOutputName.VSOME_IP_ROUTING_READY_TEST: 1.3,
            # (seconds) File: vsome_ip_routing_node0_after_cold_boot_tests.py
            MetricsOutputName.UDS_AVAILABITY: 5,  # (seconds) File: kpi_uds_availability_tests.py
            MetricsOutputName.PRIO1_DIAG_AVAILABILITY: 5,  # (seconds) File: kpi_uds_availability_tests.py
            MetricsOutputName.NODE0_KERNEL_BOOT_DURATION: 0.45,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.EARLY_CLUSTER_FIRST_IMAGE: 1.5,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.FULL_CLUSTER_AVAILABLE: 23,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.DEADRECKONING_POS_CALC_AFTER_COLD_BOOT: 3,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.INTERIOR_LIGHT_AVAILABLE: 2.05,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.INTERIOR_LIGHT_CAF_LOADED: 2.05,  # (seconds) File: generic_dlt_kpi_tests.py
        },
        "default_branch": {
            "default_kpi_threshold": 0.0,  # (seconds). Default value used when the desired target is not defined.
        },
    },
    "cde": {
        "master": {
            MetricsOutputName.NODE0_PID_1_TEST: 0.85,  # (seconds) File: kpi_pid1_node0_after_cold_boot_tests.py
            MetricsOutputName.VSOME_IP_ROUTING_READY_TEST: 1.3,
            # (seconds) File: vsome_ip_routing_node0_after_cold_boot_tests.py
            MetricsOutputName.UDS_AVAILABITY: 5,  # (seconds) File: kpi_uds_availability_tests.py
            MetricsOutputName.PRIO1_DIAG_AVAILABILITY: 5,  # (seconds) File: kpi_uds_availability_tests.py
            MetricsOutputName.NODE0_KERNEL_BOOT_DURATION: 0.45,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.EARLY_CLUSTER_FIRST_IMAGE: 1.5,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.FULL_CLUSTER_AVAILABLE: 23,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.DEADRECKONING_POS_CALC_AFTER_COLD_BOOT: 3,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.INTERIOR_LIGHT_AVAILABLE: 2.05,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.INTERIOR_LIGHT_CAF_LOADED: 2.05,  # (seconds) File: generic_dlt_kpi_tests.py
            MetricsOutputName.ANDROID_KERNEL_BOOT_DURATION: 0.75,  # (seconds) File: generic_dlt_kpi_tests.py
        },
        "default_branch": {
            "default_kpi_threshold": 0.0,  # (seconds). Default value used when the desired target is not defined.
        },
    },
    "default_target": {
        "default_branch": {
            "default_kpi_threshold": 0.0,  # (seconds). Default value used when the desired target is not defined.
        },
    },
}

TRACEABILITY_CONFIG = {
    MetricsOutputName.NODE0_PID_1_TEST: {
        "domain": "Performance",
        "feature": config.get("FEATURES", "NODE0_PID1_COLD_BOOT", fallback=""),
        "docstring": "[SIT_Automated] Node0 PID 1 test",
    },
    MetricsOutputName.VSOME_IP_ROUTING_READY_TEST: {
        "domain": "Performance",
        "feature": config.get("FEATURES", "NODE0_VSOMEIP_COLD_BOOT", fallback=""),
        "docstring": "[SIT_Automated] Vsome IP routing ready test",
    },
    MetricsOutputName.UDS_AVAILABITY: {
        "domain": "Performance",
        "feature": config.get("FEATURES", "UDS_AVAILABILITY", fallback=""),
        "docstring": "[SIT_Automated] Check target UDS availability after reset",
    },
    MetricsOutputName.PRIO1_DIAG_AVAILABILITY: {
        "domain": "Performance",
        "feature": config.get("FEATURES", "UDS_AVAILABILITY", fallback=""),
        "docstring": "[SIT_Automated] Prio1 diagnostic job availability after reset",
    },
    MetricsOutputName.NODE0_KERNEL_BOOT_DURATION: {
        "domain": "Performance",
        "feature": config.get("FEATURES", "NODE0_KERNEL_BOOT", fallback=""),
        "docstring": "[SIT_Automated] Determine boot duration of node0 kernel",
    },
    MetricsOutputName.EARLY_CLUSTER_FIRST_IMAGE: {
        "domain": "Performance",
        "feature": config.get("FEATURES", "STABILITY_KPI_MONITORING", fallback=""),
        "docstring": "[SIT_Automated] Determine early cluster first image",
    },
    MetricsOutputName.FULL_CLUSTER_AVAILABLE: {
        "domain": "Performance",
        "feature": config.get("FEATURES", "STABILITY_KPI_MONITORING", fallback=""),
        "docstring": "[SIT_Automated] Determine full cluster available",
    },
    MetricsOutputName.DEADRECKONING_POS_CALC_AFTER_COLD_BOOT: {
        "domain": "Performance",
        "feature": config.get("FEATURES", "STABILITY_KPI_MONITORING", fallback=""),
        "docstring": "[SIT_Automated] Determine deadreckoning position calculated after cold boot",
    },
    MetricsOutputName.INTERIOR_LIGHT_AVAILABLE: {
        "domain": "Performance",
        "feature": config.get("FEATURES", "STABILITY_KPI_MONITORING", fallback=""),
        "docstring": "[SIT_Automated] Determine interior light available",
    },
    MetricsOutputName.INTERIOR_LIGHT_CAF_LOADED: {
        "domain": "Performance",
        "feature": config.get("FEATURES", "STABILITY_KPI_MONITORING", fallback=""),
        "docstring": "[SIT_Automated] Determine interior light CAF loaded",
    },
    MetricsOutputName.ANDROID_KERNEL_BOOT_DURATION: {
        "domain": "System Software",
        "feature": config.get("FEATURES", "KEY_PERFORMANCE_INDICATORS_GUEST_VM_KPIS", fallback=""),
        "docstring": "[SIT_Automated] Boot KPI for Android Kernel Duration",
    },
}
