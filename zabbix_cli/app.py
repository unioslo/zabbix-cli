"""In order to mimick the API of Zabbix-cli < 3.0.0, we define a single
app object here, which we share between the different command modules.

Thus, every command is part of the same command group."""
from __future__ import annotations

import typer

from zabbix_cli.state import get_state
from zabbix_cli.state import State


class StatefulApp(typer.Typer):
    """A Typer app that provides access to the global state."""

    # NOTE: might be a good idea to add a typing.Unpack definition for the kwargs?
    def __init__(self, *args, **kwargs) -> None:
        StatefulApp.__init__.__doc__ = typer.Typer.__init__.__doc__
        super().__init__(*args, **kwargs)

    @property
    def state(self) -> State:
        return get_state()


app = StatefulApp(
    name="zabbix-cli",
    help="Zabbix-CLI is a command line interface for Zabbix.",
    add_completion=True,
)
