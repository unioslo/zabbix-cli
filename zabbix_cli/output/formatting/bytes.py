from __future__ import annotations

from pydantic import ByteSize

from .constants import NONE_STR


def bytesize_str(b: int | None, decimal: bool = False) -> str:
    if b is None or b < 0:
        return NONE_STR
    return ByteSize(b).human_readable(decimal=decimal)
