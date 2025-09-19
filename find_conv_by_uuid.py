#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ijson
import json
import argparse
import sys
import os
from collections.abc import Mapping, Sequence  # Dict/list type checks

def find_paths_containing_value(data, target_fragment, current_path=None):
    """Recursively search for string values containing *target_fragment*."""
    if current_path is None:
        current_path = []
    found_locations = []

    if isinstance(data, Mapping):
        for key, value in data.items():
            new_path = current_path + [key]
            if isinstance(value, str) and target_fragment in value:
                found_locations.append({"path": new_path, "value": value})
            elif isinstance(value, (Mapping, Sequence)) and not isinstance(value, str):
                found_locations.extend(find_paths_containing_value(value, target_fragment, new_path))

    elif isinstance(data, Sequence) and not isinstance(data, str):
        for index, item in enumerate(data):
            new_path = current_path + [index]
            if isinstance(item, str) and target_fragment in item:
                found_locations.append({"path": new_path, "value": item})
            elif isinstance(item, (Mapping, Sequence)) and not isinstance(item, str):
                found_locations.extend(find_paths_containing_value(item, target_fragment, new_path))

    return found_locations


def find_id_fragment_locations(json_filepath, target_id_fragment):
    """Iterate over conversations and collect every path containing *target_id_fragment*."""
    if not os.path.exists(json_filepath):
        print(f"Error: File not found - '{json_filepath}'", file=sys.stderr)
        return

    print(f"Searching for fragment '{target_id_fragment}' inside '{json_filepath}'...")
    all_results = []
    total_conversations_checked = 0

    try:
        with open(json_filepath, 'rb') as f:
            conversations = ijson.items(f, 'item')
            for i, conversation in enumerate(conversations):
                total_conversations_checked = i + 1
                if total_conversations_checked % 500 == 0:
                    print(f"  ... Checked {total_conversations_checked} conversations", end='\r')

                if not isinstance(conversation, dict):
                    continue

                conv_id = conversation.get("conversation_id") or conversation.get("id", f"index_{i}")
                conv_title = conversation.get("title", "[Untitled]")

                locations_in_conv = find_paths_containing_value(conversation, target_id_fragment)

                if locations_in_conv:
                    for loc in locations_in_conv:
                        all_results.append({
                            "conversation_id": conv_id,
                            "conversation_title": conv_title,
                            "path": loc["path"],
                            "found_value": loc["value"]
                        })

        print(f"\nScan complete. {total_conversations_checked} conversations inspected.")

        if all_results:
            print(f"\n--- Locations found for '{target_id_fragment}' ---")
            for result in all_results:
                path_str = ""
                for item in result['path']:
                    if isinstance(item, int):
                        path_str += f"[{item}]"
                    else:
                        path_str += f".{item}" if path_str else str(item)

                associated_key = result['path'][-1] if result['path'] else "N/A (root?)"

                print(f"\nConversation: '{result['conversation_title']}' (ID: {result['conversation_id']})")
                print(f"  Associated key/index: '{associated_key}'")
                print(f"  Full path           : {path_str}")
                value_preview = result['found_value']
                if len(value_preview) > 150:
                    value_preview = value_preview[:150] + "..."
                print(f"  Matching value      : {value_preview}")
        else:
            print(f"\nNo values containing '{target_id_fragment}' were found.")

    except ijson.JSONError as e:
        print(f"\nJSON parsing error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Locate where a file-id fragment appears within conversations.json and list the corresponding keys.",
        epilog="Example: python find_conv_by_uuid.py path/conversations.json T9L9gfa8Ca4QzK9w8dEw82"
    )
    parser.add_argument(
        "json_file",
        help="Path to the conversations.json file."
    )
    parser.add_argument(
        "file_id_fragment",
        help="The file ID or fragment to search for in conversation values (e.g. T9L9gfa8Ca4QzK9w8dEw82)."
    )

    args = parser.parse_args()

    target_fragment = args.file_id_fragment
    if target_fragment.startswith("file-"):
        target_fragment = target_fragment[len("file-"):]
        print(f"(Searching for UUID fragment: '{target_fragment}')")

    find_id_fragment_locations(args.json_file, target_fragment)
    sys.exit(0)
