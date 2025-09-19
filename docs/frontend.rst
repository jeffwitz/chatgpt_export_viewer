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

Asset handling & media filters
-----------------------------

The front-end does not perform extra detection:

1. ``currentFolderData.asset_mapping`` resolves ``asset_pointer`` values to filenames.
2. ``currentFolderData.file_types`` exposes the MIME type or textual hint.
3. ``displayConversation`` decides how to render each asset:

   - ``image/*`` -> responsive ``<img>`` element,
   - ``audio/*`` -> ``<audio controls>`` element,
   - anything else -> download link.

Filtering is handled entirely on the client. The sidebar now exposes inline emoji toggles
(`🖼`, `🎵`, `🔧`). ``updateDisplayedConversationList`` interprets the media toggles with
"OR" semantics: selecting only ``🖼`` shows image conversations, only ``🎵`` shows audio, and
selecting both shows any conversation containing at least one of the two asset types. Tool
messages can be hidden globally with ``🔧``; both the list and the rendered conversation honour
the choice.

Conversation actions
--------------------

The conversation header exposes two actions implemented in ``displayConversation``:

* **Copy all** &rarr; streams the conversation as Markdown while respecting the current
  tool-message filter.
* **Print / PDF** &rarr; triggers ``window.print()`` in-place. The helper temporarily adds the
  ``print-mode`` class to ``<body>`` so the CSS can hide navigation and maintain the exported
  layout without opening a secondary tab.

Code highlighting
-----------------

``<pre><code>`` blocks receive a minimal highlighter: a handful of regular expressions detect
strings, comments, numbers, and keywords for Python, JavaScript/C, HTML, and CSS. The
implementation intentionally stays lightweight (no full parsing) but improves offline readability
without external dependencies.

When the language hint is ``latex`` – or the source looks like TeX (``\frac{}``, ``\begin``...
even without an explicit hint) – apostrophes are *not* tokenised as string delimiters. This prevents
erroneous highlighting in inline maths.

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
* Printing relies on standard browser dialogs; ensure the ``print-mode`` overrides remain in sync
  with layout changes so exports match the on-screen conversation.
