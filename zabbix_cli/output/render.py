from __future__ import annotations

import json
from contextlib import nullcontext
from typing import TYPE_CHECKING
from typing import Any

import typer

from zabbix_cli.output.console import console
from zabbix_cli.output.console import error
from zabbix_cli.output.console import success
from zabbix_cli.state import get_state

if TYPE_CHECKING:
    from pydantic import BaseModel

    from zabbix_cli.models import BaseResult
    from zabbix_cli.models import TableRenderable


def wrap_result(result: BaseModel) -> BaseResult:
    """Wraps a BaseModel instance in a Result object so that it receives
    `return_code`, `errors`, and `message` fields, with the original object
    is available as `result`.

    Does nothing if the function argument is already a BaseResult instance.
    """
    from zabbix_cli.models import BaseResult
    from zabbix_cli.models import Result

    if isinstance(result, BaseResult):
        return result
    # TODO: handle AggregateResult? (8 months later: What did I mean by this?)
    return Result(result=result)


def render_result(
    result: TableRenderable,
    ctx: typer.Context | None = None,
    **kwargs: Any,
) -> None:
    """Render the result of a command stdout or file.

    Parameters
    ----------
    result: TableRenderable,
        The result of a command. All commands produce a TableRenderable (BaseModel).
    ctx : typer.Context, optional
        The typer context from the command invocation, by default None
    **kwargs
        Additional keyword arguments to pass to the render function.
    """
    from zabbix_cli.config.constants import OutputFormat

    # Short form aliases
    state = get_state()
    fmt = state.config.app.output.format
    # paging = state.config.output.paging
    paging = False  # TODO: implement

    ctx_manager = console.pager() if paging else nullcontext()
    with ctx_manager:
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
    result: TableRenderable, ctx: typer.Context | None = None, **kwargs: Any
) -> None:
    """Render the result of a command as a table if possible.
    If result contains a message, print success message instead.
    """
    # TODO: be able to print message _AND_ table
    # The Result/TableRenderable dichotomy is a bit of a mess
    from zabbix_cli.models import Result
    from zabbix_cli.models import ReturnCode

    if isinstance(result, Result) and result.message:
        if result.return_code == ReturnCode.ERROR:
            error(result.message)
        else:
            success(result.message)
    else:
        tbl = result.as_table()
        if not tbl.rows:
            if not result.empty_ok:
                console.print("No results found.")
        else:
            console.print(tbl)


def render_json(
    result: TableRenderable,
    ctx: typer.Context | None = None,
    **kwargs: Any,
) -> None:
    """Render the result of a command as JSON."""
    from zabbix_cli.models import ReturnCode

    result = wrap_result(result)
    o_json = result.model_dump_json(indent=2, by_alias=True)
    console.print_json(o_json, indent=2, sort_keys=False)
    if result.message:
        if result.return_code == ReturnCode.ERROR:
            error(result.message)
        else:
            success(result.message)


def render_json_legacy(
    result: TableRenderable,
    ctx: typer.Context | None = None,
    **kwargs: Any,
) -> None:
    """Render the result of a command as JSON (legacy V2 format).

    Result is always a dict with numeric string keys.

    Note:
    ----
    This function is very hacky, and will inevitably contain a number of band-aid
    fixes to enable 1:1 compatibility with the legacy V2 JSON format.
    We should try to move away from this format ASAP, so we can remove
    this function and all its hacks.
    """
    from zabbix_cli.models import Result

    # If we have a message, it should not be indexed
    # NOTE: do we have a more accurate heuristic for this?
    if isinstance(result, Result) and result.message:
        j = result.model_dump_json(indent=2)
    else:
        from zabbix_cli.models import AggregateResult

        jdict: dict[str, Any] = {}  # always a dict in legacy mode
        res = result.model_dump(mode="json", by_alias=True)
        if isinstance(result, AggregateResult):
            py_result = res.get("result", [])
        else:
            py_result = [res]

        for idx, item in enumerate(py_result):
            jdict[str(idx)] = item
        j = json.dumps(jdict, indent=2)
    console.print_json(j, indent=2, sort_keys=False)
