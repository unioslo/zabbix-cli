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
from typing import MutableMapping
from typing import Optional
from typing import Union

from pydantic import AliasChoices
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator
from pydantic import ValidationInfo
from typing_extensions import TypedDict

from zabbix_cli.models import ColsRowsType
from zabbix_cli.models import Result
from zabbix_cli.utils.utils import get_hostgroup_flag
from zabbix_cli.utils.utils import get_hostgroup_type

ParamsType = MutableMapping[
    str, Union[str, bool, int, "ParamsType", List["ParamsType"]]
]
"""Type definition for Zabbix API query parameters.

Most Zabbix API parameters are strings, but not _always_.
They can also be contained in nested dicts or in lists.
"""


class UsergroupPermission(Enum):
    """Usergroup permission levels."""

    DENY = 0
    READ_ONLY = 2
    READ_WRITE = 3
    _UNKNOWN = -1

    @classmethod
    def _missing_(cls, value: object) -> UsergroupPermission:
        return cls._UNKNOWN


class ZabbixAPIBaseModel(Result):
    """Base model for Zabbix API objects.

    Implements the `Result` interface, which allows us to render
    it as a table, JSON, csv, etc."""

    model_config = ConfigDict(validate_assignment=True, extra="allow")


class ZabbixRight(TypedDict):
    permission: int
    id: str


class User(ZabbixAPIBaseModel):
    userid: str
    username: str = Field(..., validation_alias=AliasChoices("username", "alias"))


class Usergroup(ZabbixAPIBaseModel):
    name: str
    usrgrpid: str  # technically not required, but we always fetch it
    rights: List[ZabbixRight] = []
    hostgroup_rights: List[ZabbixRight] = []
    templategroup_rights: List[ZabbixRight] = []
    users: List[User] = []


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


class Proxy(ZabbixAPIBaseModel):
    proxyid: str
    name: str = Field(..., validation_alias=AliasChoices("host", "name"))

    @model_validator(mode="after")
    def _set_name_field(self) -> Proxy:
        """Ensures the name field is set to the correct value given the current Zabbix API version."""
        # NOTE: should we use compat.proxy_name here to determine attr names?
        if self.version.release < (7, 0, 0) and hasattr(self, "host") and not self.name:
            self.name = self.host
        return self


class MacroBase(ZabbixAPIBaseModel):
    macro: str
    value: str  # could this fail if macro is secret?
    type: str
    description: str


class Macro(MacroBase):
    """Macro object. Known as 'host macro' in the Zabbix API."""

    hostid: str
    """Macro type. 0 - text, 1 - secret, 2 - vault secret (>=7.0)"""
    hostmacroid: str
    automatic: Optional[int] = None  # >= 7.0 only. 0 = user, 1 = discovery rule


class GlobalMacro(MacroBase):
    globalmacroid: str
