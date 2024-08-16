from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.table import Table

if TYPE_CHECKING:
    from zabbix_cli.models import ColsType
    from zabbix_cli.models import RowsType


def get_table(
    cols: ColsType,
    rows: RowsType,
    title: str | None = None,
    show_lines: bool = True,
    box: box.Box = box.ROUNDED,
) -> Table:
    """Returns a Rich table given a list of columns and rows."""
    table = Table(title=title, box=box, show_lines=show_lines)
    for col in cols:
        table.add_column(col, overflow="fold")
    for row in rows:
        # We might have subtables in the rows.
        # If they have no rows, we don't want to render them.
        row = [cell if not isinstance(cell, Table) or cell.rows else "" for cell in row]
        table.add_row(*row)
    return table
