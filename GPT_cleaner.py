#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import sys
import os
import argparse  # Command-line arguments
import csv       # Write CSV safely (quotes, commas in titles)

def calculate_conversation_text_length(conversation_data):
    """Compute the cumulative length of all textual parts in a conversation."""
    total_length = 0
    mapping = conversation_data.get("mapping", {})
    if not isinstance(mapping, dict):
        return 0

    for node_data in mapping.values():
        if not isinstance(node_data, dict):
            continue
        message = node_data.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, dict):
                parts = content.get("parts")
                if isinstance(parts, list):
                    for part in parts:
                        if isinstance(part, str):
                            total_length += len(part)
    return total_length


def sort_and_output(json_file_path, output_txt_file="analyse.txt"):
    """Load conversations, rank them by total text length, and write a CSV-like report."""
    if not os.path.exists(json_file_path):
        print(f"Error: JSON file '{json_file_path}' was not found.", file=sys.stderr)
        return 1

    print(f"--- Processing '{json_file_path}' (sorting by message size) ---")

    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            conversations = json.load(f)
    except json.JSONDecodeError as e:
        print(f"\nError: Failed to decode JSON in '{json_file_path}'.", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\nUnexpected error while reading '{json_file_path}':", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        return 1

    if not isinstance(conversations, list):
        print(f"Error: '{json_file_path}' does not contain the expected JSON list.", file=sys.stderr)
        return 1

    conversations_with_info = []
    print("Calculating conversation lengths...")
    for index, conv in enumerate(conversations):
        if not isinstance(conv, dict):
            print(f"Warning: Element {index} is not a dictionary. Skipping.", file=sys.stderr)
            continue

        length = calculate_conversation_text_length(conv)
        title = conv.get("title", "[Missing Title]")
        conv_id = conv.get("conversation_id", "[Missing ID]")

        conversations_with_info.append({
            "title": title,
            "length": length,
            "id": conv_id
        })
        if (index + 1) % 100 == 0:
            print(f"  {index + 1}/{len(conversations)} conversations processed...")

    print("Length calculation complete.")
    print("Sorting conversations...")
    sorted_conversations = sorted(
        conversations_with_info,
        key=lambda item: item['length'],
        reverse=True
    )
    print("Sorting complete.")

    print("\n--- Conversations sorted by total text length (descending) ---")
    if not sorted_conversations:
        print("(No valid conversations found)")
    else:
        max_len_digits = len(str(sorted_conversations[0]['length'])) if sorted_conversations else 0
        max_idx_digits = len(str(len(sorted_conversations)))

        print(f"{'#'.rjust(max_idx_digits)} | {'Length'.rjust(max_len_digits)} | Title")
        print(f"{'-'*(max_idx_digits+1)}+{'-'*(max_len_digits+2)}+{'-'*20}")

        for i, conv_info in enumerate(sorted_conversations):
            idx_str = str(i + 1).rjust(max_idx_digits)
            len_str = str(conv_info['length']).rjust(max_len_digits)
            title = conv_info['title']
            print(f"{idx_str} | {len_str} | {title}")

    print(f"\nWriting output file '{output_txt_file}'...")
    try:
        with open(output_txt_file, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            for conv_info in sorted_conversations:
                title = conv_info['title']
                uuid = conv_info['id']
                writer.writerow([title, uuid])
        print(f"File '{output_txt_file}' created successfully.")

    except IOError as e:
        print(f"\nError: Unable to write to '{output_txt_file}'.", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\nUnexpected error while writing '{output_txt_file}':", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        return 1

    print(f"\n--- Finished processing '{json_file_path}' ---")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load conversations.json, sort by total text length, display the results, and write analyse.txt (Title,UUID).",
        epilog="Example: python GPT_cleaner.py path/to/conversations.json"
    )
    parser.add_argument(
        "json_file",
        help="Path to the conversations.json file to analyse."
    )
    parser.add_argument(
        "-o", "--output",
        default="analyse.txt",
        help="Name of the output text file (default: analyse.txt)."
    )

    args = parser.parse_args()

    exit_code = sort_and_output(args.json_file, args.output)
    sys.exit(exit_code)
