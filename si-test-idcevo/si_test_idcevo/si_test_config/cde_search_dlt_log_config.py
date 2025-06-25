# Copyright (C) 2024. BMW CAR IT. All rights reserved.
"""
CDE Config file to define the DLT messages which will be searched in DLT log, by 'search_logs_tests.py' post test.
All DLT 'apid' and 'ctid' listed bellow, must also be defined in 'dlt_list_of_interest_cde.csv' plugin.
"""

DLT_LOG_VERIFICATION = {
    "search_for_acl_plugin_initialization_logs": {
        "apid": ["VSIP"],
        "ctid": ["VSIP"],
        "pattern": [
            [
                r"acl_plugin: Status is activated, restored from file /var/data/acl/status|"
                r"acl_plugin: Status is deactivated \(default\)|"
                r"acl_plugin: Status is deactivated, restored from file /var/data/acl/status",
                r"acl_plugin: No violation history entries read from file /var/data/acl/violation_history"
                r"|acl_plugin: violation history file loaded with \d+ entries",
                r"Client 0xa710 Loading plug-in library: libvsomeip-netsec-plugin.so.1 succeeded!",
                r"OFFER\(a710\): \[fee2..*:\d.\d\] \(true\)",
                r"REQUEST\(a710\): \[f8a0..*\]",
                r"netsec_plugin: ACL plugin enabled",
            ]
        ],
        "domain": "Network",
        "docstring": """[SIT_Automated] SOME/IP - ACL plugin is initialized properly""",
        "feature": ["ACL_PLUGIN"],
        "duplicates": "IDCEVODEV-103113",
    },
    "search_for_hypervisor_logs": {
        "apid": ["LOGM"],
        "ctid": ["HYPR"],
        "pattern": [[r".*"]],
        "domain": "System Software",
        "docstring": """[SIT_Automated] Checks if hypervisor logs exist on DLT messages""",
        "feature": ["HYPERVISOR_LOGGING", "HYPERVISOR_LOGGING_DLT_ADAPTER"],
        "duplicates": "IDCEVODEV-66767",
    },
    "search_for_diagnostics_initialization_logs": {
        "apid": ["LSMF"],
        "ctid": ["EXDG"],
        "pattern": [
            [
                r"Network.SomeipAcl.stopAclStopOperation:65250.1/0xFEE2.0x0001 registered for \[31,02,11,20\]",
                r"Network.SomeipAcl.startAclStartOperation:65250.2/0xFEE2.0x0002 registered for \[31,01,11,20\]",
                r"Network.SomeipAcl.readAclStatus:65250.4/0xFEE2.0x0004 registered for \[22,17,77,FFFF\]",
                r"Network.SomeipAcl.readAclReadViolationHistory:65250.3/0xFEE2.0x0003 "
                r"registered for \[22,17,78,FFFF\]",
                r".*Network.SomeipAcl:65250/0xFEE2 is available with version \d",
            ]
        ],
        "domain": "Network",
        "docstring": """[SIT_Automated] SOME/IP - Diagnostics is initialized properly""",
        "feature": ["DIAGNOSTICS"],
        "duplicates": "IDCEVODEV-11352",
    },
    "search_for_testability_logs": {
        "apid": ["VSIP"],
        "ctid": ["VSIP"],
        "pattern": [
            [
                r"REGISTER EVENT\(.*\): \[0101.00a7.8001:eventtype=0:is_provided=true:reliable=2\]",
                r"REGISTER EVENT\(.*\): \[0101.00a7.8002:eventtype=0:is_provided=true:reliable=2\]",
                r"REGISTER EVENT\(.*\): \[0101.00a7.8003:eventtype=0:is_provided=true:reliable=1\]",
                r"REGISTER EVENT\(.*\): \[0101.00a7.8004:eventtype=0:is_provided=true:reliable=2\]",
                r"REGISTER EVENT\(.*\): \[0101.00a7.8005:eventtype=2:is_provided=true:reliable=2\]",
                r"REGISTER EVENT\(.*\): \[0101.00a7.8006:eventtype=2:is_provided=true:reliable=2\]",
                r"REGISTER EVENT\(.*\): \[0101.00a7.8007:eventtype=2:is_provided=true:reliable=2\]",
                r"REGISTER EVENT\(.*\): \[0101.00a7.8008:eventtype=2:is_provided=true:reliable=1\]",
                r"REGISTER EVENT\(.*\): \[0101.00a7.800b:eventtype=0:is_provided=true:reliable=2\]",
            ]
        ],
        "domain": "Network",
        "docstring": """[SIT_Automated] SOME/IP - Testability - EnhancedTestabilityServiceHigh2 is offered""",
        "feature": ["TESTABILITY"],
        "duplicates": "IDCEVODEV-103660",
    },
    "search_for_common_api_application_logs": {
        "apid": ["LSMF", "VSIP"],
        "ctid": ["CAPI", "VSIP"],
        "pattern": [
            [
                r"Loading configuration file /etc//commonapi-someip.ini",
                r"Loading configuration file '/etc/commonapi.ini'",
                r"Using default binding 'someip'",
                r"Using default shared library folder '/usr/local/lib/commonapi'",
                r"Registering function for creating \"de.bmw.infotainment."
                r"systemfunctions.errormemory.DtcService:v0_1\" stub adapter",
                r"Registering stub for \"local:de.bmw.infotainment."
                r"systemfunctions.errormemory.DtcService:v0_1:Dtc\"",
            ],
            [
                r"REQUEST\(.*\): \[f8a0..*:\d.\d\]",
                r"Avoid trigger SD find-service message for local service",
                r"/instance/major/minor: f8a0\/.*",
                r"OFFER\(.*\): \[f8a0..*:\d.\d\] \(true\)",
                r"Port configuration missing for \[f8a0.1\]. Service is internal",
            ],
        ],
        "domain": "Network",
        "docstring": """[SIT_Automated] SOME/IP - CommonAPI can be used by application""",
        "feature": ["COMMON_API"],
        "duplicates": "IDCEVODEV-11075",
    },
    "search_for_kernel_availability_logs": {
        "apid": ["SYS"],
        "ctid": ["JOUR"],
        "pattern": [
            [
                r".*kernel: MARKER KPI - start_kernel",
                r".*kernel: MARKER KPI - setup_arch Start",
                r".*kernel: MARKER KPI - setup_arch End",
                r".*kernel: MARKER KPI - mm_init Start",
                r".*kernel: MARKER KPI - mm_init End",
                r".*kernel: MARKER KPI - sched_clock_init Start",
                r".*kernel: MARKER KPI - sched_clock_init End",
                r".*kernel: MARKER KPI sxgmac: Enter dwmac_sxgmac_probe",
                r".*kernel: MARKER KPI stmmac: Enter stmmac_dvr_probe",
                r".*kernel: MARKER KPI stmmac: Exit stmmac_dvr_probe",
                r".*kernel: MARKER KPI sxgmac: Exit dwmac_sxgmac_probe",
                r".*kernel: MARKER KPI - kernel_init Done",
            ],
        ],
        "domain": "LinuxOS",
        "docstring": """[SIT_Automated] Verify Availability of Kernel Logs in DLT""",
        "feature": ["GENERAL_INFRASTRUCTURE_LOG_AND_TRACE"],
        "duplicates": "IDCEVODEV-8889",
    },
    "search_for_can_npdu_logs": {
        "apid": ["N2SI"],
        "ctid": ["N2SI"],
        "pattern": [
            [
                r"MulticastSender::init\(\) done. Dest: \d+\.\d+(\.\d+)* PORT.*Src: \d+\.\d+(\.\d+)* PORT:\d+",
            ],
        ],
        "domain": "Network",
        "docstring": """[SIT_Automated] CAN nPDU Tunnel - configured correctly""",
        "feature": ["CAN_NPDU"],
        "duplicates": "IDCEVODEV-10691",
    },
    "search_for_someip_logs": {
        "apid": ["VSIP", ""],
        "ctid": ["VSIP", "VSIP"],
        "pattern": [
            [
                r".*Initializing vsomeip.*application \"vsomeipd\".*",
                r".*Instantiating routing manager \[Host\].*",
                r".*endpoint_manager_impl: Connecting to other clients from \d+\.\d+(\.\d+)*",
                r".*Service Discovery enabled. Trying to load module.*",
                r".*Service Discovery module loaded.*",
                r".*vsomeip tracing enabled.*vsomeip service discovery tracing not enabled.*",
                r".*Application\(vsomeipd, a710\) is initialized \(11, 100\).*",
                r".*Client 0xa710 Loading plug-in library: libvsomeip-heartbeat-plugin.so.1 succeeded!.*",
                r".*vsomeipd sent READY to systemd watchdog.*",
                r".*vsomeipd systemd watchdog is enabled.*",
                r".*Starting vsomeip application \"vsomeipd\" \(a710\) using 4 threads I/O nice -5.*",
                r".*Client \[a710\] routes unicast:\d+\.\d+(\.\d+)*, netmask:\d+\.\d+(\.\d+)*",
                r".*create_local_server: Listening @ \d+\.\d+(\.\d+)*",
                r".*create_local_server: Connecting to other clients from \d+\.\d+(\.\d+)*",
                r"vSomeIP \d(\.\d)* | \(default\).*",
                r".*Network interface \"vlan73\" state changed: up.*",
                r".*create_routing_root: Routing root @ \d+\.\d+(\.\d+)*",
                r".*Route \"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}) if: vlan73 gw: n/a\" state changed: up.*",
                r".*on_net_state_change: Starting routing root.*",
                r".*MARKER KPI NET4 SOME/IP Routing Ready.*",
                r"Client \[a710\] @ \d+\.\d+(\.\d+)*:\d+ is connecting to \[\w+\] @ \d+\.\d+(\.\d+)*",
                r".*REGISTERED_ACK\(\w+\).*",
                r".*OFFER\(\w+\): \[.*\] \(true\).*",
                r".*Application/Client \w+ @ \d+\.\d+(\.\d+)*:\d+ is registering.*",
            ],
            [
                r".*Client \w+ .* successfully connected to routing .* registering.*",
                r".*Registering to routing manager @ \d+\.\d+(\.\d+)*:\d+.*",
            ],
        ],
        "domain": "Network",
        "docstring": """[SIT_Automated] SOME/IP - Daemon - Correct configuration is loaded""",
        "feature": ["STABILITY_KPI_MONITORING"],
        "duplicates": "IDCEVODEV-103099",
    },
    "search_for_ethernet_diagnostics_logs": {
        "apid": ["ETHD"],
        "ctid": ["ETHD"],
        "pattern": [
            [r"EthernetDiagnostics initialized successfully"],
        ],
        "domain": "Network",
        "docstring": """[SIT_Automated] Ethernet - Diagnostics service is initialized properly""",
        "feature": ["ETHERNET_DIAGNOSTICS"],
        "duplicates": "IDCEVODEV-25974",
    },
}
