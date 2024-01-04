from __future__ import annotations

import logging
from enum import Enum
from typing import Any
from typing import Generic
from typing import List
from typing import Mapping
from typing import Optional
from typing import Type
from typing import TypeVar
from typing import Union

import typer
from click.core import ParameterSource

from zabbix_cli._types import EllipsisType
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.output.prompts import str_prompt


def is_set(ctx: typer.Context, option: str) -> bool:
    """Check if option is set in context."""
    src = ctx.get_parameter_source(option)
    if not src:
        logging.warning(f"Parameter {option} not found in context.")
        return False
    return src != ParameterSource.DEFAULT
    # return option in ctx.params and ctx.params[option]


def parse_int_arg(arg: str) -> int:
    """Convert string to int."""
    try:
        return int(arg.strip())
    except ValueError as e:
        raise ZabbixCLIError(f"Invalid integer value: {arg}") from e


def parse_list_arg(arg: Optional[str], keep_empty: bool = False) -> list[str]:
    """Convert comma-separated string to list."""
    try:
        args = arg.strip().split(",") if arg else []
        if not keep_empty:
            args = [a for a in args if a]
        return args
    except ValueError as e:
        raise ZabbixCLIError(f"Invalid comma-separated string value: {arg}") from e


def parse_int_list_arg(arg: str) -> list[int]:
    """Convert comma-separated string of ints to list of ints."""
    args = parse_list_arg(
        arg,
        keep_empty=False,  # Important that we never try to parse empty strings as ints
    )
    try:
        return list(map(parse_int_arg, args))
    except ValueError as e:
        raise ZabbixCLIError(f"Invalid comma-separated string value: {arg}") from e


def parse_bool_arg(arg: str) -> bool:
    """Convert string to bool."""
    try:
        return bool(arg.strip())
    except ValueError as e:
        raise ZabbixCLIError(f"Invalid boolean value: {arg}") from e


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

    E.g. `AgentAvailable("available")` or `AgentAvailable("1")`

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

    def as_api_value(self) -> T:
        """Return the equivalent Zabbix API value."""
        return self.value.api_value

    @classmethod
    def _missing_(cls, value: object) -> object:
        """
        Method that is called when an enum member is not found.

        Attempts to find the member with 2 strategies:
        1. Search for a member with the given string value (ignoring case)
        2. Search for a member with the given API value
        """
        for v in cls:  # type: ignore # again with the cls.__iter__ problem
            if v.value.api_value == value:
                return v
            # kinda hacky. Should make sure we are dealing with strings here:
            elif str(v.value).lower() == str(value).lower():
                return v
        raise ZabbixCLIError(f"Invalid {cls.__fmt_name__()}: {value!r}.")


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
