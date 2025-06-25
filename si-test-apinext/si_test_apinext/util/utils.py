# Copyright (C) 2020 CTW PT. All rights reserved.
import inspect


def match_string_with_regex(string_to_parse, regex, error_msg):
    """Match string_to_parse with regex
    :param string_to_parse : string object to be parsed
    :param regex : regular expression object to parse the input string
    :error_msg : Error message to be displayed if input string did not match regex
    :return match : Object with matching content
    """
    match = regex.search(string_to_parse)
    if match is None:
        raise AssertionError(error_msg)
    return match


def get_caller_test_case_name(custom_test_case_name: str = "") -> str:
    if custom_test_case_name:
        return custom_test_case_name

    test_case_name = "unknown_test_case_name"
    frame = inspect.currentframe().f_back
    while frame:
        frameinfo = inspect.FrameInfo(*((frame,) + inspect.getframeinfo(frame)))
        if frameinfo.function.startswith("test_"):
            test_case_name = frameinfo.function
            break
        frame = frame.f_back

    return test_case_name
