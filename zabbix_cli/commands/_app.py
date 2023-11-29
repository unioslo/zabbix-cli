"""In order to mimick the API of Zabbix-cli < 3.0.0, we define a single
app object here, which we share between the different modules.

This means every single command is part of the same command group."""
from __future__ import annotations

import typer

app = typer.Typer(
    name="zabbix-cli",
    help="Zabbix-cli is a command line interface for Zabbix.",
    add_completion=False,
)
