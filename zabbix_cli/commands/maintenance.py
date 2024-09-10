from __future__ import annotations

from typing import Optional

import typer

from zabbix_cli.app import Example
from zabbix_cli.app import app
from zabbix_cli.commands.common.args import OPTION_LIMIT
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.prompts import str_prompt_optional
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.enums import DataCollectionMode
from zabbix_cli.utils.args import parse_list_arg
from zabbix_cli.utils.utils import convert_time_to_interval

HELP_PANEL = "Maintenance"


@app.command(
    name="create_maintenance_definition",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Create a maintenance for a host from now for 1 hour (default)",
            "create_maintenance_definition 'My maintenance' --host 'My host'",
        ),
        Example(
            "Create a maintenance for a host group in a specific time period",
            "create_maintenance_definition 'My maintenance' --hostgroup 'Linux servers' --period '2022-12-31T23:00 to 2023-01-01T01:00'",
        ),
        Example(
            "Create a maintenance definition with all options",
            "create_maintenance_definition 'My maintenance' --hostgroup 'Linux servers' --period '2 hours 30 minutes 15 seconds' --description 'Maintenance for Linux servers' --data-collection ON",
        ),
    ],
)
def create_maintenance_definition(
    ctx: typer.Context,
    name: str = typer.Argument(
        help="Maintenance name.",
        show_default=False,
    ),
    description: Optional[str] = typer.Option(
        None,
        "--description",
        help="Description.",
    ),
    hosts: Optional[str] = typer.Option(
        None,
        "--host",
        help="Host(s). Comma-separated.",
    ),
    hostgroups: Optional[str] = typer.Option(
        None,
        "--hostgroup",
        help="Host group(s). Comma-separated.",
    ),
    period: str = typer.Option(
        "1 hour",
        "--period",
        help="Time period in seconds, minutes, hours, days, or as ISO timestamp.",
    ),
    data_collection: DataCollectionMode = typer.Option(
        DataCollectionMode.ON.value,
        "--data-collection",
        help="Enable or disable data collection.",
    ),
) -> None:
    """Create a new one-time maintenance definition.

    One can define an interval between two timestamps in ISO format
    or a time period in minutes, hours or days from the moment the
    definition is created. Periods are assumed to be in seconds if no unit is
    specified. If no period is specified, the default is 1 hour.
    """
    from zabbix_cli.commands.results.maintenance import (
        CreateMaintenanceDefinitionResult,
    )
    from zabbix_cli.models import Result

    hosts_arg = parse_list_arg(hosts)
    hgs_arg = parse_list_arg(hostgroups)

    start, end = convert_time_to_interval(period)
    hostlist = app.state.client.get_hosts(*hosts_arg) if hosts_arg else []
    hglist = app.state.client.get_hostgroups(*hgs_arg) if hgs_arg else []

    with app.status("Creating maintenance definition..."):
        maintenance_id = app.state.client.create_maintenance(
            name=name,
            description=description,
            active_since=start,
            active_till=end,
            hosts=hostlist,
            hostgroups=hglist,
            data_collection=data_collection,
        )
    render_result(
        Result(
            message=f"Created maintenance definition ({maintenance_id}).",
            result=CreateMaintenanceDefinitionResult(maintenance_id=maintenance_id),
        )
    )


# TODO: remove maintenances affecting certain hosts or host groups
# Either by removing the maintenance definition itself or by removing the hosts
# or host groups from the maintenance definition...
# TODO: Add remove maintenance by name
@app.command(name="remove_maintenance_definition", rich_help_panel=HELP_PANEL)
def remove_maintenance_definition(
    ctx: typer.Context,
    maintenance_id: str = typer.Argument(
        help="ID(s) of maintenance(s) to remove. Comma-separated.",
        show_default=False,
    ),
) -> None:
    """Remove a maintenance definition."""
    from zabbix_cli.models import Result

    maintenance_ids = parse_list_arg(maintenance_id)
    if not maintenance_ids:
        exit_err("Must specify at least one maintenance ID.")

    for mid in maintenance_ids:  # Check that each ID exists
        app.state.client.get_maintenance(mid)

    with app.status("Removing maintenance definition..."):
        app.state.client.delete_maintenance(*maintenance_ids)

    render_result(Result(message="Removed maintenance definition(s)."))


