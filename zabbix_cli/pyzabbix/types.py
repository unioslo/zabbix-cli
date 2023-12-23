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
from pydantic import computed_field
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_serializer
from pydantic import field_validator
from pydantic import model_validator
from pydantic import ValidationInfo
from typing_extensions import Literal
from typing_extensions import TypedDict

from zabbix_cli.models import ColsRowsType
from zabbix_cli.models import TableRenderable
from zabbix_cli.models import TableRenderableDict
from zabbix_cli.utils.args import APIStr
from zabbix_cli.utils.args import APIStrEnum
from zabbix_cli.utils.args import ChoiceMixin
from zabbix_cli.utils.utils import get_hostgroup_flag
from zabbix_cli.utils.utils import get_hostgroup_type
from zabbix_cli.utils.utils import get_item_type
from zabbix_cli.utils.utils import get_macro_type
from zabbix_cli.utils.utils import get_maintenance_status
from zabbix_cli.utils.utils import get_monitoring_status
from zabbix_cli.utils.utils import get_value_type
from zabbix_cli.utils.utils import get_zabbix_agent_status

SortOrder = Literal["ASC", "DESC"]

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


class ModifyHostItem(TypedDict):
    """Argument for a host ID in an API request."""

    hostid: Union[str, int]


ModifyHostParams = List[ModifyHostItem]


class ModifyGroupItem(TypedDict):
    """Argument for a host ID in an API request."""

    groupid: Union[str, int]


ModifyGroupParams = List[ModifyGroupItem]


class ModifyTemplateItem(TypedDict):
    """Argument for a template ID in an API request."""

    templateid: Union[str, int]


ModifyTemplateParams = List[ModifyTemplateItem]


class AgentAvailable(ChoiceMixin[str], APIStrEnum):
    """Agent availability status."""

    __choice_name__ = "Agent availability status"

    UNKNOWN = APIStr("unknown", "0")
    AVAILABLE = APIStr("available", "1")
    UNAVAILABLE = APIStr("unavailable", "2")


# See: zabbix_cli.utils.args.OnOffChoice for why we re-define on/off enum here
class MonitoringStatus(ChoiceMixin[str], APIStrEnum):
    """Monitoring status is on/off."""

    ON = APIStr("on", "0")  # Yes, 0 is on, 1 is off...
    OFF = APIStr("off", "1")


class MaintenanceStatus(ChoiceMixin[str], APIStrEnum):
    """Maintenance status is on/off."""

    # API values are inverted here compared to monitoring status...
    ON = APIStr("on", "1")
    OFF = APIStr("off", "0")


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
    legacy_json_format: ClassVar[bool] = False
    """Whether to use the legacy JSON format for rendering objects.
    This class variable is set by `State.configure` based on the
    current configuration. By default, we assume the new JSON format,
    since we eventually want to phase out support for the legacy format."""

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


class HostGroup(ZabbixAPIBaseModel):
    groupid: str
    name: str
    hosts: List[Host] = []
    # FIXME: Use Optional[str] and None default?
    flags: int = 0
    internal: int = 0  # should these be ints?

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["GroupID", "Name", "Flag", "Type", "Hosts"]
        row = [
            self.groupid,
            self.name,
            get_hostgroup_flag(self.flags),
            get_hostgroup_type(self.internal),
            ", ".join([host.host for host in self.hosts]),
        ]
        return cols, [row]


class TemplateGroup(ZabbixAPIBaseModel):
    groupid: str
    name: str
    uuid: str


class Template(ZabbixAPIBaseModel):
    """A template object. Can contain"""

    templateid: str
    host: str
    hosts: List[Host] = []
    templates: List[Template] = []
    """Child templates (templates inherited from this template)."""

    parent_templates: List[Template] = Field(
        default_factory=list,
        validation_alias=AliasChoices("parentTemplates", "parent_templates"),
        serialization_alias="parentTemplates",  # match JSON output to API format
    )
    """Parent templates (templates this template inherits from)."""

    name: Optional[str] = Field(None, exclude=True)
    """The visible name of the template.

    In most cases it will be the same as `host`.
    Excluded from JSON output, since it's redundant in 99% of cases.
    """

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["ID", "Name", "Hosts", "Children", "Parents"]
        row = [
            self.templateid,
            self.host,
            "\n".join([host.host for host in self.hosts]),
            "\n".join([template.host for template in self.templates]),
            "\n".join([parent.host for parent in self.parent_templates]),
        ]
        return cols, [row]


class Inventory(TableRenderableDict):
    """An adapter for a dict that allows it to be rendered as a table."""


