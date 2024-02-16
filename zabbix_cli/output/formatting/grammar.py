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
    >>> pluralize("apple", 1)
    '1 apple'
    >>> pluralize("apple", 2)
    '2 apples'
    >>> pluralize("category", 1)
    '1 category'
    >>> pluralize("category", 2)
    '2 categories'
    >>> pluralize("category", 0)
    '0 categories'
    >>> pluralize("category", 0, with_count=False)
    'categories'
    """
    if with_count:
        return f"{count} {_pluralize_word(word, count)}"
    return _pluralize_word(word, count)
