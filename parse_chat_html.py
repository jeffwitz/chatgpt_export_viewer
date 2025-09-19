#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import re
import argparse
import sys
from bs4 import BeautifulSoup  # HTML parsing helper

# --- Configuration ---
# TODO: Adjust these selectors after reviewing chat.html.
CONVERSATION_SELECTOR = "body > div"  # Conversation container; tweak to match the export
MESSAGE_SELECTOR = "div.text-base"  # Example based on the web UI (likely needs adjustment)
ROLE_ATTRIBUTE = "data-message-author-role"  # Attribute that may contain "user" / "assistant"
CONTENT_SELECTOR = "div.markdown"  # Container for the rendered content
FILE_LINK_CONTAINER_SELECTOR = "div.mt-1"  # Potential location for the [File] link

FILE_LINK_REGEX = re.compile(r"\[File\]:\s*(\S+)")


def extract_role_from_element(message_element):
    """Try to infer the message role from attributes or CSS classes."""
    role = message_element.get(ROLE_ATTRIBUTE)
    if role in ["user", "assistant", "tool", "system"]:
        return role

    classes = message_element.get('class', [])
    if 'message-user' in classes:
        return 'user'
    if 'message-chatgpt' in classes:
        return 'assistant'
    if 'message-tool' in classes:
        return 'tool'

    return "unknown"


def parse_html_and_extract(html_filepath, output_json_filepath):
    """Parse chat.html, extract conversations/messages/assets, and save a JSON dump."""
    if not os.path.exists(html_filepath):
        print(f"Error: HTML file not found - '{html_filepath}'", file=sys.stderr)
        return False

    print(f"Parsing '{html_filepath}'...")
    structured_conversations = []
    conversation_counter = 0

    try:
        with open(html_filepath, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'lxml')  # Prefer lxml if installed
    except ImportError:
        print("Warning: lxml not available, using html.parser instead.")
        try:
            with open(html_filepath, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
        except Exception as e:
            print(f"Error during initial HTML parsing: {e}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"Error during initial HTML parsing: {e}", file=sys.stderr)
        return False

    conversation_blocks = soup.select(CONVERSATION_SELECTOR)
    if not conversation_blocks or len(conversation_blocks) == 1:
        print("Warning: no distinct conversation blocks detected with the configured selector."
              " Trying to split on headings (h1/h2)...")
        potential_starts = soup.find_all(['h1', 'h2'])
        if potential_starts:
            print("Title-based grouping not implemented; falling back to a single conversation.")
            conversation_blocks = [soup.body] if soup.body else []
        else:
            print("No h1/h2 titles found. Treating the entire document as a single conversation.")
            conversation_blocks = [soup.body] if soup.body else []

    print(f"Processing {len(conversation_blocks)} conversation block(s).")

    for conv_block in conversation_blocks:
        if not conv_block:
            continue
        conversation_counter += 1

        title_element = conv_block.select_one('h1, h2')
        conv_title = title_element.get_text(strip=True) if title_element else f"Extracted Conversation #{conversation_counter}"

        current_conversation_messages = []
        message_elements = conv_block.select(MESSAGE_SELECTOR)
        print(f"  Conversation '{conv_title}': found {len(message_elements)} message element(s) with selector '{MESSAGE_SELECTOR}'.")

        if not message_elements:
            print("  No messages detected. Adjust MESSAGE_SELECTOR.")
            continue

        for msg_element in message_elements:
            role = extract_role_from_element(msg_element)

            content_element = msg_element.select_one(CONTENT_SELECTOR)
            content_text = content_element.get_text(separator="\n", strip=True) if content_element else ""

            image_filename = None
            file_link_container = msg_element.select_one(FILE_LINK_CONTAINER_SELECTOR)
            if file_link_container:
                match = FILE_LINK_REGEX.search(file_link_container.get_text())
                if match:
                    image_filename = match.group(1).strip()
                    print(f"    [File] link detected in dedicated container: {image_filename}")

            if not image_filename:
                match = FILE_LINK_REGEX.search(content_text)
                if match:
                    image_filename = match.group(1).strip()
                    print(f"    [File] link detected inside the message body: {image_filename}")

            current_conversation_messages.append({
                "role": role,
                "text": content_text,
                "image_filename": image_filename
            })

        if current_conversation_messages:
            structured_conversations.append({
                "id": conv_title.lower().replace(" ", "_") + f"_{conversation_counter}",
                "title": conv_title,
                "messages": current_conversation_messages
            })
        else:
            print(f"  No messages extracted for '{conv_title}'.")
        print("-" * 20)

    if not structured_conversations:
        print("Error: No conversation data extracted. Review the CSS selectors and HTML structure.", file=sys.stderr)
        return False

    print(f"\nExtraction complete. {len(structured_conversations)} structured conversation(s).")
    try:
        print(f"Saving data to '{output_json_filepath}'...")
        with open(output_json_filepath, 'w', encoding='utf-8') as outfile:
            json.dump(structured_conversations, outfile, indent=2, ensure_ascii=False)
        print("Save successful.")
        return True
    except IOError as e:
        print(f"Error writing '{output_json_filepath}': {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Unexpected error while writing JSON: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse chat.html to extract conversations, messages, and DALL-E image links.",
        epilog="Example: python parse_chat_html.py path/to/chat.html extracted_data.json"
    )
    parser.add_argument(
        "html_file",
        help="Path to the ChatGPT export chat.html file."
    )
    parser.add_argument(
        "output_json",
        help="Path to the output JSON file containing the extracted data."
    )

    args = parser.parse_args()

    if os.path.exists(args.output_json):
        overwrite = input(f"Output file '{args.output_json}' already exists. Overwrite? (y/N): ").lower()
        if overwrite != 'y':
            print("Operation cancelled.")
            sys.exit(0)

    success = parse_html_and_extract(args.html_file, args.output_json)

    if success:
        sys.exit(0)
    sys.exit(1)
