from __future__ import annotations

from datetime import datetime

from ...logs import logger
from .constants import NONE_STR


def datetime_str(
    d: datetime | int | float | None, with_time: bool = True, subsecond: bool = False
) -> str:
    """Formats an optional datetime object as as a string.

    Parameters
    ----------
    d : datetime | None
        The datetime object to format.
    with_time : bool, optional
        Whether to include the time in the formatted string, by default True
    subsecond : bool, optional
        Whether to include subsecond precision in the formatted string, by default False
        Has no effect if `with_time` is False.
    """
    if d is None:
        return NONE_STR
    if isinstance(d, (int, float)):
        try:
            d = datetime.fromtimestamp(d)
        except (ValueError, OSError) as e:  # OSError if timestamp is out of range
            if isinstance(e, OSError):
                logger.error("Timestamp out of range: %s", d)
            return NONE_STR
    fmt = "%Y-%m-%d"
    if with_time:
        fmt = f"{fmt} %H:%M:%S"
        if subsecond:
            fmt = f"{fmt}.%f"
    return d.strftime(fmt)
