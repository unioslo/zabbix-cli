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

from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import ClassVar
from typing import Dict
from typing import List
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union

from packaging.version import Version
from pydantic import AliasChoices
from pydantic import BaseModel
from pydantic import computed_field
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_serializer
from pydantic import field_validator
from pydantic import model_validator
from pydantic import ValidationInfo
from strenum import StrEnum
from typing_extensions import Literal
from typing_extensions import TypedDict

from zabbix_cli.models import TableRenderable
from zabbix_cli.models import TableRenderableDict
from zabbix_cli.utils.args import APIStr
from zabbix_cli.utils.args import APIStrEnum
from zabbix_cli.utils.args import ChoiceMixin
from zabbix_cli.utils.utils import get_ack_status
from zabbix_cli.utils.utils import get_event_status
from zabbix_cli.utils.utils import get_gui_access
from zabbix_cli.utils.utils import get_hostgroup_flag
from zabbix_cli.utils.utils import get_hostgroup_type
from zabbix_cli.utils.utils import get_item_type
from zabbix_cli.utils.utils import get_macro_type
from zabbix_cli.utils.utils import get_maintenance_active_days
from zabbix_cli.utils.utils import get_maintenance_active_months
from zabbix_cli.utils.utils import get_maintenance_every_type
from zabbix_cli.utils.utils import get_maintenance_period_type
from zabbix_cli.utils.utils import get_maintenance_status
from zabbix_cli.utils.utils import get_monitoring_status
from zabbix_cli.utils.utils import get_trigger_severity
from zabbix_cli.utils.utils import get_user_type
from zabbix_cli.utils.utils import get_usergroup_status
from zabbix_cli.utils.utils import get_value_type
from zabbix_cli.utils.utils import get_zabbix_agent_status


if TYPE_CHECKING:
    from zabbix_cli.models import ColsType  # noqa: F401
    from zabbix_cli.models import ColsRowsType
    from zabbix_cli.models import RowsType  # noqa: F401

SortOrder = Literal["ASC", "DESC"]

PrimitiveType = Union[str, bool, int]
ParamsType = Dict[str, Any]
"""Type definition for Zabbix API query parameters.
Most Zabbix API parameters are strings, but not _always_.
They can also be contained in nested dicts or in lists.
"""

# JsonValue: TypeAlias = Union[
#     List["JsonValue"],
#     Dict[str, "JsonValue"],
#     Dict[str, Any],
#     str,
#     bool,
#     int,
#     float,
#     None,
# ]
# ParamsType: TypeAlias = Dict[str, JsonValue]


class ModifyHostItem(TypedDict):
    """Argument for a host ID in an API request."""

    hostid: Union[str, int]


ModifyHostParams = List[ModifyHostItem]

"""A list of host IDs in an API request.

E.g. `[{"hostid": "123"}, {"hostid": "456"}]`
"""


class ModifyGroupItem(TypedDict):
    """Argument for a host ID in an API request."""

    groupid: Union[str, int]


ModifyGroupParams = List[ModifyGroupItem]
"""A list of host/template group IDs in an API request.

E.g. `[{"groupid": "123"}, {"groupid": "456"}]`
"""


class ModifyTemplateItem(TypedDict):
    """Argument for a template ID in an API request."""

    templateid: Union[str, int]


ModifyTemplateParams = List[ModifyTemplateItem]
"""A list of template IDs in an API request.

E.g. `[{"templateid": "123"}, {"templateid": "456"}]`
"""


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


class GUIAccess(ChoiceMixin[str], APIStrEnum):
    """GUI Access for a user group."""

    __choice_name__ = "GUI Access"

    DEFAULT = APIStr("default", "0")
    INTERNAL = APIStr("internal", "1")
    LDAP = APIStr("ldap", "2")
    DISABLE = APIStr("disable", "3")


class DataCollectionMode(ChoiceMixin[str], APIStrEnum):
    """Maintenance type."""

    ON = APIStr("on", "0")
    OFF = APIStr("off", "1")


