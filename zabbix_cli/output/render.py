from __future__ import annotations

import json
from contextlib import nullcontext
from typing import Any
from typing import Set

import typer
from typing_extensions import TypedDict

from ..config import OutputFormat
from .console import console
from .console import info
from zabbix_cli.models import AggregateResult
from zabbix_cli.models import Result
from zabbix_cli.state import get_state


def render_result(
    result: Result, ctx: typer.Context | None = None, **kwargs: Any
) -> None:
    """Render the result of a command stdout or file.

    Parameters
    ----------
    result : Result
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
    result: Result, ctx: typer.Context | None = None, **kwargs: Any
) -> None:
    """Render the result of a command as a table."""
    if result.message:
        info(result.message)
    else:
        console.print(result.as_table())


class JsonDumpsKwargs(TypedDict):
    """Common BaseModel.dump_json kwargs for both new and legacy
    JSON formats.
    """

    exclude_unset: bool
    include: Set[str]


# Always includes return code even if not set
JSON_DUMP_KWARGS = JsonDumpsKwargs(
    exclude_unset=True,
    include={"return_code"},
)


def render_json(
    result: Result, ctx: typer.Context | None = None, **kwargs: Any
) -> None:
    """Render the result of a command as JSON."""
    # include = result.model_fields | {"return_code"}
    o_json = result.model_dump_json(indent=2)
    console.print_json(o_json, indent=2, sort_keys=False)


def render_json_legacy(result: Result, ctx: typer.Context | None = None) -> None:
    """Render the result of a command as JSON (legacy V2 format).

    Result is always a dict with numeric string keys.
    """
    res = result.model_dump(mode="json")
    jdict = {}  # type: dict[str, Any] # always a dict in legacy mode
    if isinstance(result, AggregateResult):
        py_result = res.get("result", [])
    else:
        py_result = [res]

    for idx, item in enumerate(py_result):
        jdict[str(idx)] = item
    j = json.dumps(jdict, indent=2)
    console.print_json(j, indent=2, sort_keys=False)
