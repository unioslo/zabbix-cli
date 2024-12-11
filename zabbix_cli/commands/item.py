from __future__ import annotations

from typing import Optional

import typer

from zabbix_cli._v2_compat import ARGS_POSITIONAL
from zabbix_cli.app import Example
from zabbix_cli.app import app
from zabbix_cli.commands.common.args import OPTION_LIMIT
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.render import render_result
from zabbix_cli.utils.args import parse_list_arg


@app.command(
    name="show_last_values",
    rich_help_panel="Host Monitoring",  # Moved to host monitoring for now
    examples=[
        Example(
            "Get items starting with 'MongoDB'",
            "show_last_values 'MongoDB*'",
        ),
        Example(
            "Get items containing 'memory'",
            "show_last_values '*memory*'",
        ),
        Example(
            "Get all items (WARNING: slow!)",
            "show_last_values '*'",
        ),
    ],
)
def show_last_values(
    ctx: typer.Context,
    item: str = typer.Argument(
        help="Item names or IDs. Comma-separated. Supports wildcards.",
        show_default=False,
    ),
    group: bool = typer.Option(
        False, "--group", help="Group items with the same value."
    ),
    limit: Optional[int] = OPTION_LIMIT,
    args: Optional[list[str]] = ARGS_POSITIONAL,
) -> None:
    """Show the last values of given items of monitored hosts."""
    from zabbix_cli.commands.results.item import ItemResult
    from zabbix_cli.commands.results.item import group_items
    from zabbix_cli.models import AggregateResult

    if args:
        if not len(args) == 1:
            exit_err("Invalid number of positional arguments. Use options instead.")
        group = args[0] == "1"
        # No format arg in V2...

    names_or_ids = parse_list_arg(item)
    with app.status("Fetching items..."):
        items = app.state.client.get_items(
            *names_or_ids, select_hosts=True, monitored=True, limit=limit
        )

    # HACK: not super elegant, but this allows us to match V2 output while
    # with and without the --group flag, as well as ALSO rendering the entire
    # Item object instead of just a subset of fields.
    # Ideally, it would be nice to not have to re-validate when not grouping
    # but I'm not sure how to do that in Pydantic V2?
    if group:
        res = group_items(items)
        render_result(AggregateResult(result=res))
    else:
        res = [ItemResult.from_item(item) for item in items]
    render_result(AggregateResult(result=res))
