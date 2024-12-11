"""In order to mimick the API of Zabbix-cli < 3.0.0, we define a single
app object here, which we share between the different command modules.

Thus, every command is part of the same command group.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Iterable
from types import ModuleType
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import NamedTuple
from typing import Optional
from typing import Protocol
from typing import Union

import typer
from typer.core import TyperCommand
from typer.core import TyperGroup
from typer.main import Typer
from typer.main import get_group
from typer.models import CommandFunctionType
from typer.models import CommandInfo as TyperCommandInfo
from typer.models import Default

from zabbix_cli.app.plugins import PluginLoader
from zabbix_cli.logs import logger
from zabbix_cli.state import State
from zabbix_cli.state import get_state

if TYPE_CHECKING:
    from rich.console import RenderableType
    from rich.status import Status
    from rich.style import StyleType

    from zabbix_cli.config.model import Config
    from zabbix_cli.config.model import PluginConfig


class Example(NamedTuple):
    """Example command usage."""

    description: str
    command: str
    return_value: Optional[str] = None

    def __str__(self) -> str:
        return f"  [i]{self.description}[/]\n\n    [example]{self.command}[/]"


# TODO: Trigger example rendering only when user calls --help, so we don't build
#       the help text for every command on startup.
#       Need to investigate ctx.get_help() and how it's used.
#       The question is whether we have to monkeypatch this or if we can do it with
#       the current typer/click API
class CommandInfo(TyperCommandInfo):
    def __init__(
        self, *args: Any, examples: Optional[list[Example]] = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.examples = examples or []
        self.set_command_help()

    def set_command_help(self) -> None:
        if not self.help:
            self.help = inspect.getdoc(self.callback) or ""
        if not self.short_help:
            self.short_help = self.help.split("\n")[0]
        self._set_command_examples()

    def _set_command_examples(self) -> None:
        if not self.examples or not self.help:
            return
        examples = [str(e) for e in self.examples]
        examples.insert(0, "\n\n[bold underline]Examples[/]")

        self.help = self.help.strip()
        self.help += "\n\n".join(examples)


class StatusCallable(Protocol):
    """Function that returns a Status object.

    Protocol for rich.console.Console.status method.
    """

    def __call__(
        self,
        status: RenderableType,
        *,
        spinner: str = "dots",
        spinner_style: StyleType = "status.spinner",
        speed: float = 1.0,
        refresh_per_second: float = 12.5,
    ) -> Status: ...


class StatefulApp(typer.Typer):
    """A Typer app that provides access to the global state."""

    parent: Optional[StatefulApp]
    plugins: dict[str, ModuleType]

    # NOTE: might be a good idea to add a typing.Unpack definition for the kwargs?
    def __init__(self, **kwargs: Any) -> None:
        self.parent = None
        self._plugin_loader = PluginLoader()
        super().__init__(**kwargs)

    @property
    def logger(self) -> logging.Logger:
        return logger

    # Methods for adding subcommands and keeping track of hierarchy
    def add_typer(self, typer_instance: Typer, **kwargs: Any) -> None:
        kwargs.setdefault("no_args_is_help", True)
        if isinstance(typer_instance, StatefulApp):
            typer_instance.parent = self
        return super().add_typer(typer_instance, **kwargs)

    def add_subcommand(self, app: typer.Typer, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("rich_help_panel", "Subcommands")
        self.add_typer(app, **kwargs)

    def load_plugins(self, config: Config) -> None:
        """Load plugins."""
        self._plugin_loader.load(config)

    def configure_plugins(self, config: Config) -> None:
        """Configure plugins."""
        self._plugin_loader.configure_plugins(config)

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

    def as_click_group(self) -> TyperGroup:
        """Return the Typer app as a Click group."""
        return get_group(self)

    def command(
        self,
        name: Optional[str] = None,
        *,
        cls: Optional[type[TyperCommand]] = None,
        context_settings: Optional[dict[Any, Any]] = None,
        help: Optional[str] = None,
        epilog: Optional[str] = None,
        short_help: Optional[str] = None,
        options_metavar: str = "[OPTIONS]",
        add_help_option: bool = True,
        no_args_is_help: bool = False,
        hidden: bool = False,
        deprecated: bool = False,
        # Rich settings
        rich_help_panel: Union[str, None] = Default(None),
        # Zabbix-cli kwargs
        examples: Optional[list[Example]] = None,
    ) -> Callable[[CommandFunctionType], CommandFunctionType]:
        if cls is None:
            cls = TyperCommand

        def decorator(f: CommandFunctionType) -> CommandFunctionType:
            self.registered_commands.append(
                CommandInfo(
                    name=name,
                    cls=cls,
                    context_settings=context_settings,
                    callback=f,
                    help=help,
                    epilog=epilog,
                    short_help=short_help,
                    options_metavar=options_metavar,
                    add_help_option=add_help_option,
                    no_args_is_help=no_args_is_help,
                    hidden=hidden,
                    deprecated=deprecated,
                    # Rich settings
                    rich_help_panel=rich_help_panel,
                    # Zabbix-cli kwargs
                    examples=examples,
                )
            )
            return f

        return decorator

    @property
    def state(self) -> State:
        return get_state()

    @property
    def api_version(self) -> tuple[int, ...]:
        """Get the current API version. Will fail if not connected to the API."""
        return self.state.client.version.release

    @property
    def status(self) -> StatusCallable:
        return self.state.err_console.status

    def get_plugin_config(self, name: str) -> PluginConfig:
        """Get a plugin's configuration by name.

        Returns an empty PluginConfig object if no config is found.
        """
        conf = self.state.config.plugins.get(name)
        if not conf:
            # NOTE: can we import this top-level? We have probably already imported
            # the config at this point? Unless we refactor config loading _again_...?
            from zabbix_cli.config.model import PluginConfig

            logger.error(f"Plugin '{name}' not found in configuration")
            return PluginConfig()
        return conf
