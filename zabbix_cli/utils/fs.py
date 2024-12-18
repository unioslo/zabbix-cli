from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.exceptions import ZabbixCLIFileError
from zabbix_cli.exceptions import ZabbixCLIFileNotFoundError
from zabbix_cli.output.console import print_path
from zabbix_cli.output.console import success

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
        if not os.environ.get("DISPLAY") and not force:
            print_path(directory)
            return
        subprocess.run([command or "xdg-open", spath])
    success(f"Opened {directory}")


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


def make_executable(path: Path) -> None:
    """Make a file executable."""
    if sys.platform == "win32":
        logger.debug("Skipping making file %s executable on Windows", path)
        return

    if not path.exists():
        raise ZabbixCLIFileNotFoundError(
            f"File {path} does not exist. Unable to make it executable."
        )
    mode = path.stat().st_mode
    new_mode = mode | (mode & 0o444) >> 2  # copy R bits to X
    if new_mode != mode:
        path.chmod(new_mode)
        logger.info("Changed file mode of %s from %o to %o", path, mode, new_mode)
    else:
        logger.debug("File %s is already executable", path)


def move_file(src: Path, dest: Path, mkdir: bool = True) -> None:
    """Move a file to a new location."""
    try:
        if mkdir:
            mkdir_if_not_exists(dest.parent)
        src.rename(dest)
    except Exception as e:
        raise ZabbixCLIError(f"Failed to move {src} to {dest}: {e}") from e
    else:
        logger.info(f"Moved {src} to {dest}")


@contextmanager
def temp_directory() -> Generator[Path, None, None]:
    """Context manager for creating a temporary directory.

    Ripped from: https://github.com/pypa/hatch/blob/35f8ffdacc937bdcf3b250e0be1bbdf5cde30c4c/src/hatch/utils/fs.py#L112-L117"""
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as d:
        yield Path(d).resolve()
