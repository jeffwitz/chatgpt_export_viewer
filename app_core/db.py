"""Database helpers for the ChatGPT export viewer."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional


DEFAULT_DB_FILENAME = "app_data.db"


def get_database_path(base_directory: str, filename: str = DEFAULT_DB_FILENAME) -> str:
    """Return the absolute path to the SQLite database file."""

    return str(Path(base_directory).joinpath(filename))


def connect(db_path: str) -> sqlite3.Connection:
    """Create a SQLite connection with sensible defaults."""

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


@contextmanager
def connection_scope(db_path: str) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_parent_directory(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