class TriggerPriority(ChoiceMixin[str], APIStrEnum):
    UNCLASSIFIED = APIStr("unclassified", "0")
    INFORMATION = APIStr("information", "1")
    WARNING = APIStr("warning", "2")
    AVERAGE = APIStr("average", "3")
    HIGH = APIStr("high", "4")
    DISASTER = APIStr("disaster", "5")


class ExportFormat(StrEnum):
    XML = "xml"
    JSON = "json"
    YAML = "yaml"
    PHP = "php"

    @classmethod
    def _missing_(cls, v: object) -> ExportFormat:
        """Case-insensitive missing lookup.

        Allows for both `ExportFormat("JSON")` and `ExportFormat("json")`, etc."""
        if not isinstance(v, str):
            raise TypeError(f"Invalid format: {v!r}. Must be a string.")
        v = v.lower()
        for e in cls:
            if e.value.lower() == v:
                return e
        raise ValueError(f"Invalid format: {v!r}.")

    @classmethod
    def get_importables(cls) -> List[ExportFormat]:
        """Return list of formats that can be imported."""
        return [cls.JSON, cls.YAML, cls.XML]


class ZabbixAPIBaseModel(TableRenderable):
    """Base model for Zabbix API objects.

    Implements the `TableRenderable` interface, which allows us to render
    it as a table, JSON, csv, etc."""

    version: ClassVar[Version] = Version("6.4.0")  # assume latest released version
    """Zabbix API version the data stems from.
    This is a class variable that can be overridden, which causes all
    subclasses to use the new value when accessed.

    This class variable is set by `State.configure` based on the connected
    Zabbix server API version. Assumes latest released version by default.
    """
    legacy_json_format: ClassVar[bool] = False
    """Whether to use the legacy JSON format for rendering objects.

    This class variable is set by `State.configure` based on the
    current configuration. Assumes new JSON format by default."""

    model_config = ConfigDict(validate_assignment=True, extra="ignore")


class ZabbixRight(TypedDict):
    # TODO: convert to BaseModel instead of TypedDict
    permission: int
    id: str


class User(ZabbixAPIBaseModel):
    userid: str
    username: str = Field(..., validation_alias=AliasChoices("username", "alias"))
    name: Optional[str] = None
    surname: Optional[str] = None
    url: Optional[str] = None
    autologin: Optional[str] = None
    autologout: Optional[str] = None
    roleid: Optional[int] = Field(
        default=None, validation_alias=AliasChoices("roleid", "type")
    )
    # NOTE: Not adding properties we don't use, since Zabbix have a habit of breaking
    # their own API by changing names and types of properties.

    @computed_field  # type: ignore[misc]
    @property
    def role(self) -> Optional[str]:
        """Returns the role name, if available."""
        if self.roleid:
            return get_user_type(self.roleid)
        return None

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["UserID", "Username", "Name", "Surname", "Role"]  # type: ColsType
        rows = [
            [
                self.userid,
                self.username,
                self.name or "",
                self.surname or "",
                self.role or "",
            ]
        ]  # type: RowsType
        return cols, rows


class Usergroup(ZabbixAPIBaseModel):
    name: str
    usrgrpid: str
    gui_access: int
    users_status: int
    rights: List[ZabbixRight] = []
    hostgroup_rights: List[ZabbixRight] = []
    templategroup_rights: List[ZabbixRight] = []
    users: List[User] = []

    @computed_field  # type: ignore[misc] # pydantic docs use decorators on top of property (https://docs.pydantic.dev/2.0/usage/computed_fields/)
    @property
    def gui_access_str(self) -> str:
        """GUI access code as a formatted string."""
        return get_gui_access(self.gui_access)

    @computed_field  # type: ignore[misc]
    @property
    def users_status_str(self) -> str:
        """User status as a formatted string."""
        return get_usergroup_status(self.users_status)

    @computed_field  # type: ignore[misc]
    @property
    def status(self) -> str:
        """LEGACY COMPATIBILITY: 'users_status' is called 'status' in V2.
        Ensures serialized output contains the field."""
        return self.users_status_str

    @field_serializer("gui_access")
    def _LEGACY_type_serializer(self, v: Optional[int], _info) -> Union[str, int, None]:
        """Serializes the GUI access status as a formatted string in legacy JSON mode"""
        if self.legacy_json_format:
            return self.gui_access
        return v


