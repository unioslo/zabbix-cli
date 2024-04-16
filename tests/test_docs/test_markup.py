from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str((Path(__file__) / "../../../docs").resolve()))


# Skip entire test if not found
markup = pytest.importorskip("docs.scripts.utils.markup")
MarkdownSymbol = markup.MarkdownSymbol  # type: ignore


@pytest.mark.parametrize(
    "inp, expect",
    [
        (
            MarkdownSymbol(
                position=0,
                italic=True,
                bold=False,
                code=False,
                codeblock=False,
                end=False,
            ),
            "*",
        ),
        (
            MarkdownSymbol(
                position=0,
                italic=False,
                bold=True,
                code=False,
                codeblock=False,
                end=False,
            ),
            "**",
        ),
        (
            MarkdownSymbol(
                position=0,
                italic=False,
                bold=False,
                code=True,
                codeblock=False,
                end=False,
            ),
            "`",
        ),
        (
            MarkdownSymbol(
                position=0,
                italic=False,
                bold=False,
                code=False,
                codeblock=True,
                end=False,
            ),
            "```\n",
        ),
        (
            MarkdownSymbol(
                position=0,
                italic=True,
                bold=True,
                code=False,
                codeblock=False,
                end=False,
            ),
            "***",
        ),
        (
            MarkdownSymbol(
                position=0,
                italic=True,
                bold=False,
                code=True,
                codeblock=False,
                end=False,
            ),
            "*`",
        ),
        (
            MarkdownSymbol(
                position=0,
                italic=True,
                bold=False,
                code=False,
                codeblock=True,
                end=False,
            ),
            "```\n",
        ),
        (
            MarkdownSymbol(
                position=0,
                italic=False,
                bold=True,
                code=True,
                codeblock=False,
                end=False,
            ),
            "**`",
        ),
        (
            MarkdownSymbol(
                position=0,
                italic=False,
                bold=True,
                code=False,
                codeblock=True,
                end=False,
            ),
            "```\n",
        ),
        (
            MarkdownSymbol(
                position=0,
                italic=False,
                bold=False,
                code=True,
                codeblock=True,
                end=False,
            ),
            "```\n",
        ),
        (
            MarkdownSymbol(
                position=0,
                italic=True,
                bold=True,
                code=True,
                codeblock=False,
                end=False,
            ),
            "***`",
        ),
        (
            MarkdownSymbol(
                position=0,
                italic=True,
                bold=True,
                code=False,
                codeblock=True,
                end=False,
            ),
            "```\n",
        ),
        (
            MarkdownSymbol(
                position=0, italic=True, bold=True, code=True, codeblock=True, end=False
            ),
            "```\n",
        ),
    ],
)
def test_markdownsymbol_symbol(
    inp: MarkdownSymbol,  # type: ignore
    expect: str,
) -> None:
    assert inp.symbol == expect  # type: ignore


@pytest.mark.parametrize(
    "inp,expect",
    [
        pytest.param(
            "[example]zabbix-cli --version[/]",
            "```\nzabbix-cli --version\n```",
            id="Example (short end)",
        ),
        pytest.param(
            "[example]zabbix-cli --version[/example]",
            "```\nzabbix-cli --version\n```",  # Same result as above
            id="Example (explicit end style)",
        ),
        pytest.param(
            "[bold example]zabbix-cli --version[/bold example]",
            "```\nzabbix-cli --version\n```",  # Ignoring bold
            id="Example + bold",
        ),
        pytest.param(
            "[example python]zabbix-cli --version[/example python]",
            "```py\nzabbix-cli --version\n```",  # Adding language
            id="Example with language",
        ),
        pytest.param(
            "     [example]zabbix-cli --version[/example]",
            "```\nzabbix-cli --version\n```",  # Ignoring leading spaces
            id="Leading spaces outside style",
        ),
        pytest.param(
            "[example]      zabbix-cli --version[/example]",
            "```\nzabbix-cli --version\n```",  # Ignoring leading spaces inside
            id="Leading spaces inside style",
        ),
    ],
)
def test_markup_to_markdown(inp: str, expect: str) -> None:
    assert markup.markup_to_markdown(inp) == expect  # type: ignore


@pytest.mark.parametrize(
    "style",
    markup.CODE_STYLES,
)
def test_markup_to_markdown_code_styles(style: str) -> None:
    expect = "`--version`"
    assert markup.markup_to_markdown(f"[{style}]--version[/]") == expect  # type: ignore

    # Adding bold or italic doesnt change anything
    # code takes precedence
    assert markup.markup_to_markdown(f"[bold {style}]--version[/]") == expect
    assert markup.markup_to_markdown(f"[italic {style}]--version[/]") == expect
    assert markup.markup_to_markdown(f"[bold italic {style}]--version[/]") == expect


@pytest.mark.parametrize(
    "style",
    markup.CODEBLOCK_STYLES,
)
def test_markup_to_markdown_codeblock_styles(style: str) -> None:
    text = "zabbix-cli remove_hostgroup foo"
    expect = f"```\n{text}\n```"
    assert markup.markup_to_markdown(f"[{style}]{text}[/]") == expect  # type: ignore

    # Adding bold or italic doesnt change anything
    # code takes precedence
    assert markup.markup_to_markdown(f"[italic {style}]{text}[/]") == expect
    assert markup.markup_to_markdown(f"[bold {style}]{text}[/]") == expect
    assert markup.markup_to_markdown(f"[bold {style} italic]{text}[/]") == expect


# TODO: test the example spans of all commands and ensure they render as codeblocks
