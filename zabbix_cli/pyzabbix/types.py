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
from typing import ClassVar
from typing import List
from typing import MutableMapping
from typing import Optional
from typing import Union

from packaging.version import Version
from pydantic import AliasChoices
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator
from pydantic import ValidationInfo
from typing_extensions import TypedDict

from zabbix_cli.models import ColsRowsType
from zabbix_cli.models import TableRenderable
from zabbix_cli.models import TableRenderableDict
from zabbix_cli.utils.utils import get_hostgroup_flag
from zabbix_cli.utils.utils import get_hostgroup_type
from zabbix_cli.utils.utils import get_maintenance_status
from zabbix_cli.utils.utils import get_monitoring_status
from zabbix_cli.utils.utils import get_zabbix_agent_status

PrimitiveType = Union[str, bool, int]
ParamsType = MutableMapping[
    str, Union[PrimitiveType, "ParamsType", List[Union["ParamsType", PrimitiveType]]]
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


class ZabbixAPIBaseModel(TableRenderable):
    """Base model for Zabbix API objects.

    Implements the `TableRenderable` interface, which allows us to render
    it as a table, JSON, csv, etc."""

    version: ClassVar[Version] = Version("6.4.0")  # assume latest released version
    """Zabbix API version the data stems from.
    This is a class variable that can be overridden, which causes all
    subclasses to use the new value when accessed.

    WARNING: Do not access directly from outside this class.
    Prefer the `version` property instead.
    """
    model_config = ConfigDict(validate_assignment=True, extra="ignore")


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


class Template(ZabbixAPIBaseModel):
    templateid: str
    name: Optional[str] = None
    host: Optional[str] = None

    @property
    def name_or_host(self) -> str:
        """Returns the name or host field or a default value."""
        return self.name or self.host or "Unknown"


class Inventory(TableRenderableDict):
    """An adapter for a dict that allows it to be rendered as a table."""


# TODO: expand Host model with all possible fields
# Add alternative constructor to construct from API result
class Host(ZabbixAPIBaseModel):
    hostid: str
    host: str = ""
    groups: List[Hostgroup] = Field(
        default_factory=list,
        # Compat for >= 6.2.0
        validation_alias=AliasChoices("groups", "hostgroups"),
    )
    templates: List[Template] = Field(default_factory=list)
    inventory: TableRenderableDict = Field(
        default_factory=TableRenderableDict
    )  # everything is a string as of 7.0
    proxyid: Optional[str] = Field(
        None,
        # Compat for <7.0.0
        validation_alias=AliasChoices("proxyid", "proxy_hostid"),
    )
    proxy_address: Optional[str] = None
    maintenance_status: Optional[str] = None
    zabbix_agent: Optional[str] = Field(
        None, validation_alias=AliasChoices("available", "active_available")
    )
    status: Optional[str] = None

    @field_validator("host", mode="before")  # TODO: add test for this
    @classmethod
    def _use_id_if_empty(cls, v: str, info: ValidationInfo) -> str:
        """In case the Zabbix API returns no host name, use the ID instead."""
        if not v:
            return f"Unknown (ID: {info.data['hostid']})"
        return v

    def _table_cols_rows(self) -> ColsRowsType:
        cols = [
            "HostID",
            "Name",
            "Hostgroups",
            "Templates",
            "Zabbix agent",
            "Maintenance",
            "Status",
            "Proxy",
        ]
        rows = [
            [
                self.hostid,
                self.host,
                "\n".join([group.name for group in self.groups]),
                "\n".join([template.name_or_host for template in self.templates]),
                get_zabbix_agent_status(self.zabbix_agent),
                get_maintenance_status(self.maintenance_status),
                get_monitoring_status(self.status),
                self.proxy_address or "",
            ]
        ]
        return cols, rows


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


# Resolve forward references
Hostgroup.model_rebuild()
