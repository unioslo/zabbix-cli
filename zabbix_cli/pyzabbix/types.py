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

import logging
from collections.abc import Iterable
from collections.abc import MutableMapping
from collections.abc import Sequence
from datetime import datetime
from datetime import timedelta
from typing import Annotated
from typing import Any
from typing import Literal

from pydantic import AliasChoices
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import FieldSerializationInfo
from pydantic import PlainSerializer
from pydantic import SerializationInfo
from pydantic import ValidationError
from pydantic import ValidationInfo
from pydantic import ValidatorFunctionWrapHandler
from pydantic import WrapValidator
from pydantic import computed_field
from pydantic import field_serializer
from pydantic import field_validator
from pydantic_core import PydanticCustomError
from typing_extensions import TypeAliasType
from typing_extensions import TypedDict

from zabbix_cli.models import ColsRowsType
from zabbix_cli.models import RowsType
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.style import Color
from zabbix_cli.pyzabbix.enums import AckStatus
from zabbix_cli.pyzabbix.enums import ActiveInterface
from zabbix_cli.pyzabbix.enums import EventStatus
from zabbix_cli.pyzabbix.enums import GUIAccess
from zabbix_cli.pyzabbix.enums import HostgroupFlag
from zabbix_cli.pyzabbix.enums import HostgroupType
from zabbix_cli.pyzabbix.enums import InterfaceConnectionMode
from zabbix_cli.pyzabbix.enums import InterfaceType
from zabbix_cli.pyzabbix.enums import ItemType
from zabbix_cli.pyzabbix.enums import MacroType
from zabbix_cli.pyzabbix.enums import MaintenancePeriodType
from zabbix_cli.pyzabbix.enums import MaintenanceStatus
from zabbix_cli.pyzabbix.enums import MaintenanceWeekType
from zabbix_cli.pyzabbix.enums import MediaTypeType
from zabbix_cli.pyzabbix.enums import MonitoredBy
from zabbix_cli.pyzabbix.enums import MonitoringStatus
from zabbix_cli.pyzabbix.enums import ProxyCompatibility
from zabbix_cli.pyzabbix.enums import ProxyGroupState
from zabbix_cli.pyzabbix.enums import ProxyMode
from zabbix_cli.pyzabbix.enums import ProxyModePre70
from zabbix_cli.pyzabbix.enums import TriggerPriority
from zabbix_cli.pyzabbix.enums import UsergroupPermission
from zabbix_cli.pyzabbix.enums import UsergroupStatus
from zabbix_cli.pyzabbix.enums import UserRole
from zabbix_cli.pyzabbix.enums import ValueType
from zabbix_cli.utils.utils import get_maintenance_active_days
from zabbix_cli.utils.utils import get_maintenance_active_months
from zabbix_cli.utils.utils import get_maintenance_status
from zabbix_cli.utils.utils import get_monitoring_status

logger = logging.getLogger(__name__)

SortOrder = Literal["ASC", "DESC"]


# Source: https://docs.pydantic.dev/2.7/concepts/types/#named-recursive-types
def json_custom_error_validator(
    value: Any, handler: ValidatorFunctionWrapHandler, _info: ValidationInfo
) -> Any:
    """Simplify the error message to avoid a gross error stemming from
    exhaustive checking of all union options.
    """  # noqa: D205
    try:
        return handler(value)
    except ValidationError:
        raise PydanticCustomError(
            "invalid_json",
            "Input is not valid json",
        ) from None


Json = TypeAliasType(
    "Json",
    Annotated[
        MutableMapping[str, "Json"]
        | Sequence["Json"]
        | str
        | int
        | float
        | bool
        | None,
        WrapValidator(json_custom_error_validator),
    ],
)


ParamsType = MutableMapping[str, Json]
"""Type used to construct parameters for API requests.
Can only contain native JSON-serializable types.

BaseModel objects must be converted to JSON-serializable dicts before being
assigned as values in a ParamsType.
"""


def serialize_host_list_json(
    hosts: list[Host], info: SerializationInfo
) -> list[dict[str, str]]:
    """Custom JSON serializer for a list of hosts.

    Most of the time we don't want to serialize _all_ fields of a host.
    This serializer assumes that we want to serialize the minimal representation
    of hosts unless the context specifies otherwise.
    """
    if isinstance(info.context, dict):
        if info.context.get("full_host"):  # pyright: ignore[reportUnknownMemberType]
            return [host.model_dump(mode="json") for host in hosts]
    return [host.model_simple_dump() for host in hosts]


