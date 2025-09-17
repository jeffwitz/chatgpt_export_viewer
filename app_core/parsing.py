"""Parsing helpers extracted from the legacy Flask route.

The goal is to preserve the existing parsing behaviour while making
it reusable from the persistence layer.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

# --- python-magic initialisation (copied from the original app.py) ---
try:
    import magic  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    magic = None  # type: ignore

def _initialise_magic() -> Optional["magic.Magic"]:  # type: ignore[name-defined]
    if magic is None:
        print("WARN: python-magic not found.")
        return None

    try:
        if sys.platform == "win32":
            instance = magic.Magic(mime=True)  # type: ignore[attr-defined]
            print("INFO: magic init OK (Win default).")
            return instance
        instance = magic.Magic(mime=True)  # type: ignore[attr-defined]
        print("INFO: magic init OK (Linux/macOS).")
        return instance
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"WARN: magic init FAILED: {exc}")
        return None


MAGIC_INSTANCE = _initialise_magic()


@dataclass(slots=True)
class ExportData:
    """Container with the structures expected by the front-end."""

    conversations: List[dict]
    asset_mapping: Dict[str, str]
    file_types: Dict[str, str]
    required_pointers: Set[str]


def extract_asset_pointers(conversations_data: Sequence[dict]) -> Set[str]:
    """Extract the ``asset_pointer`` identifiers referenced in conversations."""

    pointers: Set[str] = set()
    if not isinstance(conversations_data, list):
        return pointers

    print(f"  Scanning {len(conversations_data)} conversations for asset pointers...")
    for conv in conversations_data:
        if not isinstance(conv, dict):
            continue
        mapping = conv.get("mapping")
        if not isinstance(mapping, dict):
            continue

        for node_data in mapping.values():
            if not isinstance(node_data, dict):
                continue
            message = node_data.get("message")
            if not isinstance(message, dict):
                continue

            parts_to_check: List[object] = []
            content = message.get("content")
            if isinstance(content, dict):
                parts = content.get("parts")
                if isinstance(parts, list):
                    parts_to_check.extend(parts)

            if message.get("author", {}).get("role") == "tool":
                metadata = message.get("metadata")
                if isinstance(metadata, dict):
                    agg_message = metadata.get("aggregate_result", {}).get("message", {})
                    if isinstance(agg_message, dict):
                        agg_content = agg_message.get("content")
                        if isinstance(agg_content, dict):
                            agg_parts = agg_content.get("parts")
                            if isinstance(agg_parts, list):
                                parts_to_check.extend(agg_parts)

            for part in parts_to_check:
                if isinstance(part, dict) and "asset_pointer" in part:
                    pointer = part["asset_pointer"]
                    if isinstance(pointer, str) and pointer.strip():
                        pointers.add(pointer.strip())

    print(f"  Scan complete. Found {len(pointers)} unique pointers.")
    return pointers


def get_file_mime_type(file_path: str) -> str:
    """Return a MIME type for ``file_path`` using python-magic when available."""

    fallback = "application/octet-stream"
    filename = os.path.basename(file_path)

    if MAGIC_INSTANCE is not None:
        try:
            detected = MAGIC_INSTANCE.from_file(file_path)  # type: ignore[attr-defined]
            if filename.lower().endswith(".dat"):
                print(f"\n    [MAGIC DEBUG for .dat] File: '{filename}' -> Detected: '{detected}'")
            if detected:
                return detected.split(";")[0].strip()
        except Exception as exc:
            print(f"    WARN: magic error for {filename}: {exc}")
    else:
        if filename.lower().endswith(".dat"):
            print(f"\n    [MIMETYPES DEBUG for .dat] File: '{filename}' (magic unavailable)")

    try:
        guessed, _ = mimetypes.guess_type(file_path)
        if filename.lower().endswith(".dat"):
            print(f"    [MIMETYPES DEBUG for .dat] File: '{filename}' -> Guessed: '{guessed}'")
        if guessed:
            return guessed
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"    WARN: mimetypes error for {filename}: {exc}")

    return fallback


def extract_assets_json_only_from_html(html_content: str) -> Optional[Dict[str, str]]:
    """Extract the ``assetsJson`` object from the export ``chat.html``."""

    variable_name = "assetsJson"
    start_delimiter, end_delimiter = "{", "}"

    print(f"--- Attempting to extract variable '{variable_name}' from HTML ---")
    pattern = re.compile(
        rf"\b{variable_name}\b\s*=\s*({start_delimiter}[\s\S]*?{end_delimiter})\s*;?",
        re.IGNORECASE,
    )
    match = pattern.search(html_content)
    separator = "-" * (len(variable_name) + 32)

    if not match:
        print(f"  ERROR: Pattern '{variable_name} = {{...}}' not found.")
        print(separator)
        return None

    json_string = match.group(1).strip()
    print(f"  SUCCESS: Found pattern. Length: {len(json_string)}")

    try:
        parsed_data = json.loads(json_string)
    except json.JSONDecodeError as exc:
        print(f"  ERROR: JSON decode failed: {exc}")
        print(separator)
        return None
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"  ERROR: Unexpected parsing error: {exc}")
        print(separator)
        return None

    if not isinstance(parsed_data, dict):
        print("  ERROR: Parsed data not dict.")
        print(separator)
        return None

    print(f"  SUCCESS: Parsed '{variable_name}' as dict.")
    print(separator)
    return parsed_data


def extract_text_from_conversation(conv_data: dict) -> str:
    """Build a flattened text representation for full-text indexing."""

    collected: List[str] = []
    if not isinstance(conv_data, dict):
        return ""

    title = conv_data.get("title")
    if isinstance(title, str):
        collected.append(title)

    mapping = conv_data.get("mapping")
    if not isinstance(mapping, dict):
        return " ".join(collected).strip()

    for node_data in mapping.values():
        if not isinstance(node_data, dict):
            continue
        message = node_data.get("message")
        if not isinstance(message, dict):
            continue

        parts: List[object] = []
        content = message.get("content")
        if isinstance(content, dict):
            raw_parts = content.get("parts")
            if isinstance(raw_parts, list):
                parts.extend(raw_parts)

        if message.get("author", {}).get("role") == "tool":
            metadata = message.get("metadata")
            if isinstance(metadata, dict):
                agg_message = metadata.get("aggregate_result", {}).get("message", {})
                if isinstance(agg_message, dict):
                    agg_content = agg_message.get("content")
                    if isinstance(agg_content, dict):
                        agg_parts = agg_content.get("parts")
                        if isinstance(agg_parts, list):
                            parts.extend(agg_parts)

        for part in parts:
            text_content: Optional[str] = None
            if isinstance(part, str):
                text_content = part
            elif isinstance(part, dict):
                if isinstance(part.get("text"), str):
                    text_content = part["text"]
                elif part.get("content_type") == "code" and isinstance(part.get("text"), str):
                    text_content = part["text"]

            if isinstance(text_content, str):
                collected.append(text_content)

    flattened = re.sub(r"\s+", " ", " ".join(collected)).strip()
    return flattened


def load_conversations_json(conversations_json_path: str) -> List[dict]:
    """Read the ``conversations.json`` file and return the list of conversations."""

    print(f"Step 1: Reading conversations: {conversations_json_path}")
    with open(conversations_json_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("conversations.json is not a list")
    print(f"  Read {len(data)} items.")
    print("Step 1 OK.")
    return data


def load_asset_mapping(chat_html_path: str) -> Dict[str, str]:
    """Extract the assets mapping from ``chat.html`` if the file exists."""

    print(f"Step 2: Reading HTML for mapping: {chat_html_path}")
    mapping: Dict[str, str] = {}
    if not os.path.exists(chat_html_path):
        print("WARN: chat.html not found.")
        print("Step 2 OK. Mapping contains 0 items.")
        return mapping

    with open(chat_html_path, "r", encoding="utf-8") as handle:
        html_content = handle.read()

    extracted_mapping = extract_assets_json_only_from_html(html_content)
    if extracted_mapping:
        mapping = extracted_mapping
    else:
        print("WARN: Failed extraction 'assetsJson'.")

    print(f"Step 2 OK. Mapping contains {len(mapping)} items.")
    return mapping


def load_file_types_map(file_types_path: str) -> Dict[str, str]:
    """Load the cached ``file_type.json`` file if it exists."""

    print("Step 6: Loading/Initializing file types map...")
    file_types: Dict[str, str] = {}

    if not os.path.exists(file_types_path):
        print("  INFO: file_type.json not found.")
        print("Step 6 OK.")
        return file_types

    try:
        with open(file_types_path, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except Exception as exc:
        print(f"  WARN: Error reading file_type.json: {exc}.")
        print("Step 6 OK.")
        return file_types

    if isinstance(loaded, dict):
        file_types = loaded
        print(f"  Loaded {len(file_types)} types.")
    else:
        print("  WARN: file_type.json not dict.")

    print("Step 6 OK.")
    return file_types


def detect_file_types(export_folder_path: str, asset_mapping: Dict[str, str], file_types: Dict[str, str]) -> Tuple[Dict[str, str], bool]:
    """Update ``file_types`` with MIME hints for the files referenced by the export."""

    print("Step 7: Identifying/Updating file types...")
    updated = False
    target_filenames = set(asset_mapping.values())

    if not target_filenames:
        print("  No target files.")
        print("Step 7 OK.")
        return file_types, updated

    print(f"  Checking types for {len(target_filenames)} filenames...")
    for index, filename in enumerate(target_filenames, start=1):
        if not isinstance(filename, str) or not filename.strip():
            continue

        current_type = file_types.get(filename)
        if isinstance(current_type, str) and current_type not in {
            "File not found",
            "Is Directory",
            "Error checking type",
            "Not a file or directory",
        }:
            continue

        file_path = os.path.join(export_folder_path, filename)
        print(f"    ({index}/{len(target_filenames)}) Checking: {filename}", end="")

        try:
            if os.path.exists(file_path):
                if os.path.isfile(file_path):
                    detected_type = get_file_mime_type(file_path)
                    print(f" -> Type: {detected_type}")
                elif os.path.isdir(file_path):
                    detected_type = "Is Directory"
                    print(" -> Is Directory.")
                else:
                    detected_type = "Not a file or directory"
                    print(" -> Not file/dir.")
            else:
                detected_type = "File not found"
                print(" -> Not found.")
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f" -> ERROR checking file: {exc}")
            detected_type = "Error checking type"

        if current_type != detected_type:
            file_types[filename] = detected_type
            updated = True

    print("Step 7 OK.")
    return file_types, updated


def save_file_types_map(file_types_path: str, file_types: Dict[str, str], updated: bool) -> None:
    """Persist ``file_types`` back to ``file_type.json`` if updated."""

    if not updated:
        print("Step 8: No file type updates.")
        return

    print("Step 8: Saving updated file types...")
    try:
        with open(file_types_path, "w", encoding="utf-8") as handle:
            json.dump(file_types, handle, indent=2, ensure_ascii=False)
        print("  Successfully saved.")
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"  ERROR saving: {exc}")


def log_file_types_preview(file_types: Dict[str, str]) -> None:
    print("DEBUG [Step 9]: Final file_types being sent:")
    log_count = 0
    displayed_dat = False
    for filename, mime in file_types.items():
        is_dat = ".dat" in filename.lower()
        if is_dat or log_count < 5:
            print(f"  '{filename}': '{mime}'")
            if is_dat:
                displayed_dat = True
        log_count += 1
        if log_count >= 15:
            if len(file_types) > 15:
                print("  ...")
            break
    if not displayed_dat and any(".dat" in name.lower() for name in file_types):
        print("  (More types exist, including other .dat files not shown)")


def conversation_has_asset(conversation: dict) -> bool:
    """Return ``True`` if at least one message references an ``asset_pointer``."""
    mapping = conversation.get("mapping") if isinstance(conversation, dict) else None
    if not isinstance(mapping, dict):
        return False

    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        message = node.get("message")
        if not isinstance(message, dict):
            continue

        parts = message.get("content", {}).get("parts") if isinstance(message.get("content"), dict) else None
        if isinstance(parts, list) and any(isinstance(part, dict) and part.get("asset_pointer") for part in parts):
            return True

        if message.get("author", {}).get("role") == "tool":
            metadata = message.get("metadata")
            if isinstance(metadata, dict):
                aggregate = metadata.get("aggregate_result", {}).get("message", {})
                if isinstance(aggregate, dict):
                    agg_parts = aggregate.get("content", {}).get("parts") if isinstance(aggregate.get("content"), dict) else None
                    if isinstance(agg_parts, list) and any(isinstance(part, dict) and part.get("asset_pointer") for part in agg_parts):
                        return True

    return False


def conversation_has_audio(
    conversation: dict,
    asset_mapping: Dict[str, str],
    file_types: Dict[str, str],
) -> bool:
    """Detect audio assets by MIME type or file extension heuristics."""
    mapping = conversation.get("mapping") if isinstance(conversation, dict) else None
    if not isinstance(mapping, dict):
        return False

    audio_ext_pattern = re.compile(r"\.(wav|mp3|ogg|m4a|aac|flac)$", re.IGNORECASE)

    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        message = node.get("message")
        if not isinstance(message, dict):
            continue

        content = message.get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            continue

        for part in parts:
            if not isinstance(part, dict):
                continue
            pointer = part.get("asset_pointer")
            if not isinstance(pointer, str):
                continue
            filename = asset_mapping.get(pointer)
            if not filename:
                continue
            mime_guess = file_types.get(filename, "")
            if isinstance(mime_guess, str):
                lowered = mime_guess.lower()
                if lowered.startswith("audio/") or any(keyword in lowered for keyword in [
                    "mpeg layer 3",
                    "wave audio",
                    "ogg data",
                    "flac audio",
                    "aac audio",
                ]):
                    return True
            if audio_ext_pattern.search(filename):
                return True

    return False


def collect_export_data(export_folder_path: str) -> ExportData:
    """Reproduce the legacy steps to gather export information."""

    conversations_json_path = os.path.join(export_folder_path, "conversations.json")
    chat_html_path = os.path.join(export_folder_path, "chat.html")
    file_types_path = os.path.join(export_folder_path, "file_type.json")

    conversations = load_conversations_json(conversations_json_path)
    asset_mapping = load_asset_mapping(chat_html_path)

    required_pointers = extract_asset_pointers(conversations)
    mapped_pointers = set(asset_mapping.keys())
    print("Step 5: Verifying mapping...")
    missing = required_pointers - mapped_pointers
    if missing:
        print(f"  WARN: {len(missing)} pointers MISSING.")
    else:
        print("  INFO: Pointers OK.")
    print("Step 5 OK.")

    file_types = load_file_types_map(file_types_path)
    file_types, updated = detect_file_types(export_folder_path, asset_mapping, file_types)
    save_file_types_map(file_types_path, file_types, updated)
    log_file_types_preview(file_types)

    return ExportData(
        conversations=conversations,
        asset_mapping=asset_mapping,
        file_types=file_types,
        required_pointers=required_pointers,
    )
