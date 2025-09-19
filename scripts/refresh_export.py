#!/usr/bin/env python3
"""Force the ingestion of an export folder into the SQLite database."""
from __future__ import annotations

import argparse
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))

sys.path.insert(0, PROJECT_ROOT)

from app_core import db as db_core
from app_core import ingest as ingest_core
from app_core import schema as schema_core

DB_PATH = db_core.get_database_path(PROJECT_ROOT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", help="Name of the export folder to ingest")
    args = parser.parse_args(argv)

    folder = args.folder
    folder_path = os.path.join(PROJECT_ROOT, folder)
    if not os.path.isdir(folder_path):
        parser.error(f"Folder '{folder}' was not found under {PROJECT_ROOT}")

    db_core.ensure_parent_directory(DB_PATH)
    with db_core.connection_scope(DB_PATH) as conn:
        info = schema_core.ensure_schema(conn)
        fts_enabled = info.get("fts_enabled", False)
        snapshot = ingest_core.ensure_export(conn, PROJECT_ROOT, folder, fts_enabled=fts_enabled)
        print(
            f"Ingestion finished for '{folder}'. Conversations: {len(snapshot.conversations)} | "
            f"Assets: {len(snapshot.asset_mapping)} | FTS: {'OK' if fts_enabled else 'disabled'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