HostList = Annotated[
    list["Host"], PlainSerializer(serialize_host_list_json, when_used="json")
]
"""List of hosts that serialize as the minimal representation of a list of hosts."""


def age_from_datetime(dt: datetime | None) -> str | None:
    """Returns the age of a datetime object as a human-readable
    string, or None if the datetime is None.
    """
    if not dt:
        return None
    n = datetime.now(tz=dt.tzinfo)
    age = n - dt
    # strip microseconds
    return str(age - timedelta(microseconds=age.microseconds))


def format_datetime(dt: datetime | None) -> str:
    """Returns a formatted datetime string, or empty string if the
    datetime is None.
    """
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class ModifyHostItem(TypedDict):
    """Argument for a host ID in an API request."""

    hostid: str | int


ModifyHostParams = list[ModifyHostItem]

"""A list of host IDs in an API request.

E.g. `[{"hostid": "123"}, {"hostid": "456"}]`
"""


class ModifyGroupItem(TypedDict):
    """Argument for a group ID in an API request."""

    groupid: str | int


ModifyGroupParams = list[ModifyGroupItem]
"""A list of host/template group IDs in an API request.

E.g. `[{"groupid": "123"}, {"groupid": "456"}]`
"""


class ModifyTemplateItem(TypedDict):
    """Argument for a template ID in an API request."""

    templateid: str | int


ModifyTemplateParams = list[ModifyTemplateItem]
"""A list of template IDs in an API request.

E.g. `[{"templateid": "123"}, {"templateid": "456"}]`
"""


class ZabbixAPIError(BaseModel):
    """Zabbix API error information."""

    code: int
    message: str
    data: str | None = None


class ZabbixAPIResponse(BaseModel):
    """The raw response from the Zabbix API"""

    jsonrpc: str
    id: int
    result: Any = None  # can subclass this and specify types (ie. ZabbixAPIListResponse, ZabbixAPIStrResponse, etc.)
    """Result of API call, if request succeeded."""
    error: ZabbixAPIError | None = None
    """Error info, if request failed."""


class ZabbixAPIBaseModel(TableRenderable):
    """Base model for Zabbix API objects.

    Implements the `TableRenderable` interface, which allows us to render
    it as a table, JSON, csv, etc.
    """

    model_config = ConfigDict(validate_assignment=True, extra="ignore")

    def model_dump_api(self) -> dict[str, Any]:
        """Dump the model as a JSON-serializable dict used in API calls.

        Excludes computed fields by default.
        """
        return self.model_dump(
            mode="json",
            exclude=set(self.__class__.model_computed_fields),
            exclude_none=True,
        )


class ZabbixRight(ZabbixAPIBaseModel):
    permission: int
    id: str
    name: str | None = None  # name of group (injected by application)

    @computed_field
    @property
    def permission_str(self) -> str:
        """Returns the permission as a formatted string."""
        return UsergroupPermission.string_from_value(self.permission)

    def model_dump_api(self) -> dict[str, Any]:
        return self.model_dump(
            mode="json", include={"permission", "id"}, exclude_none=True
        )


class User(ZabbixAPIBaseModel):
    userid: str
    username: str = Field(..., validation_alias=AliasChoices("username", "alias"))
    name: str | None = None
    surname: str | None = None
    url: str | None = None
    autologin: str | None = None
    autologout: str | None = None
    roleid: int | None = Field(
        default=None, validation_alias=AliasChoices("roleid", "type")
    )
    # NOTE: Not adding properties we don't use, since Zabbix has a habit of breaking
    # its own API by changing names and types of properties between versions.

    @computed_field
    @property
    def role(self) -> str | None:
        """Returns the role name, if available."""
        if self.roleid:
            return UserRole.string_from_value(self.roleid)
        return None

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["UserID", "Username", "Name", "Surname", "Role"]
        rows: RowsType = [
            [
                self.userid,
                self.username,
                self.name or "",
                self.surname or "",
                self.role or "",
            ]
        ]
        return cols, rows


