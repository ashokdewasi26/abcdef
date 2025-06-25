import csv
import logging
import re

COMMON_PAYLOADS = {
    "START SYSMAN - HEALTH API - Recovery Utilities Brodcast API Tests",
    "DONE SYSMAN - HEALTH API - Recovery Utilities Brodcast API Tests",
}

# 'Verify Coredump Generation after Service Crash' and 'Verify Extraction
#  of Coredump via DLT'are two tests that cause expected crashes.
# All the expected crashes contained in this two tests will be whitelisted
INDUCED_CRASH_PAYLOADS = {
    "START [SIT_Automated] Verify Coredump Generation after Service Crash",
    "DONE [SIT_Automated] Verify Extraction of Coredump via DLT",
}

GENERIC_CRASH_MSG = "Failed with result"

RECOVER_MANAGER_MESSAGES = (
    "START SYSMAN - RecoveryManager - Crashing Recovery Manager shall restart the platform",
    "START SYSMAN - RecoveryManager - Platform Restart at suspend test",
)

EXPECTED_ERRORS_AND_PAYLOADS = {
    "recovery-manager.service": {"error": GENERIC_CRASH_MSG, "whitelist": RECOVER_MANAGER_MESSAGES},
    "recovery-manage": {"error": GENERIC_CRASH_MSG, "whitelist": RECOVER_MANAGER_MESSAGES},
    "rectestNoAction.service": {
        "error": GENERIC_CRASH_MSG,
        "whitelist": COMMON_PAYLOADS,
    },
    "rectest.service": {
        "error": GENERIC_CRASH_MSG,
        "whitelist": COMMON_PAYLOADS,
    },
    "display-diagnostics.service": {
        "ecu": "rse26, cde",
        "error": GENERIC_CRASH_MSG,
        "whitelist": INDUCED_CRASH_PAYLOADS,
    },
    "system-monitor.service": {
        "ecu": "rse26, cde",
        "error": GENERIC_CRASH_MSG,
        "whitelist": INDUCED_CRASH_PAYLOADS,
    },
    # Certain crashes can cause the data to be incorrectly recorded in the Timeline.csv file.
    # It is not feasible to accurately capture the correct lifecycle when these crashes occur.
    # Therefore, for these occurrences, follow the same schema of 'example.service',
    # Where the 'error' field is set to 'NA' to indicate that the service is expected to crash
    # under certain conditions and these crashes are not considered failures that need to be
    # filtered out by the payload.
    # "example.service": {"error": "NA", "payloads": None, "ecu": "idcevo"},
    "monitor": {"error": "NA", "payloads": None},
    "early_cluster.service": {"error": "NA", "payloads": None},
    "safety_A.service": {"error": "NA", "payloads": None},
}

logger = logging.getLogger(__name__)
CRASH_PAYLOAD = ".service: Failed with result"
TIMELINE_PATH = "extracted_files/Timeline.csv"
LIFECYCLES_TO_IGNORE = [0, 1]


def get_service_from_payload(payload):
    match = re.search(r"([a-zA-Z0-9_-]+\.service)", payload)
    return match.group(1) if match else None


