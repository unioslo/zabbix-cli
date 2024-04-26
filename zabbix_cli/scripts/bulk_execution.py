from __future__ import annotations

import typer

from zabbix_cli.logs import configure_logging


app = typer.Typer(
    name="zabbix-cli-bulk-execution", help="Bulk execution of Zabbix commands"
)


@app.callback(invoke_without_command=True)
def main_callback(
    input_file: str = typer.Option(
        "-",
        "--input-file",
        "-f",
        metavar="FILE",
        help="File to read commands from, defaults to stdin",
    ),
) -> None:
    pass


def main() -> int:
    """Main entry point for the CLI."""
    try:
        configure_logging()
        app()
    except Exception as e:
        from zabbix_cli.exceptions import handle_exception

        handle_exception(e)
    return 0
