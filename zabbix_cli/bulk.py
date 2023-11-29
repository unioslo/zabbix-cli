from __future__ import annotations

from pathlib import Path
from typing import List

from zabbix_cli.exceptions import CommandFileError


def load_command_file(file: Path) -> List[str]:
    """Load a command file. Returns a list of commands"""
    contents = _do_load_command_file(file)
    return _parse_command_file_contents(contents)


def _do_load_command_file(file: Path) -> str:
    """Attempts to load the contents of a command file."""
    # CommandFileError is caught by the default exception handler
    if not file.exists():
        raise CommandFileError(f"File {file} does not exist")
    if not file.is_file():
        raise CommandFileError(f"{file} is not a file")
    try:
        return file.read_text()
    except OSError as e:
        raise CommandFileError(f"Unable to read file {file}") from e


def _parse_command_file_contents(contents: str) -> List[str]:
    """Parse the contents of a command file."""
    lines = [line for line in contents.splitlines() if not line.startswith("#")]
    if not lines:
        raise CommandFileError("Command file contains no commands")
    return lines
