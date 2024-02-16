from __future__ import annotations

from typing import Optional

import typer

from zabbix_cli.app import app
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.prompts import str_prompt_optional
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.enums import DataCollectionMode
from zabbix_cli.utils.args import parse_list_arg
from zabbix_cli.utils.utils import convert_time_to_interval


HELP_PANEL = "Maintenance"


@app.command(name="create_maintenance_definition", rich_help_panel=HELP_PANEL)
def create_maintenance_definition(
    ctx: typer.Context,
    name: Optional[str] = typer.Argument(
        None, help="Name of the maintenance definition."
    ),
    description: Optional[str] = typer.Option(
        None, "--description", help="Description"
    ),
    hosts: Optional[str] = typer.Option(
        None, "--host", help="Comma-separated list of hosts."
    ),
    hostgroups: Optional[str] = typer.Option(
        None, "--hostgroups", help="Comma-separated list of host groups."
    ),
    period: Optional[str] = typer.Option(
        None,
        "--period",
        help="Time period in seconds, minutes, hours, days, or as ISO timestamp.",
    ),
    data_collection: Optional[DataCollectionMode] = typer.Option(
        None, "--data-collection", help="Enable or disable data collection."
    ),
) -> None:
    """
    Create a new one-time maintenance definition.

    One can define an interval between two timestamps in ISO format
    or a time period in minutes, hours or days from the moment the
    definition is created

    [bold]From 22:00 until 23:00 on 2016-11-21:[/]

        [green]--period '2016-11-21T22:00 to 2016-11-21T23:00'[/]


    [bold]From now for 2 hours:[/]

        [green]--period '2 hours'[/]

    [bold]Seconds are assumed if no unit is specified:[/]

        [green]--period 3600[/]
    """
    from zabbix_cli.commands.results.maintenance import (
        CreateMaintenanceDefinitionResult,
    )
    from zabbix_cli.models import Result

    if not name:
        name = str_prompt("Name")
    if not description:
        description = str_prompt_optional("Description")
    if not hosts:
        hosts = str_prompt_optional("Hosts")
    hosts_arg = parse_list_arg(hosts)

    if not hostgroups:
        hostgroups = str_prompt_optional("Host groups")
    hgs_arg = parse_list_arg(hostgroups)

    if not period:
        period = str_prompt("Period", default="1 hour")

    if not data_collection:
        data_collection = DataCollectionMode.from_prompt(
            "Data collection", default=DataCollectionMode.ON
        )

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
    maintenance_id: Optional[str] = typer.Argument(
        None, help="ID of maintenance to remove"
    ),
) -> None:
    """Remove a maintenance definition."""
    from zabbix_cli.models import Result

    if not maintenance_id:
        maintenance_id = str_prompt("Maintenance ID(s)")

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
        None, "--maintenance-id", help="Comma-separated list of maintenance IDs."
    ),
    hostgroup: Optional[str] = typer.Option(
        None, "--hostgroup", help="Comma-separated list of host groups."
    ),
    host: Optional[str] = typer.Option(
        None, "--host", help="Comma-separated list of hosts."
    ),
) -> None:
    """Show maintenance definitions for IDs, host groups or hosts.

    At least one of --maintenance-id, --hostgroup, or --host is required."""
    from zabbix_cli.models import AggregateResult
    from zabbix_cli.commands.results.maintenance import ShowMaintenanceDefinitionsResult

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
    ),
) -> None:
    """Show maintenance periods for one or more maintenance definitions.

    Shows all maintenance definitions by default.
    """
    from zabbix_cli.models import AggregateResult
    from zabbix_cli.commands.results.maintenance import ShowMaintenancePeriodsResult

    mids = parse_list_arg(maintenance_id)
    maintenances = app.state.client.get_maintenances(maintenance_ids=mids)
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
