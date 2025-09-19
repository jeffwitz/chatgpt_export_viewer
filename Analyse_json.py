#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import sys
import os
from collections import Counter
import argparse  # CLI argument handling

# --- Analysis helpers ---

def get_value_type(value):
    """Return a human readable string describing the Python type of *value*."""
    if isinstance(value, dict):
        return "Object (dict)"
    if isinstance(value, list):
        return "Array (list)"
    if isinstance(value, str):
        return "String"
    if isinstance(value, int):
        return "Integer"
    if isinstance(value, float):
        return "Float"
    if isinstance(value, bool):
        return "Boolean"
    if value is None:
        return "Null"
    return f"Unknown ({type(value).__name__})"


def analyze_structure(data, indent="", level=0, max_depth=10):
    """Recursively describe the structure of loaded JSON data."""
    if level > max_depth:
        return f"{indent}[...] (Maximum depth reached)\n"

    description = ""
    data_type = get_value_type(data)
    description += f"{indent}Type: {data_type}\n"

    if isinstance(data, dict):
        if not data:
            description += f"{indent}  (Empty object)\n"
        else:
            description += f"{indent}  Keys ({len(data)}):\n"
            for key, value in data.items():
                description += f"{indent}    - \"{key}\":\n"
                description += analyze_structure(value, indent + "      ", level + 1, max_depth)

    elif isinstance(data, list):
        if not data:
            description += f"{indent}  (Empty list)\n"
        else:
            description += f"{indent}  Elements ({len(data)}):\n"
            element_types = Counter(get_value_type(item) for item in data)

            if len(element_types) == 1:
                first_item_type = next(iter(element_types))
                description += f"{indent}    (All elements appear to be {first_item_type})\n"

                if first_item_type == "Object (dict)" and len(data) > 0:
                    first_item_keys = set(data[0].keys())
                    all_keys_same = True
                    for item in data[1:]:
                        if not isinstance(item, dict) or set(item.keys()) != first_item_keys:
                            all_keys_same = False
                            break
                    if all_keys_same:
                        description += f"{indent}    (All objects share the same keys: {sorted(list(first_item_keys))})\n"
                    else:
                        description += f"{indent}    (Objects use different key sets)\n"

                description += f"{indent}    Sample structure (based on first element):\n"
                description += analyze_structure(data[0], indent + "      ", level + 1, max_depth)

            else:
                description += f"{indent}    Mixed element types detected:\n"
                for type_name, count in element_types.items():
                    description += f"{indent}      - {type_name}: {count} occurrence(s)\n"
                description += f"{indent}    Sample structure (based on first element):\n"
                description += analyze_structure(data[0], indent + "      ", level + 1, max_depth)

    return description


# --- Main helpers ---

def process_json_file(file_path, max_depth=10):
    """Load a JSON file, analyse its structure, and print a report."""
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.", file=sys.stderr)
        return 1

    print(f"--- Analysing structure of '{file_path}' ---")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

    except json.JSONDecodeError as e:
        print(f"\nError: Unable to decode JSON in '{file_path}'.", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\nUnexpected error while reading '{file_path}':", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        return 1

    print("\nDetected structure:")
    structure_description = analyze_structure(data, max_depth=max_depth)
    print(structure_description)

    print(f"--- Finished analysing '{file_path}' ---")
    return 0


# --- CLI entry point ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load a JSON file, inspect its structure, and report the hierarchy.",
        epilog="Example: python Analyse_json.py path/to/conversations.json"
    )
    parser.add_argument(
        "json_file",
        help="Path to the JSON file to inspect."
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="Maximum recursion depth to avoid issues with deeply nested documents (default: 10)."
    )

    args = parser.parse_args()

    exit_code = process_json_file(args.json_file, args.max_depth)
    sys.exit(exit_code)
