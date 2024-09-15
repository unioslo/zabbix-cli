from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.exceptions import ZabbixCLIFileError
from zabbix_cli.exceptions import ZabbixCLIFileNotFoundError

logger = logging.getLogger(__name__)


def read_file(file: Path) -> str:
    """Attempts to read the contents of a file."""
    if not file.exists():
        raise ZabbixCLIFileNotFoundError(f"File {file} does not exist")
    if not file.is_file():
        raise ZabbixCLIFileError(f"{file} is not a file")
    try:
        return file.read_text()
    except OSError as e:
        raise ZabbixCLIFileError(f"Unable to read file {file}") from e


def open_directory(
    directory: Path, command: Optional[str] = None, force: bool = False
) -> None:
    """Open directory in file explorer.

    Prints the path to the directory to stderr if no window server is detected.
    The path must be a directory, otherwise a ZabbixCLIError is raised.

    Args:
        directory (Path): The directory to open.
        command (str, optional): The command to use to open the directory. If `None`, the command is determined based on the platform.
        force (bool, optional): If `True`, open the directory even if no window server is detected. Defaults to `False`.
    """
    try:
        if not directory.exists():
            raise FileNotFoundError
        directory = directory.resolve(strict=True)
    except FileNotFoundError:
        raise ZabbixCLIError(f"Directory {directory} does not exist")
    except OSError:
        raise ZabbixCLIError(f"Unable to resolve symlinks for {directory}")
    if not directory.is_dir():
        raise ZabbixCLIError(f"{directory} is not a directory")

    spath = str(directory)
    if sys.platform == "win32":
        subprocess.run([command or "explorer", spath])
    elif sys.platform == "darwin":
        subprocess.run([command or "open", spath])
    else:  # Linux and Unix
        if not os.environ.get("DISPLAY"):
            from zabbix_cli.output.console import print_path

            print_path(directory)
            if not force:
                return
        subprocess.run([command or "xdg-open", spath])


def mkdir_if_not_exists(path: Path) -> None:
    """Create a directory for a given path if it does not exist.

    Returns the path if it was created, otherwise None.
    """
    if path.exists():
        return
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise ZabbixCLIFileError(f"Failed to create directory {path}: {e}") from e
    else:
        logger.info(f"Created directory: {path}")


def sanitize_filename(filename: str) -> str:
    """Make a filename safe(r) for use in filesystems.

    Very naive implementation that removes illegal characters.
    Does not check for reserved names or path length.
    """
    return re.sub(r"[^\w\-.]", "_", filename)