class Usergroup(ZabbixAPIBaseModel):
    name: str
    usrgrpid: str
    gui_access: int
    users_status: int
    rights: list[ZabbixRight] = []
    hostgroup_rights: list[ZabbixRight] = []
    templategroup_rights: list[ZabbixRight] = []
    users: list[User] = []

    @computed_field
    @property
    def gui_access_str(self) -> str:
        """GUI access code as a formatted string."""
        return GUIAccess.string_from_value(self.gui_access)

    @computed_field
    @property
    def users_status_str(self) -> str:
        """User status as a formatted string."""
        return UsergroupStatus.string_from_value(self.users_status)

    # LEGACY
    @computed_field
    @property
    def status(self) -> str:
        """LEGACY: 'users_status' is called 'status' in V2.
        Ensures serialized output contains the field.
        """
        return UsergroupStatus.string_from_value(self.users_status, with_code=True)

    # LEGACY
    @field_serializer("gui_access")
    def _LEGACY_type_serializer(
        self, v: int | None, _info: FieldSerializationInfo
    ) -> str | int | None:
        """Serializes the GUI access status as a formatted string in legacy JSON mode"""
        if self.legacy_json_format:
            return GUIAccess.string_from_value(v, with_code=True)
        return v


class Template(ZabbixAPIBaseModel):
    """A template object. Can contain hosts and other templates."""

    templateid: str
    host: str
    hosts: HostList = []
    macros: list[Macro] = []

    templates: list[Template] = []
    """Child templates (templates inherited from this template)."""

    parent_templates: list[Template] = Field(
        default_factory=list,
        validation_alias=AliasChoices("parentTemplates", "parent_templates"),
        serialization_alias="parentTemplates",  # match JSON output to API format
    )
    """Parent templates (templates this template inherits from)."""

    name: str | None = None
    """The visible name of the template."""

    def __str__(self) -> str:
        return f"{self.name or self.host!r} ({self.templateid})"

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["ID", "Name", "Hosts", "Parents", "Children"]
        rows: RowsType = [
            [
                self.templateid,
                self.name or self.host,  # prefer name, fall back on host
                "\n".join([host.host for host in self.hosts]),
                "\n".join([parent.host for parent in self.parent_templates]),
                "\n".join([template.host for template in self.templates]),
            ]
        ]
        return cols, rows


class TemplateGroup(ZabbixAPIBaseModel):
    groupid: str
    name: str
    uuid: str
    templates: list[Template] = []


class HostGroup(ZabbixAPIBaseModel):
    groupid: str
    name: str
    hosts: HostList = []
    flags: int = 0
    internal: int | None = None  # <6.2
    templates: list[Template] = []  # <6.2

    def __cols_rows__(self) -> ColsRowsType:
        # FIXME: is this ever used? Can we remove?
        cols = ["GroupID", "Name", "Flag", "Type", "Hosts"]
        rows: RowsType = [
            [
                self.groupid,
                self.name,
                HostgroupFlag.string_from_value(self.flags),
                HostgroupType.string_from_value(self.internal),
                ", ".join([host.host for host in self.hosts]),
            ]
        ]
        return cols, rows


class DictModel(ZabbixAPIBaseModel):
    """An adapter for a dict that allows it to be rendered as a table."""

    model_config = ConfigDict(extra="allow")

    def items(self) -> Iterable[tuple[str, Any]]:
        return self.model_dump(mode="python").items()

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["Key", "Value"]
        rows: RowsType = [[key, str(value)] for key, value in self.items() if value]
        return cols, rows


