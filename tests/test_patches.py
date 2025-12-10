from __future__ import annotations

import copy
import sys
from typing import Any
from typing import Callable

import pytest
import typer
import typer.rich_utils
from inline_snapshot import snapshot
from rich.color import Color
from rich.color import ColorType
from rich.console import Console
from rich.segment import Segment
from rich.style import Style
from typer.models import ParameterInfo
from zabbix_cli._patches import typer as typ
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.pyzabbix.enums import APIStr
from zabbix_cli.pyzabbix.enums import APIStrEnum


def test_typer_patches_idempotent() -> None:
    # patch() runs all patching functions
    typ.patch()

    # Run each patching function again to ensure no errors are raised
    # very primitive test, but ensures that we can call it as many times
    # as we want without any obvious errors.
    typ.patch__get_rich_console()
    typ.patch_generate_enum_convertor()
    typ.patch_get_click_type()
    typ.patch_help_text_spacing()
    typ.patch_help_text_style()


def test_patch__get_rich_console(
    capsys: pytest.CaptureFixture, force_color: Any
) -> None:
    original = copy.deepcopy(typer.rich_utils._get_rich_console)
    typ.patch__get_rich_console()
    new = typer.rich_utils._get_rich_console
    assert original != new

    original_val = original()
    new_val = new()
    assert original_val != new_val

    assert isinstance(original_val, Console)
    assert isinstance(new_val, Console)

    # Test some styles
    to_render = "[option]foo[/] [metavar]bar[/]"
    rendered = new_val.render(to_render)
    assert list(rendered) == snapshot(
        [
            Segment(
                text="foo",
                style=Style(
                    color=Color("cyan", ColorType.STANDARD, number=6), bold=True
                ),
            ),
            Segment(text=" ", style=Style()),
            Segment(
                text="bar",
                style=Style(
                    color=Color("yellow", ColorType.STANDARD, number=3), bold=True
                ),
            ),
            Segment(text="\n"),
        ]
    )

    # Flush capture buffer
    capsys.readouterr()
    new_val.print(to_render)
    assert capsys.readouterr().out == snapshot(
        "\x1b[1;36mfoo\x1b[0m \x1b[1;33mbar\x1b[0m\n"
    )


def _do_patch_generate_enum_convertor() -> Callable[[Any], Any]:
    original = copy.deepcopy(typer.main.generate_enum_convertor)
    typ.patch_generate_enum_convertor()
    new = typer.main.generate_enum_convertor
    assert original != new
    return new


def test_patch_generate_enum_convertor_apistrenum() -> None:
    generate_converter = _do_patch_generate_enum_convertor()

    # Test that the new convertor can handle APIStrEnum
    class APIEnum(APIStrEnum):
        FOO = APIStr("foo", 0)
        BAR = APIStr("bar", 1)

    converter = generate_converter(APIEnum)
    assert converter("foo") == APIEnum.FOO
    assert converter("bar") == APIEnum.BAR
    assert converter(0) == APIEnum.FOO
    assert converter(1) == APIEnum.BAR
    assert converter("0") == APIEnum.FOO
    assert converter("1") == APIEnum.BAR
    assert converter(APIEnum.FOO) == APIEnum.FOO
    assert converter(APIEnum.BAR) == APIEnum.BAR

    with pytest.raises(ZabbixCLIError):
        assert converter("baz")
    with pytest.raises(ZabbixCLIError):
        assert converter(2)
    with pytest.raises(ZabbixCLIError):
        assert converter("2")


def test_patch_generate_enum_convertor_strenum_lib() -> None:
    """Test patched converter with StrEnum from strenum library."""
    from strenum import StrEnum

    generate_converter = _do_patch_generate_enum_convertor()

    class TestEnum(StrEnum):
        FOO = "foo"
        BAR = "bar"

    converter = generate_converter(TestEnum)
    assert converter("foo") == TestEnum.FOO
    assert converter("bar") == TestEnum.BAR
    assert converter("FOO") == TestEnum.FOO
    assert converter("BAR") == TestEnum.BAR
    assert converter(TestEnum.FOO) == TestEnum.FOO
    assert converter(TestEnum.BAR) == TestEnum.BAR


@pytest.mark.skipif(sys.version_info < (3, 11), reason="Requires Python 3.11+")
def test_patch_generate_enum_convertor_strenum_stdlib() -> None:
    from enum import StrEnum

    generate_converter = _do_patch_generate_enum_convertor()

    class TestEnum(StrEnum):
        FOO = "foo"
        BAR = "bar"

    converter = generate_converter(TestEnum)
    assert converter("foo") == TestEnum.FOO
    assert converter("bar") == TestEnum.BAR
    assert converter("FOO") == TestEnum.FOO
    assert converter("BAR") == TestEnum.BAR
    assert converter(TestEnum.FOO) == TestEnum.FOO
    assert converter(TestEnum.BAR) == TestEnum.BAR


def test_patch_get_click_type() -> None:
    original = copy.deepcopy(typer.main.get_click_type)
    typ.patch_get_click_type()
    new = typer.main.get_click_type
    assert original != new

    class APIEnum(APIStrEnum):
        FOO = APIStr("foo", 0)
        BAR = APIStr("bar", 1)

    assert new(
        annotation=APIEnum, parameter_info=ParameterInfo()
    ).to_info_dict() == snapshot(
        {
            "param_type": "Choice",
            "name": "choice",
            "choices": ["foo", "bar", "0", "1"],
            "case_sensitive": True,
        }
    )

    assert new(
        annotation=APIEnum, parameter_info=ParameterInfo(case_sensitive=False)
    ).to_info_dict() == snapshot(
        {
            "param_type": "Choice",
            "name": "choice",
            "choices": ["foo", "bar", "0", "1"],
            "case_sensitive": False,
        }
    )


def test_patch_help_text_spacing(ctx: typer.Context) -> None:
    original = copy.deepcopy(typer.rich_utils._get_help_text)
    typ.patch_help_text_spacing()
    new = typer.rich_utils._get_help_text
    assert original != new

    ctx.command.help = "This is the first line.\n\nThis is the last line."
    help_text = new(obj=ctx.command, markup_mode="rich")
    console = typer.rich_utils._get_rich_console()
    assert list(console.render(help_text)) == snapshot(
        [
            Segment(text="This is the first line."),
            Segment(text="\n"),
            Segment(text=""),
            Segment(text="\n"),
            Segment(text="This is the last line."),
            Segment(text="\n"),
        ]
    )


def test_patch_help_text_style() -> None:
    # No in-depth testing here - just ensure that the function
    # sets the style we expect.
    # test_patch_help_text_spacing() tests the actual rendering.
    typ.patch_help_text_style()
    style = typer.rich_utils.STYLE_HELPTEXT
    assert style != "dim"
    assert style == snapshot("")
