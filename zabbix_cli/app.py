"""In order to mimick the API of Zabbix-cli < 3.0.0, we define a single
app object here, which we share between the different command modules.

Thus, every command is part of the same command group."""
from __future__ import annotations

from typing import Iterable
from typing import Optional
from typing import Protocol
from typing import Tuple
from typing import TYPE_CHECKING

import typer
from typer.main import Typer

from zabbix_cli.state import get_state
from zabbix_cli.state import State

if TYPE_CHECKING:
    from rich.status import Status  # noqa: F401
    from rich.console import RenderableType  # noqa: F401
    from rich.style import StyleType  # noqa: F401


class StatusCallable(Protocol):
    """Function that returns a Status object."""

    def __call__(
        self,
        status: RenderableType,
        *,
        spinner: str = "dots",
        spinner_style: StyleType = "status.spinner",
        speed: float = 1.0,
        refresh_per_second: float = 12.5,
    ) -> Status:
        ...


class StatefulApp(typer.Typer):
    """A Typer app that provides access to the global state."""

    parent: Optional[StatefulApp]

    # NOTE: might be a good idea to add a typing.Unpack definition for the kwargs?
    def __init__(self, *args, **kwargs) -> None:
        StatefulApp.__init__.__doc__ = typer.Typer.__init__.__doc__
        self.parent = None
        super().__init__(*args, **kwargs)

    def add_typer(self, typer_instance: Typer, **kwargs) -> None:
        kwargs.setdefault("no_args_is_help", True)
        if isinstance(typer_instance, StatefulApp):
            typer_instance.parent = self
        return super().add_typer(typer_instance, **kwargs)

    def add_subcommand(self, app: typer.Typer, *args, **kwargs) -> None:
        kwargs.setdefault("rich_help_panel", "Subcommands")
        self.add_typer(app, **kwargs)

    def parents(self) -> Iterable[StatefulApp]:
        """Get all parent apps."""
        app = self
        while app.parent:
            yield app.parent
            app = app.parent

    def find_root(self) -> StatefulApp:
        """Get the root app."""
        app = self
        for parent in self.parents():
            app = parent
        return app

    @property
    def state(self) -> State:
        return get_state()

    @property
    def api_version(self) -> Tuple[int, ...]:
        """Get the current API version. Will fail if not connected to the API."""
        return self.state.client.version.release

    @property
    def status(self) -> StatusCallable:
        return self.state.console.status


app = StatefulApp(
    name="zabbix-cli",
    help="Zabbix-CLI is a command line interface for Zabbix.",
    add_completion=True,
    rich_markup_mode="rich",
)
