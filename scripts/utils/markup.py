from __future__ import annotations

import itertools
from dataclasses import dataclass
from functools import cmp_to_key

from rich.text import Text
from zabbix_cli.output.style import CodeBlockStyle
from zabbix_cli.output.style import CodeStyle

CODEBLOCK_STYLES = list(CodeBlockStyle)
CODE_STYLES = list(CodeStyle)
CODEBLOCK_LANGS = {
    "python": "py",
}


@dataclass
class MarkdownSpan:
    start: int
    end: int
    italic: bool = False
    bold: bool = False
    code: bool = False
    codeblock: bool = False
    language: str = ""

    def to_symbols(self) -> tuple[MarkdownSymbol, MarkdownSymbol]:
        start = MarkdownSymbol.from_span(self, end=False)
        end = MarkdownSymbol.from_span(self, end=True)
        return start, end


@dataclass
class MarkdownSymbol:
    position: int
    italic: bool = False
    bold: bool = False
    code: bool = False
    codeblock: bool = False
    end: bool = False
    language: str = ""

    @property
    def symbol(self) -> str:
        symbol: list[str] = []
        if self.codeblock:
            # Only insert language when opening codeblock
            lang = self.language if not self.end else ""
            symbol.append(f"```{lang}\n")
            # TODO: add support for language in fences (codeblock)
        else:
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

    @classmethod
    def from_span(cls, span: MarkdownSpan, *, end: bool = False) -> MarkdownSymbol:
        return cls(
            position=span.end if end else span.start,
            italic=span.italic,
            bold=span.bold,
            code=span.code,
            codeblock=span.codeblock,
            end=end,
            language=span.language,
        )


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
    t = Text.from_markup(normalize_spaces(s))
    spans: list[MarkdownSpan] = []
    # Markdown has more limited styles than Rich markup, so we just
    # identify the ones we care about and ignore the rest.
    for span in t.spans:
        new_span = MarkdownSpan(span.start, span.end)
        styles = str(span.style).lower().split(" ")
        # Code (block) styles ignore other styles
        if any(s in CODEBLOCK_STYLES for s in styles):
            new_span.codeblock = True
            lang = next((s for s in styles if s in CODEBLOCK_LANGS), "")
            new_span.language = CODEBLOCK_LANGS.get(lang, "")
        elif any(s in CODE_STYLES for s in styles):
            new_span.code = True
        else:
            if "italic" in styles:
                new_span.italic = True
            if "bold" in styles:
                new_span.bold = True
        spans.append(new_span)

    # Convert MarkdownSpans to MarkdownSymbols
    # Each MarkdownSymbol represents a markdown formatting character along
    # with its position in the string.
    symbols = list(itertools.chain.from_iterable(sp.to_symbols() for sp in spans))
    symbols = sorted(symbols, key=cmp_to_key(mdsymbol_cmp))

    # List of characters that make up string
    plaintext = list(str(t.plain.strip()))  # remove leading and trailing whitespace
    offset = 0
    for symbol in symbols:
        plaintext.insert(symbol.position + offset, symbol.symbol)
        offset += 1

    return "".join(plaintext)


def normalize_spaces(s: str) -> str:
    """Normalizes spaces in a string while keeping newlines intact."""
    split = filter(None, s.split(" "))
    parts: list[str] = []
    for part in split:
        if part.endswith("\n"):
            parts.append(part)
        else:
            parts.append(f"{part} ")
    return "".join(parts)


def markup_as_plain_text(s: str) -> str:
    """Renders a string that might contain markup formatting as a plain text string."""
    return Text.from_markup(s).plain
