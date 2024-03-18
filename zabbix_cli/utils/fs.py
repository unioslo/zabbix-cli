from __future__ import annotations

from pathlib import Path

from zabbix_cli.exceptions import ZabbixCLIFileError


def read_file(file: Path) -> str:
    """Attempts to read the contents of a command file."""
    if not file.exists():
        raise ZabbixCLIFileError(f"File {file} does not exist")
    if not file.is_file():
        raise ZabbixCLIFileError(f"{file} is not a file")
    try:
        return file.read_text()
    except OSError as e:
        raise ZabbixCLIFileError(f"Unable to read file {file}") from e
