"""REPL (Read-Eval-Print Loop) for the Zabbix CLI."""

from __future__ import annotations

import os
import shlex
import sys
from collections import defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import DefaultDict
from typing import NamedTuple
from typing import NoReturn
from typing import Optional

import click
import click.parser
import click.shell_completion
from click.exceptions import Exit as ClickExit
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.shortcuts import prompt

from zabbix_cli.exceptions import handle_exception
from zabbix_cli.output.console import err_console
from zabbix_cli.repl.completer import ClickCompleter

if TYPE_CHECKING:
    from click.core import Context

    from zabbix_cli.app import StatefulApp


class InternalCommandException(Exception):
    pass


class ExitReplException(InternalCommandException):
    pass


CommandCallable = Callable[..., Any]
"""Callable for internal commands."""


class InternalCommand(NamedTuple):
    command: CommandCallable
    description: str


_internal_commands: dict[str, InternalCommand] = dict()


def _register_internal_command(
    names: Iterable[str], target: CommandCallable, description: str
):
    if isinstance(names, str):
        names = [names]

    for name in names:
        _internal_commands[name] = InternalCommand(target, description)


def _get_registered_target(
    name: str, default: Optional[CommandCallable] = None
) -> Optional[CommandCallable]:
    target_info = _internal_commands.get(name)
    if target_info:
        return target_info[0]
    return default


def _exit_internal() -> NoReturn:
    raise ExitReplException()


def _help_internal() -> str:
    formatter = click.HelpFormatter()
    formatter.write_heading("REPL help")
    formatter.indent()
    with formatter.section("External Commands"):
        formatter.write_text('prefix external commands with "!"')
    with formatter.section("Internal Commands"):
        formatter.write_text('prefix internal commands with ":"')
        info_table: DefaultDict[str, list[str]] = defaultdict(list)
        for mnemonic, target_info in _internal_commands.items():
            info_table[target_info[1]].append(mnemonic)
        formatter.write_dl(
            [
                (
                    ", ".join(f":{mnemonic}" for mnemonic in sorted(mnemonics)),
                    description,
                )
                for description, mnemonics in info_table.items()
            ]
        )
    return formatter.getvalue()


_register_internal_command(["q", "quit", "exit"], _exit_internal, "exits the repl")
_register_internal_command(
    ["?", "h", "help"], _help_internal, "displays general help information"
)


def bootstrap_prompt(
    prompt_kwargs: Optional[dict[str, Any]],
    group: click.Group,
    ctx: click.Context,
    show_only_unused: bool = False,
    shortest_only: bool = False,
) -> dict[str, Any]:
    """
    Bootstrap prompt_toolkit kwargs or use user defined values.

    :param prompt_kwargs: The user specified prompt kwargs.
    """
    prompt_kwargs = prompt_kwargs or {}

    defaults = {
        "history": InMemoryHistory(),
        "completer": ClickCompleter(
            group, ctx, show_only_unused=show_only_unused, shortest_only=shortest_only
        ),
        "message": "> ",
    }

    for key in defaults:
        default_value = defaults[key]
        if key not in prompt_kwargs:
            prompt_kwargs[key] = default_value

    return prompt_kwargs


def register_repl(group: click.Group, name: str = "repl"):
    """Register :func:`repl()` as sub-command *name* of *group*."""
    group.command(name=name)(click.pass_context(repl))


def exit() -> None:
    """Exit the repl"""
    _exit_internal()


def dispatch_repl_commands(command: str) -> bool:
    """Execute system commands entered in the repl.

    System commands are all commands starting with "!".

    """
    if command.startswith("!") and len(command) > 1:
        os.system(command[1:])
        return True

    return False


def handle_internal_commands(command: str) -> Any:
    """Run repl-internal commands.

    Repl-internal commands are all commands starting with ":".

    """
    if command.startswith(":"):
        target = _get_registered_target(command[1:], default=None)
        if target:
            return target()


def repl(  # noqa: C901
    old_ctx: Context,
    app: StatefulApp,
    prompt_kwargs: Optional[dict[str, Any]] = None,
    allow_system_commands: bool = True,
    allow_internal_commands: bool = True,
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

    if not isinstance(group, click.Group):
        raise RuntimeError("REPL must be started from a Typer or Click group.")
    available_commands = group.commands

    # Delete the REPL command from those available
    repl_command_name = old_ctx.command.name
    if repl_command_name:
        available_commands.pop(repl_command_name, None)

    # Remove hidden commands
    available_commands = {
        cmd_name: cmd_obj
        for cmd_name, cmd_obj in available_commands.items()
        if not cmd_obj.hidden
    }

    group.commands = available_commands
    prompt_kwargs = bootstrap_prompt(prompt_kwargs, group, group_ctx)

    if isatty:

        def get_command() -> str:
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
        except (ClickExit, SystemExit):
            pass
        except ExitReplException:
            break
        except Exception as e:
            try:
                # Pass exception to the exception handler
                # which handles printing and logging the exception
                # The exception handler also calls sys.exit() (used in non-interactive mode)
                # so we need to catch it and ignore it.
                handle_exception(e)
            except SystemExit:
                pass
        except KeyboardInterrupt:
            # User likely pressed Ctrl+C during a prompt or when a spinner
            # was active. Ensure message is printed on a new line.
            # TODO: determine if last char in terminal was newline somehow! Can we?
            err_console.print("\n[red]Aborted.[/]")
            pass
