from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from zabbix_cli.config.model import Config
from zabbix_cli.config.utils import create_config_file
from zabbix_cli.dirs import init_directories
from zabbix_cli.logs import configure_logging
from zabbix_cli.output.console import info


def main(
    zabbix_url: str = typer.Option(
        "https://zabbix.example.com",
        "--url",
        "--zabbix-url",
        "-z",
        help="Zabbix API URL to use",
    ),
    zabbix_user: Optional[str] = typer.Option(
        None,
        "--user",
        "--zabbix-user",
        help="Zabbix API username to use",
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config-file",
        "-c",
        help="Use non-default configuration file location",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-o",
        help="Overwrite existing configuration file",
    ),
) -> None:
    # TODO: support creating directory for custom file locations

    # Create required directories
    init_directories()
    config = Config.sample_config()
    config.api.url = zabbix_url
    if zabbix_user:
        config.api.username = zabbix_user
    config_file = create_config_file(config, config_file)
    info(f"Configuration file created: {config_file}")


def run() -> None:
    try:
        configure_logging()
        typer.run(main)
    except Exception as e:
        from zabbix_cli.exceptions import handle_exception

        handle_exception(e)


if __name__ == "__main__":
    run()
