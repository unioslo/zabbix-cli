from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any
from typing import Generic
from typing import Optional
from typing import TypeVar

from strenum import StrEnum
from typing_extensions import Self

from zabbix_cli.exceptions import ZabbixCLIError

T = TypeVar("T")


class APIStr(str, Generic[T]):
    """String type that can be used as an Enum choice while also
    carrying an API value associated with the string.
    """

    # Instance variables are set by __new__
    api_value: T
    value: str
    metadata: Mapping[str, Any]
    hidden: bool

    def __new__(
        cls,
        s: str,
        api_value: T = None,
        metadata: Optional[Mapping[str, Any]] = None,
        hidden: bool = False,
    ) -> APIStr[T]:
        if isinstance(s, APIStr):
            return s  # type: ignore # Type checker should be able to infer generic type
        if api_value is None:
            raise ZabbixCLIError("API value must be provided for APIStr.")
        obj = str.__new__(cls, s)
        obj.value = s
        obj.api_value = api_value
        obj.metadata = metadata or {}
        obj.hidden = hidden
        return obj


MixinType = TypeVar("MixinType", bound="Choice")


class Choice(Enum):
    """Enum subclass that allows for an Enum to have APIStr values, which
    enables it to be instantiated with either the name of the option
    or the Zabbix API value of the option.

    We can instantiate the enum with either the name or the API value:
        * `ActiveInterface("available")`
        * `ActiveInterface(1)`
        * `ActiveInterface("1")`

    We use these enums as choices in the CLI, so that users can pass in
    a human readable name for the choice or its API value.

    Since the API itself is inconsistent with usage of strings and ints,
    we support instantiation with either one.

    Provides the `from_prompt` class method, which prompts the user to select
    one of the enum members. The prompt text is generated from the class name
    by default, but can be overridden by setting the `__choice_name__` class var.

    Also provides a method for returning the API value of an enum member with the
    with the `as_api_value()` method.
    """

    value: APIStr[int]  # pyright: ignore[reportIncompatibleMethodOverride]
    __choice_name__: str = ""  # default (falls back to class name)

    def __new__(cls, value: APIStr[int]) -> Choice:
        # Adds type checking for members in enum definition
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __str__(self) -> str:
        return str(self.value)

    def casefold(self) -> str:
        return str(self.value).casefold()

    @classmethod
    def __fmt_name__(cls) -> str:
        """Return the name of the enum class in a human-readable format.

        If no default is provided, the class name is split on capital letters and
        lowercased, e.g. `ActiveInterface` becomes `active interface`.
        """
        if cls.__choice_name__:
            return cls.__choice_name__
        return (
            "".join([(" " + i if i.isupper() else i) for i in cls.__name__])
            .lower()
            .strip()
        )

    # NOTE: should we use a custom prompt class instead of repurposing the str prompt?
    @classmethod
    def from_prompt(
        cls: type[MixinType],
        prompt: Optional[str] = None,
        default: MixinType = ...,  # pyright: ignore[reportArgumentType] # rich uses ... to signify no default
    ) -> MixinType:
        """Prompt the user to select a choice from the enum.

        Args:
            prompt (Optional[str], optional): Alternative prompt.
                Defaults to None, which uses the formatted class name.

        Returns:
            MixinType: Enum member selected by the user.
        """
        from zabbix_cli.output.prompts import str_prompt

        if not prompt:
            # Assume
            prompt = cls.__fmt_name__()
            # Uppercase first letter without mangling the rest of the string
            if prompt and prompt[0].islower():
                prompt = prompt[0].upper() + prompt[1:]
        default = default if default is ... else str(default)  # pyright: ignore[reportUnnecessaryComparison]
        choice = str_prompt(
            prompt,
            choices=cls.choices(),
            default=default,
        )
        return cls(choice)

    @classmethod
    def public_members(cls) -> list[Self]:
        """Return list of visible enum members."""
        return [e for e in cls if not e.value.hidden]

    @classmethod
    def choices(cls) -> list[str]:
        """Return list of string values of the enum members."""
        return [str(e) for e in cls.public_members()]

    @classmethod
    def api_choices(cls) -> list[int]:
        """Return list of API values of the enum members."""
        # NOTE: should this be a list of strings instead?
        return [e.as_api_value() for e in cls.public_members()]

    @classmethod
    def all_choices(cls) -> list[str]:
        """All public choices as well as their API values."""
        return cls.choices() + [str(c) for c in cls.api_choices()]

    def as_api_value(self) -> int:
        """Return the equivalent Zabbix API value."""
        return self.value.api_value

    @classmethod
    def _missing_(cls, value: object) -> object:
        """Method that is called when an enum member is not found.

        Attempts to find the member with 2 strategies:
        1. Search for a member with the given string value (ignoring case)
        2. Search for a member with the given API value (converted to string)
        """
        for v in cls:
            if v.value == value:
                return v
            # kinda hacky. Should make sure we are dealing with strings here:
            elif str(v.value).lower() == str(value).lower():
                return v
            elif str(v.as_api_value()) == str(value):
                return v
        raise ZabbixCLIError(f"Invalid {cls.__fmt_name__()}: {value!r}.")