# TODO: expand Host model with all possible fields
# Add alternative constructor to construct from API result
class Host(ZabbixAPIBaseModel):
    hostid: str
    host: str = ""
    description: str | None = None
    groups: list[HostGroup] = Field(
        default_factory=list,
        # Compat for >= 6.2.0
        validation_alias=AliasChoices("groups", "hostgroups"),
    )
    templates: list[Template] = Field(
        default_factory=list,
        validation_alias=AliasChoices("templates", "parentTemplates"),
    )
    inventory: DictModel = Field(default_factory=DictModel)
    monitored_by: MonitoredBy | None = None
    proxyid: str | None = Field(
        default=None,
        # Compat for <7.0.0
        validation_alias=AliasChoices("proxyid", "proxy_hostid"),
    )
    proxy_groupid: str | None = None  # >= 7.0
    maintenance_status: str | None = None
    # active_available is a new field in 7.0.
    # Previous versions required checking the `available` field of its first interface.
    # In zabbix-cli v2, this value was serialized as `zabbix_agent`.
    active_available: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "active_available",  # >= 7.0
            "zabbix_agent",  # Zabbix-cli V2 name of this field
        ),
    )
    status: str | None = None
    macros: list[Macro] = Field(default_factory=list)
    interfaces: list[HostInterface] = Field(default_factory=list)

    # HACK: Add a field for the host's proxy that we can inject later
    proxy: Proxy | None = None

    def __str__(self) -> str:
        return f"{self.host!r} ({self.hostid})"

    def model_simple_dump(self) -> dict[str, str]:
        """Dump the model with minimal fields for simple output."""
        return {
            "host": self.host,
            "hostid": self.hostid,
        }

    def set_proxy(self, proxy_map: dict[str, Proxy]) -> None:
        """Set proxy info for the host given a mapping of proxy IDs to proxies."""
        if not (proxy := proxy_map.get(str(self.proxyid))):
            return
        self.proxy = proxy

    def get_active_status(self, *, with_code: bool = False) -> str:
        """Returns the active interface status as a formatted string."""
        if self.zabbix_version.release >= (7, 0, 0):
            return ActiveInterface.string_from_value(
                self.active_available, with_code=with_code
            )
        # We are on pre-7.0.0, check the first interface
        iface = self.interfaces[0] if self.interfaces else None
        if iface:
            return ActiveInterface.string_from_value(
                iface.available, with_code=with_code
            )
        else:
            return ActiveInterface.UNKNOWN.as_status(with_code=with_code)

    # Legacy V2 JSON format compatibility
    @field_serializer("maintenance_status", when_used="json")
    def _LEGACY_maintenance_status_serializer(
        self, v: str | None, _info: FieldSerializationInfo
    ) -> str | None:
        """Serializes the maintenance status as a formatted string
        in legacy mode, and as-is in new mode.
        """
        if self.legacy_json_format:
            return get_maintenance_status(v, with_code=True)
        return v

    @computed_field
    @property
    def zabbix_agent(self) -> str:
        """LEGACY: Serializes the zabbix agent status as a formatted string
        in legacy mode, and as-is in new mode.
        """
        # NOTE: use `self.active_available` instead of `self.zabbix_agent`
        if self.legacy_json_format:
            return self.get_active_status(with_code=True)
        return self.get_active_status()

    @field_serializer("status", when_used="json")
    def _LEGACY_status_serializer(
        self, v: str | None, _info: FieldSerializationInfo
    ) -> str | None:
        """Serializes the monitoring status as a formatted string
        in legacy mode, and as-is in new mode.
        """
        if self.legacy_json_format:
            return get_monitoring_status(v, with_code=True)
        return v

    @field_validator("host", mode="before")  # TODO: add test for this
    @classmethod
    def _use_id_if_empty(cls, v: str, info: ValidationInfo) -> str:
        """In case the Zabbix API returns no host name, use the ID instead."""
        if not v:
            return f"Unknown (ID: {info.data.get('hostid')})"
        return v

    @field_validator("proxyid", mode="after")  # TODO: add test for this
    @classmethod
    def _proxyid_0_is_none(cls, v: str, info: ValidationInfo) -> str | None:
        """Zabbix API can return 0 if host has no proxy.

        Convert to None, so we know the proxyid can always be used to
        look up the proxy, as well as in boolean contexts.
        """
        if not v or v == "0":
            return None
        return v

    def __cols_rows__(self) -> ColsRowsType:
        cols = [
            "HostID",
            "Name",
            "Host groups",
            "Templates",
            "Agent",
            "Maintenance",
            "Status",
            "Proxy",
        ]
        rows: RowsType = [
            [
                self.hostid,
                self.host,
                "\n".join([group.name for group in self.groups]),
                "\n".join([template.host for template in self.templates]),
                self.zabbix_agent,
                MaintenanceStatus.string_from_value(self.maintenance_status),
                MonitoringStatus.string_from_value(self.status),
                self.proxy.name if self.proxy else "",
            ]
        ]
        return cols, rows


class HostInterface(ZabbixAPIBaseModel):
    type: int
    ip: str
    dns: str | None = None
    port: str
    useip: int
    main: int
    # Values not required for creation:
    interfaceid: str | None = None
    available: int | None = None
    hostid: str | None = None
    bulk: int | None = None

    @computed_field
    @property
    def connection_mode(self) -> str:
        """Returns the connection mode as a formatted string."""
        return InterfaceConnectionMode.string_from_value(self.useip)

    @computed_field
    @property
    def type_str(self) -> str:
        """Returns the interface type as a formatted string."""
        return InterfaceType.string_from_value(self.type)

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["ID", "Type", "IP", "DNS", "Port", "Mode", "Default", "Available"]
        rows: RowsType = [
            [
                self.interfaceid or "",
                str(InterfaceType(self.type).value),
                self.ip,
                self.dns or "",
                self.port,
                self.connection_mode,
                str(bool(self.main)),
                ActiveInterface.string_from_value(self.available),
            ]
        ]
        return cols, rows


