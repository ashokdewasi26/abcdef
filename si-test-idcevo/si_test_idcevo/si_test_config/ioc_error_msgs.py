# Copyright (C) 2024. BMW CTW PT. All rights reserved.
"""Input config file with IOC dlt error messages"""

SET_ERROR_MSGS = [
    {
        "domain": "General",
        "messages": [
            "Error reported to EventCollector",
            "Integrity fault, Event Collector called with Error",
            "Error counter = ru8MaxErrorCounter -> nenTimedEntityExpired",
            "Reset counter retrieved: 1",
            "Loading default AdjustData due to validation errors!",
        ],
    },
    {
        "domain": "Crash Info MCU",
        "messages": [
            "OS Safety Critical Exception",
            "Hard Fault",
            "Mem Manage Fault",
            "Bus Fault",
            "Usage Fault",
        ],
    },
    {
        "domain": "Thermal Management",
        "messages": [
            "XPS Hold is LOW. Starting over temperature shutdown!",
        ],
    },
    {
        "domain": "Watchdog",
        "messages": [
            "Maximum duration between 2 SFI heartbeats is more than 100ms",
            "IO WDG timeout occurred",
            "SFI health monitor timer expired!",
        ],
    },
    {
        "domain": "Power Management",
        "messages": [
            "Failsafe occurred, IOC is going to reset the board",
        ],
    },
    {
        "domain": "Safety",
        "messages": [
            "Recognized Wake Up: unrecoverable PFM path check - PMIC monitoring failed",
            "Recognized Wake Up: unrecoverable OS stack protection violation",
            "Recognized Wake Up: unrecoverable ECC fault for SRAML memory",
            "Recognized Wake Up: unrecoverable ECC fault for Code Flash memory",
            "Recognized Wake Up: register supervision violation",
            "Recognized Wake Up: unrecoverable MPU access violation",
            "[SoC monitor] Accutal XFLT INT state =  1 XFLT INT INV state =  1 , 0 = LOW, 1 = HIGH",
        ],
    },
    {
        "domain": "STR",
        "messages": [
            "[STR] SoC suspend failed",
        ],
    },
    {
        "domain": "FW Flashing",
        "messages": [
            "[SWDLv5] Calculated CRC is different than expected:",
        ],
    },
]
