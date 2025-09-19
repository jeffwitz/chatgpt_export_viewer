"""Flask application serving ChatGPT exports with SQLite persistence."""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import quote

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
from app_core import export_render as export_core
from app_core import ingest as ingest_core
from app_core import schema as schema_core

logger = logging.getLogger(__name__)

if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_BASE_DIR = BASE_DIR
APP_DATA_DIR = os.path.join(BASE_DIR, "app_data")
EXPORT_LOCATIONS_FILE = os.path.join(APP_DATA_DIR, "export_locations.json")
UPLOAD_TMP_DIR = os.path.join(APP_DATA_DIR, "tmp_uploads")
DB_PATH = db_core.get_database_path(BASE_DIR)
# Folders that should never be treated as ChatGPT exports. Keep in sync with README.
IGNORED_FOLDERS = {"static", "templates", "__pycache__", "venv", ".indexdir", "app_data"}

SCHEMA_INFO: Dict[str, object] | None = None
FTS_ENABLED: bool = False
_DB_INIT_ERROR: Optional[Exception] = None


def _initialise_database() -> None:
    """Initialise the database schema, recording any error for later reporting."""

    global SCHEMA_INFO, FTS_ENABLED, _DB_INIT_ERROR

    if SCHEMA_INFO is not None or _DB_INIT_ERROR is not None:
        return

    try:
        db_core.ensure_parent_directory(DB_PATH)
        with db_core.connection_scope(DB_PATH) as _conn:
            SCHEMA_INFO = schema_core.ensure_schema(_conn)
            FTS_ENABLED = bool(SCHEMA_INFO.get("fts_enabled", False))
    except Exception as exc:  # pragma: no cover - defensive logging
        _DB_INIT_ERROR = exc
        logger.error("Failed to initialise database: %s", exc, exc_info=True)


def _ensure_database_ready():
    """Return an error response if the database failed to initialise."""

    _initialise_database()
    if _DB_INIT_ERROR is not None:
        logger.error("Database not ready: %s", _DB_INIT_ERROR)
        return jsonify({"error": "Database initialisation failed."}), 500
    return None


def _is_within_export_base(path: str) -> bool:
    export_base_abs = os.path.abspath(EXPORT_BASE_DIR)
    target_abs = os.path.abspath(path)
    return target_abs == export_base_abs or target_abs.startswith(f"{export_base_abs}{os.sep}")