# TODO: expand Host model with all possible fields
# Add alternative constructor to construct from API result
class Host(ZabbixAPIBaseModel):
    hostid: str
    host: str = ""
    groups: List[HostGroup] = Field(
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
    macros: List[Macro] = Field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.host!r} ({self.hostid})"

    # Legacy V2 JSON format compatibility
    @field_serializer("maintenance_status")
    def _maintenance_status_serializer(self, v: Optional[str], _info) -> Optional[str]:
        """Serializes the maintenance status as a formatted string
        in legacy mode, and as-is in new mode."""
        if self.legacy_json_format:
            return get_maintenance_status(v)
        return v

    @field_serializer("zabbix_agent")
    def _zabbix_agent_serializer(self, v: Optional[str], _info) -> Optional[str]:
        """Serializes the zabbix agent status as a formatted string
        in legacy mode, and as-is in new mode."""
        if self.legacy_json_format:
            return get_zabbix_agent_status(v)
        return v

    @field_serializer("status")
    def _status_serializer(self, v: Optional[str], _info) -> Optional[str]:
        """Serializes the monitoring status as a formatted string
        in legacy mode, and as-is in new mode."""
        if self.legacy_json_format:
            return get_monitoring_status(v)
        return v

    @field_validator("host", mode="before")  # TODO: add test for this
    @classmethod
    def _use_id_if_empty(cls, v: str, info: ValidationInfo) -> str:
        """In case the Zabbix API returns no host name, use the ID instead."""
        if not v:
            return f"Unknown (ID: {info.data['hostid']})"
        return v

    def __cols_rows__(self) -> ColsRowsType:
        cols = [
            "HostID",
            "Name",
            "HostGroups",
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
                "\n".join([template.host for template in self.templates]),
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
    hosts: List[Host] = Field(default_factory=list)

    @model_validator(mode="after")
    def _set_name_field(self) -> Proxy:
        """Ensures the name field is set to the correct value given the current Zabbix API version."""
        # NOTE: should we use compat.proxy_name here to determine attr names?
        if self.version.release < (7, 0, 0) and hasattr(self, "host") and not self.name:
            self.name = self.host
        return self


class MacroBase(ZabbixAPIBaseModel):
    macro: str
    value: Optional[str] = None  # Optional in case secret value
    type: int
    """Macro type. 0 - text, 1 - secret, 2 - vault secret (>=7.0)"""
    description: str

    @computed_field  # type: ignore[misc] # pydantic docs use decorators on top of property (https://docs.pydantic.dev/2.0/usage/computed_fields/)
    @property
    def type_fmt(self) -> str:
        """Returns the macro type as a formatted string."""
        return get_macro_type(self.type)


class Macro(MacroBase):
    """Macro object. Known as 'host macro' in the Zabbix API."""

    hostid: str
    hostmacroid: str
    automatic: Optional[int] = None  # >= 7.0 only. 0 = user, 1 = discovery rule
    hosts: List[Host] = Field(default_factory=list)
    templates: List[Template] = Field(default_factory=list)


class GlobalMacro(MacroBase):
    globalmacroid: str


class Item(ZabbixAPIBaseModel):
    itemid: str
    delay: Optional[str] = None
    hostid: Optional[str] = None
    interfaceid: Optional[str] = None
    key: Optional[str] = None
    name: Optional[str] = None
    type: Optional[int] = None
    url: Optional[str] = None
    value_type: Optional[int] = None
    description: Optional[str] = None
    history: Optional[str] = None

    @computed_field  # type: ignore[misc] # pydantic docs use decorators on top of property (https://docs.pydantic.dev/2.0/usage/computed_fields/)
    @property
    def type_fmt(self) -> str:
        """Returns the item type as a formatted string."""
        return get_item_type(self.type)

    @computed_field  # type: ignore[misc]
    @property
    def value_type_fmt(self) -> str:
        """Returns the item type as a formatted string."""
        return get_value_type(self.value_type)

    @field_serializer("type")
    def _LEGACY_type_serializer(self, v: Optional[int], _info) -> Union[str, int, None]:
        """Serializes the item type as a formatted string in legacy JSON mode"""
        if self.legacy_json_format:
            return self.type_fmt
        return v

    @field_serializer("value_type")
    def _LEGACY_value_type_serializer(
        self, v: Optional[int], _info
    ) -> Union[str, int, None]:
        """Serializes the item type as a formatted string in legacy JSON mode"""
        if self.legacy_json_format:
            return self.type_fmt
        return v

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["ID", "Name", "Key", "Type", "Interval", "History", "Description"]
        rows = [
            [
                self.itemid,
                str(self.name),
                str(self.key),
                str(self.type_fmt),
                str(self.delay),
                str(self.history),
                str(self.description),
            ]
        ]
        return cols, rows


# Resolve recursive and/or cyclic references via forward declarations
#
# See: https://docs.pydantic.dev/latest/concepts/models/#rebuild-model-schema
#
# Certain models refer to each other i.e.:
#  * Host can have multiple HostGroup
#  * HostGroup can have multiple Host
#  * Host can have multiple Template
#  * Template can have multiple Host
#  * etc.
#
# They refer to each other, thus we must establish a forward reference,
# by using string annotations, and then resolving them later.
HostGroup.model_rebuild()
Host.model_rebuild()
Template.model_rebuild()