class APIStrEnum(Choice):
    """Enum that returns value of member as str."""

    # FIXME: should inherit from string somehow!
    # Does not inherit from str now, as it would convert enum member value
    # to string, thereby losing the API associated value.
    # If we are to do that, we need to hijack the object creation and inject
    # the member value somehow?
    def as_status(self, default: str = "Unknown", with_code: bool = False) -> str:
        return self.string_from_value(self.value, default=default, with_code=with_code)

    @classmethod
    def string_from_value(
        cls: type[Self], value: Any, default: str = "Unknown", with_code: bool = False
    ) -> str:
        """Get a formatted status string given a value."""
        try:
            c = cls(value)
            # All lowercase is capitalized
            if str(c.value.islower()):
                name = c.value.capitalize()
            # Everything else is left as is
            else:
                name = str(c.value)
            code = c.value.api_value
        except (ValueError, ZabbixCLIError):
            name = default
            code = value
        if with_code:
            return f"{name} ({code})"
        return name


class AckStatus(APIStrEnum):
    NO = APIStr("no", 0)
    YES = APIStr("yes", 1)


class ActiveInterface(APIStrEnum):
    """Active interface availability status."""

    __choice_name__ = "Agent availability status"

    UNKNOWN = APIStr("unknown", 0)
    AVAILABLE = APIStr("available", 1)
    UNAVAILABLE = APIStr("unavailable", 2)


class DataCollectionMode(APIStrEnum):
    """Maintenance data collection mode."""

    ON = APIStr("on", 0)
    OFF = APIStr("off", 1)


class EventStatus(APIStrEnum):
    OK = APIStr("OK", 0)
    PROBLEM = APIStr("PROBLEM", 1)


class ExportFormat(StrEnum):
    XML = "xml"
    JSON = "json"
    YAML = "yaml"
    PHP = "php"

    @classmethod
    def _missing_(cls, value: object) -> ExportFormat:
        """Case-insensitive missing lookup.

        Allows for both `ExportFormat("JSON")` and `ExportFormat("json")`, etc.
        """
        if not isinstance(value, str):
            raise TypeError(f"Invalid format: {value!r}. Must be a string.")
        value = value.lower()
        for e in cls:
            if e.value.lower() == value:
                return e
        raise ValueError(f"Invalid format: {value!r}.")

    @classmethod
    def get_importables(cls) -> list[ExportFormat]:
        """Return list of formats that can be imported."""
        return [cls.JSON, cls.YAML, cls.XML]


class GUIAccess(APIStrEnum):
    """GUI Access for a user group."""

    __choice_name__ = "GUI Access"

    DEFAULT = APIStr("default", 0)
    INTERNAL = APIStr("internal", 1)
    LDAP = APIStr("ldap", 2)
    DISABLE = APIStr("disable", 3)


class HostgroupFlag(APIStrEnum):
    """Hostgroup flags."""

    PLAIN = APIStr("plain", 0)
    DISCOVER = APIStr("discovered", 4)


class HostgroupType(APIStrEnum):
    """Hostgroup types."""

    NOT_INTERNAL = APIStr("not internal", 0)
    INTERNAL = APIStr("internal", 1)


class InterfaceConnectionMode(APIStrEnum):
    """Interface connection mode.

    Controls the value of `useip` when creating interfaces in the API.
    """

    DNS = APIStr("DNS", 0)
    IP = APIStr("IP", 1)


