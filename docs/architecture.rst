Server Architecture
===================

Overview
--------

The Flask server (`app.py`) delegates almost all business logic to
``app_core`` to keep the code testable and maintainable.

Flow of a ``/conversations`` request
------------------------------------

1. **Validation**: the folder name is checked via ``_validate_folder_name``
   (rejects ``..`` and enforces the allowed scope).
2. **SQLite connection**: a connection is opened with
   ``app_core.db.connection_scope`` which applies the PRAGMA tuning (WAL, foreign keys).
3. **Conditional ingestion**: ``app_core.ingest.ensure_export`` compares the
   modification times of ``conversations.json`` and ``chat.html`` with the metadata stored in
   the ``exports`` table.
   - If the files are unchanged, the conversations are returned directly from the database
     (JSON is left untouched).
   - Otherwise the parsing pipeline reruns (see the "Parsing" section), results are
     (re)inserted into SQLite, then returned to the client.
4. **Response**: the JSON payload includes ``conversations``, ``asset_mapping``
   and ``file_types`` exactly like the pre-refactor behaviour.

SQLite persistence
------------------

``app_core/schema.py`` prepares three main structures:

- ``exports``: tracks a folder (mtimes, asset mapping JSON, MIME types JSON).
- ``conversations``: serialized conversations with preserved order (``sort_index``)
  plus precomputed ``has_asset`` / ``has_audio`` flags.
- ``conversation_search``: an FTS5 virtual table (``title`` + flattened content)
  used by the ``/search`` route.

Insertion uses ``_bulk_insert_conversations`` which:

- computes the flags through ``conversation_has_asset`` and ``conversation_has_audio``;
- stores the conversation JSON exactly as received (UTF-8, no mutation);
- feeds FTS if the extension is available.

Parsing and extraction
----------------------

The legacy parsing logic lives in ``app_core/parsing``:

- ``load_conversations_json`` reads the raw list.
- ``load_asset_mapping`` extracts ``assetsJson`` from ``chat.html`` with the same
  regular expression as before.
- ``detect_file_types`` prefers ``python-magic`` when available and falls back to
  ``mimetypes`` (see the dedicated section).

The module returns an ``ExportData`` structure that is ready to be stored or sent as-is.

Full-text search
----------------

The ``/search`` route uses ``conversation_search MATCH ?`` (FTS5). Past Whoosh
variants have been removed. If the host SQLite build lacks FTS5, the server responds
with HTTP 501 and the interface can disable the search box accordingly.
