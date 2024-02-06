from __future__ import annotations

from typing import List
from typing import Optional

import typer

from zabbix_cli._v2_compat import ARGS_POSITIONAL
from zabbix_cli.app import app
from zabbix_cli.models import AggregateResult
from zabbix_cli.models import Result
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import err_console
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.types import TriggerPriority
from zabbix_cli.utils.args import parse_bool_arg
from zabbix_cli.utils.args import parse_int_arg
from zabbix_cli.utils.args import parse_list_arg


HELP_PANEL = "Problem"


class AcknowledgeEventResult(TableRenderable):
    """Result type for `acknowledge_event` command."""

    event_ids: List[str] = []
    close: bool = False
    message: Optional[str] = None


class AcknowledgeTriggerLastEventResult(AcknowledgeEventResult):
    """Result type for `acknowledge_trigger_last_event` command."""

    trigger_ids: List[str] = []


@app.command(name="acknowledge_event", rich_help_panel=HELP_PANEL)
def acknowledge_event(
    ctx: typer.Context,
    event_ids: Optional[str] = typer.Argument(
        None, help="Comma-separated list of event ID(s)"
    ),
    message: str = typer.Option(
        "[Zabbix-CLI] Acknowledged via acknowledge_events",
        "--message",
        "-m",
        help="Message to add to the event",
    ),
    close: bool = typer.Option(
        False,
        "--close",
        "-c",
        help="Close the event after acknowledging it",
    ),
    # Legacy positional args
    args: Optional[List[str]] = ARGS_POSITIONAL,
) -> None:
    """Acknowledge event(s) by ID."""
    if not event_ids:
        event_ids = str_prompt("Event ID(s)")
    eids = parse_list_arg(event_ids)
    if not eids:
        exit_err("No event IDs specified.")

    if args:
        if len(args) != 2:
            exit_err("Invalid number of positional arguments.")
        message = args[0]
        close = parse_bool_arg(args[1])
    # Don't prompt for missing message. It's optional.
    acknowledged_ids = app.state.client.acknowledge_event(
        *eids, message=message, close=close
    )

    msg = "Event(s) acknowledged"
    if close:
        msg += " and closed"
    render_result(
        Result(
            message=msg,
            result=AcknowledgeEventResult(
                event_ids=acknowledged_ids, close=close, message=message
            ),
        )
    )


@app.command(name="acknowledge_trigger_last_event", rich_help_panel=HELP_PANEL)
def acknowledge_trigger_last_event(
    ctx: typer.Context,
    trigger_ids: str,
    message: Optional[str] = typer.Option(
        None,
        "--message",
        help="Message to include in acknowledgement",
    ),
    close: bool = typer.Option(
        False,
        "--close",
        "-c",
        help="Close the event after acknowledging it",
    ),
    # Legacy positional args
    args: Optional[List[str]] = ARGS_POSITIONAL,
) -> None:
    """Acknowledges the the last event for the given trigger(s)."""
    tids = parse_list_arg(trigger_ids)
    if not tids:
        exit_err("No trigger IDs specified.")
    if args:
        if len(args) != 2:
            exit_err("Invalid number of positional arguments.")
        message = args[0]
        close = parse_bool_arg(args[1])

    # Message is optional, so we don't prompt for it if it's missing
    events = [app.state.client.get_event(object_id=tid) for tid in tids]
    event_ids = [e.eventid for e in events]
    acknowledged_ids = app.state.client.acknowledge_event(
        *event_ids, message=message, close=close
    )

    msg = "Event(s) acknowledged"
    if close:
        msg += " and closed"
    render_result(
        Result(
            message=msg,
            result=AcknowledgeTriggerLastEventResult(
                trigger_ids=tids,
                event_ids=acknowledged_ids,
                close=close,
                message=message,
            ),
        )
    )


@app.command(name="show_trigger_events", rich_help_panel=HELP_PANEL)
def show_trigger_events(
    ctx: typer.Context,
    trigger_id: Optional[str] = typer.Option(
        None,
        "--trigger-id",
        help="ID of trigger(s) to show events for.",
    ),
    hostgroups: Optional[str] = typer.Option(
        None,
        # FIXME: decide between singular and plural option names
        "--hostgroup",
        "--hostgroups",
        help="Host group(s) to show events for.",
    ),
    hosts: Optional[str] = typer.Option(
        None,
        "--host",
        "--hosts",
        help="Host(s) to show events for.",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Maximum number of events to show.",
    ),
    args: Optional[List[str]] = ARGS_POSITIONAL,
) -> None:
    """Show the latest events for the given trigger(s), host(s), and/or host group(s).

    At least one trigger ID, host or host group must be specified."""
    if args:
        if len(args) != 2:
            exit_err("Invalid number of positional arguments.")
        trigger_id = args[0]
        limit = parse_int_arg(args[1])

    # Parse commma-separated args
    trigger_ids = parse_list_arg(trigger_id)
    hostgroups_args = parse_list_arg(hostgroups)
    hosts_args = parse_list_arg(hosts)
    if not trigger_ids and not hostgroups_args and not hosts_args:
        err_console.print(ctx.get_help())
        exit_err("At least one trigger ID, host or host group must be specified.")

    # Fetch the host(group)s if specified
    hostgroups_list = [app.state.client.get_hostgroup(hg) for hg in hostgroups_args]
    hosts_list = [app.state.client.get_host(host) for host in hosts_args]

    events = app.state.client.get_events(
        object_ids=trigger_ids,
        group_ids=[hg.groupid for hg in hostgroups_list],
        host_ids=[host.hostid for host in hosts_list],
        sort_field="clock",
        sort_order="DESC",
        limit=limit,
    )
    render_result(AggregateResult(result=events))


@app.command(name="show_alarms", rich_help_panel=HELP_PANEL)
def show_alarms(
    ctx: typer.Context,
    description: Optional[str] = typer.Option(
        None,
        "--description",
        help="Description of alarm(s) to show.",
    ),
    # Could this be a list of priorities in V2?
    priority: Optional[TriggerPriority] = typer.Option(
        None,
        "--priority",
        help="Priority of alarm(s) to show.",
    ),
    hostgroups: Optional[str] = typer.Option(
        None,
        "--hostgroups",
        help="Host group(s) to show alarms for. Comma-separated.",
    ),
    unacknowledged: bool = typer.Option(
        True,
        "--unack/--ack",
        help="Show only alarms whose last event is unacknowledged.",
    ),
    args: Optional[List[str]] = ARGS_POSITIONAL,
) -> None:
    """Show the latest events for the given trigger(s), host(s), and/or host group(s).

    At least one trigger ID, host or host group must be specified."""
    if args:
        if len(args) != 4:
            exit_err("Invalid number of positional arguments.")
        description = args[0]
        priority = TriggerPriority(args[1])
        hostgroups = args[2]
        # in V2, "*" was used to indicate "false"
        if args[3] == "*":
            unacknowledged = False
        else:
            unacknowledged = parse_bool_arg(args[3])

    hostgroups_args = parse_list_arg(hostgroups)
    hgs = [app.state.client.get_hostgroup(hg) for hg in hostgroups_args]
    triggers = app.state.client.get_triggers(
        hostgroups=hgs,
        description=description,
        priority=priority,
        unacknowledged=unacknowledged,
        select_hosts=True,
    )
    render_result(AggregateResult(result=triggers))