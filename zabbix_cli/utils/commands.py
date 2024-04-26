from __future__ import annotations

from typing import TYPE_CHECKING

import typer
import typer.core

from zabbix_cli.exceptions import ZabbixCLIError

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


def get_command_by_name(ctx: typer.Context, name: str) -> click.core.Command:
    """Get a CLI command given its name."""
    if not isinstance(ctx.command, typer.core.TyperGroup):
        # NOTE: ideally we shouldn't leak this error to the user, but
        # can this even happen? Isn't it always a command group?
        raise ZabbixCLIError(f"Command {ctx.command.name} is not a command group.")
    if not ctx.command.commands:
        raise ZabbixCLIError(f"Command group {ctx.command.name} has no commands.")
    command = ctx.command.commands.get(name)
    if not command:
        raise ZabbixCLIError(f"Command {name} not found.")
    return command
