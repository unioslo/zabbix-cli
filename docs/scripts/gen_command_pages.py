"""Generate the code reference pages and navigation."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict
from typing import List

import jinja2
import yaml  # type: ignore
from sanitize_filename import sanitize

from zabbix_cli.app import app

sys.path.append(Path(__file__).parent.as_posix())
sys.path.append(Path(__file__).parent.parent.parent.as_posix())

from utils.commands import get_app_commands  # noqa: E402
from utils.commands import CommandSummary  # noqa: E402
from common import COMMANDS_DIR  # noqa
from common import DATA_DIR  # noqa
from common import TEMPLATES_DIR  # noqa


def gen_command_list(commands: list[CommandSummary]) -> None:
    command_names = [c.name for c in commands]
    with open(DATA_DIR / "commandlist.yaml", "w") as f:
        yaml.dump(command_names, f, sort_keys=False)


def gen_command_pages(commands: list[CommandSummary]) -> None:
    categories: Dict[str, List[CommandSummary]] = {}
    for command in commands:
        if command.hidden:
            continue
        category = command.category or command.name
        if category not in categories:
            categories[category] = []
        categories[category].append(command)

    loader = jinja2.FileSystemLoader(searchpath=TEMPLATES_DIR)
    env = jinja2.Environment(loader=loader)

    # Render each individual command page
    pages = {}  # type: dict[str, str] # {category: filename}
    for category_name, cmds in categories.items():
        template = env.get_template("category.md.j2")
        filename = sanitize(category_name.replace(" ", "_"))
        filepath = COMMANDS_DIR / f"{filename}.md"
        with open(filepath, "w") as f:
            f.write(template.render(category=category_name, commands=cmds))
        pages[category_name] = filename


def main() -> None:
    commands = get_app_commands(app)
    gen_command_list(commands)
    gen_command_pages(commands)


if __name__ == "__main__":
    main()