class HostGroup(ZabbixAPIBaseModel):
    groupid: str
    name: str
    hosts: List[Host] = []
    # FIXME: Use Optional[str] and None default?
    flags: int = 0
    internal: int = 0  # should these be ints?

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["GroupID", "Name", "Flag", "Type", "Hosts"]
        rows = [
            [
                self.groupid,
                self.name,
                get_hostgroup_flag(self.flags),
                get_hostgroup_type(self.internal),
                ", ".join([host.host for host in self.hosts]),
            ]
        ]  # type: RowsType
        return cols, rows


class TemplateGroup(ZabbixAPIBaseModel):
    groupid: str
    name: str
    uuid: str
    templates: List[Template] = []


class Template(ZabbixAPIBaseModel):
    """A template object. Can contain hosts and other templates."""

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

    name: Optional[str] = None
    """The visible name of the template."""

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["ID", "Name", "Hosts", "Children", "Parents"]
        rows = [
            [
                self.templateid,
                self.name or self.host,  # prefer name, fall back on host
                "\n".join([host.host for host in self.hosts]),
                "\n".join([template.host for template in self.templates]),
                "\n".join([parent.host for parent in self.parent_templates]),
            ]
        ]  # type: RowsType
        return cols, rows


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
        ]  # type: RowsType
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
    def type_str(self) -> str:
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
    key: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("key_", "key")
    )
    name: Optional[str] = None
    type: Optional[int] = None
    url: Optional[str] = None
    value_type: Optional[int] = None
    description: Optional[str] = None
    history: Optional[str] = None
    lastvalue: Optional[str] = None
    hosts: List[Host] = []

    @computed_field  # type: ignore[misc] # pydantic docs use decorators on top of property (https://docs.pydantic.dev/2.0/usage/computed_fields/)
    @property
    def type_str(self) -> str:
        """Returns the item type as a formatted string."""
        return get_item_type(self.type)

    @computed_field  # type: ignore[misc]
    @property
    def value_type_str(self) -> str:
        """Returns the item type as a formatted string."""
        return get_value_type(self.value_type)

    @field_serializer("type")
    def _LEGACY_type_serializer(self, v: Optional[int], _info) -> Union[str, int, None]:
        """Serializes the item type as a formatted string in legacy JSON mode"""
        if self.legacy_json_format:
            return self.type_str
        return v

    @field_serializer("value_type")
    def _LEGACY_value_type_serializer(
        self, v: Optional[int], _info
    ) -> Union[str, int, None]:
        """Serializes the item type as a formatted string in legacy JSON mode"""
        if self.legacy_json_format:
            return self.type_str
        return v

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["ID", "Name", "Key", "Type", "Interval", "History", "Description"]
        rows = [
            [
                self.itemid,
                str(self.name),
                str(self.key),
                str(self.type_str),
                str(self.delay),
                str(self.history),
                str(self.description),
            ]
        ]  # type: RowsType
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
    description: Optional[str] = None


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
    start_date: Optional[datetime] = None
    start_time: Optional[int] = None
    every: Optional[int] = None
    dayofweek: Optional[int] = None
    day: Optional[int] = None
    month: Optional[int] = None

    @computed_field  # type: ignore[misc]
    @property
    def timeperiod_type_str(self) -> str:
        """Returns the time period type as a formatted string."""
        return get_maintenance_period_type(self.timeperiod_type)

    @computed_field  # type: ignore[misc]
    @property
    def period_str(self) -> str:
        return str(timedelta(seconds=self.period))

    @computed_field  # type: ignore[misc]
    @property
    def start_time_str(self) -> str:
        return str(timedelta(seconds=self.start_time or 0))

    @computed_field  # type: ignore[misc]
    @property
    def start_date_str(self) -> str:
        if self.start_date and self.start_date.year > 1970:  # hack to avoid 1970-01-01
            return self.start_date.strftime("%Y-%m-%d %H:%M")
        return ""

    @computed_field  # type: ignore[misc]
    @property
    def month_str(self) -> List[str]:
        return get_maintenance_active_months(self.month)

    @computed_field  # type: ignore[misc]
    @property
    def dayofweek_str(self) -> List[str]:
        return get_maintenance_active_days(self.dayofweek)

    @computed_field  # type: ignore[misc]
    @property
    def every_str(self) -> str:
        return get_maintenance_every_type(self.every)

    def __cols_rows__(self) -> ColsRowsType:
        """Renders the table based on the time period type.

        Fields are added/removed based on the time period type."""
        # TODO: Use enum to define these values
        # and then re-use them in the get_maintenance_period_type function
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
        ]  # type: ColsType
        rows = [
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
        ]  # type: RowsType
        return cols, rows

    def _get_cols_rows_one_time(self) -> ColsRowsType:
        """Get the cols and rows for a one time schedule."""
        cols = ["Type", "Duration", "Start date"]  # type: ColsType
        rows = [
            [
                self.timeperiod_type_str,
                self.period_str,
                self.start_date_str,
            ]
        ]  # type: RowsType
        return cols, rows


