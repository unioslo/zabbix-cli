# Rich markup styles for the CLI
from __future__ import annotations

from typing import Any

from rich.theme import Theme
from strenum import StrEnum
from typer.rich_utils import STYLE_OPTION

# NOTE: we define these enums to allow us to parse the markup text and
#       correctly convert it to markdown in the docs. Without this, we would
#       have to hard-code each style to correspond to a specific markdown formatting
#       in the docs generator, which would be error-prone and difficult to maintain.
#       E.g. [command]zabbix-cli hostgroup_remove foo[/] becomes `zabbix-cli hostgroup_remove foo`
#       while [example]zabbix-cli --version[/] becomes ```\nzabbix-cli --version\n``` (code block)


class CodeBlockStyle(StrEnum):
    """Names of styles for text representing code blocks.

    Displayed as a code block in markdown.
    """

    EXAMPLE = "example"
    """An example command."""

    # TODO: add language style here or as separate enum? if so, how to parse in docs?

    # NOTE: add "code" style here or in CodeStyle?


class CodeStyle(StrEnum):
    """Names of styles for text representing code, configuration or commands.

    Displayed as inline code-formatted text in markdown.
    """

    CONFIG_OPTION = "configopt"
    """Configuration file option/key/entry."""

    CLI_OPTION = "option"
    """CLI option, e.g. --verbose."""

    CLI_VALUE = "value"
    """CLI value, arg or metavar e.g. 'FILE'."""

    CLI_COMMAND = "command"
    """CLI command e.g. 'hostgroup_remove'."""

    CODE = "code"


class TextStyle(StrEnum):
    """Names of styles for non-code text"""

    WARNING = "warning"
    ERROR = "error"
    INFO = "info"
    SUCCESS = "success"


class TableStyle(StrEnum):
    """Names of styles for table headers, rows, etc."""

    HEADER = "table_header"


####################
# Colors
####################
# Colors should be used to colorize output and help define styles,
# but they should not contain any formatting (e.g. bold, italic, `x` on `y`, etc.)
####################


# TODO: refactor and define info, success, warning, error as STYLES, not COLORS.
#       Having multiple members with the same value is bad
class Color(StrEnum):
    INFO = "default"
    SUCCESS = "green"
    WARNING = "yellow"
    ERROR = "red"
    YELLOW = "yellow"
    GREEN = "green"
    RED = "red"
    MAGENTA = "magenta"
    CYAN = "cyan"
    BLUE = "blue"

    def __call__(self, message: str) -> str:
        return f"[{self.value}]{message}[/]"


# TODO: define primary, secondary, tertiary colors, then replace
#       green with primary, magenta with secondary, yellow with tertiary, etc.
RICH_THEME = Theme(
    {
        CodeBlockStyle.EXAMPLE.value: "bold green",
        CodeStyle.CLI_COMMAND.value: "bold green",
        CodeStyle.CLI_OPTION.value: STYLE_OPTION,
        CodeStyle.CLI_VALUE.value: "bold magenta",
        CodeStyle.CONFIG_OPTION.value: "italic yellow",
        CodeStyle.CODE.value: "bold green",
        TextStyle.SUCCESS.value: Color.SUCCESS,
        TextStyle.WARNING.value: f"bold {Color.WARNING}",
        TextStyle.ERROR.value: f"bold {Color.ERROR}",
        TextStyle.INFO.value: Color.SUCCESS,
        TableStyle.HEADER.value: "bold green",
    }
)

# NOTE: this seems a bit TOO decoupled? Would be nice if we could define
# styles as a combination of style name + style value.
# That would require rewriting parts of the docs utils for parsing Rich
# markup to markdown.


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

    @classmethod
    def fmt_bool(cls, value: bool) -> str:
        return success(cls.YES) if value else error(cls.NO)


def render_config_option(option: str) -> str:
    """Render a configuration file option/key/entry."""
    return f"[{CodeStyle.CONFIG_OPTION}]{option}[/]"


def render_cli_option(option: str) -> str:
    """Render a CLI option."""
    return f"[{CodeStyle.CLI_OPTION}]{option}[/]"


def render_cli_value(value: Any) -> str:
    """Render a CLI value/argument."""
    return f"[{CodeStyle.CLI_VALUE}]{value!r}[/]"


def render_cli_command(value: str) -> str:
    """Render a CLI command."""
    return f"[{CodeStyle.CLI_COMMAND}]{value}[/]"