class InterfaceType(APIStrEnum):
    """Interface type."""

    AGENT = APIStr("Agent", 1, metadata={"port": "10050"})
    SNMP = APIStr("SNMP", 2, metadata={"port": "161"})
    IPMI = APIStr("IPMI", 3, metadata={"port": "623"})
    JMX = APIStr("JMX", 4, metadata={"port": "12345"})

    def get_port(self: InterfaceType) -> str:
        """Returns the default port for the given interface type."""
        try:
            return self.value.metadata["port"]
        except KeyError:
            raise ZabbixCLIError(f"Unknown interface type: {self}")


class InventoryMode(APIStrEnum):
    """Host inventory mode."""

    DISABLED = APIStr("disabled", -1)
    MANUAL = APIStr("manual", 0)
    AUTOMATIC = APIStr("automatic", 1)


class ItemType(APIStrEnum):
    ZABBIX_AGENT = APIStr("Zabbix agent", 0)
    SNMPV1_AGENT = APIStr("SNMPv1 agent", 1)
    ZABBIX_TRAPPER = APIStr("Zabbix trapper", 2)
    SIMPLE_CHECK = APIStr("Simple check", 3)
    SNMPV2_AGENT = APIStr("SNMPv2 agent", 4)
    ZABBIX_INTERNAL = APIStr("Zabbix internal", 5)
    SNMPV3_AGENT = APIStr("SNMPv3 agent", 6)
    ZABBIX_AGENT_ACTIVE = APIStr("Zabbix agent (active)", 7)
    ZABBIX_AGGREGATE = APIStr("Zabbix aggregate", 8)
    WEB_ITEM = APIStr("Web item", 9)
    EXTERNAL_CHECK = APIStr("External check", 10)
    DATABASE_MONITOR = APIStr("Database monitor", 11)
    IPMI_AGENT = APIStr("IPMI agent", 12)
    SSH_AGENT = APIStr("SSH agent", 13)
    TELNET_AGENT = APIStr("TELNET agent", 14)
    CALCULATED = APIStr("calculated", 15)
    JMX_AGENT = APIStr("JMX agent", 16)
    SNMP_TRAP = APIStr("SNMP trap", 17)
    DEPENDENT_ITEM = APIStr("Dependent item", 18)
    HTTP_AGENT = APIStr("HTTP agent", 19)
    SNMP_AGENT = APIStr("SNMP agent", 20)
    SCRIPT = APIStr("Script", 21)


class MacroType(APIStrEnum):
    TEXT = APIStr("text", 0)
    SECRET = APIStr("secret", 1)
    VAULT_SECRET = APIStr("vault secret", 2)


class MacroAutomatic(APIStrEnum):
    """Macro automatic (discovered) status."""

    NO = APIStr("no", 0)  # user managed
    YES = APIStr("yes", 1)  # managed by discovery rule


class MaintenancePeriodType(APIStrEnum):
    """Maintenance period."""

    ONETIME = APIStr("one time", 0)
    DAILY = APIStr("daily", 2)
    WEEKLY = APIStr("weekly", 3)
    MONTHLY = APIStr("monthly", 4)


class MaintenanceStatus(APIStrEnum):
    """Host maintenance status."""

    # API values are inverted here compared to monitoring status...
    ON = APIStr("on", 1)
    OFF = APIStr("off", 0)


class MaintenanceType(APIStrEnum):
    """Maintenance type."""

    WITH_DC = APIStr("With DC", 0)
    WITHOUT_DC = APIStr("Without DC", 1)


class MaintenanceWeekType(APIStrEnum):
    """Maintenance every week type."""

    FIRST_WEEK = APIStr("first week", 1)
    SECOND_WEEK = APIStr("second week", 2)
    THIRD_WEEK = APIStr("third week", 3)
    FOURTH_WEEK = APIStr("fourth week", 4)
    LAST_WEEK = APIStr("last week", 5)


class MediaTypeType(APIStrEnum):
    """Type of media type."""

    EMAIL = APIStr("email", 0)
    SCRIPT = APIStr("script", 1)
    SMS = APIStr("SMS", 2)
    WEBHOOK = APIStr("webhook", 4)
    # no 3 value in API


class MonitoredBy(APIStrEnum):  # >=7.0 only
    SERVER = APIStr("server", 0)
    PROXY = APIStr("proxy", 1)
    PROXY_GROUP = APIStr("proxygroup", 2)


