"""Persistence orchestration for ChatGPT export ingestion."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import sqlite3

from .parsing import (
    ExportData,
    collect_export_data,
    conversation_has_asset,
    conversation_has_audio,
    conversation_time_bounds,
    extract_text_from_conversation,
)


@dataclass(slots=True)
class ExportSnapshot:
    conversations: List[dict]
    asset_mapping: Dict[str, str]
    file_types: Dict[str, str]
    export_id: int


class ExportNotFoundError(FileNotFoundError):
    """Raised when the requested export folder or files are missing."""


def _stat_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except FileNotFoundError as exc:
        raise ExportNotFoundError(str(exc)) from exc


def ensure_export(
    conn: sqlite3.Connection,
    base_directory: str,
    folder_name: str,
    *,
    fts_enabled: bool = True,
) -> ExportSnapshot:
    """Ensure the export data is present and up to date in SQLite."""

    folder_path = os.path.join(base_directory, folder_name)
    conversations_path = os.path.join(folder_path, "conversations.json")
    chat_path = os.path.join(folder_path, "chat.html")

    conversations_mtime = _stat_mtime(conversations_path)
    chat_mtime = _stat_mtime(chat_path)

    row = conn.execute(
        "SELECT * FROM exports WHERE folder_name = ?",
        (folder_name,),
    ).fetchone()

    if row and row["conversations_mtime"] == conversations_mtime and row["chat_mtime"] == chat_mtime:
        return _load_snapshot(conn, row["id"])

    export_data = collect_export_data(folder_path)
    export_id = _persist_export(
        conn,
        folder_name,
        conversations_mtime,
        chat_mtime,
        export_data,
        fts_enabled=fts_enabled,
    )
    return ExportSnapshot(
        conversations=export_data.conversations,
        asset_mapping=export_data.asset_mapping,
        file_types=export_data.file_types,
        export_id=export_id,
    )


def _persist_export(
    conn: sqlite3.Connection,
    folder_name: str,
    conversations_mtime: float,
    chat_mtime: float,
    export_data: ExportData,
    *,
    fts_enabled: bool,
) -> int:
    """Store the export content into SQLite."""

    now = time.time()
    asset_json = json.dumps(export_data.asset_mapping, ensure_ascii=False)
    file_types_json = json.dumps(export_data.file_types, ensure_ascii=False)

    cursor = conn.execute(
        "SELECT id FROM exports WHERE folder_name = ?",
        (folder_name,),
    )
    existing = cursor.fetchone()

    if existing:
        export_id = existing["id"]
        conn.execute(
            """
            UPDATE exports
               SET conversations_mtime = ?,
                   chat_mtime = ?,
                   last_indexed_at = ?,
                   asset_mapping_json = ?,
                   file_types_json = ?
             WHERE id = ?
            """,
            (conversations_mtime, chat_mtime, now, asset_json, file_types_json, export_id),
        )
        conn.execute("DELETE FROM conversations WHERE export_id = ?", (export_id,))
        if fts_enabled:
            conn.execute("DELETE FROM conversation_search WHERE export_id = ?", (export_id,))
    else:
        cursor = conn.execute(
            """
            INSERT INTO exports (folder_name, conversations_mtime, chat_mtime, last_indexed_at, asset_mapping_json, file_types_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (folder_name, conversations_mtime, chat_mtime, now, asset_json, file_types_json),
        )
        export_id = cursor.lastrowid

    _bulk_insert_conversations(conn, export_id, export_data, fts_enabled=fts_enabled)
    return int(export_id)


def _conversation_flags(conversation: dict, asset_mapping: Dict[str, str], file_types: Dict[str, str]) -> Tuple[int, int]:
    has_asset = 1 if conversation_has_asset(conversation) else 0
    has_audio = 1 if conversation_has_audio(conversation, asset_mapping, file_types) else 0
    return has_asset, has_audio


