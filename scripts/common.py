from __future__ import annotations

from pathlib import Path

from zabbix_cli.dirs import DIRS
from zabbix_cli.dirs import Directory

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


def sanitize_dirname(d: Directory) -> str:
    """Sanitize directory name for use in filenames."""
    return f"{d.name.lower().replace(' ', '_')}_dir"


def add_path_placeholders(s: str) -> str:
    """Add placeholders for file paths used by the application in a string.

    Enables somewhat consistent file paths in the documentation
    regardless of the runner environment.
    """
    for directory in DIRS:
        # Naive string replacement, then clean up double slashes if any
        s = s.replace(f"{directory.path}", f"/path/to/{sanitize_dirname(directory)}")
        s = s.replace("//", "/")
    return s
