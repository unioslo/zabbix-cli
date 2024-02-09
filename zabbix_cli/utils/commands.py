from __future__ import annotations

from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    import click


def get_parent_ctx(
    ctx: typer.Context | click.core.Context,
) -> typer.Context | click.core.Context:
    """Get the top-level parent context of a context."""
    if ctx.parent is None:
        return ctx
    return get_parent_ctx(ctx.parent)


def get_command_help(command: typer.models.CommandInfo) -> str:
    """Get the help text of a command."""
    if command.help:
        return command.help
    if command.callback and command.callback.__doc__:
        lines = command.callback.__doc__.strip().splitlines()
        if lines:
            return lines[0]
    if command.short_help:
        return command.short_help
    return ""


# NOTE: This arg should probably get a custom parser or callback to prompt for missing value
# But parsers dont fire on defaults, and callbacks don't carry the value in a typesafe way;
# we have to access it via the ctx object...
ARG_HOSTNAME_OR_ID = typer.Argument(None, help="Hostname or ID of host.")