@app.command(name="show_maintenance_definitions", rich_help_panel=HELP_PANEL)
def show_maintenance_definitions(
    ctx: typer.Context,
    maintenance_id: Optional[str] = typer.Option(
        None, "--maintenance-id", help="Maintenance IDs. Comma-separated."
    ),
    hostgroup: Optional[str] = typer.Option(
        None, "--hostgroup", help="Host group names. Comma-separated."
    ),
    host: Optional[str] = typer.Option(
        None, "--host", help="Host names. Comma-separated."
    ),
) -> None:
    """Show maintenance definitions for IDs, host groups or hosts.

    At least one of [option]--maintenance-id[/], [option]--hostgroup[/], or [option]--host[/] is required.
    """
    from zabbix_cli.commands.results.maintenance import ShowMaintenanceDefinitionsResult
    from zabbix_cli.models import AggregateResult

    if not any((maintenance_id, hostgroup, host)):
        maintenance_id = str_prompt_optional("Maintenance ID")
        hostgroup = str_prompt_optional("Host group(s)")
        host = str_prompt_optional("Host(s)")

    mids = parse_list_arg(maintenance_id)
    hg_names = parse_list_arg(hostgroup)
    host_names = parse_list_arg(host)

    if not any((mids, hg_names, host_names)):
        exit_err("Must specify at least one maintenance ID, host group, or host.")

    # Checks that host(group)s exist and gets their IDs
    if hg_names:
        hostgroups = app.state.client.get_hostgroups(*hg_names)
    else:
        hostgroups = []
    if host_names:
        hosts = app.state.client.get_hosts(*host_names)
    else:
        hosts = []

    with app.status("Fetching maintenance definitions..."):
        maintenances = app.state.client.get_maintenances(
            maintenance_ids=mids,
            hostgroups=hostgroups,
            hosts=hosts,
        )

    render_result(
        AggregateResult(
            result=[
                ShowMaintenanceDefinitionsResult(
                    maintenanceid=m.maintenanceid,
                    name=m.name,
                    type=m.maintenance_type,
                    active_till=m.active_till,  # type: ignore # validator handles None
                    hosts=[h.host for h in m.hosts],
                    groups=[hg.name for hg in m.hostgroups],
                    description=m.description,
                )
                for m in maintenances
            ]
        )
    )


@app.command(name="show_maintenance_periods", rich_help_panel=HELP_PANEL)
def show_maintenance_periods(
    ctx: typer.Context,
    maintenance_id: Optional[str] = typer.Argument(
        None,
        help="Maintenance IDs. Comma-separated. Supports wildcards.",
        show_default=False,
    ),
    limit: int = OPTION_LIMIT,
) -> None:
    """Show maintenance periods for one or more maintenance definitions.

    Shows all maintenance definitions by default.
    """
    from zabbix_cli.commands.results.maintenance import ShowMaintenancePeriodsResult
    from zabbix_cli.models import AggregateResult

    mids = parse_list_arg(maintenance_id)
    with app.status("Fetching maintenance periods..."):
        maintenances = app.state.client.get_maintenances(
            maintenance_ids=mids, limit=limit
        )

    render_result(
        AggregateResult(
            result=[
                ShowMaintenancePeriodsResult(
                    maintenanceid=m.maintenanceid,
                    name=m.name,
                    timeperiods=m.timeperiods,
                    hosts=[h.host for h in m.hosts],
                    groups=[hg.name for hg in m.hostgroups],
                )
                for m in maintenances
            ]
        )
    )
