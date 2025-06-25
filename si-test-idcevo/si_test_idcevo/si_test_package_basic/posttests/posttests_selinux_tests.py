# Copyright (C) 2024. BMW CTW PT. All rights reserved.

import ast
import csv
import glob
import json
import os
from collections import defaultdict
from pathlib import Path

from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import metadata

SELINUX_KNOWN_COMPONENTS_PATH = "/resources/selinux_known_components.json"

target = TargetShare().target


class SELinuxPostTest(object):

    __test__ = True

    def strip_null_bytes(self, lines):
        for line in lines:
            yield line.replace("\0", "")

    def find_android_maintainer(self, domain_to_find):
        """find the maintainer for the given android domain"""
        with open(SELINUX_KNOWN_COMPONENTS_PATH, "r") as known_components_file:
            known_components = json.loads(known_components_file.read())
            for component in known_components:
                if "domain" not in component or component["domain"] == domain_to_find:
                    note = None if "note" not in component else component["note"]
                    return {"maintainer": component["maintainer"], "note": note}
        return {"maintainer": None, "note": None}

    def write_to_csv(self, output_csv, unique_violations, permissive_domains):
        """Write a summary report of the unique violations"""
        num_violations = 0
        with output_csv.open("w", newline="\n") as out_file:
            fieldnames = ["scontext", "tcontext", "tclass", "mode", "permissions"]

            csv_writer = csv.DictWriter(out_file, fieldnames=fieldnames, delimiter=",")
            csv_writer.writeheader()

            for domain, findings in sorted(unique_violations.items(), key=lambda item: -len(item[1])):
                for tcontext, tclass, permission in findings:
                    num_violations += 1
                    csv_writer.writerow(
                        dict(
                            zip(
                                fieldnames,
                                [
                                    domain,
                                    tcontext,
                                    tclass,
                                    "Permissive" if domain in permissive_domains else "Enforcing",
                                    permission,
                                ],
                            )
                        )
                    )
        return num_violations

    def generate_summary_reports(self, dltlyse_report_csv, report_dir):
        """
        Extract the unique SELinux violations for both Android an node0 and generate separate reports for them.
        The reports are written to the extracted_files alongside the full selinux_violations.csv

        Generate one additional csv file with SELinux violation stats for the SELinux Status Page in Confluence.
        """
        android_output_csv = Path(report_dir, f"{dltlyse_report_csv.stem}-android.csv")
        node0_output_csv = Path(report_dir, f"{dltlyse_report_csv.stem}-node0.csv")

        permissive_domains = defaultdict(set)
        enforcing_domains = defaultdict(set)

        violations_uniq = defaultdict(lambda: defaultdict(set))
        violations_count = defaultdict(int)
        with dltlyse_report_csv.open(newline="\n") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                scontext = row["scontext"].split(":")
                if len(scontext) < 3:  # Some malformed entries might happen
                    continue
                sdomain = scontext[2]
                # Only android domains have 's0' level set at position 3
                domain_type = "android" if len(scontext) > 3 and scontext[3].startswith("s0") else "node0"
                for access in row["permissions"].split():
                    violations_count[domain_type] += 1
                    violations_uniq[domain_type][sdomain].add((row["tcontext"], row["tclass"], access))

                if "1" in row["permissive"]:  # Some cells may contain 1' instead of 1
                    permissive_domains[domain_type].add(sdomain)
                else:
                    enforcing_domains[domain_type].add(sdomain)

        unique_count_android = self.write_to_csv(
            android_output_csv, violations_uniq["android"], permissive_domains["android"]
        )
        unique_count_node0 = self.write_to_csv(node0_output_csv, violations_uniq["node0"], permissive_domains["node0"])

        # Write SELinux Status Summary for the SELinux Status Page
        status_output = Path(report_dir, "selinux_status_summary.csv")
        with status_output.open("w", newline="\n") as out_file:
            fieldnames = [
                "Type",
                "Unique Count",
                "Violation Count",
                "Permissive Domains Count",
                "Violating Domains Count",
            ]
            android_summary = dict(
                zip(
                    fieldnames,
                    [
                        "Android",
                        unique_count_android,
                        violations_count["android"],
                        len(permissive_domains["android"]),
                        len(permissive_domains["android"]) + len(enforcing_domains["android"]),
                    ],
                )
            )
            node0_summary = dict(
                zip(
                    fieldnames,
                    [
                        "Node0",
                        unique_count_node0,
                        violations_count["node0"],
                        len(permissive_domains["node0"]),
                        len(permissive_domains["node0"]) + len(enforcing_domains["node0"]),
                    ],
                )
            )

            csv_writer = csv.DictWriter(out_file, fieldnames=fieldnames, delimiter=",")
            csv_writer.writeheader()
            csv_writer.writerow(android_summary)
            csv_writer.writerow(node0_summary)

    @metadata(testsuite=["SI", "SI-long", "SI-android", "IDCEVO-SP21"], domain="SWINT")
    def test_generate_selinux_report(self):

        migration_stats_glob_pattern = "/images/selinux_migration_stats.csv"
        images_dir = glob.glob(migration_stats_glob_pattern)
        if len(images_dir) != 1:
            raise Exception(
                "Expected 1 glob match for {} in {}. Found {}".format(
                    migration_stats_glob_pattern, os.getcwd(), len(images_dir)
                )
            )
        node0_domains_csv = Path(images_dir[0])

        dltlyse_report_csv = Path(target.options.result_dir, "extracted_files/selinux_violations.csv")
        output_csv = Path(target.options.result_dir, "selinux_domain_violations.csv")

        domain_violations_count = defaultdict(int)
        android_domain_violations = defaultdict(list)
        unique_domain_violations = defaultdict(set)
        permissive_domains = set()
        with dltlyse_report_csv.open(newline="\n") as csvfile:
            reader = csv.DictReader(self.strip_null_bytes(csvfile))
            for row in reader:
                scontext = row["scontext"].split(":")
                domain = scontext[2]
                domain_violations_count[domain] += 1
                for permission in ast.literal_eval(row["permissions"]):
                    # only android domains have 's0' level set at position 3
                    if len(scontext) > 3 and scontext[3] == "s0":
                        android_domain_violations[domain].append((row["tcontext"], row["tclass"], permission))
                    unique_domain_violations[domain].add((row["tcontext"], row["tclass"], permission))
                if "1" in row["permissive"]:  # some cells of the csv contain 1' and not just 1
                    permissive_domains.add(domain)

        domains_written = set()
        with output_csv.open("w", newline="\n") as out_file, node0_domains_csv.open(
            newline="\n"
        ) as node0_domains_csvfile:
            node0_csv_reader = csv.DictReader(node0_domains_csvfile)
            fieldnames = node0_csv_reader.fieldnames + ["Domain Violations", "Unique Domain Violations"]

            csv_writer = csv.DictWriter(out_file, fieldnames=fieldnames, delimiter=",")
            csv_writer.writeheader()

            # write node0 domains to csv
            for row in node0_csv_reader:
                domain = row["Domain"]
                domains_written.add(domain)
                row["Domain Violations"] = domain_violations_count[domain]
                row["Unique Domain Violations"] = len(unique_domain_violations[domain])
                csv_writer.writerow(row)

            # write Android domains to csv
            for domain, _ in sorted(android_domain_violations.items(), key=lambda item: -len(item[1])):
                maintainer_info = self.find_android_maintainer(domain)
                if maintainer_info["note"] is None:
                    maintainer_info["note"] = "android component"
                if maintainer_info["maintainer"] is not None:
                    domains_written.add(domain)
                    csv_writer.writerow(
                        dict(
                            zip(
                                fieldnames,
                                [
                                    "",
                                    domain,
                                    maintainer_info["maintainer"],
                                    maintainer_info["note"],
                                    "Permissive" if domain in permissive_domains else "Enforcing",
                                    domain_violations_count[domain],
                                    len(unique_domain_violations[domain]),
                                ],
                            )
                        )
                    )

            # Sanity check -- list domains with violations not found in migration_stats (i.e. not
            # identified as node0 project domains) or Android domains with no identified maintainer
            diff = set(unique_domain_violations.keys()) - domains_written
            node0_output = ""
            android_output = ""
            for domain in diff:
                if domain.endswith("_t"):
                    node0_output += (
                        f"{domain}, {domain_violations_count[domain]}, {len(unique_domain_violations[domain])}; "
                    )
                else:
                    android_output += (
                        f"{domain}, {domain_violations_count[domain]}, {len(unique_domain_violations[domain])}; "
                    )

            if node0_output:
                row = defaultdict(str)
                row["Executable"] = (
                    "Other node0 domains with violations "
                    f"(domain, #violations, #unique violations): {node0_output}. "
                    "Those need clarification! You can find the violations in the selinux_violations.csv"
                )
                csv_writer.writerow(row)
            if android_output:
                row = defaultdict(str)
                row["Executable"] = (
                    "Other Android domains with violations "
                    f"(domain, #violations, #unique violations): {android_output}. "
                    "Those need clarification! You can find the violations in the selinux_violations.csv"
                )
                csv_writer.writerow(row)

        self.generate_summary_reports(dltlyse_report_csv, Path(target.options.result_dir, "extracted_files"))
