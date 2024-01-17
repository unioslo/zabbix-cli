from __future__ import annotations

from typing import List
from typing import Optional

import typer

from zabbix_cli._v2_compat import ARGS_POSITIONAL
from zabbix_cli.app import app
from zabbix_cli.models import AggregateResult
from zabbix_cli.models import Result
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.utils.args import parse_bool_arg
from zabbix_cli.utils.args import parse_int_arg
from zabbix_cli.utils.args import parse_list_arg


HELP_PANEL = "Problem"


class AcknowledgeEventResult(TableRenderable):
    """Result type for `acknowledge_event` command."""

    event_ids: List[str] = []
    close: bool = False
    message: Optional[str] = None


class AcknowledgeTriggerLastEventResult(TableRenderable):
    """Result type for `acknowledge_trigger_last_event` command."""

    trigger_ids: List[str] = []
    event_ids: List[str] = []
    close: bool = False
    message: Optional[str] = None


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
    trigger_id: str = typer.Argument(..., help="ID of trigger to show events for."),
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Maximum number of events to show.",
    ),
    args: Optional[List[str]] = ARGS_POSITIONAL,
) -> None:
    if args:
        if len(args) != 2:
            exit_err("Invalid number of positional arguments.")
        limit = parse_int_arg(args[0])
    events = app.state.client.get_events(
        object_ids=trigger_id,
        sort_field="clock",
        sort_order="DESC",
        limit=limit,
    )
    render_result(AggregateResult(result=events))
