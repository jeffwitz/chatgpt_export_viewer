"""SQLite schema definition for the persistance layer."""
from __future__ import annotations

import sqlite3
from typing import Dict


CREATE_TABLES = (
    """
    CREATE TABLE IF NOT EXISTS exports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        folder_name TEXT UNIQUE NOT NULL,
        conversations_mtime REAL NOT NULL,
        chat_mtime REAL NOT NULL,
        last_indexed_at REAL NOT NULL,
        asset_mapping_json TEXT NOT NULL,
        file_types_json TEXT NOT NULL
    );
    """,
    """
CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        export_id INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
        conversation_id TEXT NOT NULL,
        sort_index INTEGER NOT NULL,
        title TEXT,
        raw_json TEXT NOT NULL,
        has_asset INTEGER NOT NULL DEFAULT 0,
        has_audio INTEGER NOT NULL DEFAULT 0,
        first_message_time REAL,
        last_message_time REAL,
        UNIQUE(export_id, conversation_id)
    );
    """,
)

CREATE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_conversations_export_sort ON conversations(export_id, sort_index)",
    "CREATE INDEX IF NOT EXISTS idx_conversations_export_conv ON conversations(export_id, conversation_id)",
)

FTS_TABLE = """
CREATE VIRTUAL TABLE IF NOT EXISTS conversation_search
USING fts5(
    export_id UNINDEXED,
    conversation_id UNINDEXED,
    title,
    content
);
"""


def ensure_schema(conn: sqlite3.Connection) -> Dict[str, bool]:
    """Create the schema if it does not already exist."""

    for statement in CREATE_TABLES:
        conn.executescript(statement)

    for statement in CREATE_INDEXES:
        conn.execute(statement)

    _ensure_conversation_time_columns(conn)

    fts_enabled = True
    try:
        conn.execute("SELECT count(*) FROM conversation_search LIMIT 1")
    except sqlite3.OperationalError:
        try:
            conn.executescript(FTS_TABLE)
        except sqlite3.OperationalError:
            fts_enabled = False

    return {"fts_enabled": fts_enabled}


def _ensure_conversation_time_columns(conn: sqlite3.Connection) -> None:
    """Add timestamp columns to `conversations` if missing."""

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(conversations)")
    }
    if "first_message_time" not in columns:
        conn.execute("ALTER TABLE conversations ADD COLUMN first_message_time REAL")
    if "last_message_time" not in columns:
        conn.execute("ALTER TABLE conversations ADD COLUMN last_message_time REAL")
