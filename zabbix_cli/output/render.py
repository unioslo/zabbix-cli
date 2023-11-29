from __future__ import annotations

import json
from contextlib import nullcontext
from typing import Any
from typing import Sequence
from typing import TypeVar
from typing import Union

import typer
from pydantic import BaseModel
from pydantic import RootModel

from ..exceptions import OverwriteError
from ..format import OutputFormat
from ..logs import logger
from .console import console
from .console import info
from .console import warning
from .table import BuiltinTypeException
from .table import EmptySequenceError
from .table import get_renderable
from zabbix_cli.state import get_state


T = TypeVar("T")

# TODO: add ResultType = T | list[T] to types.py


def render_result(result: T, ctx: typer.Context | None = None, **kwargs: Any) -> None:
    """Render the result of a command stdout or file.

    Parameters
    ----------
    result : T
        The result of a command.
    ctx : typer.Context, optional
        The typer context from the command invocation, by default None
    **kwargs
        Additional keyword arguments to pass to the render function.
    """
    # Short form aliases
    state = get_state()
    fmt = state.config.output.format
    paging = state.config.output.paging
    raw_mode = state.config.harbor.raw_mode
    validation = state.config.harbor.validate_data

    ctx_manager = console.pager() if paging else nullcontext()
    with ctx_manager:  # type: ignore # not quite sure why mypy is complaining here
        if raw_mode:  # raw mode ignores output format
            render_raw(result, ctx, **kwargs)
        elif fmt == OutputFormat.JSON or not validation:
            render_json(result, ctx, **kwargs)
        elif fmt == OutputFormat.TABLE:
            render_table(result, ctx, **kwargs)
        else:
            raise ValueError(f"Unknown output format {fmt!r}.")


def render_table(
    result: T | Sequence[T], ctx: typer.Context | None = None, **kwargs: Any
) -> None:
    """Render the result of a command as a table."""
    # TODO: handle "primitives" like strings and numbers

    # Try to render compact table if enabled
    state = get_state()
    compact = state.config.output.table.compact
    if compact:
        try:
            render_table_compact(result, **kwargs)
        except NotImplementedError as e:
            logger.debug(f"Unable to render compact table: {e}")
        except (EmptySequenceError, BuiltinTypeException):
            pass  # can't render these types
        else:
            return

    # If we got to this point, we have not printed a compact table.
    # Use built-in table rendering from harborapi.
    render_table_full(result)


def render_table_compact(result: T | Sequence[T], **kwargs) -> None:
    """Render the result of a command as a compact table."""
    renderable = get_renderable(result, **kwargs)
    console.print(renderable)


def render_table_full(result: T | Sequence[T], **kwargs) -> None:
    state = get_state()
    show_description = state.config.output.table.description
    max_depth = state.config.output.table.max_depth

    def print_item(item: T | str) -> None:
        """Prints a harbor base model as a table (optionally with description),
        if it is a harborapi BaseModel, otherwise just prints the item."""
        if isinstance(item, BaseModel):
            console.print(
                item.as_panel(with_description=show_description, max_depth=max_depth)
            )
        else:
            console.print(item)

    if isinstance(result, Sequence) and not isinstance(result, str):
        for item in result:
            print_item(item)
    else:
        print_item(result)


def render_json(
    result: T | Sequence[T], ctx: typer.Context | None = None, **kwargs: Any
) -> None:
    """Render the result of a command as JSON."""
    state = get_state()
    p = state.options.output_file
    with_stdout = state.options.with_stdout
    no_overwrite = state.options.no_overwrite
    indent = state.config.output.JSON.indent
    sort_keys = state.config.output.JSON.sort_keys

    # We use a Pydantic RootModel to render any type as JSON
    class Output(RootModel[Union[T, Sequence[T]]]):
        root: Union[T, Sequence[T]]

    o = Output(root=result)
    o_json = o.model_dump_json(indent=indent)

    # TODO: Take a look at this. We probably _do_ want to support file output
    # since we have a REPL and thus users can't use a shell redirect there,
    # and as such we need some way to natively support writing the JSON output
    # to a file. This, however, is a bit confusing with the `--with-stdout` option.
    # Maybe the answer is to just remove the `--with-stdout` option and always
    # print the output to the terminal regardles, and PERHAPS add a `--no-stdout` option.

    if p:
        if p.exists() and no_overwrite:
            raise OverwriteError(f"File {p.resolve()} exists.")
        with open(p, "w") as f:
            f.write(o_json)
            info(f"Output written to {p.resolve()}")

    # Print to stdout if no output file is specified or if the
    # --with-stdout flag is set.
    if not p or with_stdout:
        # We have to specify indent again here, because print_json()
        # ignores the indent of the JSON string passed to it.
        console.print_json(o_json, indent=indent, sort_keys=sort_keys)


def render_raw(result: Any, ctx: typer.Context | None = None, **kwargs: Any) -> None:
    """Render the result of data fetched in raw mode."""
    state = get_state()
    try:
        result = json.dumps(result)
        console.print_json(result, indent=state.config.output.JSON.indent)
    except Exception as e:
        warning(f"Unable to render raw data as JSON: {e}")
        console.print(result)
