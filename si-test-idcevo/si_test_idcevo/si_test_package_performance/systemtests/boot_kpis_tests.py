# Copyright (C) 2024. BMW CTW PT. All rights reserved.
import configparser
import copy
import json
import logging
import re

from pathlib import Path

from mtee.metric import MetricLogger
from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.test_environment import TEST_ENVIRONMENT as TE
from mtee.testing.tools import metadata
from si_test_idcevo.si_test_helpers.android_testing.test_base import TestBase
from si_test_idcevo.si_test_helpers.reboot_handlers import wait_for_application_target


# Config parser reading data from config file.
config = configparser.ConfigParser()
config.read(Path(__file__).parent.resolve() / "features_config.ini")

logger = logging.getLogger(__name__)
metric_logger = MetricLogger()

DLT_KPI_MARKERS_PATH = "/resources/dlt_filter_idcevo.json"
WANTED_APID = "BOOT"
WANTED_CTID = "PERF"


class TestBootKPIs:
    @classmethod
    def setup_class(cls):
        cls.test = TestBase.get_instance()
        cls.test.setup_base_class()
        wait_for_application_target(cls.test.mtee_target)

        if cls.test.mtee_target.has_capability(TE.test_bench.rack):
            dlt_filter_path = (
                "/ws/repos/dltlyse-plugins-gen22/dltlyse_plugins_gen22/"
                "plugins_gen22/data/DLTBootchart/dlt_filter_idcevo.json"
            )
        else:
            dlt_filter_path = DLT_KPI_MARKERS_PATH

        try:
            with open(dlt_filter_path, "r") as file:
                cls.filter_file = json.load(file)
        except Exception as e:
            raise AssertionError(f"Couldn't find or parse {dlt_filter_path}. Found exception: {e}")

    @classmethod
    def teardown_class(cls):
        cls.test.teardown_base_class()

    def setup_filters(self):
        compiled_kpi_filters = [
            {
                "apid": boot_kpi["apid"],
                "ctid": boot_kpi["ctid"],
                "payload_decoded": re.compile(boot_kpi["RegExp"]),
                "name": boot_kpi["Name"],
            }
            for boot_kpi in self.filter_file["config"]["markers"]
            if boot_kpi["apid"] == WANTED_APID and boot_kpi["ctid"] == WANTED_CTID
        ]
        return compiled_kpi_filters

    def analyze_found_kpis(self, dlt_msgs, compiled_kpi_filters):
        boot_kpis_found = {}

        # Sort the messages by asceding order of message index
        dlt_msgs_sorted = sorted(dlt_msgs, key=lambda msg: msg.mcnt)

        for msg in dlt_msgs_sorted:
            for kpi_regex in compiled_kpi_filters:
                if match := kpi_regex["payload_decoded"].search(msg.payload_decoded):
                    name = kpi_regex["name"].replace(" ", "_")
                    # Some KPIs will have duplicate entries in "dlt_msgs".
                    # Since the messages are sorted, and taking into account the line below,
                    # only the last occurrence of each KPI will be stored, which comes from the "Core 7" KPIs
                    # the last to get printed and containing all the KPIs we want to collect.
                    if name:
                        boot_kpis_found[name] = float(match.group(1))

        boot_kpis_missing = [
            marker["Name"].replace(" ", "_")
            for marker in self.filter_file["config"]["markers"]
            if marker["apid"] == WANTED_APID
            and marker["ctid"] == WANTED_CTID
            and marker["Name"].replace(" ", "_") not in boot_kpis_found.keys()
        ]

        return boot_kpis_found, boot_kpis_missing

    @metadata(
        testsuite=["domain", "SI", "SI-performance"],
        component="tee_idcevo",
        domain="IDCEvo Test",
        asil="None",
        testmethod="Analyzing Requirements",
        testtype="Requirements-based test",
        testsetup="SW-Component",
        categorization="functional",
        priority="1",
        duplicates="IDCEVODEV-12891",
        traceability={
            config.get("tests", "traceability"): {
                "FEATURE": config.get("FEATURES", "STABILITY_KPI_MONITORING"),
            },
        },
    )
    def test_001_get_boot_kpis(self):
        """
        [SIT_Automated] Extract and publish boot performance KPIs

            Steps:
            - Generate the DLT filters for the boot performance KPIs from a file located in dltlyse-plugins-gen22 repo
            - Start a DLTContext, perform a reboot and await the KPI messages
            - Iterate the obtained messages, and add KPIs that were found to dictionary: "boot_kpis_found"
            - Find missing KPIs by comparing "boot_kpis_found" to original file and store them in "boot_kpis_missing"
            - Publish KPIs with metric logger
        """

        compiled_kpi_filters = self.setup_filters()
        dlt_filters = copy.deepcopy(compiled_kpi_filters)
        for kpi_filter in dlt_filters:
            kpi_filter.pop("name", None)

        with DLTContext(self.test.mtee_target.connectors.dlt.broker, filters=[(WANTED_APID, WANTED_CTID)]) as trace:
            self.test.mtee_target.reboot(prefer_softreboot=True)
            dlt_msgs = trace.wait_for_multi_filters(
                filters=dlt_filters,
                drop=True,
                count=0,
                timeout=60,
            )
            self.test.mtee_target.resume_after_reboot()

        boot_kpis_found, boot_kpis_missing = self.analyze_found_kpis(dlt_msgs, compiled_kpi_filters)
        metric_logger.publish({"name": "boot_kpis", **boot_kpis_found})
        assert not boot_kpis_missing, f"These boot KPIs are missing: {boot_kpis_missing}"
