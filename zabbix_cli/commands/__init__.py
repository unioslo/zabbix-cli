from __future__ import annotations

import importlib
from pathlib import Path


def bootstrap_commands() -> None:
    """Bootstrap all command defined in the command modules."""
    module_dir = Path(__file__).parent
    for module in module_dir.glob("*.py"):
        if module.stem == "__init__":
            continue
        importlib.import_module(f".{module.stem}", package=__package__)


# NOTE: The main app commands are imported in zabbix_cli.app, because
# binaries built with pyinstaller cannot resolve dynamic imports like
# bootstrap_commands() here.
# However, dynamic importing is still performed here in order to load
# local commands not committed to source control.

bootstrap_commands()
