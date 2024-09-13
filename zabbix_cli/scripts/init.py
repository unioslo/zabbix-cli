from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import typer

from zabbix_cli.output.console import warning

app = typer.Typer(name="zabbix-cli-init", help="Set up Zabbix-CLI configuration")


@app.callback(invoke_without_command=True)
def main_callback(
    zabbix_url: Optional[str] = typer.Option(
        None,
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
    warning(
        "[command]zabbix-cli-init[/] is deprecated. Use [command]zabbix-cli init[/]."
    )

    # HACK: run the CLI with the init command
    args = ["zabbix-cli", "init"]
    if zabbix_url:
        args.extend(["--url", zabbix_url])
    if zabbix_user:
        args.extend(["--user", zabbix_user])
    if config_file:
        args.extend(["--config-file", str(config_file)])
    if overwrite:
        args.append("--overwrite")

    subprocess.run(args)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
