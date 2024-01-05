"""Patches and extensions to typer.

Typer is inflexible in some ways, so we patch it to make it more suitable
for our use cases."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from types import TracebackType
from typing import Any
from typing import Callable
from typing import cast
from typing import Optional
from typing import Type
from uuid import UUID

import click
import typer
from typer.main import lenient_issubclass
from typer.models import ParameterInfo

from zabbix_cli.utils.args import APIStrEnum


class patch:
    def __init__(self, description: str) -> None:
        self.description = description

    def __enter__(self) -> patch:
        print("Patching", self.description, "...")
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:
        if not exc_type:
            return True
        import rich
        import sys

        # Rudimentary, but provides enough info to debug and fix the issue
        console = rich.console.Console(stderr=True)
        console.print_exception()
        console.print(f"[bold red]Failed to patch [i]{self.description}[/][/]")
        console.print(f"Typer version: {typer.__version__}")
        console.print(f"Python version: {sys.version}")

        return True


def patch_help_text() -> None:
    """Remove dimming of help text.

    https://github.com/tiangolo/typer/issues/437#issuecomment-1224149402
    """
    with patch("typer.rich_utils.STYLE_HELPTEXT"):
        typer.rich_utils.STYLE_HELPTEXT = ""


def patch_generate_enum_convertor() -> None:
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

    with patch("typer.main.generate_enum_convertor"):
        typer.main.generate_enum_convertor = generate_enum_convertor


def patch_get_click_type() -> None:
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
    with patch("typer.main.get_click_type"):
        typer.main.get_click_type = get_click_type


def patch_all() -> None:
    """Patch all typer issues."""
    patch_help_text()
    patch_generate_enum_convertor()
    patch_get_click_type()
