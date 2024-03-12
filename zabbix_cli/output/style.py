# Rich markup styles for the CLI
from __future__ import annotations

from typing import Any

from rich.theme import Theme
from strenum import StrEnum


STYLE_CONFIG_OPTION = "italic yellow"
"""Used to signify a configuration file option/key/entry."""

STYLE_CLI_OPTION = "green"
"""Used to signify a CLI option, e.g. --verbose."""

STYLE_CLI_VALUE = "bold magenta"
"""Used to signify a CLI value e.g. 'FILE'."""

STYLE_CLI_COMMAND = "bold green"
"""Used to signify a CLI command e.g. 'artifact get'."""

STYLE_TABLE_HEADER = "bold green"
STYLE_WARNING = "yellow"

####################
# Colors
####################
# Colors should be used to colorize output and help define styles,
# but they should not contain any formatting (e.g. bold, italic, `x` on `y`, etc.)
####################


class Color(StrEnum):
    INFO = "default"
    SUCCESS = "green"
    WARNING = "yellow"
    ERROR = "red"


def blue(message: str) -> str:
    return f"[blue]{message}[/]"


def cyan(message: str) -> str:
    return f"[cyan]{message}[/]"


def green(message: str) -> str:
    return f"[green]{message}[/]"


def magenta(message: str) -> str:
    return f"[magenta]{message}[/]"


def red(message: str) -> str:
    return f"[red]{message}[/]"


def yellow(message: str) -> str:
    return f"[yellow]{message}[/]"


def bold(message: str) -> str:
    return f"[bold]{message}[/]"


def warning(message: str) -> str:
    return f"[warning]{message}[/]"


def error(message: str) -> str:
    return f"[error]{message}[/]"


def success(message: str) -> str:
    return f"[success]{message}[/]"


def info(message: str) -> str:
    return f"[info]{message}[/]"


RICH_THEME = Theme(
    {
        "command": STYLE_CLI_COMMAND,
        "option": STYLE_CLI_OPTION,
        "value": STYLE_CLI_VALUE,
        "configopt": STYLE_CONFIG_OPTION,
        "success": Color.SUCCESS,
        "warning": f"bold {Color.WARNING}",
        "error": f"bold {Color.ERROR}",
        "info": Color.SUCCESS,
    }
)

####################
# Emojis
####################


EMOJI_YES = ":white_check_mark:"
EMOJI_NO = ":cross_mark:"


class Icon(StrEnum):
    DEBUG = "⚙"
    INFO = "!"
    OK = "✓"
    ERROR = "✗"
    PROMPT = "?"
    WARNING = "⚠"


# TODO: replace all use of constants with these enums
class Emoji(StrEnum):
    YES = EMOJI_YES
    NO = EMOJI_NO


def render_config_option(option: str) -> str:
    """Render a configuration file option/key/entry."""
    return f"[{STYLE_CONFIG_OPTION}]{option}[/]"


def render_cli_option(option: str) -> str:
    """Render a CLI option."""
    return f"[{STYLE_CLI_OPTION}]{option}[/]"


def render_cli_value(value: Any) -> str:
    """Render a CLI value/argument."""
    return f"[{STYLE_CLI_VALUE}]{value!r}[/]"


def render_cli_command(value: str) -> str:
    """Render a CLI command."""
    return f"[{STYLE_CLI_COMMAND}]{value}[/]"
