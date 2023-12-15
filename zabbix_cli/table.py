from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.table import Table

if TYPE_CHECKING:
    from zabbix_cli.models import ColsType, RowsType


def get_default_table(**kwargs) -> Table:
    """Returns Rich table with default settings for the application."""
    kwargs.setdefault("box", box.ROUNDED)
    return Table(**kwargs)


def get_table(cols: ColsType, rows: RowsType, **kwargs) -> Table:
    """Returns a Rich table given a list of columns and rows."""
    table = get_default_table(**kwargs)
    for col in cols:
        table.add_column(col, overflow="fold")
    for row in rows:
        table.add_row(*row)
        table.add_section()
    return table
