# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""
Config file to define the bootlog messages which will be searched in bootlog, by 'search_bootlog_tests.py'
and 'search_lk_tests.py'.

Both structures are similar, the only difference is that 'LK_BOOTLOG_VERIFICATION' possesses the 'cmd' key,
which is a command that will be executed during the tests, on which the validation of 'pattern' will be searched.
"""

LK_BOOTLOG_VERIFICATION = {
    "check_android_strongbox": {
        "cmd": "bio list",
        "pattern": [
            [
                r".*strongbox_a",
                r".*strongbox_b",
            ],
        ],
        "domain": "System Software",
        "docstring": """[SIT_Automated] Check Android Strongbox
        Steps:
        - Enter LK mode.
        - Execute the command "bio list".
        - Check if "strongbox_a" and "strongbox_b" are present in output.
        """,
        "feature": ["ANDROID_STRONGBOX_BACKED_KEYSTORE"],
        "duplicates": "IDCEVODEV-9272",
        "hardware revision": {"cde": "", "idcevo": "", "rse26": ""},
    },
    "rpmb_validation": {
        "cmd": "rpmb test",
        "pattern": [
            [
                r"\[RPMB\] successfully set provision state to 0x1",
                r"\[RPMB\] key blocked successfully",
                r"\[RPMB\] init success",
                r"\[AVB\] boot header init success",
                r".*\[PASSED\] 12 tests.*",
            ],
        ],
        "domain": "System Software",
        "docstring": """[SIT_Automated] RPMB Test
         Steps:
            - Enter LK mode.
            - Run RPBM test with "rpmb test" command.
            - Validate the output of RPBM test.""",
        "feature": ["SOC_BASIC_SECURITY_RPMB_LK"],
        "duplicates": "IDCEVODEV-10109",
        "hardware revision": {"cde": "", "idcevo": "", "rse26": ""},
    },
}

BOOTLOG_VERIFICATION = {
    "search_for_serial_port_bootloader_logs": {
        "pattern": [
            [
                r".*welcome to lk\/MP.*",
                r".*boot args 0x84000000 0x0 0x0 0x0.*",
            ],
        ],
        "domain": "System Software",
        "docstring": """[SIT_Automated] Check Bootloader logs on serial port""",
        "feature": ["HYPERVISOR_LOGGING_START_LOGS"],
        "duplicates": "IDCEVODEV-7258",
        "hardware revision": {"cde": "", "idcevo": "", "rse26": ""},
    },
    "search_for_hypervisor_start_up_logs": {
        "pattern": [
            [r".*KPI\: HV start.*"],
        ],
        "domain": "System Software",
        "docstring": """[SIT_Automated] Hypervisor logs on startup""",
        "feature": ["HYPERVISOR_LOGGING_START_LOGS"],
        "duplicates": "IDCEVODEV-7440",
        "hardware revision": {"cde": "", "idcevo": "", "rse26": ""},
    },
    # Test is skipped ("Test is inactive: IDCEVODEV-420534")
    # "search_for_start_hypervisor_logs": {
    #     "pattern": [
    #         [r".*HYP:\[.*"],
    #         [r".*jmp hypervisor at core.*"],
    #     ],
    #     "domain": "System Software",
    #     "docstring": """[SIT_Automated] Start Hypervisor""",
    #     "feature": ["FIRMWARE_STARTUP", "FIRMWARE_STARTUP_START_DSP"],
    #     "duplicates": "IDCEVODEV-10106",
    #     "hardware revision": {"cde": "", "idcevo": "", "rse26": ""},
    # },
    "search_for_bcp_rev_id_logs": {
        "pattern": [
            [r".*bcp states (01234e12345678|012345678).*"],
        ],
        "domain": "System Software",
        "docstring": """[SIT_Automated] Verify when adjust block is not found""",
        "feature": ["HW_VARIANT_ADJUST"],
        "duplicates": "IDCEVODEV-48585",
        "hardware revision": {"cde": "", "idcevo": r"(C|D)\d", "rse26": ""},
    },
    "search_for_rpmb_rev_id_logs": {
        "pattern": [
            [r".*(bcp|rpmb) rev-id received.*"],
        ],
        "domain": "System Software",
        "docstring": """[SIT_Automated] Verify variant handling based on SOC Adjust block works""",
        "feature": ["HW_VARIANT_ADJUST"],
        "duplicates": "IDCEVODEV-48584",
        "hardware revision": {"cde": "", "idcevo": r"(C|D)\d", "rse26": ""},
    },
    "search_for_bootlog_activation_state": {
        "pattern": [
            [r".*androidboot(.*)=orange.*"],
        ],
        "domain": "System Software",
        "docstring": """[SIT_Automated] AVB Activation state""",
        "feature": ["BOOTLOADER_SECURITY_ANDROID_BOOT"],
        "duplicates": "IDCEVODEV-11428",
        "hardware revision": {"cde": "", "idcevo": "", "rse26": ""},
    },
}
