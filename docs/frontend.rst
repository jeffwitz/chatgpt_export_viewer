Front-end and Rendering
=======================

Math rendering
--------------

* ``static/katex.min.js`` and ``static/auto-render.min.js`` are loaded from the
  ``templates/index.html`` template.
* After a conversation is rendered, ``displayConversation`` calls
  ``renderMathInElement`` (see ``static/script.js``) with the ``$...$``, ``$$...$$``
  and ``\(\)`` / ``\[\]`` delimiters.
* ``throwOnError`` is disabled so expressions show up even when the syntax is incomplete.

If KaTeX fails to load (network issue or broken path) the function gracefully returns
and logs a warning in the console.

Fonts and assets
----------------

* Stylesheets no longer use remote ``@import`` rules: they fall back to local fonts
  available on the machine (``system-ui``, ``Segoe UI``...), which keeps everything offline.
* The KaTeX font files required for math rendering ship in ``static/fonts``.

Asset handling
--------------

The front-end does not perform extra detection:

1. ``currentFolderData.asset_mapping`` resolves ``asset_pointer`` values to filenames.
2. ``currentFolderData.file_types`` exposes the MIME type or textual hint.
3. ``displayConversation`` decides how to render each asset:

   - ``image/*`` -> responsive ``<img>`` element,
   - ``audio/*`` -> ``<audio controls>`` element,
   - anything else -> download link.

The "Media/Files", "Audio only", and "Images only" checkboxes filter the list client-side
through ``updateDisplayedConversationList``.

Code highlighting
-----------------

``<pre><code>`` blocks receive a minimal highlighter: a handful of regular expressions detect
strings, comments, numbers, and keywords for Python, JavaScript/C, HTML, and CSS. The
implementation intentionally stays lightweight (no full parsing) but improves offline readability
without external dependencies.

Client-side search
------------------

* The title search relies on local filtering (``updateDisplayedConversationList``).
* The global search input triggers a debounced call to ``/search``; results are
  highlighted in the list.

UI considerations
-----------------

* XSS: ``markdown-it`` runs with ``html: true``. Add a sanitizer (e.g. DOMPurify) if you plan
  to load untrusted exports.
* Accessibility: the asset icon is decorative only; consider adding ``sr-only`` text to help
  screen readers.