class MonitoringStatus(APIStrEnum):
    """Host monitoring status."""

    ON = APIStr("on", 0)  # Yes, 0 is on, 1 is off...
    OFF = APIStr("off", 1)
    UNKNOWN = APIStr(
        "unknown", 3, hidden=True
    )  # Undocumented, but shows up in virtual trigger hosts (get_triggers(select_hosts=True))


class ProxyCompatibility(APIStrEnum):
    """Proxy compatibility status for >=7.0"""

    UNDEFINED = APIStr("undefined", 0)
    CURRENT = APIStr("current", 1)
    OUTDATED = APIStr("outdated", 2)
    UNSUPPORTED = APIStr("unsupported", 3)


class ProxyGroupState(APIStrEnum):
    UNKNOWN = APIStr("unknown", 0)
    OFFLINE = APIStr("offline", 1)
    RECOVERING = APIStr("recovering", 2)
    ONLINE = APIStr("online", 3)
    DEGRADING = APIStr("degrading", 4)


class ProxyMode(APIStrEnum):
    """Proxy mode."""

    ACTIVE = APIStr("active", 0)
    PASSIVE = APIStr("passive", 1)


class ProxyModePre70(APIStrEnum):
    """Proxy mode pre 7.0."""

    ACTIVE = APIStr("active", 5)
    PASSIVE = APIStr("passive", 6)


class SNMPAuthProtocol(APIStrEnum):
    """Authentication protocol for SNMPv3."""

    __choice_name__ = "SNMPv3 auth protocol"

    MD5 = APIStr("MD5", 0)
    SHA1 = APIStr("SHA1", 1)
    # >=6.0 only:
    SHA224 = APIStr("SHA224", 2)
    SHA256 = APIStr("SHA256", 3)
    SHA384 = APIStr("SHA384", 4)
    SHA512 = APIStr("SHA512", 5)


class SNMPPrivProtocol(APIStrEnum):
    """Privacy protocol for SNMPv3."""

    __choice_name__ = "SNMPv3 privacy protocol"

    DES = APIStr("DES", 0)
    AES = APIStr("AES", 1)  # < 6.0 only
    # >=6.0 only:
    AES128 = APIStr("AES128", 1)  # >= 6.0
    AES192 = APIStr("AES192", 2)
    AES256 = APIStr("AES256", 3)
    AES192C = APIStr("AES192C", 4)
    AES256C = APIStr("AES256C", 5)


class SNMPSecurityLevel(APIStrEnum):
    __choice_name__ = "SNMPv3 security level"

    # Match casing from Zabbix API
    NO_AUTH_NO_PRIV = APIStr("noAuthNoPriv", 0)
    AUTH_NO_PRIV = APIStr("authNoPriv", 1)
    AUTH_PRIV = APIStr("authPriv", 2)


class TriggerPriority(APIStrEnum):
    UNCLASSIFIED = APIStr("unclassified", 0)
    INFORMATION = APIStr("information", 1)
    WARNING = APIStr("warning", 2)
    AVERAGE = APIStr("average", 3)
    HIGH = APIStr("high", 4)
    DISASTER = APIStr("disaster", 5)


class UsergroupPermission(APIStrEnum):
    """Usergroup permission levels."""

    DENY = APIStr("deny", 0)
    READ_ONLY = APIStr("ro", 2)
    READ_WRITE = APIStr("rw", 3)


class UsergroupStatus(APIStrEnum):
    """Usergroup status."""

    ENABLED = APIStr("enabled", 0)
    DISABLED = APIStr("disabled", 1)


class UserRole(APIStrEnum):
    __choice_name__ = "User role"

    # Match casing from Zabbix API
    USER = APIStr("user", 1)
    ADMIN = APIStr("admin", 2)
    SUPERADMIN = APIStr("superadmin", 3)
    GUEST = APIStr("guest", 4)


class ValueType(APIStrEnum):
    NUMERIC_FLOAT = APIStr("Numeric (float)", 0)
    CHARACTER = APIStr("Character", 1)
    LOG = APIStr("Log", 2)
    NUMERIC_UNSIGNED = APIStr("Numeric (unsigned)", 3)
    TEXT = APIStr("Text", 4)
