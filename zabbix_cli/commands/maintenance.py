from __future__ import annotations

from typing import Optional

import typer

from zabbix_cli.app import app
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.utils.args import APIStr
from zabbix_cli.utils.args import APIStrEnum
from zabbix_cli.utils.args import ChoiceMixin
from zabbix_cli.utils.args import parse_list_arg


HELP_PANEL = "Maintenance"


class SomeResult(TableRenderable):
    """Result type for `load_balance_proxy_hosts` command."""

    pass


class DataCollectionMode(ChoiceMixin[str], APIStrEnum):
    """Maintenance type."""

    ON = APIStr("on", "0")
    OFF = APIStr("off", "1")


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
        None, "--hosts", help="Comma-separated list of hosts."
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
    One can define an interval between two timestamps in ISO format
    or a time period in minutes, hours or days from the moment the
    definition is created

    [bold]From 22:00 until 23:00 on 2016-11-21:[/]

        [green]--period '2016-11-21T22:00 to 2016-11-21T23:00'[/]


    [bold]From now for 2 hours:[/]

        [green]--period '2 hours'[/]
    """
    if not name:
        name = str_prompt("Name")
    if not description:
        description = str_prompt("Description", empty_ok=True, default="")
    if not hosts:
        hosts = str_prompt("Hosts", empty_ok=True, default="")
    hostlist = parse_list_arg(hosts)  # noqa: F841

    if not hostgroups:
        hostgroups = str_prompt("Host groups", empty_ok=True, default="")
    hostgrouplist = parse_list_arg(hostgroups)  # noqa: F841

    if not hosts and not hostgroups:
        exit_err("Must specify at least one host or host group.")

    if not period:
        period = str_prompt("Period")

    if not data_collection:
        data_collection = DataCollectionMode.from_prompt("Data collection")


@app.command(name="remove_maintenance_definition", rich_help_panel=HELP_PANEL)
def remove_maintenance_definition(ctx: typer.Context) -> None:
    pass


@app.command(name="show_maintenance_definitions", rich_help_panel=HELP_PANEL)
def show_maintenance_definitions(ctx: typer.Context) -> None:
    pass


@app.command(name="show_maintenance_periods", rich_help_panel=HELP_PANEL)
def show_maintenance_periods(ctx: typer.Context) -> None:
    pass
