from __future__ import annotations

from enum import Enum
from typing import Any
from typing import Generic
from typing import List
from typing import Mapping
from typing import Optional
from typing import Type
from typing import TYPE_CHECKING
from typing import TypeVar
from typing import Union

from strenum import StrEnum

from zabbix_cli.exceptions import ZabbixCLIError

if TYPE_CHECKING:
    from zabbix_cli._types import EllipsisType

T = TypeVar("T")


class APIStr(str, Generic[T]):
    """String type that can be used as an Enum choice while also
    carrying an API value associated with the string."""

    api_value: T
    metadata: Mapping[str, Any]

    def __new__(
        cls,
        s: str,
        api_value: T,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> APIStr[T]:
        obj = str.__new__(cls, s)
        obj.api_value = api_value
        obj.metadata = metadata or {}
        return obj


MixinType = TypeVar("MixinType", bound="ChoiceMixin")


class ChoiceMixin(Generic[T]):
    """Mixin that allows for an Enum to have APIStr values, which
    enables it to be instantiated with either the name of the option
    or the Zabbix API value of the option.

    We can instantiate the enum with either the name or the API value:
        * `AgentAvailable("available")`
        * `AgentAvailable("1")`
        * `AgentAvailable(1)`

    Since the API is inconsistent with usage of strings and ints, we support
    instantiation with both.

    Provides the `from_prompt` class method, which prompts the user to select
    one of the enum members. The prompt text is generated from the class name
    by default, but can be overridden by setting the `__choice_name__` class var.

    Also provides a method for returning the API value of an enum member with the
    with the `as_api_value()` method.
    """

    value: APIStr[T]
    __choice_name__: str = ""  # default (falls back to class name)

    def __init__(self, *args, **kwargs) -> None:
        pass

    @classmethod
    def __fmt_name__(cls) -> str:
        """Return the name of the enum class in a human-readable format.

        If no default is provided, the class name is split on capital letters and
        lowercased, e.g. `AgentAvailable` becomes `agent availability status`.
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
        cls: Type[MixinType],
        prompt: Optional[str] = None,
        default: Union[MixinType, EllipsisType] = ...,
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
        default = default if default is ... else str(default)
        choice = str_prompt(
            prompt,
            choices=cls.choices(),
            default=default,
        )
        return cls(choice)

    @classmethod
    def choices(cls) -> List[str]:
        """Return list of string values of the enum members."""
        return [str(e) for e in cls]  # type: ignore # how do we stipulate that the class requires __iter__?

    @classmethod
    def all_choices(cls) -> List[str]:
        """Choices including API values."""
        return [str(e) for e in cls] + [str(e.as_api_value()) for e in cls]  # type: ignore # how do we stipulate that the class requires __iter__?

    def as_api_value(self) -> T:
        """Return the equivalent Zabbix API value."""
        return self.value.api_value

    @classmethod
    def _missing_(cls, value: object) -> object:
        """
        Method that is called when an enum member is not found.

        Attempts to find the member with 2 strategies:
        1. Search for a member with the given string value (ignoring case)
        2. Search for a member with the given API value (converted to string)
        """
        for v in cls:  # type: ignore # again with the cls.__iter__ problem
            if v.value == value:
                return v
            # kinda hacky. Should make sure we are dealing with strings here:
            elif str(v.value).lower() == str(value).lower():
                return v
            elif str(v.as_api_value()) == str(value):
                return v
        raise ZabbixCLIError(f"Invalid {cls.__fmt_name__()}: {value!r}.")


# class EnumChoice(NamedTuple):
#     """Enum choice."""

#     name: str
#     value: str


# class ChoiceMeta(EnumMeta):
#     """Metaclass for APIStrEnum Enums."""

#     # HACK: doing something very illegal with the iterator here
#     def __iter__(cls) -> Iterator[EnumChoice]:
#         """Iterate over the enum members."""
#         items = []
#         for name, member in cls._member_map_.items():
#             items.append(member)
#             member_api_value = copy(member)
#             items.append(EnumChoice(name=str(name), value=str(member.as_api_value())))  # type: ignore
#         return iter(items)


class APIStrEnum(Enum):
    """Enum that returns value of member as str."""

    # FIXME: should inherit from string somehow!
    # Does not inherit from str now, as it would convert enum member value
    # to string, thereby losing the API associated value.
    # If we are to do that, we need to hijack the object creation and inject
    # the member value somehow?

    def __str__(self) -> str:
        return str(self.value)

    def casefold(self) -> str:
        return str(self.value).casefold()


class OnOffChoice(ChoiceMixin[str], APIStrEnum):
    """On/Off choice."""

    # TODO: find a way to create subclasses/different enums from this,
    # so that we can re-use these members, but with different a
    # class names  or __choice__name__
    # Currently, we can't subclass enums with members, so just creating a
    # new enum with the same members is the only way to do it.

    ON = APIStr("on", "0")  # Yes, 0 is on, 1 is off...
    OFF = APIStr("off", "1")


class UserRole(ChoiceMixin[str], APIStrEnum):
    __choice_name__ = "User role"

    # Match casing from Zabbix API
    USER = APIStr("user", "1")
    ADMIN = APIStr("admin", "2")
    SUPERADMIN = APIStr("superadmin", "3")
    GUEST = APIStr("guest", "4")


class UsergroupPermission(ChoiceMixin[int], APIStrEnum):
    """Usergroup permission levels."""

    DENY = APIStr("deny", 0)
    READ_ONLY = APIStr("ro", 2)
    READ_WRITE = APIStr("rw", 3)


class AgentAvailable(ChoiceMixin[str], APIStrEnum):
    """Agent availability status."""

    __choice_name__ = "Agent availability status"

    UNKNOWN = APIStr("unknown", "0")
    AVAILABLE = APIStr("available", "1")
    UNAVAILABLE = APIStr("unavailable", "2")


# See: zabbix_cli.utils.args.OnOffChoice for why we re-define on/off enum here
class MonitoringStatus(ChoiceMixin[str], APIStrEnum):
    """Host monitoring status."""

    ON = APIStr("on", "0")  # Yes, 0 is on, 1 is off...
    OFF = APIStr("off", "1")


class MaintenanceStatus(ChoiceMixin[str], APIStrEnum):
    """Host maintenance status."""

    # API values are inverted here compared to monitoring status...
    ON = APIStr("on", "1")
    OFF = APIStr("off", "0")


class InventoryMode(ChoiceMixin[str], APIStrEnum):
    """Host inventory mode."""

    DISABLED = APIStr("disabled", "-1")
    MANUAL = APIStr("manual", "0")
    AUTOMATIC = APIStr("automatic", "1")


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


class InterfaceConnectionMode(ChoiceMixin[str], APIStrEnum):
    """Interface connection mode.

    Controls the value of `useip` when creating interfaces in the API."""

    DNS = APIStr("DNS", "0")
    IP = APIStr("IP", "1")


class InterfaceType(ChoiceMixin[int], APIStrEnum):
    """Interface type."""

    AGENT = APIStr("Agent", 1, metadata={"port": 10050})
    SNMP = APIStr("SNMP", 2, metadata={"port": 161})
    IPMI = APIStr("IPMI", 3, metadata={"port": 623})
    JMX = APIStr("JMX", 4, metadata={"port": 12345})

    # TODO: test to ensure we always catch all cases (i.e. error should never be thrown)
    def get_port(self: InterfaceType) -> str:
        """Returns the default port for the given interface type."""
        try:
            return self.value.metadata["port"]
        except KeyError:
            raise ZabbixCLIError(f"Unknown interface type: {self}")


class SNMPSecurityLevel(ChoiceMixin[int], APIStrEnum):
    __choice_name__ = "SNMPv3 security level"

    # Match casing from Zabbix API
    NO_AUTH_NO_PRIV = APIStr("noAuthNoPriv", 0)
    AUTH_NO_PRIV = APIStr("authNoPriv", 1)
    AUTH_PRIV = APIStr("authPriv", 2)


class SNMPAuthProtocol(ChoiceMixin[int], APIStrEnum):
    """Authentication protocol for SNMPv3."""

    __choice_name__ = "SNMPv3 auth protocol"

    MD5 = APIStr("MD5", 0)
    SHA1 = APIStr("SHA1", 1)
    # >=6.0 only:
    SHA224 = APIStr("SHA224", 2)
    SHA256 = APIStr("SHA256", 3)
    SHA384 = APIStr("SHA384", 4)
    SHA512 = APIStr("SHA512", 5)


class SNMPPrivProtocol(ChoiceMixin[int], APIStrEnum):
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
