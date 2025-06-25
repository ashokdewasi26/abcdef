# Copyright (C) 2024. BMW CTW PT. All rights reserved.
# flake8: noqa
# All files are valid until proven invalid ;)
import configparser
import os
import sys
from collections import defaultdict

ROOT_DIR = "si_test_idcevo"

"""
Example of a config file: example_config.ini

# example testcases
[tests]
hostname = example
traceability = example

# example Features
[FEATURES]
FEATURE_VARIABLE_NAME = FEATURE_TICKET (EXAMPLEPM-123456)
"""


def read_config_files():
    """Finds config files and creates a dictionary with file paths as keys and configs as values"""
    files_and_configs = {}

    for root, _, files in os.walk(ROOT_DIR):
        for file in files:
            if file.endswith("config.ini"):
                full_path = os.path.join(root, file)
                config = configparser.ConfigParser()
                config.read(full_path)
                files_and_configs[full_path] = config

    return files_and_configs


def find_duplicate_tickets(files_and_configs):
    """
    A test for tox which validates if there are no duplicate tickets (same value assigned to more than one variable)

        Steps:
        - Reads file and finds features associated per ticket
        - Looks for repeated use of tickets and generates an informative report per file

        Expected outcome:
        - Test passes if no duplicates are found in each file
        - Test reports duplicates and fails the tox test in case they are found

        Example of wrong behaviour:
            [FEATURES]
            INTER_VM_COMMUNICATION = IDCEVOPM-4587
            COMMS_BETWEEN_VMS = IDCEVOPM-4587
    """
    error_found = False

    for file, config in files_and_configs.items():
        no_duplicates = True
        ticket_and_associated_feature_names = defaultdict(list)
        print(f"\nChecking file for duplicate tickets: {os.path.basename(file)}")
        if "FEATURES" in config:
            for feature, ticket in config["FEATURES"].items():
                ticket_and_associated_feature_names[ticket].append(feature)

            for ticket, features in ticket_and_associated_feature_names.items():
                if len(features) > 1 and ticket != "TODO":
                    print(f"  Duplicate ticket '{ticket}' found for features: {', '.join(features)}")
                    error_found = True
                    no_duplicates = False
        else:
            sys.exit(f"\n❌  Couldn't find the expected [FEATURES] section in {file} ❌")

        if no_duplicates:
            print("  No duplicates here!")

    return error_found


def validate_feature_variable_mapping(files_and_configs):
    """
    A test for tox which validates if the same variables for tickets exist across all ECU files.
    This is necessary because even if a test is skipped for a given ECU, their metadata is still
    read, and consequentely if the feature variable name didn't exist for the given ECU, it would cause an error

        Steps:
        - Reads file and creates a dictionary with feature variable names as keys and files as values
        - Validate if all feature variable names are present in all config files

        Expected outcome:
        - Test passes if all feature variable names are present in all config files
        - The test checks for each feature ticket in all files, and if it doesn't find one, the tox test fails
    """
    error_found = False
    ticket_and_associated_ecus = defaultdict(list)
    print(f"\nChecking if feature tickets are present in all files...")
    for file, config in files_and_configs.items():
        if "FEATURES" in config:
            for feature in config["FEATURES"].keys():
                ticket_and_associated_ecus[feature].append(os.path.basename(file))

    for feature, ecus in ticket_and_associated_ecus.items():
        if len(ecus) != len(files_and_configs):
            missing_features_in_config_files = [
                os.path.basename(file) for file in files_and_configs.keys() if os.path.basename(file) not in ecus
            ]
            print(f"  Missing feature ticket '{feature}': {missing_features_in_config_files}'")
            error_found = True

    if not error_found:
        print("  All tickets present in all files!")

    return error_found


def validate_alphabetical_order(files_and_configs):
    """
    A test for tox which validates if the feature variable names are ordered alphabetically

        Steps:
        - Iterates through each config file in the provided dictionary
        - Validate if all feature variable names are alphabetically sorted

        Expected outcome:
        - Test passes if all feature variable names in all files are alphabetically sorted
        - Test fails and prints out a message indicating the feature variable name that is out of order if it finds any.
    """
    error_found = False

    for file, config in files_and_configs.items():
        alphabetical_order = True
        print(f"\nChecking alphabetical order in file: {os.path.basename(file)}")
        if "FEATURES" in config:
            features = list(config["FEATURES"].items())
            for i, (feature, ticket) in enumerate(features):
                if i > 0 and features[i - 1][0] > feature:
                    print(f"  Feature '{feature}' is out of alphabetical order")
                    error_found = True
                    alphabetical_order = False

        if alphabetical_order:
            print("  File sorted alphabetically!")

    return error_found


if __name__ == "__main__":

    files_and_configs = read_config_files()

    errors = (
        find_duplicate_tickets(files_and_configs)
        + validate_feature_variable_mapping(files_and_configs)
        + validate_alphabetical_order(files_and_configs)
    )

    if errors:
        sys.exit("\n⚠️  Issues found, please resolve before merging. ⚠️")
    else:
        print("\nNo issues found in any file, validation passed.")
