"""Type definitions for Zabbix API objects.


Since we are supporting multiple versions of the Zabbix API at the same time,
we don't operate with very strict type definitions. Some definitions are
TypedDicts, while others are Pydantic models. All models are able to
take extra fields, since we don't know (or always care) which fields are
present in which API versions.

It's not type-safe, but it's better than nothing. In the future, we might
want to look into defining Pydantic models that can accommodate multiple
Zabbix versions.
"""
from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import ConfigDict
from pydantic import field_validator
from pydantic import ValidationInfo
from typing_extensions import TypedDict

from zabbix_cli.models import ColsRowsType
from zabbix_cli.models import Result
from zabbix_cli.utils.utils import get_hostgroup_flag
from zabbix_cli.utils.utils import get_hostgroup_type


class UsergroupPermission(Enum):
    """Usergroup permission levels."""

    DENY = 0
    READ_ONLY = 2
    READ_WRITE = 3
    _UNKNOWN = -1

    @classmethod
    def _missing_(cls, value: int) -> UsergroupPermission:
        return cls._UNKNOWN


class ZabbixAPIBaseModel(Result):
    """Base model for Zabbix API objects.

    Implements the `Result` interface, which allows us to render
    it as a table, JSON, csv, etc."""

    model_config = ConfigDict(validate_assignment=True, extra="allow")


class ZabbixRight(TypedDict):
    permission: int
    id: str


class Usergroup(ZabbixAPIBaseModel):
    name: str
    usrgrpid: str  # technically not required, but we always fetch it
    rights: List[ZabbixRight] = []
    hostgroup_rights: List[ZabbixRight] = []
    templategroup_rights: List[ZabbixRight] = []


class Host(ZabbixAPIBaseModel):
    hostid: str
    host: str = ""

    @field_validator("host", mode="before")  # TODO: add test for this
    @classmethod
    def _use_id_if_empty(cls, v: str, info: ValidationInfo) -> str:
        """In case the Zabbix API returns no host name, use the ID instead."""
        if not v:
            return f"Unknown (ID: {info.data['hostid']})"
        return v


class Hostgroup(ZabbixAPIBaseModel):
    groupid: str
    name: str
    hosts: List[Host] = []
    flags: int = 0
    internal: int = 0

    def _table_cols_rows(self) -> ColsRowsType:
        cols = ["GroupID", "Name", "Flag", "Type", "Hosts"]
        row = [
            self.groupid,
            self.name,
            get_hostgroup_flag(self.flags),
            get_hostgroup_type(self.internal),
            ", ".join([host.host for host in self.hosts]),
        ]
        return cols, [row]
