"""Commands that interact with the application itself."""
from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from typing import Optional
from typing import TYPE_CHECKING

import typer

from zabbix_cli.app import app
from zabbix_cli.config.model import Config
from zabbix_cli.dirs import CONFIG_DIR
from zabbix_cli.dirs import DATA_DIR
from zabbix_cli.dirs import EXPORT_DIR
from zabbix_cli.dirs import LOGS_DIR
from zabbix_cli.dirs import SITE_CONFIG_DIR
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.output.console import error
from zabbix_cli.output.console import info
from zabbix_cli.output.console import print_path
from zabbix_cli.output.console import print_toml
from zabbix_cli.output.console import success
from zabbix_cli.output.formatting.path import path_link
from zabbix_cli.output.render import render_result
from zabbix_cli.utils.utils import open_directory

if TYPE_CHECKING:
    from zabbix_cli.state import State

HELP_PANEL = "CLI"


@app.command("show_zabbixcli_config", rich_help_panel=HELP_PANEL)
def show_zabbixcli_version(ctx: typer.Context) -> None:
    """Show the current application configuration."""
    config = app.state.config
    print_toml(config.as_toml())
    if config.config_path:
        info(f"Config file: {config.config_path}")


class DirectoryType(Enum):
    """Directory types."""

    CONFIG = "config"
    DATA = "data"
    LOGS = "logs"
    SITE_CONFIG = "siteconfig"
    EXPORTS = "exports"

    def as_path(self) -> Path:
        DIR_MAP = {
            DirectoryType.CONFIG: CONFIG_DIR,
            DirectoryType.DATA: DATA_DIR,
            DirectoryType.LOGS: LOGS_DIR,
            DirectoryType.SITE_CONFIG: SITE_CONFIG_DIR,
            DirectoryType.EXPORTS: EXPORT_DIR,
        }
        d = DIR_MAP.get(self)
        if d is None:
            raise ZabbixCLIError(f"No default path available for {self!r}.")
        return d


def get_directory(directory_type: DirectoryType, config: Config) -> Path:
    if directory_type == DirectoryType.CONFIG and config.config_path:
        return config.config_path.parent
    elif directory_type == DirectoryType.EXPORTS:
        return config.app.export_directory
    else:
        return directory_type.as_path()


@app.command("open", rich_help_panel=HELP_PANEL)
def open_config_dir(
    ctx: typer.Context,
    directory_type: DirectoryType = typer.Argument(
        ...,
        help="The type of directory to open.",
        case_sensitive=False,
        show_default=False,
    ),
    force: bool = typer.Option(
        False,
        "--force",
        is_flag=True,
        help="LINUX: Try to open desite no detected window manager.",
    ),
    path: bool = typer.Option(
        False,
        "--path",
        is_flag=True,
        help="Show path instead of opening directory.",
    ),
    open_command: Optional[str] = typer.Option(
        None,
        "--command",
        help="Specify command to use to use for opening.",
    ),
) -> None:
    """Opens an app directory in the system's file manager.

    Use --force to attempt to open when no DISPLAY env var is set."""
    directory = get_directory(directory_type, app.state.config)
    if path:
        print_path(directory)
    else:
        open_directory(directory, command=open_command, force=force)
        success(f"Opened {directory}")


@app.command("debug", hidden=True, rich_help_panel=HELP_PANEL)
def debug_cmd(
    ctx: typer.Context,
    with_auth: bool = typer.Option(
        False, "--auth", help="Include auth token in the result."
    ),
) -> None:
    """Print debug info."""
    # In-line imports to reduce startup time
    # (This is a hidden command after all)
    # NOTE: move to separate function if we want to test this
    from zabbix_cli.models import TableRenderable
    from rich.table import Table
    from pydantic import field_serializer, ConfigDict
    from packaging.version import Version
    from typing import Tuple, Any
    from typing_extensions import TypedDict

    class ImplementationInfo(TypedDict):
        name: str
        version: Tuple[Any, ...]
        hexversion: int
        cache_tag: str

    class PythonInfo(TypedDict):
        version: str
        implementation: ImplementationInfo
        platform: str

    class DebugInfo(TableRenderable):
        config_path: Optional[Path] = None
        api_version: Optional[Version] = None
        url: Optional[str] = None
        user: Optional[str] = None
        auth_token: Optional[str] = None
        connected_to_zabbix: bool = False
        python: PythonInfo

        model_config = ConfigDict(arbitrary_types_allowed=True)

        @field_serializer("api_version")
        def ser_api_version(self, _info) -> str:
            return str(self.api_version)

        @property
        def config_path_str(self) -> str:
            return (
                path_link(self.config_path)
                if self.config_path
                else str(self.config_path)
            )

        @classmethod
        def from_debug_data(cls, state: State, with_auth: bool = False) -> DebugInfo:
            # So far we only use state, but we can expand this in the future
            obj = cls(
                python={
                    "version": sys.version,
                    "implementation": {
                        "name": sys.implementation.name,
                        "version": sys.implementation.version,
                        "hexversion": sys.implementation.hexversion,
                        "cache_tag": sys.implementation.cache_tag,
                    },
                    "platform": sys.platform,
                }
            )

            # Config might not be configured
            try:
                obj.config_path = state.config.config_path
            except RuntimeError:
                pass

            # We might not be connected to the API
            try:
                obj.api_version = state.client.version
                obj.url = state.client.url
                obj.user = state.config.app.username
                if with_auth:
                    obj.auth_token = state.client.auth
                obj.connected_to_zabbix = True
            except RuntimeError:
                error("Unable to retrieve API info: Not connected to Zabbix API. ")
            except Exception as e:
                error(f"Unable to retrieve API info: {e}")
            return obj

        def as_table(self) -> Table:
            table = Table(title="Debug Info")
            table.add_column("Key", justify="right", style="cyan")
            table.add_column("Value", justify="left", style="magenta")

            table.add_row("Config File", self.config_path_str)
            table.add_row("API URL", str(self.url))
            table.add_row("API Version", str(self.api_version))
            table.add_row("User", str(self.user))
            table.add_row("Auth Token", str(self.auth_token))
            table.add_row("Connected to Zabbix", str(self.connected_to_zabbix))
            table.add_row("Python Version", str(self.python["version"]))
            table.add_row("Platform", str(self.python["platform"]))

            return table

    render_result(DebugInfo.from_debug_data(app.state, with_auth=with_auth))
