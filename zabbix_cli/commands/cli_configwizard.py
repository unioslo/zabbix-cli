"""Config wizard for Zabbix CLI."""

from __future__ import annotations

import ast
import inspect
import logging
import sys
import textwrap
from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from enum import EnumMeta
from operator import attrgetter
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Generic
from typing import Optional
from typing import TypeVar
from typing import Union
from typing import get_args

from pydantic import SecretStr
from rich.panel import Panel

from zabbix_cli.bulk import BulkRunnerMode
from zabbix_cli.config.constants import OutputFormat
from zabbix_cli.config.model import Config
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.output.console import console
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.prompts import bool_prompt
from zabbix_cli.output.prompts import float_prompt
from zabbix_cli.output.prompts import int_prompt
from zabbix_cli.output.prompts import list_prompt
from zabbix_cli.output.prompts import path_prompt
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.utils.args import parse_bool_arg

if sys.version_info >= (3, 10):
    from itertools import pairwise
else:
    # source: https://docs.python.org/3.12/library/itertools.html#itertools.pairwise
    def pairwise(iterable: Iterable[Any]) -> Iterable[tuple[Any, Any]]:
        # pairwise('ABCDEFG') → AB BC CD DE EF FG
        iterator = iter(iterable)
        a = next(iterator, None)
        for b in iterator:
            yield a, b
            a = b


logger = logging.getLogger(__name__)


EnumT = TypeVar("EnumT", bound=Enum)


@dataclass
class EnumMember(Generic[EnumT]):
    member: EnumT
    description: str = ""  # docstring


# Adapted from https://davidism.com/attribute-docstrings/
def get_enum_attr_docs(cls: type[EnumT]) -> dict[EnumT, str]:
    """Get any docstrings placed after attribute assignments in a class body."""
    cls_node = ast.parse(textwrap.dedent(inspect.getsource(cls))).body[0]

    if not isinstance(cls_node, ast.ClassDef):
        raise TypeError("Given object was not a class.")

    out: dict[EnumT, str] = {}

    # Consider each pair of nodes.
    for a, b in pairwise(cls_node.body):
        # Must be an assignment then a constant string.
        if (
            not isinstance(a, (ast.Assign, ast.AnnAssign))
            or not isinstance(b, ast.Expr)
            or not isinstance(b.value, ast.Constant)
            or not isinstance(b.value.value, str)
        ):
            continue

        doc = inspect.cleandoc(b.value.value)

        if isinstance(a, ast.Assign):
            # An assignment can have multiple targets (a = b = v).
            targets = a.targets
        else:
            # An annotated assignment only has one target.
            targets = [a.target]

        for target in targets:
            # Must be assigning to a plain name.
            if not isinstance(target, ast.Name):
                continue

            out[getattr(cls, target.id)] = doc

    return out


def get_enum_members(enum: type[EnumT]) -> list[EnumMember[EnumT]]:
    """Get enum members as a list of EnumMember namedtuples."""
    # Get the docstrings for the enum members
    try:
        docs = get_enum_attr_docs(enum)
    except Exception as e:
        logger.error("Failed to get attribute docstrings for enum %s: %s", enum, e)
        docs: dict[Enum, str] = {}
    return [
        EnumMember(member=member, description=docs.get(member, "")) for member in enum
    ]


