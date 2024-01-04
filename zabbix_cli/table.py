from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.table import Table

if TYPE_CHECKING:
    from zabbix_cli.models import ColsType, RowsType


def get_default_table(title: str | None = None, **kwargs) -> Table:
    """Returns Rich table with default settings for the application."""
    kwargs.setdefault("box", box.ROUNDED)
    return Table(title=title, **kwargs)


def get_table(
    cols: ColsType, rows: RowsType, title: str | None = None, **kwargs
) -> Table:
    """Returns a Rich table given a list of columns and rows."""
    table = get_default_table(title=title, **kwargs)
    for col in cols:
        table.add_column(col, overflow="fold")
    for row in rows:
        table.add_row(*row)
        table.add_section()
    return table
