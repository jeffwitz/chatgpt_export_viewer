# ChatGPT Export Viewer (SQLite Edition)

This Flask application lets you browse ChatGPT exports locally (`conversations.json`, `chat.html`, and their associated assets). SQLite persistence avoids reparsing the raw files on every request.

## Key Features
- Bootstrap web interface to browse conversations, display messages and attachments, copy Markdown, and render KaTeX.
- Automatic detection of assets (images, audio, other files) with MIME type inference.
- Full-text search powered by the SQLite FTS5 extension (Whoosh is no longer required).
- Utility scripts to inspect and clean exports (`Analyse_json.py`, `GPT_cleaner.py`, and more).
- Works entirely offline - fonts and libraries are bundled locally.
- Lightweight syntax highlighting (Python, JS/C, HTML, CSS) with no external dependency.
- Local filters to highlight conversations that contain media, audio, or images.

## Quick Installation
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # or install Flask/ijson/python-magic manually if needed
```

> Note: the core app only relies on the Python standard library plus Flask. If `python-magic` is installed, MIME detection becomes more accurate.

## Starting the Server
```bash
source .venv/bin/activate  # or activate your preferred environment
FLASK_APP=app python -m flask run --no-debugger --no-reload --host 0.0.0.0 --port 5001
```

Drop your export folders (the ones that contain `conversations.json` and `chat.html`) at the repository root; they will be detected automatically.

## Importing a ZIP Export
- Use the "Import ZIP export" form in the interface to upload the archive you received from ChatGPT.
- Provide the target path - it can point to any mounted volume (external SSD, NAS, etc.).
- The application extracts the archive, creates the export folder, indexes it in SQLite, and adds it to the list automatically.
- You can leave the "Folder name" field empty to reuse the ZIP filename.

## Sphinx Documentation

Developer documentation lives in `docs/`. To build it:

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt  # includes sphinx-rtd-theme
cd docs
sphinx-build -b html . _build/html
```

The generated pages describe the server architecture, asset detection, and the front-end rendering logic (math, assets, search).

## SQLite Persistence
- The database file is `app_data.db` at the repository root.
- The first load of a folder parses all raw files and stores the results (conversations, asset mapping, MIME guesses) in SQLite.
- Subsequent requests read directly from SQLite, removing the initial delay.
- An FTS5 virtual table (`conversation_search`) powers the search route. If FTS5 is not available in your SQLite build, the `/search` route returns a 501 error.

### Utility Scripts
Use the CLI script to ingest (or reingest) an export manually:
```bash
source .venv/bin/activate
python scripts/refresh_export.py 06042025
```

## Development Notes
- Python code follows PEP 8; type annotations are being added progressively.
- Server-side modules:
  - `app_core/parsing.py`: extraction logic (mirrors the original behaviour).
  - `app_core/db.py`: SQLite connection helpers.
  - `app_core/schema.py`: schema creation and migrations.
  - `app_core/ingest.py`: ingestion pipeline + search.
- Front-end logic stays in the browser (`static/script.js`).

## Quick Checks
```bash
source .venv/bin/activate
python -m compileall app.py app_core
python -m pytest  # add tests as needed
```

## Roadmap
- Add unit tests for `app_core.parsing`.
- Handle very large exports through incremental ingestion.
- Expose a UI button that triggers a manual reindex.
