from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

import typer

from zabbix_cli.config.model import Config
from zabbix_cli.config.utils import get_config


class RunMode(str, Enum):
    SHOW = "show"
    DEFAULTS = "defaults"


def main(
    arg: RunMode = typer.Argument(RunMode.DEFAULTS, case_sensitive=False),
    filename: Optional[Path] = None,
):
    """Print current or default config to stdout."""
    from zabbix_cli.logs import configure_logging

    configure_logging()
    if arg == RunMode.SHOW:
        config = get_config(filename)
    else:
        config = Config.sample_config()
    print(config.as_toml())
