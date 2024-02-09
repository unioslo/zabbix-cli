from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from zabbix_cli.config.constants import DEFAULT_CONFIG_FILE
from zabbix_cli.config.model import Config
from zabbix_cli.dirs import init_directories
from zabbix_cli.dirs import mkdir_if_not_exists
from zabbix_cli.logs import configure_logging
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info


def main(
    zabbix_url: str = typer.Option(
        "https://zabbix.example.com",
        "--zabbix-url",
        help="Zabbix API URL to use",
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
    if config_file:
        # If a custom config file was passed in, we have to ensure we
        # create its directory too
        mkdir_if_not_exists(config_file.parent)
    else:
        config_file = DEFAULT_CONFIG_FILE

    if config_file.exists() and not overwrite:
        exit_err(f"Configuration file already exists: {config_file}")

    config = Config.sample_config()
    config.api.url = zabbix_url
    config.dump_to_file(config_file)
    info(f"Configuration file created: {config_file}")


def run() -> None:
    configure_logging()
    typer.run(main)


if __name__ == "__main__":
    run()