class ProblemTag(ZabbixAPIBaseModel):
    tag: str
    operator: Optional[int]
    value: Optional[str]


class Maintenance(ZabbixAPIBaseModel):
    maintenanceid: str
    name: str
    active_since: Optional[datetime] = None
    active_till: Optional[datetime] = None
    description: Optional[str] = None
    maintenance_type: Optional[int] = None
    tags_evaltype: Optional[int] = None
    timeperiods: List[TimePeriod] = []
    tags: List[ProblemTag] = []
    hosts: List[Host] = []
    hostgroups: List[HostGroup] = Field(
        default_factory=list, validation_alias=AliasChoices("groups", "hostgroups")
    )

    @field_validator("timeperiods", mode="after")
    @classmethod
    def _sort_time_periods(cls, v: List[TimePeriod]) -> List[TimePeriod]:
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
    clock: datetime
    name: str
    value: Optional[int] = None  # docs seem to imply this is optional
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

    @computed_field  # type: ignore[misc]
    @property
    def age(self) -> str:
        """Returns the age of the event as a formatted string."""
        n = datetime.now(tz=self.clock.tzinfo)
        age = n - self.clock
        # strip microseconds
        return str(age - timedelta(microseconds=age.microseconds))

    @computed_field  # type: ignore[misc]
    @property
    def status_str(self) -> str:
        return get_event_status(self.value)

    @computed_field  # type: ignore[misc]
    @property
    def acknowledged_str(self) -> str:
        return get_ack_status(self.acknowledged)

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
        self, v: Optional[int], _info
    ) -> Union[str, int, None]:
        """Serializes the value field as a formatted string in legacy JSON mode"""
        if self.legacy_json_format:
            return self.status_str
        return v

    @field_serializer("acknowledged")
    def _LEGACY_acknowledged_serializer(self, v: int, _info) -> Union[str, int]:
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
        rows = [
            [
                self.eventid,
                self.objectid,
                self.name,
                self.clock.strftime("%Y-%m-%d %H:%M:%S"),
                self.age,
                self.acknowledged_str_cell,
                self.status_str_cell,
            ]
        ]
        return cols, rows


