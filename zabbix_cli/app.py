"""In order to mimick the API of Zabbix-cli < 3.0.0, we define a single
app object here, which we share between the different command modules.

Thus, every command is part of the same command group."""
from __future__ import annotations

from typing import Tuple

import typer
from typer.main import Typer

from zabbix_cli.state import get_state
from zabbix_cli.state import State


class StatefulApp(typer.Typer):
    """A Typer app that provides access to the global state."""

    # NOTE: might be a good idea to add a typing.Unpack definition for the kwargs?
    def __init__(self, *args, **kwargs) -> None:
        StatefulApp.__init__.__doc__ = typer.Typer.__init__.__doc__
        super().__init__(*args, **kwargs)

    def add_typer(self, typer_instance: Typer, **kwargs) -> None:
        kwargs.setdefault("no_args_is_help", True)
        return super().add_typer(typer_instance, **kwargs)

    def add_subcommand(self, app: typer.Typer, *args, **kwargs) -> None:
        kwargs.setdefault("rich_help_panel", "Subcommands")
        self.add_typer(app, **kwargs)

    @property
    def state(self) -> State:
        return get_state()

    @property
    def api_version(self) -> Tuple[int, ...]:
        """Get the current API version. Will fail if not connected to the API."""
        return self.state.client.version.release


app = StatefulApp(
    name="zabbix-cli",
    help="Zabbix-CLI is a command line interface for Zabbix.",
    add_completion=True,
    rich_markup_mode="rich",
)
