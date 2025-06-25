# Copyright (C) 2025. BMW CTW PT. All rights reserved.
# flake8: noqa
import json
import os
import jsonschema
import sys

from jsonschema import validate


# Define the known issues JSON schema
schema = {
    "type": "object",
    "patternProperties": {
        "^.*$": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"ticket": {"type": "string"}, "error": {"type": "string"}},
                "required": ["ticket", "error"],
            },
        }
    },
    "additionalProperties": False,
}

# Directory containing known issues JSON files
json_dir = "test-summarizer/known_issues"

# Track validation errors
has_errors = False

# Validate each JSON file
for filename in os.listdir(json_dir):
    if filename.endswith(".json"):
        filepath = os.path.join(json_dir, filename)
        with open(filepath, "r") as file:
            try:
                data = json.load(file)
                validate(instance=data, schema=schema)
                print(f"{filename} is valid.")
            except jsonschema.exceptions.ValidationError as e:
                print(f"{filename} is invalid: {e.message}")
                has_errors = True
            except json.JSONDecodeError as e:
                print(f"{filename} is not a valid JSON file: {e.msg}")
                print(f"Error at line {e.lineno}, column {e.colno}")
                has_errors = True

# Exit with a non-zero status code if there were validation errors
if has_errors:
    sys.exit("Validation errors found in JSON files.")
else:
    print("All JSON files are valid.")
