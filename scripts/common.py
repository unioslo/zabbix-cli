from __future__ import annotations

from pathlib import Path

# Directory of all docs files
DOC_DIR = Path(__file__).parent.parent

# Directory of data files for Jinja2 templates
DATA_DIR = DOC_DIR / "data"
if not DATA_DIR.exists():
    DATA_DIR.mkdir(parents=True)

# Directory of Jinja2 templates
TEMPLATES_DIR = DOC_DIR / "templates"

# Directory of generated command doc pages
COMMANDS_DIR = DOC_DIR / "commands"
if not COMMANDS_DIR.exists():
    COMMANDS_DIR.mkdir(parents=True)
