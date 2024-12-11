from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Optional

from packaging.version import Version
from pydantic import ConfigDict
from pydantic import FieldSerializationInfo
from pydantic import field_serializer
from rich.box import SIMPLE_HEAD
from rich.table import Table
from typing_extensions import Self
from typing_extensions import TypedDict

from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import error
from zabbix_cli.output.formatting.path import path_link

if TYPE_CHECKING:
    from zabbix_cli.commands.cli import DirectoryType
    from zabbix_cli.models import ColsRowsType
    from zabbix_cli.models import RowsType
    from zabbix_cli.state import State


class ImplementationInfo(TypedDict):
    name: str
    version: tuple[Any, ...]
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
    def ser_api_version(self, _info: FieldSerializationInfo) -> str:
        return str(self.api_version)

    @property
    def config_path_str(self) -> str:
        return (
            path_link(self.config_path) if self.config_path else str(self.config_path)
        )

    @classmethod
    def from_debug_data(cls, state: State, with_auth: bool = False) -> DebugInfo:
        # So far we only use state, but we can expand this in the future
        from zabbix_cli.exceptions import ZabbixCLIError

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
        except ZabbixCLIError:
            pass

        # We might not be connected to the API
        try:
            obj.api_version = state.client.version
            obj.url = state.client.url
            obj.user = state.config.api.username
            if with_auth:
                obj.auth_token = state.client.auth
            obj.connected_to_zabbix = True
        except ZabbixCLIError:
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


class HistoryResult(TableRenderable):
    """Result type for `show_history` command."""

    __show_lines__ = False
    __box__ = SIMPLE_HEAD

    commands: list[str] = []


class DirectoriesResult(TableRenderable):
    """Result type for `show_dirs` command."""

    directories: list[dict[str, Path]] = []

    @classmethod
    def from_directory_types(cls, dirs: list[DirectoryType]) -> Self:
        return cls(directories=[{str(d.value): d.as_path()} for d in dirs])

    def __cols_rows__(self) -> ColsRowsType:
        from zabbix_cli.output.style import Emoji

        cols = ["Type", "Path", "Exists"]
        rows: RowsType = []
        for d in self.directories:
            for key in d:
                p = d[key]
                exists = Emoji.fmt_bool(p.exists())
                rows.append([key, str(d[key]), exists])
        return cols, rows
