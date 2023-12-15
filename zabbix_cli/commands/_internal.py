"""Commands that interact with the application itself."""
from __future__ import annotations

import sys
from typing import Optional
from typing import TYPE_CHECKING

import typer

from zabbix_cli.app import app
from zabbix_cli.output.console import info
from zabbix_cli.output.render import render_result

if TYPE_CHECKING:
    from zabbix_cli.state import State


@app.command("show_zabbixcli_config")
def show_zabbixcli_version(ctx: typer.Context) -> None:
    """Show the current application configuration."""
    config = app.state.config
    print(config.as_toml())

    if config.config_path:
        info(f"Config file: {config.config_path}")


@app.command("debug", hidden=True)
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
    from pathlib import Path
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
        auth: Optional[str] = None
        connected_to_zabbix: bool = False
        python: PythonInfo

        model_config = ConfigDict(arbitrary_types_allowed=True)

        @field_serializer("api_version")
        def ser_api_version(self, _info) -> str:
            return str(self.api_version)

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
                    obj.auth = state.client.auth
                obj.connected_to_zabbix = True
            except RuntimeError:
                pass
            return obj

        def as_table(self) -> Table:
            table = Table(title="Debug Info")
            table.add_column("Key", justify="right", style="cyan")
            table.add_column("Value", justify="left", style="magenta")

            table.add_row("Config File", str(self.config_path))
            table.add_row("API URL", str(self.url))
            table.add_row("API Version", str(self.api_version))
            table.add_row("User", str(self.user))
            table.add_row("Auth Token", str(self.auth))
            table.add_row("Connected to Zabbix", str(self.connected_to_zabbix))
            table.add_row("Python Version", str(self.python["version"]))
            table.add_row("Platform", str(self.python["platform"]))

            return table

    render_result(DebugInfo.from_debug_data(app.state, with_auth=with_auth))
