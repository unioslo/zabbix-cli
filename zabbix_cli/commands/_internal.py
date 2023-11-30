"""Commands that interact with the application itself."""
from __future__ import annotations

import typer

from zabbix_cli.app import app


@app.command("show_zabbixcli_config")
def show_zabbixcli_version(ctx: typer.Context) -> None:
    """Show the current application configuration."""
    print(app.state.config.as_toml())
