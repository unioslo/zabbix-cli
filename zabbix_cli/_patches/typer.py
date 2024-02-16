"""Monkeypatches Typer to extend certain functionality and change the
styling of its output.

Will probably break for some version of Typer at some point."""
from __future__ import annotations

import inspect
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from typing import Callable
from typing import cast
from typing import Iterable
from typing import Type
from typing import Union
from uuid import UUID

import click
import typer
from typer.main import lenient_issubclass
from typer.models import ParameterInfo

from zabbix_cli._patches.common import get_patcher
from zabbix_cli.pyzabbix.enums import APIStrEnum

patcher = get_patcher(f"Typer version: {typer.__version__}")


# class patch(BasePatcher):
#     """Context manager that logs and prints diagnostic info if an exception
#     occurs."""

#     def __package_info__(self) -> str:
#         return f"Typer version: {typer.__version__}"

# def __init__(self, description: str) -> None:
#     self.description = description

# def __enter__(self) -> patch:
#     return self

# def __exit__(
#     self,
#     exc_type: Optional[Type[BaseException]],
#     exc_val: Optional[BaseException],
#     exc_tb: Optional[TracebackType],
# ) -> bool:
#     if not exc_type:
#         return True
#     import rich
#     import sys

#     # Rudimentary, but provides enough info to debug and fix the issue
#     console = rich.console.Console(stderr=True)
#     console.print_exception()
#     console.print(f"[bold red]Failed to patch [i]{self.description}[/][/]")
#     console.print(f"Typer version: {typer.__version__}")
#     console.print(f"Python version: {sys.version}")

#     return True


def patch_help_text_style() -> None:
    """Remove dimming of help text.

    https://github.com/tiangolo/typer/issues/437#issuecomment-1224149402
    """
    with patcher("typer.rich_utils.STYLE_HELPTEXT"):
        typer.rich_utils.STYLE_HELPTEXT = ""


def patch_help_text_spacing() -> None:
    """Adds a single blank line between short and long help text of a command
    when using `--help`.

    As of Typer 0.9.0, the short and long help text is printed without any
    blank lines between them. This is bad for readability (IMO).
    """
    from rich.console import group
    from rich.markdown import Markdown
    from rich.text import Text
    from typer.rich_utils import MarkupMode
    from typer.rich_utils import DEPRECATED_STRING
    from typer.rich_utils import STYLE_DEPRECATED
    from typer.rich_utils import STYLE_HELPTEXT_FIRST_LINE
    from typer.rich_utils import MARKUP_MODE_RICH
    from typer.rich_utils import MARKUP_MODE_MARKDOWN
    from typer.rich_utils import STYLE_HELPTEXT
    from typer.rich_utils import _make_rich_rext

    @group()
    def _get_help_text(
        *,
        obj: Union[click.Command, click.Group],
        markup_mode: MarkupMode,
    ) -> Iterable[Union[Markdown, Text]]:
        """Build primary help text for a click command or group.

        Returns the prose help text for a command or group, rendered either as a
        Rich Text object or as Markdown.
        If the command is marked as deprecated, the deprecated string will be prepended.
        """
        # Prepend deprecated status
        if obj.deprecated:
            yield Text(DEPRECATED_STRING, style=STYLE_DEPRECATED)

        # Fetch and dedent the help text
        help_text = inspect.cleandoc(obj.help or "")

        # Trim off anything that comes after \f on its own line
        help_text = help_text.partition("\f")[0]

        # Get the first paragraph
        first_line = help_text.split("\n\n")[0]
        # Remove single linebreaks
        if markup_mode != MARKUP_MODE_MARKDOWN and not first_line.startswith("\b"):
            first_line = first_line.replace("\n", " ")
        yield _make_rich_rext(
            text=first_line.strip(),
            style=STYLE_HELPTEXT_FIRST_LINE,
            markup_mode=markup_mode,
        )

        # Get remaining lines, remove single line breaks and format as dim
        remaining_paragraphs = help_text.split("\n\n")[1:]
        if remaining_paragraphs:
            if markup_mode != MARKUP_MODE_RICH:
                # Remove single linebreaks
                remaining_paragraphs = [
                    x.replace("\n", " ").strip()
                    if not x.startswith("\b")
                    else "{}\n".format(x.strip("\b\n"))
                    for x in remaining_paragraphs
                ]
                # Join back together
                remaining_lines = "\n".join(remaining_paragraphs)
            else:
                # Join with double linebreaks if markdown
                remaining_lines = "\n\n".join(remaining_paragraphs)
            yield _make_rich_rext(
                text="\n",
                style=STYLE_HELPTEXT,
                markup_mode=markup_mode,
            )
            yield _make_rich_rext(
                text=remaining_lines,
                style=STYLE_HELPTEXT,
                markup_mode=markup_mode,
            )

    with patcher("typer.rich_utils._get_help_text"):
        typer.rich_utils._get_help_text = _get_help_text


