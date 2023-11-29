# Rich markup styles for the CLI
from __future__ import annotations

from typing import Any

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
STYLE_COMMAND = "bold italic green"
STYLE_WARNING = "yellow"


EMOJI_YES = ":white_check_mark:"
EMOJI_NO = ":cross_mark:"

####################
# Colors
####################
# Colors should be used to colorize output and help define styles,
# but they should not contain any formatting (e.g. bold, italic, `x` on `y`, etc.)
####################


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


def render_warning(msg: str) -> str:
    return f"[{STYLE_WARNING}]WARNING: {msg}[/]"


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
