from __future__ import annotations

import itertools
from dataclasses import dataclass
from functools import cmp_to_key

from rich.text import Text

from .style import STYLE_CLI_COMMAND
from .style import STYLE_CLI_OPTION
from .style import STYLE_CLI_VALUE
from .style import STYLE_CONFIG_OPTION

CODEBLOCK_STYLES = [
    STYLE_CLI_OPTION,
    STYLE_CONFIG_OPTION,
    STYLE_CLI_VALUE,
    STYLE_CLI_COMMAND,
]


@dataclass
class MarkdownSpan:
    start: int
    end: int
    italic: bool = False
    bold: bool = False
    code: bool = False

    def to_symbols(self) -> tuple[MarkdownSymbol, MarkdownSymbol]:
        kwargs = {
            "italic": self.italic,
            "bold": self.bold,
            "code": self.code,
        }
        start = MarkdownSymbol(position=self.start, **kwargs)
        end = MarkdownSymbol(position=self.end, end=True, **kwargs)
        return start, end


@dataclass
class MarkdownSymbol:
    position: int
    italic: bool = False
    bold: bool = False
    code: bool = False
    end: bool = False

    @property
    def symbol(self) -> str:
        symbol = []
        if self.italic:
            symbol.append("*")
        if self.bold:
            symbol.append("**")
        if self.code:
            symbol.append("`")
        s = "".join(symbol)
        if self.end:
            s = f"{s[::-1]}"
        return s


# Easier than implementing rich comparison methods on MarkdownSymbol
def mdsymbol_cmp(a: MarkdownSymbol, b: MarkdownSymbol) -> int:
    if a.position < b.position:
        return -1
    elif a.position > b.position:
        return 1
    else:
        # code tags cannot have other tags inside them
        if a.code and not b.code:
            return 1
        if b.code and not a.code:
            return -1
    return 0


# TODO: rename `markup_to_markdown` to `markup_as_markdown`
# OR    rename `markup_to_plaintext` to `markup_as_plaintext`
#       I am partial to `x_to_y`.


def markup_to_markdown(s: str) -> str:
    """Parses a string that might contain markup formatting and converts it to Markdown.

    This is a very naive implementation that only supports a subset of Rich markup, but it's
    good enough for our purposes.
    """
    t = Text.from_markup(s)
    spans = []  # list[MarkdownSpan]
    # Markdown has more limited styles than Rich markup, so we just
    # identify the ones we care about and ignore the rest.
    for span in t.spans:
        new_span = MarkdownSpan(span.start, span.end)
        span_style = str(span.style)
        # Code block styles ignore other styles
        if span_style in CODEBLOCK_STYLES:
            new_span.code = True
        else:
            if "italic" in span_style:
                new_span.italic = True
            if "bold" in span_style:
                new_span.bold = True
        spans.append(new_span)

    # Convert MarkdownSpans to MarkdownSymbols
    # Each MarkdownSymbol represents a markdown formatting character along
    # with its position in the string.
    symbols = list(
        itertools.chain.from_iterable(sp.to_symbols() for sp in spans)
    )  # list[MarkdownSymbol]
    symbols = sorted(symbols, key=cmp_to_key(mdsymbol_cmp))

    # List of characters that make up string
    plaintext = list(str(t.plain))
    offset = 0
    for symbol in symbols:
        plaintext.insert(symbol.position + offset, symbol.symbol)
        offset += 1

    return "".join(plaintext)


def markup_as_plain_text(s: str) -> str:
    """Renders a string that might contain markup formatting as a plain text string."""
    return Text.from_markup(s).plain
