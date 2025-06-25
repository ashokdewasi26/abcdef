# Copyright (C) 2023. BMW CTW PT. All rights reserved.

import glob
import logging
import re

logger = logging.getLogger(__name__)

# Get the content inside of parenthesis (excluding parenthesis) from a string.
REGEX_EXP_CONTENT_INSIDE_PARENTHESIS = r"\((.*?)\)"
# Get memory addresses inside of a string.
REGEX_EXP_GET_MEMORY_ADDRESS = r"0x[A-Fa-f0-9]+"
# Get the content inside of parenthesis (including parenthesis) from a string.
REGEX_EXP_GET_PARENTHESIS_CONTENT = r"\(.*?\)"
# Splits the different words of a given string.
REGEX_EXP_SPLIT_STRING_WORDS = r"\b[a-zA-Z0-9_:]+\b"


def _converts_list_to_dict(input_list):
    """
    Converts a list into a dict.
    :param input_list: expected format ["string1 (keyword1,keyword2,...)", ...]
    returns: dict with the following format: {"string1": [keyword1,keyword2,...], ...}
    """

    output_dict = {}
    for obtained_output_str in input_list:
        received_function_name = re.sub(REGEX_EXP_GET_PARENTHESIS_CONTENT, "", obtained_output_str)
        if match := re.findall(REGEX_EXP_CONTENT_INSIDE_PARENTHESIS, obtained_output_str):
            output_dict[received_function_name] = re.findall(REGEX_EXP_SPLIT_STRING_WORDS, match[0])
        else:
            output_dict[received_function_name] = [""]

    return output_dict


def compares_expected_vs_obtained_output(expected_output, obtained_output):
    """
    Verifies if two lists/dicts are similar.
    :param expected_output: list or dict containg the expected output.
        In case of a dict:
        - key: corresponds to a string.
        - items: corresponds to a list of keywords.
    :param obtained_output: list containg the obtained output.
    :returns: empty list if expected output is obtained, otherwise appends an error message to the output list.
    """

    error_message = []

    if isinstance(expected_output, dict):
        obtained_output_splitted = _converts_list_to_dict(obtained_output)

        for expected_string, expected_keywords in expected_output.items():
            if received_keywords := obtained_output_splitted.get(expected_string, []):
                keywords_missing = set(expected_keywords) - set(received_keywords)
                if keywords_missing:
                    error_message.append(
                        f"Missing expected keywords: {keywords_missing}, in {expected_string}."
                        f"Received keywords: {received_keywords}."
                    )
            else:
                error_message.append(f"Missing expected output: {expected_string}")

        if error_message:
            error_message = "\n".join(error_message)

    if isinstance(expected_output, list):
        output_missing = list(set(expected_output) - set(obtained_output))
        output_unexpected = list(set(obtained_output) - set(expected_output))

        # If all the expected data is present in obtained output there is no error.
        # If expected data ia missing and unexpected data is found then raise error.
        if output_missing and output_unexpected:
            error_message = (
                f"Missing expected output: {output_missing}. Unexpected received output: {output_unexpected}"
            )

    return error_message


def keywords_vs_obtained_output(keywords_dict, obtained_output):
    """
    Checks if the obtained output contains lines matching the given patterns.

    :param keywords_dict: dict containing the expected patterns.
        - key: corresponds to a string representing the pattern name.
        - value: a string pattern to be matched against the obtained output.
    :param obtained_output: list containing the obtained output lines to be checked.
    :returns: list of keys from keywords_dict whose patterns were not matched in the obtained output.
    """
    matched_keys = set()

    # Check each pattern against all lines
    for key, pattern in keywords_dict.items():
        regex = re.compile(pattern)
        for line in obtained_output:
            if regex.match(line):
                matched_keys.add(key)
                break

    # Determine the missing keys
    missing_keys = set(keywords_dict.keys()) - matched_keys

    return list(missing_keys)


def extracts_target_variable_from_string(pattern, string):
    """
    Extracts a target variable from a string.
    :param pattern: regex pattern to find a specific parameter in a string.
    :param string: input string.
    returns: target variable value (str) or empty list if no match.
    """

    target_value = []
    if match := re.search(pattern, string):
        target_value = match.group(1)
    return target_value


def get_logcat_file_path():
    """Get Android logcat file path.

    :return logcat_files_path_list : (list) List containing logcat file(s) path
    """
    return glob.glob("/workspace/logcat_*.log*")


def match_string_with_regex(reg_pattern, strings_to_parse):
    """
    Searches a reg pattern in a single string or list of strings and returns the matched item.
    :param regex reg_pattern: regex pattern to search
    :param str / list strings_to_parse: list of strings or single string to parse
    :return str match_found: Returns matched string if found else returns None
    """

    if isinstance(strings_to_parse, str):
        strings_to_parse = [strings_to_parse]

    for element in strings_to_parse:
        if re.search(reg_pattern, element):
            logger.info(f"Found pattern- {reg_pattern} in list {strings_to_parse}")
            return element
    logger.info(f"Not found pattern- {reg_pattern} in list- {strings_to_parse}")
    return None


def remove_memory_addresses(input_list):
    """
    Removes memory addresses from strings.
    :param input_list: list of strings.
    returns: list of strings.
    """

    replaced_list = [re.sub(REGEX_EXP_GET_MEMORY_ADDRESS, "", item) for item in input_list]
    return replaced_list