def _bulk_insert_conversations(
    conn: sqlite3.Connection,
    export_id: int,
    export_data: ExportData,
    *,
    fts_enabled: bool,
) -> None:
    payload: List[Tuple[int, str, int, str, str, int, int, Optional[float], Optional[float]]] = []
    fts_rows: List[Tuple[int, str, str, str]] = []

    for sort_index, conversation in enumerate(export_data.conversations):
        conversation_id = conversation.get("conversation_id") or conversation.get("id")
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            continue

        conversation_id = conversation_id.strip()
        title = conversation.get("title") if isinstance(conversation.get("title"), str) else None
        raw_json = json.dumps(conversation, ensure_ascii=False)
        has_asset, has_audio = _conversation_flags(conversation, export_data.asset_mapping, export_data.file_types)
        first_ts, last_ts = conversation_time_bounds(conversation)
        payload.append((
            export_id,
            conversation_id,
            sort_index,
            title,
            raw_json,
            has_asset,
            has_audio,
            first_ts,
            last_ts,
        ))

        text_content = extract_text_from_conversation(conversation)
        if fts_enabled and text_content:
            fts_rows.append((export_id, conversation_id, title or "[Sans Titre]", text_content))

    conn.executemany(
        """
        INSERT INTO conversations (
            export_id,
            conversation_id,
            sort_index,
            title,
            raw_json,
            has_asset,
            has_audio,
            first_message_time,
            last_message_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        payload,
    )

    if fts_enabled and fts_rows:
        conn.executemany(
            """
            INSERT INTO conversation_search (export_id, conversation_id, title, content)
            VALUES (?, ?, ?, ?)
            """,
            fts_rows,
        )


def _ensure_conversation_time_data(conn: sqlite3.Connection, export_id: int) -> None:
    """Populate missing first/last message timestamps for stored conversations."""

    cursor = conn.execute(
        """
        SELECT conversation_id, raw_json
          FROM conversations
         WHERE export_id = ?
           AND (first_message_time IS NULL OR last_message_time IS NULL)
        """,
        (export_id,),
    )

    updates: List[Tuple[Optional[float], Optional[float], int, str]] = []
    for row in cursor.fetchall():
        try:
            conversation = json.loads(row["raw_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        first_ts, last_ts = conversation_time_bounds(conversation)
        updates.append((first_ts, last_ts, export_id, row["conversation_id"]))

    if updates:
        conn.executemany(
            """
            UPDATE conversations
               SET first_message_time = ?,
                   last_message_time = ?
             WHERE export_id = ?
               AND conversation_id = ?
            """,
            updates,
        )
        conn.commit()


def _load_snapshot(conn: sqlite3.Connection, export_id: int) -> ExportSnapshot:
    row = conn.execute(
        "SELECT folder_name, asset_mapping_json, file_types_json FROM exports WHERE id = ?",
        (export_id,),
    ).fetchone()
    if row is None:
        raise ExportNotFoundError(f"Export id {export_id} not found in database")

    conversations_rows = conn.execute(
        """
        SELECT conversation_id, raw_json
          FROM conversations
         WHERE export_id = ?
         ORDER BY sort_index ASC
        """,
        (export_id,),
    ).fetchall()

    conversations = [json.loads(row["raw_json"]) for row in conversations_rows]
    asset_mapping = json.loads(row["asset_mapping_json"]) if row["asset_mapping_json"] else {}
    file_types = json.loads(row["file_types_json"]) if row["file_types_json"] else {}

    return ExportSnapshot(
        conversations=conversations,
        asset_mapping=asset_mapping,
        file_types=file_types,
        export_id=export_id,
    )


def search_conversations(
    conn: sqlite3.Connection,
    export_id: int,
    query: str,
    *,
    fts_enabled: bool,
    start_ts: Optional[float] = None,
    end_ts: Optional[float] = None,
    limit: int = 100,
) -> List[Dict[str, str]]:
    if not fts_enabled:
        raise RuntimeError("Full-text search disabled (SQLite FTS5 unavailable)")

    if start_ts is not None or end_ts is not None:
        _ensure_conversation_time_data(conn, export_id)

    sql = [
        """
        SELECT conversation_search.conversation_id, conversation_search.title
          FROM conversation_search
          JOIN conversations AS c
            ON c.export_id = conversation_search.export_id
           AND c.conversation_id = conversation_search.conversation_id
         WHERE conversation_search.export_id = ?
           AND conversation_search MATCH ?
        """
    ]
    params: List[object] = [export_id, query]

    if start_ts is not None:
        sql.append("  AND c.first_message_time IS NOT NULL AND c.first_message_time >= ?")
        params.append(start_ts)
    if end_ts is not None:
        sql.append("  AND c.last_message_time IS NOT NULL AND c.last_message_time <= ?")
        params.append(end_ts)

    sql.append("  LIMIT ?")
    params.append(limit)

    cursor = conn.execute("\n".join(sql), params)
    return [{"id": row["conversation_id"], "title": row["title"]} for row in cursor.fetchall()]