def enum_prompt(
    choice_type: str,
    choices: type[EnumT],
    *,
    default: EnumT | None = None,
    show_default: bool = False,
    **kwargs: Any,
) -> EnumT:
    """Prompt for a choice input given an enum."""
    members = get_enum_members(choices)
    member_map = {str(idx): member for idx, member in enumerate(members, start=1)}  # noqa: C416 # dict comprehension is clearer
    lines = [choice_type]
    for idx, member in member_map.items():
        # TODO: add consistent formatting of spacing
        lines.append(f"{idx}) {member.member.name} - {member.description}")
    console.print("\n".join(lines))

    if default:
        default_arg = next(
            iter(k for k, v in member_map.items() if v.member == default), None
        )
    else:
        default_arg = None

    choice = str_prompt(
        "Enter selection",
        default=default_arg,
        show_default=show_default,
        choices=list(member_map.keys()),
        show_choices=True,
        **kwargs,
    )
    try:
        return member_map[choice].member
    except KeyError as e:
        logger.error("Failed to get choice %s for enum %s: %s", choice, choices, e)
        # NOTE: not really sure how to write this error message.
        # In theory it should be unreachable.
        raise ValueError(
            f"Unexpected choice {choice} for {choice_type} - expected one of {list(member_map.keys())}"
        ) from e
    except ValueError as e:
        logger.error("Unable to convert choice %s to %s enum: %s", choice, choices, e)
        raise ValueError(f"Unable to parse choice {choice!r} for {choice_type}") from e


def is_enum_type(obj: object) -> bool:
    """Check if an object is an enum."""
    return type(obj) is EnumMeta


T = TypeVar("T")


class AnySet(set[T]):
    pass


class AllSet(set[T]):
    pass


# TODO: NotAnySet
# TODO: NotAllSet


@dataclass
class ConfigOption(Generic[T]):
    """Configuration option for the CLI."""

    name: str
    attr: str
    type: type[T]
    empty_ok: bool = True
    message: Optional[str] = None
    depends_on: Union[AnySet[str], AllSet[str]] = field(default_factory=AnySet)

    def get_value(self, config: Config) -> T:
        return attrgetter(self.attr)(config)

    def get_message(self) -> str:
        """Get the message for the prompt."""
        if self.message:
            return self.message
        elif is_enum_type(self.type):
            return f"Select {self.name}"
        return f"Enter {self.name}"


def secret_str_prompt(
    message: str,
    *,
    default: SecretStr | None = None,
    show_default: bool = False,
    empty_ok: bool = False,
    password: bool = True,
) -> SecretStr:
    """Prompt for a secret string input."""
    value = str_prompt(
        message,
        default=default.get_secret_value() if default else None,
        show_default=show_default,
        empty_ok=empty_ok,
        password=password,
    )
    return SecretStr(value)


PROMPT_MAP: dict[type, Callable[..., object]] = {
    str: str_prompt,
    int: str_prompt,
    float: float_prompt,
    bool: bool_prompt,
    list: list_prompt,
    SecretStr: secret_str_prompt,
    Enum: enum_prompt,
}


def get_prompt(type: type[T]) -> Callable[..., object]:
    """Get the prompt function for a given type."""
    if type in PROMPT_MAP:
        return PROMPT_MAP[type]
    elif issubclass(type, Enum):
        return enum_prompt
    raise ValueError(f"Unsupported type for config option: {type}")


def bool_path_prompt(
    message: str,
    attr: str,
    *,
    default: Union[bool, Path] = True,
    show_default: bool = False,
    empty_ok: bool = False,
) -> Union[bool, Path]:
    """Prompt for a boolean or path input."""
    default_val = str(default) if isinstance(default, Path) else "y" if default else "n"
    inp = str_prompt(
        f"{message} [y/n/<path>]",
        default=default_val,
        show_default=True,
        show_choices=False,
    )
    try:
        val = parse_bool_arg(inp)
    except ZabbixCLIError:
        try:
            val = Path(inp)
        except Exception:
            exit_err(
                f"Invalid input for {attr}: {inp}. Must be 'y', 'n', or a valid path to a file."
            )
    return val