class CreateHostInterfaceDetails(ZabbixAPIBaseModel):
    """Parameters for creating a host interface."""

    version: int
    bulk: int | None = None
    community: str | None = None
    max_repetitions: int | None = None
    securityname: str | None = None
    securitylevel: int | None = None
    authpassphrase: str | None = None
    privpassphrase: str | None = None
    authprotocol: int | None = None
    privprotocol: int | None = None
    contextname: str | None = None


class UpdateHostInterfaceDetails(ZabbixAPIBaseModel):
    """Parameters for updating a host interface."""

    version: int | None = None
    bulk: int | None = None
    community: str | None = None
    max_repetitions: int | None = None
    securityname: str | None = None
    securitylevel: int | None = None
    authpassphrase: str | None = None
    privpassphrase: str | None = None
    authprotocol: int | None = None
    privprotocol: int | None = None
    contextname: str | None = None


class Proxy(ZabbixAPIBaseModel):
    """Zabbix Proxy object."""

    proxyid: str
    name: str = Field(..., validation_alias=AliasChoices("host", "name"))
    hosts: HostList = Field(default_factory=list)
    status: int | None = None
    operating_mode: int | None = None
    address: str = Field(
        validation_alias=AliasChoices(
            "address",  # >=7.0.0
            "proxy_address",  # <7.0.0
        )
    )
    proxy_groupid: str | None = None  # >= 7.0
    compatibility: int | None = None  # >= 7.0
    version: int | None = None  # >= 7.0
    local_address: str | None = None  # >= 7.0
    local_port: str | None = None  # >= 7.0

    def __hash__(self) -> str:
        return self.proxyid  # kinda hacky, but lets us use it in dicts

    @computed_field
    @property
    def mode(self) -> str:
        """Returns the proxy mode as a formatted string."""
        if self.zabbix_version.release >= (7, 0, 0):
            cls = ProxyMode
        else:
            cls = ProxyModePre70
        return cls.string_from_value(self.operating_mode)

    @computed_field
    @property
    def compatibility_str(self) -> str:
        """Returns the proxy compatibility as a formatted string."""
        return ProxyCompatibility.string_from_value(self.compatibility)

    @property
    def compatibility_rich(self) -> str:
        """Returns the proxy compatibility as a Rich markup formatted string."""
        compat = self.compatibility_str
        if compat == "Current":
            style = Color.SUCCESS
        elif compat == "Outdated":
            style = Color.WARNING
        elif compat == "Unsupported":
            style = Color.ERROR
        else:
            style = Color.INFO
        return style(compat)


class ProxyGroup(ZabbixAPIBaseModel):
    """Zabbix Proxy Group object."""

    proxy_groupid: str
    name: str
    description: str
    failover_delay: str
    min_online: str  # 1-1000, may be a macro
    state: ProxyGroupState
    proxies: list[Proxy] = Field(default_factory=list)

    def __cols_rows__(self) -> ColsRowsType:
        cols = [
            "ID",
            "Name",
            "Description",
            "Failover Delay",
            "Minimum Available",
            "State",
            "Proxies",
        ]
        rows: RowsType = [
            [
                self.proxy_groupid,
                self.name,
                self.description,
                self.failover_delay,
                str(self.min_online),
                str(self.state),  # TODO: make prettier
                "\n".join(proxy.name for proxy in self.proxies),
            ]
        ]
        return cols, rows


class MacroBase(ZabbixAPIBaseModel):
    macro: str
    value: str | None = None  # Optional in case secret value
    type: int
    """Macro type. 0 - text, 1 - secret, 2 - vault secret (>=7.0)"""
    description: str

    @computed_field
    @property
    def type_str(self) -> str:
        """Returns the macro type as a formatted string."""
        return MacroType.string_from_value(self.type)


class Macro(MacroBase):
    """Macro object. Known as 'host macro' in the Zabbix API."""

    hostid: str
    hostmacroid: str
    automatic: int | None = None  # >= 7.0 only. 0 = user, 1 = discovery rule
    hosts: HostList = Field(default_factory=list)
    templates: list[Template] = Field(default_factory=list)


class GlobalMacro(MacroBase):
    """Global macro object."""

    globalmacroid: str