def patch_generate_enum_convertor() -> None:
    """Patches enum value converter with an additional fallback to
    instantiating the enum with the value directly."""

    def generate_enum_convertor(enum: Type[Enum]) -> Callable[[Any], Any]:
        lower_val_map = {str(val.value).lower(): val for val in enum}

        def convertor(value: Any) -> Any:
            if value is not None:
                low = str(value).lower()
                if low in lower_val_map:
                    key = lower_val_map[low]
                    return enum(key)
                # Fall back to passing in the value as-is
                try:
                    return enum(value)
                except ValueError:
                    return None

        return convertor

    with patcher("typer.main.generate_enum_convertor"):
        typer.main.generate_enum_convertor = generate_enum_convertor


def patch_get_click_type() -> None:
    """Adds support for our custom `APIStrEnum` type.

    Used in conjunction with our custom generate_enum_convertor to support
    instantiating `APIStrEnum` with both the human-readable value and the API value
    (e.g. `"Enabled"` and `0`).

    Uses the `APIStrEnum.all_choices()` method to get the list of choices."""

    def get_click_type(
        *, annotation: Any, parameter_info: ParameterInfo
    ) -> click.ParamType:
        if parameter_info.click_type is not None:
            return parameter_info.click_type

        elif parameter_info.parser is not None:
            return click.types.FuncParamType(parameter_info.parser)

        elif annotation == str:
            return click.STRING
        elif annotation == int:
            if parameter_info.min is not None or parameter_info.max is not None:
                min_ = None
                max_ = None
                if parameter_info.min is not None:
                    min_ = int(parameter_info.min)
                if parameter_info.max is not None:
                    max_ = int(parameter_info.max)
                return click.IntRange(min=min_, max=max_, clamp=parameter_info.clamp)
            else:
                return click.INT
        elif annotation == float:
            if parameter_info.min is not None or parameter_info.max is not None:
                return click.FloatRange(
                    min=parameter_info.min,
                    max=parameter_info.max,
                    clamp=parameter_info.clamp,
                )
            else:
                return click.FLOAT
        elif annotation == bool:
            return click.BOOL
        elif annotation == UUID:
            return click.UUID
        elif annotation == datetime:
            return click.DateTime(formats=parameter_info.formats)
        elif (
            annotation == Path
            or parameter_info.allow_dash
            or parameter_info.path_type
            or parameter_info.resolve_path
        ):
            return click.Path(
                exists=parameter_info.exists,
                file_okay=parameter_info.file_okay,
                dir_okay=parameter_info.dir_okay,
                writable=parameter_info.writable,
                readable=parameter_info.readable,
                resolve_path=parameter_info.resolve_path,
                allow_dash=parameter_info.allow_dash,
                path_type=parameter_info.path_type,
            )
        elif lenient_issubclass(annotation, typer.FileTextWrite):
            return click.File(
                mode=parameter_info.mode or "w",
                encoding=parameter_info.encoding,
                errors=parameter_info.errors,
                lazy=parameter_info.lazy,
                atomic=parameter_info.atomic,
            )
        elif lenient_issubclass(annotation, typer.FileText):
            return click.File(
                mode=parameter_info.mode or "r",
                encoding=parameter_info.encoding,
                errors=parameter_info.errors,
                lazy=parameter_info.lazy,
                atomic=parameter_info.atomic,
            )
        elif lenient_issubclass(annotation, typer.FileBinaryRead):
            return click.File(
                mode=parameter_info.mode or "rb",
                encoding=parameter_info.encoding,
                errors=parameter_info.errors,
                lazy=parameter_info.lazy,
                atomic=parameter_info.atomic,
            )
        elif lenient_issubclass(annotation, typer.FileBinaryWrite):
            return click.File(
                mode=parameter_info.mode or "wb",
                encoding=parameter_info.encoding,
                errors=parameter_info.errors,
                lazy=parameter_info.lazy,
                atomic=parameter_info.atomic,
            )
        # our patch for APIStrEnum
        elif lenient_issubclass(annotation, APIStrEnum):
            annotation = cast(Type[APIStrEnum], annotation)
            return click.Choice(
                annotation.all_choices(),
                case_sensitive=parameter_info.case_sensitive,
            )
        elif lenient_issubclass(annotation, Enum):
            return click.Choice(
                [item.value for item in annotation],
                case_sensitive=parameter_info.case_sensitive,
            )
        raise RuntimeError(f"Type not yet supported: {annotation}")  # pragma no cover

    """Patch typer's get_click_type to support more types."""
    with patcher("typer.main.get_click_type"):
        typer.main.get_click_type = get_click_type


def patch() -> None:
    """Apply all patches."""
    patch_help_text_style()
    patch_help_text_spacing()
    patch_generate_enum_convertor()
    patch_get_click_type()
