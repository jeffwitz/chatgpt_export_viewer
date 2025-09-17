"""Flask application serving ChatGPT exports with SQLite persistence."""
from __future__ import annotations

import os
from typing import Dict, List

from flask import (
    Flask,
    abort,
    jsonify,
    render_template,
    request,
    send_from_directory,
)

from app_core import db as db_core
from app_core import ingest as ingest_core
from app_core import schema as schema_core

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_BASE_DIR = BASE_DIR
DB_PATH = db_core.get_database_path(BASE_DIR)
# Folders that should never be treated as ChatGPT exports. Keep in sync with README.
IGNORED_FOLDERS = {"static", "templates", "__pycache__", "venv", ".indexdir"}

# Ensure the database directory exists and initialise the schema once at import.
db_core.ensure_parent_directory(DB_PATH)
with db_core.connection_scope(DB_PATH) as _conn:
    SCHEMA_INFO = schema_core.ensure_schema(_conn)
    FTS_ENABLED = SCHEMA_INFO.get("fts_enabled", False)


def get_export_folders() -> List[str]:
    """Locate export folders containing the expected files."""

    folders: List[str] = []
    print(f"\nSearching for export folders in: {EXPORT_BASE_DIR}")
    try:
        for entry in os.listdir(EXPORT_BASE_DIR):
            entry_path = os.path.join(EXPORT_BASE_DIR, entry)
            if not os.path.isdir(entry_path) or entry.startswith("."):
                continue
            if entry in IGNORED_FOLDERS:
                continue
            conversations_path = os.path.join(entry_path, "conversations.json")
            chat_path = os.path.join(entry_path, "chat.html")
            if os.path.exists(conversations_path) and os.path.exists(chat_path):
                folders.append(entry)
                print(f"  + Found valid: {entry}")
            else:
                print(f"  - Skipping '{entry}': missing files")
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"ERROR listing folders: {exc}")

    try:
        folders.sort(key=lambda name: name.replace("-", "").replace("_", ""), reverse=True)
    except Exception:
        folders.sort()
    print(f"Final list of folders: {folders}")
    return folders


def _validate_folder_name(folder_name: str | None) -> str:
    if not folder_name or ".." in folder_name or folder_name.startswith("/"):
        # Explicitly reject suspicious names before touching the filesystem.
        abort(400)
    safe_path = os.path.abspath(os.path.join(EXPORT_BASE_DIR, folder_name))
    if not safe_path.startswith(os.path.abspath(EXPORT_BASE_DIR)):
        abort(403)
    if not os.path.isdir(safe_path):
        abort(404)
    return folder_name


@app.route("/")
def index_route():
    folders = get_export_folders()
    return render_template("index.html", folders=folders)


@app.route("/conversations")
def get_conversations_route():
    folder_name = _validate_folder_name(request.args.get("folder_name"))
    print(f"\n{'=' * 10} Processing request for folder: {folder_name} {'=' * 10}")

    try:
        with db_core.connection_scope(DB_PATH) as conn:
            # ensure_export() compares mtimes and only re-parses the raw files when
            # necessary, otherwise the data comes straight from SQLite.
            snapshot = ingest_core.ensure_export(
                conn,
                EXPORT_BASE_DIR,
                folder_name,
                fts_enabled=FTS_ENABLED,
            )
            response_data: Dict[str, object] = {
                "conversations": snapshot.conversations,
                "asset_mapping": snapshot.asset_mapping,
                "file_types": snapshot.file_types,
            }
    except ingest_core.ExportNotFoundError as exc:
        print(f"ERROR reading export: {exc}")
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"ERROR while processing export '{folder_name}': {exc}")
        return jsonify({"error": f"Failed to process export: {exc}"}), 500

    print(f"Step 9: Sending response.")
    print(f"{'=' * 10} Finished request for {folder_name} {'=' * 10}\n")
    return jsonify(response_data)


