# Copyright (C) 2024. BMW CTW PT. All rights reserved.
# flake8: noqa
import os
import re
import sys

ROOT_DIR = "si_test_idcevo"


def validate_test_classes():
    """
    A test for tox which validates if:
        - Test files have the correct ending (..._tests.py)
        - System test classes begin with 'Test' (class Test...)
        - Post test classes end with 'PostTest' (class ...PostTest)
        - Post test classes have a line with '__test__ = True'
    """
    systemtest_class_pattern = re.compile(r"^\s*class Test\w*", re.MULTILINE)
    posttest_class_pattern = re.compile(r"class \w*PostTest")
    posttest_test_true_pattern = re.compile(r"__test__ = True")
    systemtests_without_expected_class = []
    posttests_without_expected_class = []
    files_without_expected_ending = []

    for root, _, files in os.walk(ROOT_DIR):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r") as f:
                    file_content = f.read()

                if "systemtests" in root:
                    if systemtest_class_pattern.search(file_content):
                        if not file.endswith("_tests.py"):
                            files_without_expected_ending.append(file_path)
                    elif file.endswith("_tests.py"):
                        systemtests_without_expected_class.append(file_path)

                elif "posttests" in root:
                    if posttest_class_pattern.search(file_content) and posttest_test_true_pattern.search(file_content):
                        if not file.endswith("_tests.py"):
                            files_without_expected_ending.append(file_path)
                    elif file.endswith("_tests.py"):
                        posttests_without_expected_class.append(file_path)

    return files_without_expected_ending, systemtests_without_expected_class, posttests_without_expected_class


if __name__ == "__main__":
    (
        files_without_expected_ending,
        systemtests_without_expected_class,
        posttests_without_expected_class,
    ) = validate_test_classes()
    if files_without_expected_ending or systemtests_without_expected_class or posttests_without_expected_class:

        if systemtests_without_expected_class:
            print("\nSYSTEM tests without correct class formatting [name must begin with 'Test' (class Test...)]:")
            for path in systemtests_without_expected_class:
                print(f"  {path}")

        if posttests_without_expected_class:
            print(
                "\nPOST tests without correct class formatting [name must end with 'PostTest' (class ...PostTest) and have a line with '__test__ = True']:"
            )
            for path in posttests_without_expected_class:
                print(f"  {path}")

        if files_without_expected_ending:
            print("\nFiles with correct class formatting but not ending with '_tests.py':")
            for path in files_without_expected_ending:
                print(f"  {path}")
        sys.exit(f"\nValidation failed: Some files do not adhere to the naming conventions.\n")
    else:
        print("\nAll files adhere to the naming conventions.\n")
