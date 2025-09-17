"""Sphinx configuration for the ChatGPT export viewer documentation."""
from __future__ import annotations

import os
import sys
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

project = "ChatGPT Export Viewer"
author = "Jeff"
current_year = datetime.utcnow().year
copyright = f"{current_year}, {author}"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

todo_include_todos = True

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
