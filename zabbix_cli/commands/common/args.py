from __future__ import annotations

from typing import Any
from typing import Optional

import typer


def get_limit_option(
    limit: Optional[int] = 0,
    resource: str = "results",
    long_option: str = "--limit",
    short_option: str = "-n",
) -> Any:  # TODO: Can we type this better?
    """Limit option factory."""
    return typer.Option(
        limit,
        long_option,
        short_option,
        help=f"Limit the number of {resource}. 0 to show all.",
    )


OPTION_LIMIT = get_limit_option(0)
