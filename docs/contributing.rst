Contributing
============

Set up the environment
----------------------

1. Create/activate your virtualenv.
2. Install Flask and any optional dependencies you need (``python-magic`` is optional).
3. For the documentation, install the development extras (including the theme):
   ``pip install -r requirements-dev.txt``.

Building the documentation
--------------------------

```bash
cd docs
sphinx-build -b html . _build/html
```

The HTML output lives in ``docs/_build/html``. For live reload, use ``sphinx-autobuild``.

Code style
----------

* Python: PEP 8 with type annotations, short testable functions.
* JavaScript: use const/let appropriately, keep comments for non-trivial sections only.
* CSS/HTML: favour clarity and descriptive class names.

Recommended tests
-----------------

* ``python -m compileall app.py app_core`` to catch syntax errors.
* Add unit tests targeting ``app_core.parsing`` and ``app_core.ingest`` whenever you change their logic.

