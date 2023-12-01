from __future__ import annotations

from contextlib import nullcontext
from typing import Any
from typing import Sequence

import typer

from ..config import OutputFormat
from .console import console
from .console import info
from zabbix_cli.models import ResultType
from zabbix_cli.state import get_state


def render_result(
    result: ResultType, ctx: typer.Context | None = None, **kwargs: Any
) -> None:
    """Render the result of a command stdout or file.

    Parameters
    ----------
    result : ResultType
        The result of a command.
    ctx : typer.Context, optional
        The typer context from the command invocation, by default None
    **kwargs
        Additional keyword arguments to pass to the render function.
    """
    # Short form aliases
    state = get_state()
    fmt = state.config.app.output_format
    # paging = state.config.output.paging
    paging = False  # TODO: implement

    ctx_manager = console.pager() if paging else nullcontext()
    with ctx_manager:  # type: ignore # not quite sure why mypy is complaining here
        if fmt == OutputFormat.JSON:
            render_json(result, ctx, **kwargs)
        elif fmt == OutputFormat.TABLE:
            render_table(result, ctx, **kwargs)
        else:
            raise ValueError(f"Unknown output format {fmt!r}.")


def render_table(
    result: ResultType, ctx: typer.Context | None = None, **kwargs: Any
) -> None:
    """Render the result of a command as a table."""

    def print_item(item: ResultType) -> None:
        """Prints a harbor base model as a table (optionally with description),
        if it is a harborapi BaseModel, otherwise just prints the item."""
        if item.message:
            info(item.message)
        else:
            console.print(item.as_table())

    if isinstance(result, Sequence) and not isinstance(result, str):
        for item in result:
            print_item(item)
    else:
        print_item(result)


def render_json(
    result: ResultType, ctx: typer.Context | None = None, **kwargs: Any
) -> None:
    """Render the result of a command as JSON."""
    o_json = result.model_dump_json(indent=2)
    console.print_json(o_json, indent=2, sort_keys=False)
