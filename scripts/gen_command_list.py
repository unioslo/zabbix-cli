"""Generate documentation of commands and categories.

Generates the following files:

- `commandlist.yaml`: List with names of all commands.
- `commands.yaml`: Mapping of all categories to detailed information
                   about each command.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore
from zabbix_cli.app import app

sys.path.append(Path(__file__).parent.as_posix())
from common import DATA_DIR  # noqa
from utils.commands import get_app_commands  # noqa: E402


def main() -> None:
    commands = get_app_commands(app)
    command_names = [c.name for c in commands]

    categories: dict[str, list[dict[str, Any]]] = {}
    for command in commands:
        category = command.category or ""
        if category not in categories:
            categories[category] = []
        cmd_dict = command.model_dump(mode="json")
        # cmd_dict["usage"] = command.usage
        categories[category].append(cmd_dict)

    with open(DATA_DIR / "commands.yaml", "w") as f:
        yaml.dump(categories, f, sort_keys=True)

    with open(DATA_DIR / "commandlist.yaml", "w") as f:
        yaml.dump(command_names, f, sort_keys=True)


if __name__ == "__main__":
    main()
