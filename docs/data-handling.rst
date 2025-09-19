Data Handling
=============

File type detection
-------------------

MIME detection relies on ``detect_file_types`` (``app_core/parsing``):

* the list of target files comes from the ``asset_mapping`` extracted
  from ``chat.html``;
* for each file the cached ``file_type.json`` is read when present;
* if the type is unknown or flagged as ``Error``, the function attempts:

  1. ``python-magic`` (when installed) to inspect the binary header;
  2. ``mimetypes.guess_type`` as a pure-Python fallback;
  3. otherwise defaulting to ``application/octet-stream``.

The results are written back to ``file_type.json`` to avoid repeated detections.
This file is also stored in SQLite (``file_types_json`` column) so it can be served immediately.

Asset and audio detection
-------------------------

* ``conversation_has_asset`` traverses the ``mapping`` structure and returns ``True``
  as soon as an ``asset_pointer`` is found.
* ``conversation_has_audio`` uses the mapping to recover the filename and checks:

  - the stored MIME type (``audio/`` or keywords like ``wave audio``, ``ogg data``...)
  - the ``.wav``, ``.mp3``, ``.ogg``, ``.m4a``, ``.aac`` or ``.flac`` extensions.

The front-end consumes these flags to filter conversations and display the appropriate icons.

Preserving the JSON structure
-----------------------------

Conversations stored in the database keep the original JSON representation.
When they are rehydrated, ``mapping`` and ``message`` preserve all fields required by the UI
(including tool aggregates).

