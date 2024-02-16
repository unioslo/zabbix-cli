from __future__ import annotations

from typing import List
from typing import Optional

import typer

from zabbix_cli._v2_compat import ARGS_POSITIONAL
from zabbix_cli.app import app
from zabbix_cli.app import Example
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result


HELP_PANEL = "Item"


@app.command(
    name="show_last_values",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Get items starting with 'MongoDB'",
            "zabbix-cli show_last_values 'MongoDB*'",
        ),
        Example(
            "Get items containing 'memory'",
            "zabbix-cli show_last_values '*memory*'",
        ),
        Example(
            "Get all items (WARNING: slow!)",
            "zabbix-cli show_last_values '*'",
        ),
    ],
)
def show_last_values(
    ctx: typer.Context,
    item_name: Optional[str] = typer.Argument(
        None,
        help="Name of item(s) to get. Supports wildcards.",
    ),
    group: bool = typer.Option(
        False, "--group", is_flag=True, help="Group items with the same value."
    ),
    args: Optional[List[str]] = ARGS_POSITIONAL,
) -> None:
    """Shows the last values of given item(s) of monitored hosts."""
    from zabbix_cli.commands.results.item import ItemResult
    from zabbix_cli.commands.results.item import group_items
    from zabbix_cli.models import AggregateResult

    if args:
        if not len(args) == 1:
            exit_err("Invalid number of positional arguments. Use options instead.")
        group = args[0] == "1"
        # No format arg in V2...
    if not item_name:
        item_name = str_prompt("Item name")

    items = app.state.client.get_items(item_name, select_hosts=True, monitored=True)

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
