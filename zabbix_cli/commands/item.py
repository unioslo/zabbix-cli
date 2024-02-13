from __future__ import annotations

from typing import List
from typing import Optional
from typing import TYPE_CHECKING

import typer
from pydantic import computed_field
from pydantic import Field

from zabbix_cli._v2_compat import ARGS_POSITIONAL
from zabbix_cli.app import app
from zabbix_cli.app import Example
from zabbix_cli.models import AggregateResult
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.types import Item


if TYPE_CHECKING:
    from zabbix_cli.models import RowsType  # noqa: F401
    from zabbix_cli.models import ColsRowsType


HELP_PANEL = "Item"


class UngroupedItem(TableRenderable):
    itemid: str
    name: Optional[str]
    key: Optional[str]
    lastvalue: Optional[str]
    host: Optional[str]

    @classmethod
    def from_item(cls, item: Item) -> UngroupedItem:
        return cls(
            itemid=item.itemid,
            name=item.name,
            key=item.key,
            lastvalue=item.lastvalue,
            host=item.hosts[0].host if item.hosts else None,
        )

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["Item ID", "Name", "Key", "Last value", "Host"]
        rows = [
            [
                self.itemid,
                self.name or "",
                self.key or "",
                self.lastvalue or "",
                self.host or "",
            ]
        ]  # type: RowsType
        return cols, rows


class ItemResult(Item):
    """Alternate rendering of Item."""

    grouped: bool = Field(False, exclude=True)

    @classmethod
    def from_item(cls, item: Item) -> ItemResult:
        return cls.model_validate(item, from_attributes=True)

    @computed_field  # type: ignore[misc]
    @property
    def host(self) -> str:
        """LEGACY: serialize list of hosts as newline-delimited string."""
        return "\n".join(h.host for h in self.hosts)

    def __cols_rows__(self) -> ColsRowsType:
        # As long as we include the "host" computed field, we need to
        # override the __cols_rows__ method.
        cols = ["Name", "Key", "Last value", "Hosts"]
        rows = [
            [
                self.name or "",
                self.key or "",
                self.lastvalue or "",
                "\n".join(h.host for h in self.hosts),
            ],
        ]  # type: RowsType
        if self.grouped:
            cols.insert(0, "Item ID")
            rows[0].insert(0, self.itemid)
        return cols, rows


def group_items(items: List[Item]) -> List[ItemResult]:
    """Group items by key+lastvalue.

    Keeps first item for each key+lastvalue pair, and adds hosts from
    duplicate items to the first item.


    Example:

    ```py
        # Given the following items:
        >>> items = [
            Item(itemid="1", key="foo", lastvalue="bar", hosts=[Host(hostid="1")]),
            Item(itemid="2", key="foo", lastvalue="bar", hosts=[Host(hostid="2")]),
            Item(itemid="3", key="baz", lastvalue="baz", hosts=[Host(hostid="3")]),
            Item(itemid="4", key="baz", lastvalue="baz", hosts=[Host(hostid="4")]),
        ]
        >>> group_items(items)
        [
            Item(itemid="1", key="foo", lastvalue="bar", hosts=[Host(hostid="1"), Host(hostid="2")]),
            Item(itemid="3", key="baz", lastvalue="baz", hosts=[Host(hostid="3"), Host(hostid="4")]),
        ]
        # Hosts from items 2 and 4 were added to item 1 and 3, respectively.
    ```
    """
    item_map = {}  # type: dict[str, ItemResult]

    for item in items:
        if not item.name or not item.lastvalue or not item.key or not item.hosts:
            continue

        key = item.key + item.lastvalue
        for host in item.hosts:
            if key in item_map:
                item_map[key].hosts.append(host)
            else:
                res = ItemResult.from_item(item)
                res.grouped = True
                item_map[key] = res
    return list(item_map.values())


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
