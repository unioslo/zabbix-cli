from __future__ import annotations

from typing import List
from typing import TYPE_CHECKING

import typer
from rich.box import SIMPLE_HEAD

from zabbix_cli import auth
from zabbix_cli.app import app
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.logs import logger
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import success
from zabbix_cli.output.render import render_result

if TYPE_CHECKING:
    from zabbix_cli.models import ColsType  # noqa: F401
    from zabbix_cli.models import RowsType  # noqa: F401


HELP_PANEL = "CLI"


@app.command(name="login", rich_help_panel=HELP_PANEL)
def import_configuration(
    ctx: typer.Context,
) -> None:
    """Reauthenticate with the Zabbix API.

    Creates a new auth token.
    """
    if not app.state.repl:
        raise ZabbixCLIError("This command is only available in the REPL.")

    client = app.state.client
    config = app.state.config

    # End current session if it's active
    try:
        app.state.client.user.logout()
        if config.app.use_auth_token_file:
            auth.clear_auth_token_file(config)
    # Fails if no active session (ok)
    except Exception as e:
        logger.debug("Failed to log out: %s", e)

    auth.login(client, config)
    success(f"Logged in to {config.api.url} as {config.app.username}.")


class HistoryResult(TableRenderable):
    """Result type for `show_history` command."""

    __show_lines__ = False
    __box__ = SIMPLE_HEAD

    commands: List[str] = []


# TODO: find out how to log full command invocations (especially in REPL, where we cant use sys.argv)
@app.command("show_history", help=HELP_PANEL)
def show_history(
    ctx: typer.Context,
    limit: int = typer.Option(
        10, "--limit", "-N", help="Limit to last N commands. 0 to disable.", min=0
    ),
    # TODO: Add --session option to limit to current session
    # In order to add that, we need to store the history len at the start of the session
) -> None:
    """Show the command history."""
    # Load the entire history, then limit afterwards
    history = list(app.state.history.get_strings())
    history = history[-limit:]
    render_result(HistoryResult(commands=history))
