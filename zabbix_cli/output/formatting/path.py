"""Control the formatting of console output."""

from __future__ import annotations

from pathlib import Path


def path_link(path: Path, absolute: bool = True) -> str:
    """Return a link to a path."""
    abspath = path.resolve().absolute()
    if absolute:
        path_str = str(abspath)
    else:
        path_str = str(path)
    return f"[link=file://{abspath}]{path_str}[/link]"
