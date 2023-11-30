from __future__ import annotations

import importlib
from pathlib import Path

# from ._internal import *  # noqa: F403


# TODO: import all modules automatically here
def bootstrap_commands() -> None:
    """Bootstrap all command defined in the command modules."""
    module_dir = Path(__file__).parent
    for module in module_dir.glob("*.py"):
        if module.stem == "__init__":
            continue
        importlib.import_module(f".{module.stem}", package=__package__)
