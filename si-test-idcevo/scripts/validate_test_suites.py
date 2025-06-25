# Copyright (C) 2024. BMW CTW PT. All rights reserved.
# flake8: noqa
import glob
import os
import sys

EXPECTED_PATHS = [
    "si-test-idcevo",
    "partition-manager-systemtests",
    "recovery-manager-systemtests",
    "system-functions",
    "diagnostic-log-trace-systemtests",
    "lifecycle-components-systemtests",
]


def validate_test_suites(directory, file_patterns):
    """
    A test for tox which:
        - Searches for all systemtests/posttests config files in test-suites
        - Checks if file paths are contained in EXPECTED_PATHS
        - if any path contains "si-test-idcevo", validate if it exists
    """
    invalid_paths = []
    for pattern in file_patterns:
        # Find all files matching the pattern
        for filepath in glob.glob(os.path.join(directory, f"*{pattern}*")):
            with open(filepath, "r") as file:
                for line in file:
                    line = line.strip()
                    line = line.replace("!", "")
                    # Check if the line contains at least one "/"
                    if "/" in line:
                        parts = line.split("/", 1)
                        if parts[0] not in EXPECTED_PATHS:
                            invalid_paths.append(line)
                        elif parts[0] == "si-test-idcevo":
                            line = line.replace("si-test-idcevo", "si_test_idcevo")
                            if not os.path.exists(line):
                                invalid_paths.append(line)

    return invalid_paths


if __name__ == "__main__":
    test_suites_directory = "test-suites"
    file_patterns = ["systemtests", "posttests"]
    invalid_paths = validate_test_suites(test_suites_directory, file_patterns)

    # Print results
    if invalid_paths:
        print("\nInvalid paths found:")
        for path in invalid_paths:
            print(f"  {path}")
        sys.exit("⚠️  Invalid paths found, please resolve before testing. ⚠️")
    else:
        print("All test suite paths are valid.")