def _ensure_export_id(conn, folder_name: str) -> int:
    """Return the export id, refreshing the DB if the source changed."""

    export_row = conn.execute(
        "SELECT id, conversations_mtime, chat_mtime FROM exports WHERE folder_name = ?",
        (folder_name,),
    ).fetchone()

    conversations_path = os.path.join(EXPORT_BASE_DIR, folder_name, "conversations.json")
    chat_path = os.path.join(EXPORT_BASE_DIR, folder_name, "chat.html")

    try:
        conversations_mtime = os.path.getmtime(conversations_path)
        chat_mtime = os.path.getmtime(chat_path)
    except FileNotFoundError as exc:
        raise ingest_core.ExportNotFoundError(str(exc)) from exc

    if export_row and export_row["conversations_mtime"] == conversations_mtime and export_row["chat_mtime"] == chat_mtime:
        return int(export_row["id"])

    snapshot = ingest_core.ensure_export(
        conn,
        EXPORT_BASE_DIR,
        folder_name,
        fts_enabled=FTS_ENABLED,
    )
    return snapshot.export_id


@app.route("/search")
def search_conversations():
    if not FTS_ENABLED:
        return jsonify({"error": "Search unavailable (SQLite FTS5 missing)."}), 501

    folder_name = _validate_folder_name(request.args.get("folder_name"))
    query_string = request.args.get("query")
    if not query_string:
        return jsonify({"error": "Missing query"}), 400

    print(f"\n{'=' * 10} Processing SEARCH: Folder={folder_name}, Query='{query_string}' {'=' * 10}")

    try:
        with db_core.connection_scope(DB_PATH) as conn:
            export_id = _ensure_export_id(conn, folder_name)
            results = ingest_core.search_conversations(
                conn,
                export_id,
                query_string,
                fts_enabled=FTS_ENABLED,
            )
    except ingest_core.ExportNotFoundError:
        return jsonify({"error": "Folder not found"}), 404
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 501
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"ERROR during search: {exc}")
        return jsonify({"error": f"Search error: {exc}"}), 500

    print(f"Search OK. Returning {len(results)} results.")
    print(f"{'=' * 10} Finished SEARCH {'=' * 10}\n")
    return jsonify(results)


@app.route("/export_files/<path:folder_name>/<path:filepath>")
def serve_export_file(folder_name: str, filepath: str):
    print(f"Request for export file: folder='{folder_name}', filepath='{filepath}'")
    if not folder_name or ".." in folder_name or folder_name.startswith("/"):
        abort(400)
    if not filepath or ".." in filepath or filepath.startswith("/"):
        abort(400)

    safe_directory = os.path.abspath(os.path.join(EXPORT_BASE_DIR, folder_name))
    if not safe_directory.startswith(os.path.abspath(EXPORT_BASE_DIR)):
        abort(403)
    if not os.path.isdir(safe_directory):
        abort(404)

    requested_path = os.path.abspath(os.path.join(safe_directory, filepath))
    if not requested_path.startswith(safe_directory):
        abort(403)

    print(f"Attempting to serve '{filepath}' from '{safe_directory}'")
    try:
        return send_from_directory(safe_directory, filepath, as_attachment=False)
    except FileNotFoundError:
        print("Error: File not found.")
        try:
            actual_filename = next(
                (entry for entry in os.listdir(safe_directory) if entry.lower() == filepath.lower()),
                None,
            )
        except OSError:
            actual_filename = None
        if actual_filename:
            print(f"  Found case-insensitive: '{actual_filename}'.")
            return send_from_directory(safe_directory, actual_filename)
        abort(404)
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"Error serving file: {exc}")
        abort(500)


@app.route("/static/<path:filename>")
def serve_static(filename: str):
    static_dir = os.path.join(BASE_DIR, "static")
    return send_from_directory(static_dir, filename)


if __name__ == "__main__":
    print("Starting Flask server...")
    print(f"SQLite path: {DB_PATH}")
    print(f"FTS enabled: {FTS_ENABLED}")
    app.run(debug=True, host="0.0.0.0", port=5001, use_reloader=True)