_CONFIG_OPTIONS: dict[str, list[ConfigOption[Any]]] = {
    "API Connection Settings": [
        ConfigOption(
            name="API URL",
            attr="api.url",
            type=str,
        ),
        ConfigOption(
            name="Username",
            attr="api.username",
            type=str,
        ),
        ConfigOption(
            name="Password",
            attr="api.password",
            type=SecretStr,
        ),
        ConfigOption(
            name="Auth token",
            attr="api.auth_token",
            type=SecretStr,
        ),
        ConfigOption(
            name="Verify SSL",
            message="Verify SSL certificates? (y/n or path to custom CA bundle)",
            attr="api.verify_ssl",
            type=Union[bool, Path],  # pyright: ignore[reportArgumentType] # TODO: fix union types
        ),
    ],
    "Application Settings": [
        ConfigOption(
            name="Session file",
            message="Store API session IDs locally to avoid login prompt each time?",
            attr="app.use_session_file",
            type=bool,
        ),
        ConfigOption(
            name="Session file location",
            attr="app.session_file",
            type=Path,
            depends_on=AnySet({"app.use_session_file"}),
        ),
        ConfigOption(
            name="Auth file",
            message="Configure auth file? (`username::password` stored in plaintext)",
            attr="app.use_auth_file",
            type=bool,
        ),
        ConfigOption(
            name="Auth file location",
            attr="app.auth_file",
            type=Path,
            depends_on=AnySet({"app.use_auth_file"}),
        ),
        ConfigOption(
            name="Insecure session/auth file",
            message="Allow insecure session/auth file",
            attr="app.allow_insecure_auth_file",
            type=bool,
            depends_on=AnySet({"app.use_session_file", "app.auth_file"}),
        ),
        ConfigOption(
            name="Enable command history",
            message="Enable command history",
            attr="app.history",
            type=bool,
        ),
        ConfigOption(
            name="Command history file location",
            attr="app.history_file",
            type=Path,
            depends_on=AnySet({"app.history"}),
        ),
        ConfigOption(
            name="Bulk operation mode",
            attr="app.bulk_mode",
            type=BulkRunnerMode,
        ),
    ],
    "Output Settings": [
        ConfigOption(
            name="Output format",
            attr="app.output.format",
            type=OutputFormat,
        ),
        ConfigOption(
            name="Output color",
            message="Enable color output?",
            attr="app.output.color",
            type=bool,
        ),
        # paging NYI
    ],
}

COMMAND_OPTIONS = {
    # Hosts
    "create_host": [
        ConfigOption(
            name="Default host groups",
            attr="app.commands.create_host.hostgroups",
            type=list[str],
        ),
        ConfigOption(
            name="Interface creation",
            message="Automatically create interfaces?",
            attr="app.commands.create_host.create_interface",
            type=bool,
        ),
    ],
    # Groups
    "create_hostgroup": [
        ConfigOption(
            name="Default read-only user groups",
            attr="app.commands.create_hostgroup.ro_groups",
            type=list[str],
            empty_ok=True,
        ),
        ConfigOption(
            name="Default read/write user groups",
            attr="app.commands.create_hostgroup.rw_groups",
            type=list[str],
            empty_ok=True,
        ),
    ],
    "create_templategroup": [
        ConfigOption(
            name="Default read-only user groups",
            attr="app.commands.create_templategroup.ro_groups",
            type=list[str],
            empty_ok=True,
        ),
        ConfigOption(
            name="Default read/write user groups",
            attr="app.commands.create_templategroup.rw_groups",
            type=list[str],
            empty_ok=True,
        ),
    ],
    # Users
    "create_user": [
        ConfigOption(
            name="Default usergroups",
            attr="app.commands.create_user.usergroups",
            type=list[str],
            empty_ok=True,
        ),
    ],
    "create_notification_user": [
        ConfigOption(
            name="Default usergroups",
            attr="app.commands.create_notification_user.usergroups",
            type=list[str],
            empty_ok=True,
        ),
    ],
}