class Item(ZabbixAPIBaseModel):
    """Zabbix Item."""

    itemid: str
    delay: str | None = None
    hostid: str | None = None
    interfaceid: str | None = None
    key: str | None = Field(default=None, validation_alias=AliasChoices("key_", "key"))
    name: str | None = None
    type: int | None = None
    url: str | None = None
    value_type: int | None = None
    description: str | None = None
    history: str | None = None
    lastvalue: str | None = None
    hosts: HostList = []

    @computed_field
    @property
    def type_str(self) -> str:
        """Returns the item type as a formatted string."""
        return ItemType.string_from_value(self.type)

    @computed_field
    @property
    def value_type_str(self) -> str:
        """Returns the item type as a formatted string."""
        return ValueType.string_from_value(self.value_type)

    @field_serializer("type")
    def _LEGACY_type_serializer(
        self, v: int | None, _info: FieldSerializationInfo
    ) -> str | int | None:
        """Serializes the item type as a formatted string in legacy JSON mode."""
        if self.legacy_json_format:
            return self.type_str
        return v

    @field_serializer("value_type")
    def _LEGACY_value_type_serializer(
        self, v: int | None, _info: FieldSerializationInfo
    ) -> str | int | None:
        """Serializes the item type as a formatted string in legacy JSON mode."""
        if self.legacy_json_format:
            return self.type_str
        return v

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["ID", "Name", "Key", "Type", "Interval", "History", "Description"]
        rows: RowsType = [
            [
                self.itemid,
                str(self.name),
                str(self.key),
                str(self.type_str),
                str(self.delay),
                str(self.history),
                str(self.description),
            ]
        ]
        return cols, rows


class Role(ZabbixAPIBaseModel):
    roleid: str
    name: str
    type: int
    readonly: int  # 0 = read-write, 1 = read-only


class MediaType(ZabbixAPIBaseModel):
    mediatypeid: str
    name: str
    type: int
    description: str | None = None

    @computed_field
    @property
    def type_str(self) -> str:
        return MediaTypeType.string_from_value(self.type)

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["ID", "Name", "Type", "Description"]
        rows: RowsType = [
            [
                self.mediatypeid,
                self.name,
                self.type_str,
                self.description or "",
            ]
        ]
        return cols, rows


class UserMedia(ZabbixAPIBaseModel):
    """Media attached to a user object."""

    # https://www.zabbix.com/documentation/current/en/manual/api/reference/user/object#media
    mediatypeid: str
    sendto: str
    active: int = 0  # 0 = enabled, 1 = disabled (YES REALLY!)
    severity: int = 63  # all (1111 in binary - all bits set)
    period: str = "1-7,00:00-24:00"  # 24/7


class TimePeriod(ZabbixAPIBaseModel):
    period: int
    timeperiod_type: int
    start_date: datetime | None = None
    start_time: int | None = None
    every: int | None = None
    dayofweek: int | None = None
    day: int | None = None
    month: int | None = None

    @computed_field
    @property
    def timeperiod_type_str(self) -> str:
        """Returns the time period type as a formatted string."""
        return MaintenancePeriodType.string_from_value(self.timeperiod_type)

    @computed_field
    @property
    def period_str(self) -> str:
        return str(timedelta(seconds=self.period))

    @computed_field
    @property
    def start_time_str(self) -> str:
        return str(timedelta(seconds=self.start_time or 0))

    @computed_field
    @property
    def start_date_str(self) -> str:
        if self.start_date and self.start_date.year > 1970:  # hack to avoid 1970-01-01
            return self.start_date.strftime("%Y-%m-%d %H:%M")
        return ""

    @computed_field
    @property
    def month_str(self) -> list[str]:
        return get_maintenance_active_months(self.month)

    @computed_field
    @property
    def dayofweek_str(self) -> list[str]:
        return get_maintenance_active_days(self.dayofweek)

    @computed_field
    @property
    def every_str(self) -> str:
        return MaintenanceWeekType.string_from_value(self.every)

    def __cols_rows__(self) -> ColsRowsType:
        """Renders the table based on the time period type.

        Fields are added/removed based on the time period type.
        """
        # TODO: use MaintenancePeriodType enum for this
        if self.timeperiod_type == 0:
            return self._get_cols_rows_one_time()
        # TODO: add __cols_rows__ method for each timeperiod type
        # other timeperiod types here...
        else:
            return self._get_cols_rows_default()

    def _get_cols_rows_default(self) -> ColsRowsType:
        """Fallback for when we don't know the time period type."""
        cols = [
            "Type",
            "Duration",
            "Start date",
            "Start time",
            "Every",
            "Day of week",
            "Day",
            "Months",
        ]
        rows: RowsType = [
            [
                self.timeperiod_type_str,
                self.period_str,
                self.start_date_str,
                self.start_time_str,
                self.every_str,
                "\n".join(self.dayofweek_str),
                str(self.day),
                "\n".join(self.month_str),
            ]
        ]
        return cols, rows

    def _get_cols_rows_one_time(self) -> ColsRowsType:
        """Get the cols and rows for a one time schedule."""
        cols = ["Type", "Duration", "Start date"]
        rows: RowsType = [
            [
                self.timeperiod_type_str,
                self.period_str,
                self.start_date_str,
            ]
        ]
        return cols, rows


