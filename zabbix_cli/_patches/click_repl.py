# type: ignore
"""Patches for click_repl package."""

from __future__ import annotations

import shlex
import sys
from typing import TYPE_CHECKING
from typing import Any
from typing import Dict
from typing import Optional

import click
import click_repl
from click.exceptions import Exit as ClickExit
from click_repl import ExitReplException
from click_repl import bootstrap_prompt
from click_repl import dispatch_repl_commands
from click_repl import handle_internal_commands
from prompt_toolkit.shortcuts import prompt

from zabbix_cli._patches.common import get_patcher
from zabbix_cli.exceptions import handle_exception

if TYPE_CHECKING:
    from click.core import Context

    from zabbix_cli.app import StatefulApp

patcher = get_patcher(f"click_repl version: {click_repl.__version__}")


def repl(  # noqa: C901
    old_ctx: Context,
    prompt_kwargs: Dict[str, Any] = None,
    allow_system_commands: bool = True,
    allow_internal_commands: bool = True,
    app: Optional[StatefulApp] = None,
) -> None:
    """Start an interactive shell. All subcommands are available in it.

    :param old_ctx: The current Click context.
    :param prompt_kwargs: Parameters passed to
        :py:func:`prompt_toolkit.shortcuts.prompt`.

    If stdin is not a TTY, no prompt will be printed, but only commands read
    from stdin.
    """
    # parent should be available, but we're not going to bother if not
    group_ctx = old_ctx.parent or old_ctx
    group = group_ctx.command
    isatty = sys.stdin.isatty()

    # Delete the REPL command from those available, as we don't want to allow
    # nesting REPLs (note: pass `None` to `pop` as we don't want to error if
    # REPL command already not present for some reason).
    repl_command_name = old_ctx.command.name
    if isinstance(group_ctx.command, click.CommandCollection):
        available_commands = {
            cmd_name: cmd_obj
            for source in group_ctx.command.sources
            for cmd_name, cmd_obj in source.commands.items()
        }
    else:
        available_commands = group_ctx.command.commands
    available_commands.pop(repl_command_name, None)

    # Remove hidden commands
    available_commands = {
        cmd_name: cmd_obj
        for cmd_name, cmd_obj in available_commands.items()
        if not cmd_obj.hidden
    }

    group.commands = available_commands
    prompt_kwargs = bootstrap_prompt(prompt_kwargs, group)

    if isatty:

        def get_command():
            return prompt(**prompt_kwargs)

    else:
        get_command = sys.stdin.readline

    while True:
        try:
            command = get_command()
        except KeyboardInterrupt:
            continue
        except EOFError:
            break

        if not command:
            if isatty:
                continue
            else:
                break

        if allow_system_commands and dispatch_repl_commands(command):
            continue

        if allow_internal_commands:
            try:
                result = handle_internal_commands(command)
                if isinstance(result, str):
                    click.echo(result)
                    continue
            except ExitReplException:
                break

        try:
            args = shlex.split(command)
        except ValueError as e:
            click.echo(f"{type(e).__name__}: {e}")
            continue

        try:
            if app:
                group = app.as_click_group()
            with group.make_context(None, args, parent=group_ctx) as ctx:
                group.invoke(ctx)
                ctx.exit()
        except click.ClickException as e:
            e.show()
        except ClickExit:
            pass
        except SystemExit:
            pass
        except ExitReplException:
            break
        # PATCH: Handle zabbix-cli exceptions
        except Exception as e:
            try:
                handle_exception(e)
            except SystemExit:
                pass
        # PATCH: Continue on keyboard interrupt
        except KeyboardInterrupt:
            from zabbix_cli.output.console import err_console

            # User likely pressed Ctrl+C during a prompt or when a spinner
            # was active. Ensure message is printed on a new line.
            # TODO: determine if last char in terminal was newline somehow! Can we?
            err_console.print("\n[red]Aborted.[/]")
            pass


def patch_exception_handling() -> None:
    """Patch click_repl's exception handling to fall back on zabbix-cli exception handlers."""
    with patcher("click_repl.repl"):
        click_repl.repl = repl


def patch() -> None:
    """Apply all patches."""
    patch_exception_handling()
