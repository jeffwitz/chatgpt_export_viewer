"""Flask application serving ChatGPT exports with SQLite persistence."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from typing import Dict, List

from flask import (
    Flask,
    abort,
    jsonify,
    render_template,
    request,
    send_from_directory,
)
from werkzeug.utils import secure_filename

from app_core import db as db_core
from app_core import ingest as ingest_core
from app_core import schema as schema_core

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_BASE_DIR = BASE_DIR
APP_DATA_DIR = os.path.join(BASE_DIR, "app_data")
EXPORT_LOCATIONS_FILE = os.path.join(APP_DATA_DIR, "export_locations.json")
UPLOAD_TMP_DIR = os.path.join(APP_DATA_DIR, "tmp_uploads")
DB_PATH = db_core.get_database_path(BASE_DIR)
# Folders that should never be treated as ChatGPT exports. Keep in sync with README.
IGNORED_FOLDERS = {"static", "templates", "__pycache__", "venv", ".indexdir", "app_data"}

# Ensure the database directory exists and initialise the schema once at import.
db_core.ensure_parent_directory(DB_PATH)
with db_core.connection_scope(DB_PATH) as _conn:
    SCHEMA_INFO = schema_core.ensure_schema(_conn)
    FTS_ENABLED = SCHEMA_INFO.get("fts_enabled", False)


def _load_export_locations() -> Dict[str, str]:
    if not os.path.exists(EXPORT_LOCATIONS_FILE):
        return {}
    try:
        with open(EXPORT_LOCATIONS_FILE, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"WARN: failed to read export locations ({exc})")
        return {}

    data = raw.get("exports") if isinstance(raw, dict) else None
    if not isinstance(data, dict):
        print("WARN: export locations file has unexpected structure")
        return {}

    cleaned: Dict[str, str] = {}
    for name, path in data.items():
        if isinstance(name, str) and isinstance(path, str) and name:
            cleaned[name] = path
    return cleaned


def _save_export_locations(locations: Dict[str, str]) -> None:
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    payload = {"exports": locations}
    with open(EXPORT_LOCATIONS_FILE, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _build_export_registry() -> Dict[str, str]:
    registry: Dict[str, str] = {}
    stored = _load_export_locations()
    for name, path in stored.items():
        registry[name] = os.path.abspath(path)

    base_abs = os.path.abspath(EXPORT_BASE_DIR)
    try:
        for entry in os.listdir(base_abs):
            if entry.startswith(".") or entry in IGNORED_FOLDERS:
                continue
            entry_path = os.path.join(base_abs, entry)
            if not os.path.isdir(entry_path):
                continue
            registry.setdefault(entry, entry_path)
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"ERROR listing base exports: {exc}")

    return registry


def _has_export_files(path: str) -> bool:
    return (
        os.path.exists(os.path.join(path, "conversations.json"))
        and os.path.exists(os.path.join(path, "chat.html"))
    )


def get_export_folders() -> List[str]:
    """Locate export folders containing the expected files."""

    folders: List[str] = []
    registry = _build_export_registry()
    for name, path in registry.items():
        if not os.path.isdir(path):
            print(f"  - Skipping '{name}': path not found ({path})")
            continue
        if _has_export_files(path):
            folders.append(name)
            print(f"  + Found valid: {name} -> {path}")
        else:
            print(f"  - Skipping '{name}': missing files in {path}")

    try:
        folders.sort(key=lambda n: n.replace("-", "").replace("_", ""), reverse=True)
    except Exception:
        folders.sort()
    print(f"Final list of folders: {folders}")
    return folders


def _resolve_export_folder(folder_name: str | None) -> str:
    if not folder_name or ".." in folder_name or os.sep in folder_name:
        abort(400)
    registry = _build_export_registry()
    folder_path = registry.get(folder_name)
    if not folder_path or not os.path.isdir(folder_path):
        abort(404)
    folder_path = os.path.abspath(folder_path)
    if os.path.basename(os.path.normpath(folder_path)) != folder_name:
        abort(400)
    if not _has_export_files(folder_path):
        abort(404)
    return folder_path


def _register_export_location(folder_name: str, folder_path: str) -> None:
    locations = _load_export_locations()
    locations[folder_name] = os.path.abspath(folder_path)
    _save_export_locations(locations)


def _destination_suggestions() -> List[str]:
    registry = _build_export_registry()
    suggestions = {os.path.dirname(path) for path in registry.values()}
    suggestions.add(os.path.abspath(EXPORT_BASE_DIR))
    return sorted({s for s in suggestions if s})


def _safe_extract_zip(archive: zipfile.ZipFile, destination: str) -> None:
    for member in archive.infolist():
        member_path = member.filename
        if member_path.startswith("/") or member_path.startswith("\\"):
            raise ValueError("Archive member has an absolute path")
        target_path = os.path.abspath(os.path.join(destination, member_path))
        if not target_path.startswith(os.path.abspath(destination)):
            raise ValueError("Archive member escapes extraction directory")
        if member.is_dir():
            os.makedirs(target_path, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with archive.open(member) as source, open(target_path, "wb") as target:
            shutil.copyfileobj(source, target)


def _locate_export_root(extracted_root: str) -> str | None:
    candidates: List[str] = []
    for current_root, _dirs, files in os.walk(extracted_root):
        if "conversations.json" in files and "chat.html" in files:
            candidates.append(current_root)
    if not candidates:
        return None
    candidates.sort(key=lambda path: (len(os.path.relpath(path, extracted_root).split(os.sep)), len(path)))
    return candidates[0]


def _validate_folder_name(folder_name: str | None) -> str:
    _resolve_export_folder(folder_name)
    return folder_name or ""


@app.route("/")
def index_route():
    folders = get_export_folders()
    destinations = _destination_suggestions()
    return render_template("index.html", folders=folders, destination_suggestions=destinations)


@app.route("/conversations")
def get_conversations_route():
    folder_name = _validate_folder_name(request.args.get("folder_name"))
    folder_path = _resolve_export_folder(folder_name)
    base_directory = os.path.dirname(folder_path)
    print(f"\n{'=' * 10} Processing request for folder: {folder_name} {'=' * 10}")

    try:
        with db_core.connection_scope(DB_PATH) as conn:
            # ensure_export() compares mtimes and only re-parses the raw files when
            # necessary, otherwise the data comes straight from SQLite.
            snapshot = ingest_core.ensure_export(
                conn,
                base_directory,
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

    folder_path = _resolve_export_folder(folder_name)
    conversations_path = os.path.join(folder_path, "conversations.json")
    chat_path = os.path.join(folder_path, "chat.html")

    try:
        conversations_mtime = os.path.getmtime(conversations_path)
        chat_mtime = os.path.getmtime(chat_path)
    except FileNotFoundError as exc:
        raise ingest_core.ExportNotFoundError(str(exc)) from exc

    if export_row and export_row["conversations_mtime"] == conversations_mtime and export_row["chat_mtime"] == chat_mtime:
        return int(export_row["id"])

    base_directory = os.path.dirname(folder_path)
    snapshot = ingest_core.ensure_export(
        conn,
        base_directory,
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


def _normalise_folder_name(candidate: str) -> str:
    name = secure_filename(candidate.strip())
    return name or "export"


@app.route("/upload_export", methods=["POST"])
def upload_export():
    upload = request.files.get("file")
    if upload is None or upload.filename == "":
        return jsonify({"error": "Aucun fichier ZIP fourni."}), 400

    destination_root_raw = (request.form.get("destination_root") or "").strip()
    if not destination_root_raw:
        return jsonify({"error": "Le chemin de destination est requis."}), 400
    destination_root = os.path.abspath(destination_root_raw)
    try:
        os.makedirs(destination_root, exist_ok=True)
    except OSError as exc:
        return jsonify({"error": f"Impossible d'utiliser ce chemin: {exc}"}), 400

    provided_name = request.form.get("folder_name", "")
    generated = provided_name.strip() == ""
    base_name = os.path.splitext(upload.filename)[0] if generated else provided_name
    folder_name = _normalise_folder_name(base_name)
    if folder_name in IGNORED_FOLDERS:
        return jsonify({"error": "Nom de dossier non autorisé."}), 400

    registry = _build_export_registry()
    target_path = os.path.join(destination_root, folder_name)
    if folder_name in registry or os.path.exists(target_path):
        if generated:
            suffix = 1
            candidate = folder_name
            while candidate in registry or os.path.exists(os.path.join(destination_root, candidate)):
                candidate = f"{folder_name}-{suffix}"
                suffix += 1
            folder_name = candidate
            target_path = os.path.join(destination_root, folder_name)
        else:
            return jsonify({"error": "Un dossier portant ce nom existe déjà."}), 400

    os.makedirs(destination_root, exist_ok=True)
    if os.path.exists(target_path):
        return jsonify({"error": "Le dossier de destination existe déjà."}), 400

    os.makedirs(UPLOAD_TMP_DIR, exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix="upload_", dir=UPLOAD_TMP_DIR)
    zip_path = os.path.join(temp_dir, "upload.zip")
    extract_dir = os.path.join(temp_dir, "extract")
    os.makedirs(extract_dir, exist_ok=True)

    try:
        upload.save(zip_path)
        with zipfile.ZipFile(zip_path) as archive:
            _safe_extract_zip(archive, extract_dir)
    except zipfile.BadZipFile:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": "Le fichier n'est pas une archive ZIP valide."}), 400
    except ValueError as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": f"Archive invalide: {exc}"}), 400
    except Exception as exc:  # pragma: no cover - defensive logging
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": f"Erreur lors de l'extraction: {exc}"}), 500

    export_root = _locate_export_root(extract_dir)
    if not export_root:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": "Archive ZIP sans conversations.json/chat.html."}), 400

    try:
        if os.path.abspath(export_root) == os.path.abspath(extract_dir):
            os.makedirs(target_path)
            for entry in os.listdir(export_root):
                shutil.move(os.path.join(export_root, entry), target_path)
        else:
            shutil.move(export_root, target_path)
    except Exception as exc:  # pragma: no cover - defensive logging
        shutil.rmtree(temp_dir, ignore_errors=True)
        shutil.rmtree(target_path, ignore_errors=True)
        return jsonify({"error": f"Impossible de déplacer l'export: {exc}"}), 500
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    if not _has_export_files(target_path):
        shutil.rmtree(target_path, ignore_errors=True)
        return jsonify({"error": "Le dossier importé est incomplet."}), 400

    try:
        with db_core.connection_scope(DB_PATH) as conn:
            ingest_core.ensure_export(
                conn,
                destination_root,
                folder_name,
                fts_enabled=FTS_ENABLED,
            )
    except Exception as exc:  # pragma: no cover - defensive logging
        shutil.rmtree(target_path, ignore_errors=True)
        return jsonify({"error": f"Erreur lors de l'ingestion: {exc}"}), 500

    _register_export_location(folder_name, target_path)
    return jsonify({"status": "ok", "folder": folder_name, "path": target_path})


@app.route("/export_files/<path:folder_name>/<path:filepath>")
def serve_export_file(folder_name: str, filepath: str):
    print(f"Request for export file: folder='{folder_name}', filepath='{filepath}'")
    if not folder_name or ".." in folder_name or os.sep in folder_name:
        abort(400)
    if not filepath or ".." in filepath or filepath.startswith("/"):
        abort(400)

    safe_directory = _resolve_export_folder(folder_name)

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