def _load_export_locations() -> Dict[str, str]:
    if not os.path.exists(EXPORT_LOCATIONS_FILE):
        return {}
    try:
        with open(EXPORT_LOCATIONS_FILE, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read export locations: %s", exc)
        return {}

    data = raw.get("exports") if isinstance(raw, dict) else None
    if not isinstance(data, dict):
        logger.warning("Export locations file has unexpected structure")
        return {}

    cleaned: Dict[str, str] = {}
    modified = False
    for name, path in data.items():
        if isinstance(name, str) and isinstance(path, str) and name:
            cleaned[name] = path
        else:
            modified = True

    if modified:
        _save_export_locations(cleaned)

    return cleaned


def _save_export_locations(locations: Dict[str, str]) -> None:
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    payload = {"exports": locations}
    with open(EXPORT_LOCATIONS_FILE, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _build_export_registry() -> Dict[str, str]:
    registry: Dict[str, str] = {}
    stored = _load_export_locations()
    updated_locations: Dict[str, str] = {}
    registry_modified = False

    for name, path in stored.items():
        abs_path = os.path.abspath(path)
        if (
            not os.path.isdir(abs_path)
            or not _has_export_files(abs_path)
            or not _is_within_export_base(abs_path)
        ):
            registry_modified = True
            continue
        updated_locations[name] = abs_path
        registry[name] = abs_path

    base_abs = os.path.abspath(EXPORT_BASE_DIR)
    try:
        for entry in os.listdir(base_abs):
            if entry.startswith(".") or entry in IGNORED_FOLDERS:
                continue
            entry_path = os.path.join(base_abs, entry)
            if not os.path.isdir(entry_path) or not _has_export_files(entry_path):
                continue
            abs_entry_path = os.path.abspath(entry_path)
            if registry.get(entry) != abs_entry_path:
                registry_modified = True
            registry[entry] = abs_entry_path
            updated_locations[entry] = abs_entry_path
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error listing base exports: %s", exc)

    if registry_modified:
        _save_export_locations(updated_locations)

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
            logger.info("Skipping export '%s': path not found (%s)", name, path)
            continue
        if _has_export_files(path):
            folders.append(name)
            logger.info("Found export '%s' at %s", name, path)
        else:
            logger.info("Skipping export '%s': missing files in %s", name, path)

    try:
        folders.sort(key=lambda n: n.replace("-", "").replace("_", ""), reverse=True)
    except Exception:
        folders.sort()
    logger.info("Export folders available: %s", folders)
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


def _parse_datetime_param(value: str | None) -> Optional[float]:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None

    def _normalise(raw: str) -> str:
        normalised = raw
        if normalised.endswith("Z"):
            normalised = normalised[:-1] + "+00:00"
        return normalised

    candidates = [_normalise(cleaned)]
    if "T" not in cleaned:
        candidates.append(_normalise(f"{cleaned}T00:00:00"))

    for candidate in candidates:
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            continue

    raise ValueError(f"Invalid ISO datetime: {value}")


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
    if not folder_name:
        abort(400)
    separators = {sep for sep in (os.sep, os.altsep) if sep}
    if ".." in folder_name or any(sep in folder_name for sep in separators):
        abort(400)
    return folder_name


@app.route("/")
def index_route():
    folders = get_export_folders()
    destinations = _destination_suggestions()
    return render_template("index.html", folders=folders, destination_suggestions=destinations)


@app.route("/conversations")
def get_conversations_route():
    readiness_error = _ensure_database_ready()
    if readiness_error:
        return readiness_error

    folder_name = _validate_folder_name(request.args.get("folder_name"))
    folder_path = _resolve_export_folder(folder_name)
    base_directory = os.path.dirname(folder_path)
    logger.info("Processing conversations request for '%s'", folder_name)

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
        logger.error("Export not found while fetching conversations: %s", exc)
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Error while processing export '%s'", folder_name)
        return jsonify({"error": f"Failed to process export: {exc}"}), 500

    logger.info("Conversations request completed for '%s'", folder_name)
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
    readiness_error = _ensure_database_ready()
    if readiness_error:
        return readiness_error

    if not FTS_ENABLED:
        return jsonify({"error": "Search unavailable (SQLite FTS5 missing)."}), 501

    folder_name = _validate_folder_name(request.args.get("folder_name"))
    query_string = request.args.get("query")
    if not query_string:
        return jsonify({"error": "Missing query"}), 400

    try:
        start_ts = _parse_datetime_param(request.args.get("start"))
        end_ts = _parse_datetime_param(request.args.get("end"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    logger.info("Processing search in '%s' for query '%s'", folder_name, query_string)

    try:
        with db_core.connection_scope(DB_PATH) as conn:
            export_id = _ensure_export_id(conn, folder_name)
            results = ingest_core.search_conversations(
                conn,
                export_id,
                query_string,
                fts_enabled=FTS_ENABLED,
                start_ts=start_ts,
                end_ts=end_ts,
            )
    except ingest_core.ExportNotFoundError:
        return jsonify({"error": "Folder not found"}), 404
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 501
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Error during search in '%s'", folder_name)
        return jsonify({"error": f"Search error: {exc}"}), 500

    logger.info("Search in '%s' returned %d result(s)", folder_name, len(results))
    return jsonify(results)


@app.route("/export/print")
def export_conversation_print():
    readiness_error = _ensure_database_ready()
    if readiness_error:
        return readiness_error

    folder_name = _validate_folder_name(request.args.get("folder_name"))
    conversation_id = request.args.get("conversation_id")
    if not conversation_id:
        return jsonify({"error": "Missing conversation_id"}), 400

    try:
        with db_core.connection_scope(DB_PATH) as conn:
            export_id = _ensure_export_id(conn, folder_name)
            row = conn.execute(
                """
                SELECT c.title, c.raw_json, e.asset_mapping_json, e.file_types_json
                  FROM conversations AS c
                  JOIN exports AS e ON e.id = c.export_id
                 WHERE c.export_id = ?
                   AND c.conversation_id = ?
                """,
                (export_id, conversation_id),
            ).fetchone()
            if row is None:
                return jsonify({"error": "Conversation not found"}), 404

            conversation = json.loads(row["raw_json"])
            asset_mapping = json.loads(row["asset_mapping_json"]) if row["asset_mapping_json"] else {}
            file_types = json.loads(row["file_types_json"]) if row["file_types_json"] else {}
            title = row["title"] or conversation.get("title") or conversation_id
    except ingest_core.ExportNotFoundError:
        return jsonify({"error": "Folder not found"}), 404

    asset_base_url = f"/export_files/{quote(folder_name)}"

    messages = export_core.build_print_messages(
        conversation,
        asset_mapping=asset_mapping,
        file_types=file_types,
        asset_base_url=asset_base_url,
    )

    return render_template(
        "print.html",
        title=title,
        messages=messages,
        folder_name=folder_name,
        conversation_id=conversation_id,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def _normalise_folder_name(candidate: str) -> str:
    name = secure_filename(candidate.strip())
    return name or "export"


@app.route("/upload_export", methods=["POST"])
def upload_export():
    readiness_error = _ensure_database_ready()
    if readiness_error:
        return readiness_error

    upload = request.files.get("file")
    if upload is None or upload.filename == "":
        return jsonify({"error": "Aucun fichier ZIP fourni."}), 400

    destination_root_raw = (request.form.get("destination_root") or "").strip()
    if not destination_root_raw:
        return jsonify({"error": "Le chemin de destination est requis."}), 400
    destination_root = os.path.abspath(destination_root_raw)

    if not _is_within_export_base(destination_root):
        logger.warning(
            "Rejected upload destination outside export base: %s", destination_root_raw
        )
        return jsonify({"error": "Destination folder is not allowed."}), 400

    try:
        os.makedirs(destination_root, exist_ok=True)
    except OSError as exc:
        return jsonify({"error": f"Impossible d'utiliser ce chemin: {exc}"}), 400

    provided_name = request.form.get("folder_name", "")
    generated = provided_name.strip() == ""
    base_name = os.path.splitext(upload.filename)[0] if generated else provided_name
    folder_name = _normalise_folder_name(base_name)
    if folder_name in IGNORED_FOLDERS:
        return jsonify({"error": "Folder name not allowed."}), 400

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
            return jsonify({"error": "A folder with this name already exists."}), 400

    os.makedirs(destination_root, exist_ok=True)
    if os.path.exists(target_path):
        return jsonify({"error": "Destination folder already exists."}), 400

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
        return jsonify({"error": f"Extraction error: {exc}"}), 500

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
        return jsonify({"error": f"Could not move the export: {exc}"}), 500
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    if not _has_export_files(target_path):
        shutil.rmtree(target_path, ignore_errors=True)
        return jsonify({"error": "Imported folder is incomplete."}), 400

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
        return jsonify({"error": f"Ingestion error: {exc}"}), 500

    _register_export_location(folder_name, target_path)
    return jsonify({"status": "ok", "folder": folder_name, "path": target_path})


@app.route("/export_files/<path:folder_name>/<path:filepath>")
def serve_export_file(folder_name: str, filepath: str):
    logger.info("Serving export file '%s' from folder '%s'", filepath, folder_name)
    if not folder_name or ".." in folder_name or os.sep in folder_name:
        abort(400)
    if not filepath or ".." in filepath or filepath.startswith("/"):
        abort(400)

    safe_directory = _resolve_export_folder(folder_name)

    requested_path = os.path.abspath(os.path.join(safe_directory, filepath))
    if not requested_path.startswith(safe_directory):
        abort(403)

    try:
        return send_from_directory(safe_directory, filepath, as_attachment=False)
    except FileNotFoundError:
        logger.warning("Requested file '%s' not found in '%s'", filepath, safe_directory)
        try:
            actual_filename = next(
                (entry for entry in os.listdir(safe_directory) if entry.lower() == filepath.lower()),
                None,
            )
        except OSError:
            actual_filename = None
        if actual_filename:
            logger.info(
                "Serving case-insensitive match '%s' for requested file '%s'",
                actual_filename,
                filepath,
            )
            return send_from_directory(safe_directory, actual_filename)
        abort(404)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Error serving file '%s' from '%s'", filepath, folder_name)
        abort(500)


@app.route("/static/<path:filename>")
def serve_static(filename: str):
    static_dir = os.path.join(BASE_DIR, "static")
    return send_from_directory(static_dir, filename)


if __name__ == "__main__":
    _initialise_database()
    if _DB_INIT_ERROR is not None:
        logger.error("Database initialisation failed at startup: %s", _DB_INIT_ERROR)
    logger.info("Starting Flask server...")
    logger.info("SQLite path: %s", DB_PATH)
    logger.info("FTS enabled: %s", FTS_ENABLED)
    app.run(debug=True, host="0.0.0.0", port=5001, use_reloader=True)
