from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import Optional

from pydantic import Field
from pydantic import model_serializer
from typing_extensions import Self

from zabbix_cli.models import TableRenderable
from zabbix_cli.pyzabbix.enums import MacroAutomatic
from zabbix_cli.pyzabbix.types import Macro

if TYPE_CHECKING:
    from zabbix_cli.models import ColsRowsType
    from zabbix_cli.models import RowsType


class ShowHostUserMacrosResult(TableRenderable):
    hostmacroid: str
    macro: str
    value: Optional[str] = None
    type: str
    description: Optional[str] = None
    hostid: str
    automatic: Optional[int] = None

    @classmethod
    def from_result(cls, macro: Macro) -> Self:
        return cls(
            hostmacroid=macro.hostmacroid,
            macro=macro.macro,
            value=macro.value,
            type=macro.type_str,
            description=macro.description,
            hostid=macro.hostid,
            automatic=macro.automatic,
        )

    def __cols_rows__(self) -> ColsRowsType:
        cols = [
            "Macro ID",
            "Macro",
            "Value",
            "Type",
            "Description",
            "Host ID",
            "Automatic",
        ]
        rows: RowsType = [
            [
                self.hostmacroid,
                self.macro,
                str(self.value),
                self.type,
                self.description or "",
                self.hostid,
                MacroAutomatic.string_from_value(self.automatic),
            ]
        ]
        return cols, rows


class MacroHostListV2(TableRenderable):
    macro: Macro

    def __cols_rows__(self) -> ColsRowsType:
        rows: RowsType = [
            [self.macro.macro, str(self.macro.value), host.hostid, host.host]
            for host in self.macro.hosts
        ]
        return ["Macro", "Value", "HostID", "Host"], rows

    @model_serializer()
    def model_ser(self) -> dict[str, Any]:
        if not self.macro.hosts:
            return {}  # match V2 output
        return {
            "macro": self.macro.macro,
            "value": self.macro.value,
            "hostid": self.macro.hosts[0].hostid,
            "host": self.macro.hosts[0].host,
        }


class MacroHostListV3(TableRenderable):
    macro: Macro

    def __cols_rows__(self) -> ColsRowsType:
        rows: RowsType = [
            [host.hostid, host.host, self.macro.macro, str(self.macro.value)]
            for host in self.macro.hosts
        ]
        return ["Host ID", "Host", "Macro", "Value"], rows


class GlobalMacroResult(TableRenderable):
    """Result of `define_global_macro` command."""

    globalmacroid: str = Field(json_schema_extra={"header": "Global Macro ID"})
    macro: str
    value: Optional[str] = None  # for usermacro.get calls


class ShowUsermacroTemplateListResult(TableRenderable):
    macro: str
    value: Optional[str] = None
    templateid: str
    template: str

    def __cols__(self) -> list[str]:
        return ["Macro", "Value", "Template ID", "Template"]
