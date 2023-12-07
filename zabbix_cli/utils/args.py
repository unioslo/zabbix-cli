from __future__ import annotations

from enum import Enum
from typing import Generic
from typing import List
from typing import Type
from typing import TYPE_CHECKING
from typing import TypeVar
from typing import Union

from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.output.prompts import str_prompt

if TYPE_CHECKING:
    import sys

    if sys.version_info >= (3, 10):
        from types import EllipsisType
    else:
        from typing import Any as EllipsisType


# from strenum import StrEnum


T = TypeVar("T")


class APIStr(str, Generic[T]):
    """String type that can be used as an Enum choice while also
    carrying an API value associated with the string."""

    api_value: T

    def __new__(cls, s, api_value: T) -> APIStr[T]:
        obj = str.__new__(cls, s)
        obj.api_value = api_value
        return obj


MixinType = TypeVar("MixinType", bound="ChoiceMixin")


class ChoiceMixin(Generic[T]):
    """Mixin that allows for an Enum to have APIStr values, which
    enables it to be instantiated with both the string and the API value.

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
        lowercased, e.g. `AgentAvailabilityStatus` becomes `agent availability status`.
        """
        if cls.__choice_name__:
            return cls.__choice_name__
        return (
            "".join([(" " + i if i.isupper() else i) for i in cls.__name__])
            .lower()
            .strip()
        )

    @classmethod
    def from_prompt(
        cls: Type[MixinType],
        prompt: str | None = None,
        default: Union[MixinType, EllipsisType] = ...,
    ) -> MixinType:
        """Prompt the user to select a choice from the enum.

        Args:
            prompt (str | None, optional): Alternative prompt.
                Defaults to None, which uses the formatted class name.

        Returns:
            MixinType: Enum member selected by the user.
        """
        if not prompt:
            # Assume
            prompt = cls.__fmt_name__()
            # Uppercase first letter without mangling the rest of the string
            if prompt and prompt[0].islower():
                prompt = prompt[0].upper() + prompt[1:]
        choice = str_prompt(prompt, choices=cls.choices(), default=str(default))
        return cls(choice)  # type: ignore # mixin takes no args...

    @classmethod
    def choices(cls) -> List[str]:
        """Return list of string values of the enum members."""
        return [str(e) for e in cls]  # type: ignore # how do we stipulate that the class requires __iter__?

    def as_api_value(self) -> T:
        """Return the equivalent Zabbix API value."""
        return self.value.api_value

    @classmethod
    def _missing_(cls, value: object) -> object:
        """Attempts to instantiate Enum from Zabbix API value if argument
        was not found among member string values."""
        for v in cls:  # type: ignore # again with the cls.__iter__ problem
            if v.value.api_value == value:
                return v
        raise ZabbixCLIError(f"Invalid {cls.__fmt_name__()}: {value!r}.")


class APIStrEnum(Enum):
    """Enum that returns value of member as str."""

    # FIXME: should inherit from string somehow!
    # Does not inherit from str now, as it would convert enum member value
    # to string, thereby losing the API associated value.

    def __str__(self) -> str:
        return self.value


class AgentAvailabilityStatus(ChoiceMixin[int], APIStrEnum):
    """Agent availability status."""

    UNKNOWN = APIStr("unknown", 0)
    AVAILABLE = APIStr("available", 1)
    UNAVAILABLE = APIStr("unavailable", 2)


class OnOffChoice(ChoiceMixin[str], APIStrEnum):
    """On/Off choice."""

    # TODO: find a way to create subclasses/different enums from this,
    # so that we can re-use these members, but with different a
    # class names  or __choice__name__
    # Currently, we can't subclass enums with members, so just creating a
    # new enum with the same members is the only way to do it.

    ON = APIStr("on", "0")  # Yes, 0 is on, 1 is off...
    OFF = APIStr("off", "1")


AgentAvailabilityStatus.choices()