class ProblemTag(ZabbixAPIBaseModel):
    tag: str
    operator: int | None
    value: str | None


class Maintenance(ZabbixAPIBaseModel):
    maintenanceid: str
    name: str
    active_since: datetime | None = None
    active_till: datetime | None = None
    description: str | None = None
    maintenance_type: int | None = None
    tags_evaltype: int | None = None
    timeperiods: list[TimePeriod] = []
    tags: list[ProblemTag] = []
    hosts: HostList = []
    hostgroups: list[HostGroup] = Field(
        default_factory=list, validation_alias=AliasChoices("groups", "hostgroups")
    )

    @field_validator("timeperiods", mode="after")
    @classmethod
    def _sort_time_periods(cls, v: list[TimePeriod]) -> list[TimePeriod]:
        """Cheeky hack to consistently render mixed time period types.

        This validator ensures time periods are sorted by complexity, so that the
        most complex ones are rendered first, thus adding all the necessary
        columns to the table when multiple time periods are rendered in aggregate.

        See: TimePeriod.__cols_rows__
        See: AggregateResult.__cols_rows__

        """
        # 0 = one time. We want those last.
        return sorted(v, key=lambda tp: tp.timeperiod_type, reverse=True)


class Event(ZabbixAPIBaseModel):
    eventid: str
    source: int
    object: int
    objectid: str
    acknowledged: int
    clock: datetime | None = None
    name: str
    value: int | None = None  # docs seem to imply this is optional
    severity: int
    # NYI:
    # r_eventid
    # c_eventid
    # cause_eventid
    # correlationid
    # userid
    # suppressed
    # opdata
    # urls

    @computed_field
    @property
    def age(self) -> str | None:
        """Returns the age of the event as a formatted string."""
        return age_from_datetime(self.clock)

    @computed_field
    @property
    def status_str(self) -> str:
        return EventStatus.string_from_value(self.value)

    @computed_field
    @property
    def acknowledged_str(self) -> str:
        return AckStatus.string_from_value(self.acknowledged)

    @property
    def status_str_cell(self) -> str:
        """Formatted and styled status string for use in a table cell."""
        if self.status_str == "OK":
            color = "green"
        else:
            color = "red"
        return f"[{color}]{self.status_str}[/]"

    @property
    def acknowledged_str_cell(self) -> str:
        """Formatted and styled state string for use in a table cell."""
        if self.acknowledged_str == "Yes":
            color = "green"
        else:
            color = "red"
        return f"[{color}]{self.acknowledged_str}[/]"

    @field_serializer("value")
    def _LEGACY_value_serializer(
        self, v: int | None, _info: FieldSerializationInfo
    ) -> str | int | None:
        """Serializes the value field as a formatted string in legacy JSON mode"""
        if self.legacy_json_format:
            return self.status_str
        return v

    @field_serializer("acknowledged")
    def _LEGACY_acknowledged_serializer(
        self, v: int, _info: FieldSerializationInfo
    ) -> str | int:
        """Serializes the acknowledged field as a formatted string in legacy JSON mode"""
        if self.legacy_json_format:
            return self.acknowledged_str
        return v

    def __cols_rows__(self) -> ColsRowsType:
        cols = [
            "Event ID",
            "Trigger ID",
            "Name",
            "Last change",
            "Age",
            "Acknowledged",
            "Status",
        ]
        rows: RowsType = [
            [
                self.eventid,
                self.objectid,
                self.name,
                format_datetime(self.clock),
                self.age or "",
                self.acknowledged_str_cell,
                self.status_str_cell,
            ]
        ]
        return cols, rows


