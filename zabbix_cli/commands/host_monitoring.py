from __future__ import annotations

import typer

from zabbix_cli.app import app
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.enums import MonitoringStatus

HELP_PANEL = "Host Monitoring"


@app.command(
    name="define_host_monitoring_status",
    rich_help_panel=HELP_PANEL,
    hidden=True,
    deprecated=True,
)
@app.command(name="monitor_host", rich_help_panel=HELP_PANEL)
def monitor_host(
    hostname: str = typer.Argument(
        help="Name of host",
        show_default=False,
    ),
    new_status: MonitoringStatus = typer.Argument(
        help="Monitoring status",
        case_sensitive=False,
        show_default=False,
    ),
) -> None:
    """Monitor or unmonitor a host."""
    from zabbix_cli.models import Result

    host = app.state.client.get_host(hostname)
    app.state.client.update_host_status(host, new_status)
    render_result(
        Result(
            message=f"Updated host {hostname!r}. New monitoring status: {new_status}"
        )
    )


@app.command(name="show_host_inventory", rich_help_panel=HELP_PANEL)
def show_host_inventory(
    hostname_or_id: str = typer.Argument(
        help="Hostname or ID",
        show_default=False,
    ),
) -> None:
    """Show host inventory details for a specific host."""
    # TODO: support undocumented filter argument from V2
    # TODO: Add mapping of inventory keys to human readable names (Web GUI names)
    host = app.state.client.get_host(hostname_or_id, select_inventory=True)
    render_result(host.inventory)


@app.command(name="update_host_inventory", rich_help_panel=HELP_PANEL)
def update_host_inventory(
    ctx: typer.Context,
    hostname_or_id: str = typer.Argument(
        help="Hostname or ID of host.",
        show_default=False,
    ),
    key: str = typer.Argument(
        help="Inventory key",
        show_default=False,
    ),
    value: str = typer.Argument(
        help="Inventory value",
        show_default=False,
    ),
) -> None:
    """Update a host inventory field.

    Inventory fields in the API do not always match Web GUI field names.
    Use `zabbix-cli -o json show_host_inventory <hostname>` to see the available fields.
    """
    from zabbix_cli.models import Result

    host = app.state.client.get_host(hostname_or_id)
    to_update = {key: value}
    app.state.client.update_host_inventory(host, to_update)
    render_result(Result(message=f"Updated inventory field {key!r} for host {host}."))
