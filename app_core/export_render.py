"""Helpers to render conversations for print-friendly views."""
from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import quote

import markdown

CONTROL_CHARS = dict.fromkeys(range(0x00, 0x20), None)
CONTROL_CHARS.update({0x7F: None})
PRIVATE_USE_START = 0xE000
PRIVATE_USE_END = 0xF8FF

AUDIO_KEYWORDS = ("mpeg layer 3", "wave audio", "ogg data", "flac audio", "aac audio")
IMAGE_KEYWORDS = ("png image data", "jpeg image data", "gif image data", "webp image data", "svg xml", "bitmap")


@dataclass
class ConversationMessage:
    role: str
    parts: List[object]
    created_at: Optional[datetime]


def _clean_text(value: str) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = value.translate(CONTROL_CHARS)
    cleaned = "".join(ch for ch in cleaned if not PRIVATE_USE_START <= ord(ch) <= PRIVATE_USE_END)
    return cleaned


def _normalise_timestamp(raw: object) -> Optional[datetime]:
    if isinstance(raw, (int, float)):
        ts = float(raw)
    elif isinstance(raw, str):
        try:
            ts = float(raw)
        except ValueError:
            return None
    else:
        return None
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    return dt.astimezone()


def _message_parts(message: dict) -> List[object]:
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, dict):
        parts = content.get("parts")
        if isinstance(parts, list) and parts:
            return parts
        text = content.get("text")
        if isinstance(text, str) and text.strip():
            return [text]
    elif isinstance(content, list) and content:
        return list(content)
    return []


def _iter_conversation_messages(conversation: dict) -> List[ConversationMessage]:
    mapping = conversation.get("mapping") if isinstance(conversation, dict) else None
    if not isinstance(mapping, dict):
        return []

    nodes: Dict[str, dict] = {}
    root_ids: set[str] = set()
    for node_id, node_data in mapping.items():
        if not isinstance(node_id, str) or not isinstance(node_data, dict):
            continue
        message = node_data.get("message")
        if not isinstance(message, dict):
            message = None
        children = node_data.get("children") if isinstance(node_data.get("children"), list) else []
        nodes[node_id] = {
            "message": message,
            "children": [child for child in children if isinstance(child, str)],
        }
        parent = node_data.get("parent")
        if (not parent or parent == "client-created-root") and node_id != "client-created-root":
            root_ids.add(node_id)

    for node in nodes.values():
        node["children"] = [child for child in node["children"] if child in nodes]

    ordered: List[ConversationMessage] = []
    visited: set[str] = set()

    def dfs(node_id: str) -> None:
        if node_id in visited:
            return
        visited.add(node_id)
        node = nodes.get(node_id)
        if not node:
            return
        message = node.get("message")
        if isinstance(message, dict):
            role = message.get("author", {}).get("role")
            is_user_system = message.get("metadata", {}).get("is_user_system_message") is True
            if role in {"user", "assistant", "tool"} or (role == "system" and is_user_system):
                parts = _message_parts(message)
                if parts:
                    ordered.append(
                        ConversationMessage(
                            role=role or "unknown",
                            parts=parts,
                            created_at=_normalise_timestamp(message.get("create_time")),
                        )
                    )
        for child in node.get("children", []):
            dfs(child)

    roots = sorted(root_ids) if root_ids else sorted(k for k in nodes.keys() if k != "client-created-root")
    for root in roots:
        dfs(root)

    return ordered


def _classify_asset(filename: str, file_types: Dict[str, str]) -> str:
    guess = file_types.get(filename, "")
    if isinstance(guess, str):
        lowered = guess.lower()
        if lowered.startswith("image/") or any(keyword in lowered for keyword in IMAGE_KEYWORDS):
            return "image"
        if lowered.startswith("audio/") or any(keyword in lowered for keyword in AUDIO_KEYWORDS):
            return "audio"
    lower_name = filename.lower()
    if any(lower_name.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".avif", ".heic", ".heif")):
        return "image"
    if any(lower_name.endswith(ext) for ext in (".wav", ".mp3", ".ogg", ".m4a", ".aac", ".flac")):
        return "audio"
    return "file"


def _markdown_to_html(text: str) -> str:
    return markdown.markdown(
        text,
        extensions=[
            "markdown.extensions.extra",
            "markdown.extensions.sane_lists",
            "markdown.extensions.fenced_code",
        ],
        output_format="html5",
    )


def _part_to_html(
    part: object,
    asset_mapping: Dict[str, str],
    file_types: Dict[str, str],
    asset_base_url: str,
) -> str:
    if isinstance(part, str):
        cleaned = _clean_text(part).strip()
        if not cleaned:
            return ""
        return _markdown_to_html(cleaned)

    if isinstance(part, dict):
        pointer = part.get("asset_pointer")
        if isinstance(pointer, str):
            filename = asset_mapping.get(pointer)
            if filename:
                kind = _classify_asset(filename, file_types)
                safe_name = _clean_text(filename)
                encoded = quote(filename)
                url = f"{asset_base_url}/{encoded}"
                if kind == "image":
                    return (
                        "<div class=\"asset-block image-block\">"
                        f"<img src=\"{url}\" alt=\"{html.escape(safe_name)}\" />"
                        f"<p class=\"asset-caption\">Image: {html.escape(safe_name)}</p>"
                        "</div>"
                    )
                if kind == "audio":
                    return (
                        "<div class=\"asset-block audio-block\">"
                        f"<audio controls preload=\"metadata\" src=\"{url}\"></audio>"
                        f"<p class=\"asset-caption\">Audio: {html.escape(safe_name)}</p>"
                        "</div>"
                    )
                return (
                    "<p class=\"asset-link\">"
                    f"<a href=\"{url}\" target=\"_blank\" rel=\"noopener\">File: {html.escape(safe_name)}</a>"
                    "</p>"
                )
            return f"<p><em>Missing attachment: {html.escape(pointer)}</em></p>"

        if part.get("content_type") == "code" and isinstance(part.get("text"), str):
            language = _clean_text(part.get("language") or "")
            body = _clean_text(part.get("text", ""))
            escaped = html.escape(body)
            class_attr = f"language-{language}" if language else ""
            return f"<pre><code class=\"{class_attr}\">{escaped}</code></pre>"

        if isinstance(part.get("text"), str):
            cleaned = _clean_text(part["text"]).strip()
            if cleaned:
                return _markdown_to_html(cleaned)

    return ""


def build_print_messages(
    conversation: dict,
    *,
    asset_mapping: Dict[str, str],
    file_types: Dict[str, str],
    asset_base_url: str,
) -> List[dict]:
    messages = []
    for message in _iter_conversation_messages(conversation):
        parts_html = [
            fragment
            for fragment in (
                _part_to_html(part, asset_mapping, file_types, asset_base_url)
                for part in message.parts
            )
            if fragment
        ]
        created_at = message.created_at
        messages.append(
            {
                "role": message.role or "unknown",
                "role_label": (message.role or "unknown").upper(),
                "content_html": "\n".join(parts_html) if parts_html else "<p><em>Empty message</em></p>",
                "created_at_display": created_at.strftime("%Y-%m-%d %H:%M:%S %Z") if created_at else "",
                "created_at_iso": created_at.isoformat() if created_at else "",
            }
        )
    return messages