class Trigger(ZabbixAPIBaseModel):
    triggerid: str
    """Required for update operations."""
    description: str | None = None
    """Required for create operations."""
    expression: str | None = None
    """Required for create operations."""
    event_name: str | None = None
    opdata: str | None = None
    comments: str | None = None
    error: str | None = None
    flags: int | None = None
    lastchange: datetime | None = None
    priority: int | None = None
    state: int | None = None
    templateid: str | None = None
    type: int | None = None
    url: str | None = None
    url_name: str | None = None  # >6.0
    value: int | None = None
    recovery_mode: int | None = None
    recovery_expression: str | None = None
    correlation_mode: int | None = None
    correlation_tag: str | None = None
    manual_close: int | None = None
    uuid: str | None = None
    hosts: list[Host] = []
    # NYI:
    # groups: List[HostGroup] = Field(
    #     default_factory=list, validation_alias=AliasChoices("groups", "hostgroups")
    # )
    # items
    # functions
    # dependencies
    # discoveryRule
    # lastEvent

    @computed_field
    @property
    def age(self) -> str | None:
        """Returns the age of the event as a formatted string."""
        return age_from_datetime(self.lastchange)

    @computed_field
    @property
    def hostname(self) -> str | None:
        """Returns the hostname of the trigger."""
        if self.hosts:
            return self.hosts[0].host
        return None

    @computed_field
    @property
    def severity(self) -> str:
        return TriggerPriority.string_from_value(self.priority)

    def __cols_rows__(self) -> ColsRowsType:
        cols = [
            "Trigger ID",
            "Host",
            "Description",
            "Severity",
            "Last Change",
            "Age",
        ]
        rows: RowsType = [
            [
                self.triggerid,
                self.hostname or "",
                self.description or "",
                self.severity,
                format_datetime(self.lastchange),
                self.age or "",
            ]
        ]
        return cols, rows


class Image(ZabbixAPIBaseModel):
    imageid: str
    name: str
    imagetype: int
    # NOTE: Optional so we can fetch an image without its data
    # This lets us get the IDs of all images without keeping the data in memory
    image: str | None = None


class Map(ZabbixAPIBaseModel):
    sysmapid: str
    name: str
    height: int
    width: int
    backgroundid: str | None = None  # will this be an empty string instead?
    # Other fields are omitted. We only use this for export and import.


class ImportRule(BaseModel):  # does not need to inherit from ZabbixAPIBaseModel
    createMissing: bool
    updateExisting: bool | None = None
    deleteMissing: bool | None = None


class ImportRules(ZabbixAPIBaseModel):
    discoveryRules: ImportRule
    graphs: ImportRule
    groups: ImportRule | None = None  # < 6.2
    host_groups: ImportRule | None = None  # >= 6.2
    hosts: ImportRule
    httptests: ImportRule
    images: ImportRule
    items: ImportRule
    maps: ImportRule
    mediaTypes: ImportRule
    template_groups: ImportRule | None = None  # >= 6.2
    templateLinkage: ImportRule
    templates: ImportRule
    templateDashboards: ImportRule
    triggers: ImportRule
    valueMaps: ImportRule
    templateScreens: ImportRule | None = None  # < 6.0
    applications: ImportRule | None = None  # < 6.0
    screens: ImportRule | None = None  # < 6.0

    model_config = ConfigDict(validate_assignment=True)

    @classmethod
    def get(
        cls,
        *,
        create_missing: bool = False,
        update_existing: bool = False,
        delete_missing: bool = False,
    ) -> ImportRules:
        """Create import rules given directives and Zabbix API version."""
        # Create/delete missing
        cd = ImportRule(createMissing=create_missing, deleteMissing=delete_missing)
        # Create/update missing
        cu = ImportRule(createMissing=create_missing, updateExisting=update_existing)
        # Create/update/delete missing
        cud = ImportRule(
            createMissing=create_missing,
            updateExisting=update_existing,
            deleteMissing=delete_missing,
        )
        rules = ImportRules(
            discoveryRules=cud,
            graphs=cud,
            hosts=cu,
            httptests=cud,
            images=cu,
            items=cud,
            maps=cu,
            mediaTypes=cu,
            templateLinkage=cd,
            templates=cu,
            templateDashboards=cud,
            triggers=cud,
            valueMaps=cud,
        )
        if cls.zabbix_version.release >= (6, 2, 0):
            rules.host_groups = cu
            rules.template_groups = cu
        else:
            rules.groups = ImportRule(createMissing=create_missing)

        if cls.zabbix_version.major < 6:
            rules.applications = cd
            rules.screens = cu
            rules.templateScreens = cud

        return rules


def resolve_forward_refs() -> None:
    """Certain models have forward references that need to be resolved.

    I.e. HostGroup has a field `hosts` that references the Host model,
    which is defined _after_ the HostGroup model. This function resolves
    those forward references so that we can serialize them properly.

    We do the simplest possible resolution here, which is to just
    rebuild all the models in the module. This is inefficient, but
    guarantees we won't have any runtime errors due to unresolved
    forward references.
    """
    for obj in globals().values():
        if not isinstance(obj, type):
            continue
        try:
            if not issubclass(obj, ZabbixAPIBaseModel):
                continue
        except TypeError:
            continue
        obj.model_rebuild()


resolve_forward_refs()
