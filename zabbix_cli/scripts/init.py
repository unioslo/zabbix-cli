from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from zabbix_cli.config.utils import init_config
from zabbix_cli.exceptions import ConfigExistsError
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.logs import configure_logging


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

    try:
        init_config(
            config_file=config_file,
            overwrite=overwrite,
            url=zabbix_url,
            username=zabbix_user,
        )
    except ConfigExistsError as e:
        raise ZabbixCLIError(f"{e}. Use [option]--overwrite[/] to overwrite it") from e


def run() -> None:
    try:
        configure_logging()
        typer.run(main)
    except Exception as e:
        from zabbix_cli.exceptions import handle_exception

        handle_exception(e)


if __name__ == "__main__":
    run()
