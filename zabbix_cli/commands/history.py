"""Commands that interact with the application itself."""
from __future__ import annotations

from typing import Dict
from typing import List
from typing import TYPE_CHECKING

import typer
from pydantic import model_serializer

from zabbix_cli.app import app
from zabbix_cli.history import History
from zabbix_cli.history import HistoryEntry
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.render import render_result


if TYPE_CHECKING:
    from zabbix_cli.models import ColsType  # noqa: F401
    from zabbix_cli.models import ColsRowsType
    from zabbix_cli.models import RowsType  # noqa: F401


class HistoryResult(TableRenderable):
    """Result type for `show_history` command."""

    commands: List[HistoryEntry] = []

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["Command", "Timestamp"]  # type: ColsType
        rows = [
            [entry.ctx.command_path, str(entry.timestamp)] for entry in self.commands
        ]  # type: RowsType
        return cols, rows

    @model_serializer
    def ser_model(self) -> List[Dict[str, str]]:
        return [
            {
                "command": entry.ctx.command_path,
                "timestamp": str(entry.timestamp),
            }
            for entry in self.commands
        ]


# TODO: find out how to log full command invocations (especially in REPL, where we cant use sys.argv)
@app.command("show_history", hidden=True)
def show_history(ctx: typer.Context) -> None:
    """Show the command history."""
    history = History()
    render_result(HistoryResult(commands=list(history)))