def lifecycles_and_crashes_services_based_in_timeline(
    timeline_report_csv,
    lifecycle_limits_for_expected_crashes_tests,
    target_type,
    expected_crashes_without_payload,
    exact_lifecycle_service_which_crashed={},
):
    """Categorize service crashes during test lifecycles from TIMELINE_PATH.

    Processes crash data from a CSV file to identify expected service crashes during test lifecycles and incorporate
     them into lifecycle limits. It also determines the specific lifecycle in which each expected crash occurred.

    Parameters:
    - timeline_report_csv (file object)
    - failures_not_whitelisted (dict): A dictionary containing non-whitelisted failures, which will be
        updated by this function.
    -exact_lifecycle_service_which_crashed (dict): Optional, contains the exact lifecycle on which a service failed
    This method performs the following steps:

    1. Reads the 'Timeline.csv' file, which contains the expected crashed service report.
    2. Populates the `exact_lifecycle_service_which_crashed` dictionary with the services and their
    corresponding ECU lifecycles where intentional kernel crashes occurred. This is done by matching
    the dict name and it's corresponding 'error' value in the `EXPECTED_ERRORS_AND_PAYLOADS` structure
    with the payload field in the CSV file.
    3. Populates the `lifecycle_limits_for_expected_crashes_tests` dictionary with the ECU lifecycles that
    should be ignored when checking for non-whitelisted failures. This is done by searching for the start and end
    payloads defined in the `EXPECTED_ERRORS_AND_PAYLOADS` structure and adding the corresponding lifecycles to
    the dictionary.
    """
    error_patterns = {}
    whitelist_services = []
    # Precompute error patterns to avoid repeated computation
    for service, details in EXPECTED_ERRORS_AND_PAYLOADS.items():
        if "ecu" not in details or target_type in details["ecu"]:
            whitelist_services.append(service)
            error_patterns[service] = f"{service}: {details['error']}"
            if details["error"] == "NA":
                expected_crashes_without_payload.append(service)
    logger.info(f"Whitelist services: {whitelist_services}")
    logger.info(f"Error patterns: {error_patterns}")
    with timeline_report_csv.open("r", newline="\n") as csvfile:

        reader = csv.DictReader(csvfile)
        for row in reader:
            lifecycle = int(row["ECU lifecycle"])
            payload = row["payload"]
            for service, error_pattern in error_patterns.items():
                if error_pattern in payload:
                    exact_lifecycle_service_which_crashed.setdefault(service, []).append(lifecycle)
                    break
            for service in whitelist_services:
                details = EXPECTED_ERRORS_AND_PAYLOADS[service]
                whitelist = details.get("whitelist")
                if whitelist and payload in whitelist:
                    lifecycle_limits_for_expected_crashes_tests.setdefault(service, []).append(lifecycle)


def remove_expected_crashes_from_list_of_crashes(timeline_report_csv, failures_not_whitelisted, target_type):
    """Exclude intentional kernel crashes from non-whitelisted failures.

    Parameters:
    - timeline_report_csv (file object)
    - failures_not_whitelisted (dict): A dictionary containing non-whitelisted failures, which will be
        updated by this function.

    This method performs the following steps:
    """
    exact_lifecycle_service_which_crashed = {}
    lifecycle_limits_for_expected_crashes_tests = {}
    expected_crashes_without_payload = []
    lifecycles_and_crashes_services_based_in_timeline(
        timeline_report_csv,
        lifecycle_limits_for_expected_crashes_tests,
        target_type,
        expected_crashes_without_payload,
        exact_lifecycle_service_which_crashed,
    )
    logger.info("expected_crashes_without_payload: %s", expected_crashes_without_payload)
    whitelisted_failures = failures_not_whitelisted[:]

    for failure in whitelisted_failures:
        service = failure["service"]
        failed_lifecycles = failure["lifecycle"]
        expected_lifecycles = lifecycle_limits_for_expected_crashes_tests.get(service, [])

        if service in expected_crashes_without_payload:
            failures_not_whitelisted.remove(failure)
            continue

        for failed_lifecycle in failed_lifecycles:
            if any(
                start <= failed_lifecycle <= end
                for start, end in zip(expected_lifecycles[::2], expected_lifecycles[1::2])
            ):
                failures_not_whitelisted.remove(failure)
                break


def failed_services_based_in_timeline_file(timeline_report_csv, failed_services):
    """
    Extracts and aggregates failed service names from a 'timeline.csv' report.

    Unlike DLT-based approaches with different filters, this function ensures consistent
    failed service tracking for teams using 'timeline.csv' as their primary data source.

    Args:
    - timeline_report_csv (str): File object for the CSV report.
    - failed_services (dict): Dictionary mapping ECU lifecycle indices to sets of failed service names.

    """
    with timeline_report_csv.open("r", newline="\n") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            payload = row["payload"]
            ecu_lifecycle = row["ECU lifecycle"]
            if CRASH_PAYLOAD in payload:
                service_name = payload.split(": ")[1].split(" ")[0]
                failed_services[int(ecu_lifecycle)].add(service_name)
