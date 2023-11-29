"""Defines directories for the application.

Follows the XDG Base Directory Specification Linux: <https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html>
See <https://pypi.org/project/platformdirs/> for other platforms.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import NamedTuple

from platformdirs import PlatformDirs

from .__about__ import APP_NAME
from .__about__ import AUTHOR


_PLATFORM_DIR = PlatformDirs(APP_NAME, AUTHOR)

CONFIG_DIR = _PLATFORM_DIR.user_config_path
"""Directory for user configuration files."""

DATA_DIR = _PLATFORM_DIR.user_data_path
"""Directory for user data files."""

LOGS_DIR = _PLATFORM_DIR.user_log_path
"""Directory to store user log files."""

SITE_CONFIG_DIR = _PLATFORM_DIR.site_config_path
"""Directory for site-wide configuration files, i.e. `/etc/xdg/zabbix-cli`."""

EXPORT_DIR = DATA_DIR / "exports"
"""Directory to store exported data."""


class Directory(NamedTuple):
    name: str
    path: Path
    required: bool = False
    create: bool = True
    """Do not log/print on failure to create directory."""


DIRS = [
    Directory("Config", CONFIG_DIR),
    Directory("Data", DATA_DIR),
    Directory("Logs", LOGS_DIR),
    # Don't create site config directory by default (root-only)
    Directory("Site Config", SITE_CONFIG_DIR, create=False),
    # Exports directory is created on demand
    Directory("Exports", EXPORT_DIR, create=False),
]

DIR_MAP = {
    "Config": CONFIG_DIR,
    "Data": DATA_DIR,
    "Logs": LOGS_DIR,
    "Site Config": SITE_CONFIG_DIR,
    "Exports": EXPORT_DIR,
}
"""Map of directory types to their default paths."""


def mkdir_if_not_exists(path: Path) -> None:
    """Create a directory if it does not exist.
    Returns the path if it was created, otherwise None."""
    if path.exists():
        return
    try:
        path.mkdir(parents=True)
    except Exception as e:
        raise e
    else:
        from .output.console import info

        info(f"Created directory: {path}")


def init_directories() -> None:
    """Create required directories."""
    from .output.console import exit_err
    from .output.console import error

    for directory in DIRS:
        if directory.path.exists() or not directory.create:
            logging.debug(
                "Skipping creating directory '%s'. Exists: %s",
                directory.path,
                directory.path.exists(),
            )
            continue
        try:
            directory.path.mkdir(parents=True)
        except Exception as e:
            if directory.required:
                func = exit_err
            else:
                func = error
            func(
                f"Failed to create {directory.name} directory {directory.path}: {e}",
                exc_info=True,
            )
