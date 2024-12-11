from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Optional

from pydantic import Field
from pydantic import computed_field

from zabbix_cli.models import TableRenderable
from zabbix_cli.pyzabbix.types import Item

if TYPE_CHECKING:
    from zabbix_cli.models import ColsRowsType
    from zabbix_cli.models import RowsType


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
        rows: RowsType = [
            [
                self.itemid,
                self.name or "",
                self.key or "",
                self.lastvalue or "",
                self.host or "",
            ]
        ]
        return cols, rows


class ItemResult(Item):
    """Alternate rendering of Item."""

    grouped: bool = Field(False, exclude=True)

    @classmethod
    def from_item(cls, item: Item) -> ItemResult:
        return cls.model_validate(item, from_attributes=True)

    @computed_field
    @property
    def host(self) -> str:
        """LEGACY: serialize list of hosts as newline-delimited string."""
        return "\n".join(h.host for h in self.hosts)

    def __cols_rows__(self) -> ColsRowsType:
        # As long as we include the "host" computed field, we need to
        # override the __cols_rows__ method.
        cols = ["Name", "Key", "Last value", "Hosts"]
        rows: RowsType = [
            [
                self.name or "",
                self.key or "",
                self.lastvalue or "",
                "\n".join(h.host for h in self.hosts),
            ],
        ]
        if self.grouped:
            cols.insert(0, "Item ID")
            rows[0].insert(0, self.itemid)
        return cols, rows


def group_items(items: list[Item]) -> list[ItemResult]:
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
    from zabbix_cli.commands.results.item import ItemResult

    item_map: dict[str, ItemResult] = {}

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