class Trigger(ZabbixAPIBaseModel):
    triggerid: str
    description: Optional[str]
    expression: Optional[str]
    event_name: str
    opdata: str
    comments: str
    error: str
    flags: int
    lastchange: datetime
    priority: int
    state: int
    templateid: Optional[str]
    type: int
    url: str
    url_name: str
    value: int
    recovery_mode: int
    recovery_expression: str
    correlation_mode: int
    correlation_tag: str
    manual_close: int
    uuid: str
    hosts: List[Host] = []
    # NYI:
    # groups: List[HostGroup] = Field(
    #     default_factory=list, validation_alias=AliasChoices("groups", "hostgroups")
    # )
    # items
    # functions
    # dependencies
    # discoveryRule
    # lastEvent

    @computed_field  # type: ignore[misc]
    @property
    def age(self) -> str:
        """Returns the age of the event as a formatted string."""
        n = datetime.now(tz=self.lastchange.tzinfo)
        age = n - self.lastchange
        # strip microseconds
        return str(age - timedelta(microseconds=age.microseconds))

    @computed_field  # type: ignore[misc]
    @property
    def hostname(self) -> Optional[str]:
        """Returns the hostname of the trigger."""
        if self.hosts:
            return self.hosts[0].host
        return None

    @computed_field  # type: ignore[misc]
    @property
    def severity(self) -> str:
        return get_trigger_severity(self.priority)

    def __cols_rows__(self) -> ColsRowsType:
        cols = [
            "Trigger ID",
            "Host",
            "Description",
            "Severity",
            "Last Change",
            "Age",
        ]
        rows = [
            [
                self.triggerid,
                self.hostname or "",
                self.description or "",
                self.severity,
                self.lastchange.strftime("%Y-%m-%d %H:%M:%S"),
                self.age,
            ]
        ]
        return cols, rows


class Image(ZabbixAPIBaseModel):
    imageid: str
    name: str
    imagetype: int
    # NOTE: Optional so we can fetch an image without its data
    # This lets us get the IDs of all images without keeping the data in memory
    image: Optional[str] = None


class Map(ZabbixAPIBaseModel):
    sysmapid: str
    name: str
    height: int
    width: int
    backgroundid: Optional[str] = None  # will this be an empty string instead?
    # Other fields are omitted. We only use this for export and import.


class ImportRule(BaseModel):
    createMissing: bool
    updateExisting: Optional[bool] = None


class ImportRules(ZabbixAPIBaseModel):
    discoveryRules: ImportRule
    graphs: ImportRule
    groups: Optional[ImportRule] = None  # < 6.2
    host_groups: Optional[ImportRule] = None  # >= 6.2
    template_groups: Optional[ImportRule] = None  # >= 6.2
    hosts: ImportRule
    images: ImportRule
    items: ImportRule
    maps: ImportRule
    templateLinkage: ImportRule
    templates: ImportRule
    triggers: ImportRule
    valueMaps: ImportRule
    mediaTypes: ImportRule
    applications: Optional[ImportRule] = None
    screens: Optional[ImportRule] = None
    templateScreens: Optional[ImportRule] = None

    model_config = ConfigDict(validate_assignment=True)

    @classmethod
    def get(
        cls, create_missing: bool = False, update_existing: bool = False
    ) -> ImportRules:
        """Create import rules given directives and Zabbix API version."""
        create = ImportRule(createMissing=create_missing)
        create_update = ImportRule(
            createMissing=create_missing, updateExisting=update_existing
        )
        rules = ImportRules(
            discoveryRules=create_update,
            graphs=create_update,
            hosts=create_update,
            images=create_update,
            items=create_update,
            maps=create_update,
            templateLinkage=create,
            templates=create_update,
            triggers=create_update,
            valueMaps=create_update,
            mediaTypes=create_update,
        )
        if cls.version.release >= (6, 2, 0):
            rules.host_groups = create_update
            rules.template_groups = create_update
        else:
            rules.groups = create_update

        if cls.version.major < 6:
            rules.applications = create
            rules.screens = create_update
            rules.templateScreens = create_update

        return rules

    def dump_params(self) -> ParamsType:
        return self.model_dump(mode="json", exclude_none=True)