class ConfigWizard:
    def __init__(self, config: Config) -> None:
        self.config = config

    def print_section(self, title: str) -> None:
        """Print a section title."""
        console.rule(title)

    def print_command_subsection(self, command: str) -> None:
        """Print a command subsection title."""
        console.rule(f"[command]{command}[/]")

    def run(self) -> None:
        """Run the configuration wizard.

        Modifies the config object in place.
        """
        panel = Panel(
            """\
Welcome to the Zabbix CLI configuration wizard!
This wizard will help you set up your Zabbix CLI configuration file.\
""",
            title="Zabbix CLI Configuration Wizard",
            expand=False,
        )
        console.print(panel)

        str_prompt("Press Enter to continue...", empty_ok=True, show_default=False)
        self.do_run()

    def do_run(self) -> None:
        # Keep track of options we have set and their values
        options_set: dict[str, Any] = {}

        def iter_config_options(options: list[ConfigOption[Any]]) -> None:
            for option in options:
                # Option(s) must be set and not falsey
                # i.e. `use_session_file = False` will not prompt
                # for the session file location
                if option.depends_on:
                    operator = all if isinstance(option.depends_on, AllSet) else any
                    if not operator(options_set.get(dep) for dep in option.depends_on):
                        continue

                # Store the value before prompting
                v_pre = option.get_value(self.config)
                v_new = self.prompt(option)

                # Only update config if the value has changed
                if v_pre != v_new:
                    self.assign_config_value(option.attr, v_new)

                options_set[option.attr] = v_new

                console.print("")  # newline between inputs

        for section, options_or_subsubsection in _CONFIG_OPTIONS.items():
            self.print_section(section)
            iter_config_options(options_or_subsubsection)

        if bool_prompt("Configure command defaults?", default=True):
            for command, options_or_subsubsection in COMMAND_OPTIONS.items():
                self.print_command_subsection(command)
                iter_config_options(options_or_subsubsection)

    def assign_config_value(self, attr: str, value: Any) -> None:
        """Assign the value to the config object."""
        attrs = attr.split(".")
        obj = self.config

        # Decompose the attribute string into its components
        for attr in attrs[:-1]:
            if not hasattr(obj, attr):
                raise ValueError(f"Invalid config attribute: {attr}")
            obj = getattr(obj, attr)

        # Set the value on the last attribute
        if hasattr(obj, attrs[-1]):
            setattr(obj, attrs[-1], value)
        else:
            raise ValueError(f"Invalid config attribute: {attrs[-1]}")

    # TODO: fix this generic annotation.
    #       How can we convince type checker that the prompt function
    #       returns the correct type?
    def prompt(self, option: ConfigOption[Any]) -> Any:
        """Prompt for a configuration option and return the value."""
        if option.type is str:
            value = str_prompt(
                option.get_message(),
                default=option.get_value(self.config),
                show_default=True,
                empty_ok=option.empty_ok,
            )
        elif option.type == SecretStr:
            value = secret_str_prompt(
                option.get_message(),
                default=option.get_value(self.config),
                show_default=True,
                empty_ok=True,
                password=True,
            )
        elif option.type is bool:
            value = bool_prompt(
                option.get_message(),
                default=option.get_value(self.config),
                show_default=True,
            )
        elif option.type is int:
            value = int_prompt(
                option.get_message(),
                default=option.get_value(self.config),
                show_default=True,
                empty_ok=option.empty_ok,
            )
        elif option.type is float:
            value = float_prompt(
                option.get_message(),
                default=option.get_value(self.config),
                show_default=True,
                empty_ok=option.empty_ok,
            )
        elif option.type == list[str]:
            value = list_prompt(
                option.get_message(),
                default=option.get_value(self.config),
                empty_ok=option.empty_ok,
                type=str,
            )
        elif option.type == Path:
            value = path_prompt(
                option.get_message(),
                default=option.get_value(self.config),
                show_default=True,
            )
        # TODO: improve heuristic for union types
        elif (args := get_args(option.type)) and all(
            arg in (bool, Path) for arg in args
        ):
            value = bool_path_prompt(
                option.get_message(),
                option.attr,
                default=option.get_value(self.config),
                show_default=True,
                empty_ok=False,
            )
        elif is_enum_type(option.type):
            value = enum_prompt(
                option.get_message(),
                option.type,
                default=option.get_value(self.config),
                show_default=True,
            )
        else:
            raise ValueError(f"Unsupported type for config option: {option.type}")
        return value


def run_wizard(config: Config) -> None:
    """Run the Zabbix CLI configuration wizard."""
    wizard = ConfigWizard(config)
    wizard.run()
