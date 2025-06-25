import argparse
import logging
import sys
import xml.etree.ElementTree as ET  # noqa: N817

from xml.dom import minidom
from lxml import etree


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def remove_setup_nose_test_case_errors(test_results_xmf_file):
    """
    Removes 'test suite for' named test cases and adjacent system-err elements,
    as well as testcases with errors originating from nose.suite.py in the traceback, from the given XML file.

    Args:
        test_results_xmf_file (str): The path to the XML file containing the test results.

    Returns:
        int: 1 if any test cases were removed, 0 if no changes were made, and -1 if an exception occurred.
    """
    try:
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(test_results_xmf_file, parser)
        root = tree.getroot()

        errors_to_remove = ["nose.suite", "adb: unable to connect for unroot"]
        error_found = False

        testcases_to_remove = root.xpath("//testcase[contains(@name, 'test suite for')]")
        for testcase in testcases_to_remove:
            next_elem = testcase.getnext()
            if next_elem is not None and next_elem.tag == "system-err":
                root.remove(next_elem)
            root.remove(testcase)

        for testcase in root.findall(".//testcase"):
            error = testcase.find(".//error")
            if error is not None and any(err in error.get("message") for err in errors_to_remove):
                root.remove(testcase)
                error_found = True

        if testcases_to_remove or error_found:
            tree.write(
                test_results_xmf_file,
                pretty_print=True,
                encoding="UTF-8",
                xml_declaration=True,
            )
            return 1
        else:
            return 0
    except Exception as e:
        logging.info(f"The following error occurred: {e}")
        return -1


def sanitize_xml_file(file_path):
    """
    Sanitizes an XML file by:
    1. Formatting the XML content to avoid errors while file filtering.
    2. Removing all markdown formatting from the content.
    3. Removing all <testcase> elements with a specific starting name.
    4. Removing all <item name="test_file_bs_maintainer"> and <item name="test_file_bs_maintainer_email"> elements.

    Args:
        file_path (str): The file path of the XML file to be sanitized.

    Returns:
        int: 0 if the file was sanitized successfully, -1 if an exception occurred.
    """
    testcase_name_start = "SystemFunctionsPostTest.test_007_check_for_fatal_errors_si"
    items_to_remove = ["test_file_bs_maintainer", "test_file_bs_maintainer_email"]

    try:
        # Format the XML file
        tree = ET.parse(file_path)
        root = tree.getroot()
        if root is not None:
            xml_string = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            pretty_xml = minidom.parseString(xml_string).toprettyxml(indent="  ")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(pretty_xml)

        # Clean the XML file
        with open(file_path, "r") as file:
            content = file.read()

        # Remove markdown formatting
        cleaned_content = content.replace("*", "").replace("#", "")

        cleaned_lines = cleaned_content.splitlines()
        cleaned_lines_without_testcase = []
        skip = False
        for line in cleaned_lines:
            if any(item in line for item in items_to_remove):
                continue  # Skip the line with the item to remove
            if testcase_name_start in line and "<testcase" in line:
                skip = True  # Start skipping lines until the end of the testcase element
            if skip and "</testcase>" in line:
                skip = False  # Stop skipping lines after the end of the testcase element
                continue
            if not skip:
                cleaned_lines_without_testcase.append(line)
        cleaned_content = "\n".join(cleaned_lines_without_testcase)
        with open(file_path, "w") as file:
            file.write(cleaned_content)
        return remove_setup_nose_test_case_errors(file_path)

    except Exception as e:
        logger.info(f"An error occurred: {e}")
        return -1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove invalid test cases from an XML file.")
    parser.add_argument("xml_file_path", help="Path to the XML file")
    args = parser.parse_args()
    test_results_xmf_file = args.xml_file_path
    sys.exit(sanitize_xml_file(test_results_xmf_file))
