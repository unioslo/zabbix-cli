"""Commands that interact with the application itself."""
from __future__ import annotations

import typer

from zabbix_cli.app import app
from zabbix_cli.output.console import info


@app.command("show_zabbixcli_config")
def show_zabbixcli_version(ctx: typer.Context) -> None:
    """Show the current application configuration."""
    config = app.state.config
    print(config.as_toml())

    if config.config_path:
        info(f"Config file: {config.config_path}")
