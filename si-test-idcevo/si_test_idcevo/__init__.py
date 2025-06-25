"""SI test packages and helpers for IDCevo"""

__version__ = "1.00"

import os
from pathlib import Path

LIFECYCLES_PATH = os.path.join("extracted_files", "Lifecycles")
METRIC_EXTRACTOR_ARTIFACT_PATH = Path("extracted_files") / "metric_extractors" / "1"

INPUT_CSV_FILE = "dlt_msgs_of_interest.csv"

APPIUM_ELEMENT_TIMEOUT = 3  # seconds

# Default variables for appium session
DEFAULT_SYSTEM_PORT = 8200
DEFAULT_PORT_SERVER = 4723
DEFAULT_ADB_PORT = 5037

# Real phone tests variables
REAL_PHONE_SYSTEM_PORT = DEFAULT_SYSTEM_PORT + 10


# ATTENTION! These names have requirements:
# - they must not contain spaces nor special characters
class MetricsOutputName:
    NODE0_PID_1_TEST = "node0_pid1_kpi_msg_processed_time"
    VSOME_IP_ROUTING_READY_TEST = "vsomeip_routing_ready_available_tmsp"
    KERNEL_START = "node0_kernel_kpi_start_kernel"
    UDS_AVAILABITY = "uds_available_tmsp"
    PRIO1_DIAG_AVAILABILITY = "prio1_diag_available_tmsp"
    EARLY_CLUSTER_INIT = "early_cluster_initialized"
    EARLY_CLUSTER_FIRST_IMAGE = "early_cluster_first_image"
    EARLY_CLUSTER_FULL_CONTENT = "early_cluster_full_content"
    NODE0_KERNEL_BOOT_DURATION = "node0_kernel_boot_duration_time"
    FULL_CLUSTER_AVAILABLE = "full_cluster_available"
    DEADRECKONING_POS_CALC_AFTER_COLD_BOOT = "deadreckoning_pos_calc_after_cold_boot"
    INTERIOR_LIGHT_AVAILABLE = "interior_light_available"
    INTERIOR_LIGHT_CAF_LOADED = "interior_light_caf_loaded"
    ANDROID_KERNEL_START = "android_kernel_start"
    ANDROID_PID_1_TEST = "android_pid1"
    ANDROID_KERNEL_BOOT_DURATION = "android_kernel_boot_duration"
    ANDROID_BOOT_ANIMATION_START = "android_boot_animation_start"
    ANDROID_BOOT_ANIMATION_END = "android_boot_animation_end"
    ANDROID_BOOT_ANIMATION_DURATION = "android_boot_animation_duration"
    ANDROID_LAUNCHER_ALL_WIDGETS_DRAWN = "android_launcher_all_widgets_drawn"
    CID_READY_SHOW_CONTENT = "cid_ready_show_content"
    PHUD_DRIVER_READY_SHOW_CONTENT = "phud_driver_ready_show_content"
    ACCOUNT_PROTECTIONS_SVC = "account_protections_svc_created"
    ACCOUNT_PROTECTIONS_PROXY = "account_protections_proxy_available"
    ACCOUNT_PROTECTIONS_ADD_KEY = "account_protections_add_key"
    ACCOUNT_DATA_PROXY = "account_data_proxy_available"
    USER_ACCOUNTS_PROXY = "user_accounts_proxy_available"
    DIGITALKEY_PROXY = "digitalkey_proxy_available"
    ACCOUNT_DATA_SUBSCRIPTION = "account_data_subscription"
    ACCOUNT_PROTECTIONS_SUBSCRIPTION = "account_protections_subscription"
    INITIAL_USER_DETECTION = "initial_user_detection_time"
    FIRST_UDP_MESSAGE_RECEIVED = "first_udp_message_received"
    DSP_BOOT_DURATION = "dsp_boot_duration"


LOOPBACK_TEST_CMD = "echo -e -n '\\x01\\x00\\x00\\x01\\x00\\x64\\x00\\x00\\x00\\x60' > /dev/ipc12"
MEMORY_MANAGE_FAULT_CMD = "echo -e -n '\\x01\\x00\\x00\\x05\\x00\\x02' > /dev/ipc12"
SAFETY_FAULT_CMD = "echo -e -n '\\x01\\x00\\x00\\x05\\x00\\x04' > /dev/ipc12"
HARD_FAULT_CMD = "echo -e -n '\\x01\\x00\\x00\\x05\\x00\\x03' > /dev/ipc12"
SAFETY_MCU_ROM = "echo -e -n '\\x01\\x00\\x00\\x07\\x00\\x00' > /dev/ipc12"
SAFETY_REACTION_TRIGGER_CMD = "echo -e -n '\\x01\\x00\\x00\\x0C\\x00' > /dev/ipc12"
SAFETY_WAKEUP_REASON_CMD = "echo -e -n '\\x01\\x00\\x00\\x0D\\x00' > /dev/ipc12"
SINGLE_BIT_ECC_CMD = "echo -e -n '\\x01\\x00\\x00\\x07\\x00\\x01' > /dev/ipc12"
SPACE_PROTECTION_CMD = "echo -e -n '\\x01\\x00\\x00\\x09\\x00\\x04' > /dev/ipc12"
IAR_STACK_PROTECTION = "echo -e -n '\\x01\\x00\\x00\\x09\\x00\\x02' > /dev/ipc12"
SCG_SPLLCSR_CMD = "echo -e -n '\\x01\\x00\\x00\\x08\\x00\\x04\\x02' > /dev/ipc12"
MULTIBIT_ECC_ERROR_FOR_SRAMU = "echo -e -n '\\x01\\x00\\x00\\x07\\x00\\x04' > /dev/ipc12"
