from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import typer

from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import warning

app = typer.Typer(
    name="zabbix-cli-bulk-execution", help="Bulk execution of Zabbix commands"
)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    input_file: Optional[Path] = typer.Argument(
        None,
        help="File to read commands from.",
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Alternate configuration file to use.",
    ),
    input_file_legacy: Optional[Path] = typer.Option(
        None,
        "--file",
        "--input-file",
        "-f",
        hidden=True,
        help="File to read commands from.",
    ),
) -> None:
    warning(
        "zabbix-cli-bulk-execution is deprecated. Use [command]zabbix-cli --file[/] instead."
    )

    f = input_file or input_file_legacy
    if not f:
        exit_err("No input file provided. Reading from stdin is not supported.")

    # HACK: run the CLI with the file argument
    args = ["zabbix-cli", "--file", str(f)]
    if config_file:
        args.extend(["--config", str(config_file)])
    subprocess.run(args)


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
