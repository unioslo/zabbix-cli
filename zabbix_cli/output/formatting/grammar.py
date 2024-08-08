from __future__ import annotations


def _pluralize_word(word: str, count: int) -> str:
    if count == 1:
        return word
    if word.endswith("y"):
        return word[:-1] + "ies"
    return word + "s"


def pluralize(word: str, count: int, with_count: bool = True) -> str:
    """Pluralize a word based on a count.

    Examples:
    >>> from zabbix_cli.output.formatting.grammar import pluralize as p
    >>> p("apple", 1)
    '1 apple'
    >>> p("apple", 2)
    '2 apples'
    >>> p("category", 1)
    '1 category'
    >>> p("category", 2)
    '2 categories'
    >>> p("category", 0)
    '0 categories'
    >>> p("category", 0, with_count=False) # see pluralize_no_count
    'categories'
    """
    if with_count:
        return f"{count} {_pluralize_word(word, count)}"
    return _pluralize_word(word, count)


def pluralize_no_count(word: str, count: int) -> str:
    """Pluralize a word without a count prepended to the pluralized word.

    Shortcut for `pluralize(word, count, with_count=False)`.

    Examples:
    >>> from zabbix_cli.output.formatting.grammar import pluralize_no_count as pnc
    >>> pnc("apple", 1)
    'apple'
    >>> pnc("apple", 2)
    'apples'
    >>> pnc("category", 1)
    'category'
    >>> pnc("category", 2)
    'categories'
    """
    return _pluralize_word(word, count)
