from __future__ import annotations

import json
from contextlib import nullcontext
from typing import Any

import typer
from pydantic import BaseModel

from ..config import OutputFormat
from .console import console
from .console import success
from zabbix_cli.models import AggregateResult
from zabbix_cli.models import Result
from zabbix_cli.models import TableRenderable
from zabbix_cli.models import TableRenderableDict
from zabbix_cli.models import TableRenderableProto
from zabbix_cli.state import get_state


def wrap_result(result: BaseModel) -> Result:
    """Wraps a BaseModel instance in a Result object so that it receives
    `return_code`, `errors`, and `message` fields, with the original object
    is available as `result`.

    Does nothing if the function argument is already a Result object."""
    if isinstance(result, Result):
        return result
    # TODO: handle AggregateResult?
    return Result(result=result)


def render_result(
    result: TableRenderable | TableRenderableDict,
    ctx: typer.Context | None = None,
    **kwargs: Any,
) -> None:
    """Render the result of a command stdout or file.

    Parameters
    ----------
    result: TableRenderable | TableRenderableDict,
        The result of a command. All commands produce a TableRenderable (BaseModel)
        or a TableRenderableDict (RootModel).
        Both of these types implement the `TableRenderableProto` protocol.
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
            if state.config.app.legacy_json_format:
                render_json_legacy(result, ctx, **kwargs)
            else:
                render_json(result, ctx, **kwargs)
        elif fmt == OutputFormat.TABLE:
            render_table(result, ctx, **kwargs)
        # TODO: implement CSV
        else:
            raise ValueError(f"Unknown output format {fmt!r}.")


def render_table(
    result: TableRenderableProto, ctx: typer.Context | None = None, **kwargs: Any
) -> None:
    """Render the result of a command as a table if possible.
    If result contains a message, print success message instead.
    """
    if isinstance(result, Result) and result.message:
        success(result.message)
    else:
        tbl = result.as_table()
        if not tbl.rows:
            console.print("No results found.")
        else:
            console.print(tbl)


def render_json(
    result: TableRenderable | TableRenderableDict,
    ctx: typer.Context | None = None,
    **kwargs: Any,
) -> None:
    """Render the result of a command as JSON."""
    result = wrap_result(result)
    o_json = result.model_dump_json(indent=2)
    console.print_json(o_json, indent=2, sort_keys=False)


def render_json_legacy(
    result: TableRenderable | TableRenderableDict,
    ctx: typer.Context | None = None,
    **kwargs: Any,
) -> None:
    """Render the result of a command as JSON (legacy V2 format).

    Result is always a dict with numeric string keys.

    NOTE
    ----

    This function is very hacky, and will inevitably contain a number of band-aid
    fixes to enable 1:1 compatibility with the legacy V2 JSON format.
    We should try to move away from this format ASAP, so we can remove
    this function and all its hacks.
    """
    # If we have a message, it should not be indexed
    # NOTE: do we have a more accurate heuristic for this?
    if isinstance(result, Result) and result.message:
        j = result.model_dump_json(indent=2)
    else:
        jdict = {}  # type: dict[str, Any] # always a dict in legacy mode
        res = result.model_dump(mode="json")
        if isinstance(result, AggregateResult):
            py_result = res.get("result", [])  # type: ignore # bad annotation
        else:
            py_result = [res]

        for idx, item in enumerate(py_result):
            jdict[str(idx)] = item
        j = json.dumps(jdict, indent=2)
    console.print_json(j, indent=2, sort_keys=False)
