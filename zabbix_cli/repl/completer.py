from __future__ import annotations

import os
import shlex
from collections.abc import Generator
from glob import iglob
from typing import Any
from typing import Optional

import click
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.completion import Completer
from prompt_toolkit.completion import Completion
from prompt_toolkit.document import Document

from zabbix_cli.commands.common.args import CommandParam

__all__ = ["ClickCompleter"]

IS_WINDOWS = os.name == "nt"


AUTO_COMPLETION_PARAM = "shell_complete"


def split_arg_string(string: str, posix: bool = True) -> list[str]:
    """Split an argument string as with :func:`shlex.split`, but don't
    fail if the string is incomplete. Ignores a missing closing quote or
    incomplete escape sequence and uses the partial token as-is.
    .. code-block:: python
        split_arg_string("example 'my file")
        ["example", "my file"]
        split_arg_string("example my\\")
        ["example", "my"]
    :param string: String to split.
    """

    lex = shlex.shlex(string, posix=posix)
    lex.whitespace_split = True
    lex.commenters = ""
    out: list[str] = []

    try:
        for token in lex:
            out.append(token)
    except ValueError:
        # Raised when end-of-string is reached in an invalid state. Use
        # the partial token as-is. The quote or escape character is in
        # lex.state, not lex.token.
        out.append(lex.token)

    return out


def _resolve_context(args: list[Any], ctx: click.Context) -> click.Context:
    """Produce the context hierarchy starting with the command and
    traversing the complete arguments. This only follows the commands,
    it doesn't trigger input prompts or callbacks.

    :param args: List of complete args before the incomplete value.
    :param cli_ctx: `click.Context` object of the CLI group
    """

    while args:
        command = ctx.command

        if isinstance(command, click.MultiCommand):
            if not command.chain:
                name, cmd, args = command.resolve_command(ctx, args)

                if cmd is None:
                    return ctx

                ctx = cmd.make_context(name, args, parent=ctx, resilient_parsing=True)
                args = ctx.protected_args + ctx.args
            else:
                sub_ctx = ctx
                while args:
                    name, cmd, args = command.resolve_command(ctx, args)

                    if cmd is None:
                        return ctx

                    sub_ctx = cmd.make_context(
                        name,
                        args,
                        parent=ctx,
                        allow_extra_args=True,
                        allow_interspersed_args=False,
                        resilient_parsing=True,
                    )
                    args = sub_ctx.args
                ctx = sub_ctx
                args = [*sub_ctx.protected_args, *sub_ctx.args]
        else:
            break

    return ctx


class ClickCompleter(Completer):
    __slots__ = ("cli", "ctx", "parsed_args", "parsed_ctx", "ctx_command")

    def __init__(
        self,
        cli: click.Group,
        ctx: click.Context,
        show_only_unused: bool = False,
        shortest_only: bool = False,
    ) -> None:
        self.cli = cli
        self.ctx = ctx
        self.parsed_args = []
        self.parsed_ctx = ctx
        self.ctx_command = ctx.command
        self.show_only_unused = show_only_unused
        self.shortest_only = shortest_only

    def _get_completion_from_autocompletion_functions(
        self,
        param: click.Parameter,
        autocomplete_ctx: click.Context,
        args: list[str],
        incomplete: str,
    ):
        param_choices: list[Completion] = []
        autocompletions = param.shell_complete(autocomplete_ctx, incomplete)
        for autocomplete in autocompletions:
            param_choices.append(Completion(str(autocomplete.value), -len(incomplete)))
        return param_choices

    def _get_completion_for_Path_types(
        self, param: click.Parameter, args: list[str], incomplete: str
    ) -> list[Completion]:
        if "*" in incomplete:
            return []

        choices: list[Completion] = []
        _incomplete = os.path.expandvars(incomplete)
        search_pattern = _incomplete.strip("'\"\t\n\r\v ").replace("\\\\", "\\") + "*"
        quote = ""

        if " " in _incomplete:
            for i in incomplete:
                if i in ("'", '"'):
                    quote = i
                    break

        for path in iglob(search_pattern):
            if " " in path:
                if quote:
                    path = quote + path
                else:
                    if IS_WINDOWS:
                        path = repr(path).replace("\\\\", "\\")
            else:
                if IS_WINDOWS:
                    path = path.replace("\\", "\\\\")

            choices.append(
                Completion(
                    str(path),
                    -len(incomplete),
                    display=str(os.path.basename(path.strip("'\""))),
                )
            )

        return choices

    def _get_completion_for_Boolean_type(self, param: click.Parameter, incomplete: str):
        return [
            Completion(str(k), -len(incomplete), display_meta=str("/".join(v)))
            for k, v in {
                "true": ("1", "true", "t", "yes", "y", "on"),
                "false": ("0", "false", "f", "no", "n", "off"),
            }.items()
            if any(i.startswith(incomplete) for i in v)
        ]

    def _get_completion_from_command_param(
        self, param: click.Parameter, incomplete: str
    ) -> list[Completion]:
        return [
            Completion(command, -len(incomplete))
            for command in self.cli.list_commands(self.parsed_ctx)
            if command.startswith(incomplete)
        ]

    def _get_completion_from_params(
        self,
        autocomplete_ctx: click.Context,
        args: list[str],
        param: click.Parameter,
        incomplete: str,
    ) -> list[Completion]:
        choices: list[Completion] = []
        if isinstance(param.type, click.types.BoolParamType):
            # Only suggest completion if parameter is not a flag
            if isinstance(param, click.Option) and not param.is_flag:
                choices.extend(self._get_completion_for_Boolean_type(param, incomplete))
        elif isinstance(param.type, (click.Path, click.File)):
            choices.extend(self._get_completion_for_Path_types(param, args, incomplete))
        elif isinstance(param.type, CommandParam):
            choices.extend(self._get_completion_from_command_param(param, incomplete))
        elif getattr(param, AUTO_COMPLETION_PARAM, None) is not None:
            choices.extend(
                self._get_completion_from_autocompletion_functions(
                    param,
                    autocomplete_ctx,
                    args,
                    incomplete,
                )
            )

        return choices

    def _get_completion_for_cmd_args(
        self,
        ctx_command: click.Command,
        incomplete: str,
        autocomplete_ctx: click.Context,
        args: list[str],
    ) -> list[Completion]:
        choices: list[Completion] = []
        param_called = False

        for param in ctx_command.params:
            if isinstance(param.type, click.types.UnprocessedParamType):
                return []

            elif getattr(param, "hidden", False):
                continue

            elif isinstance(param, click.Option):
                opts = param.opts + param.secondary_opts
                previous_args = args[: param.nargs * -1]
                current_args = args[param.nargs * -1 :]

                # Show only unused opts
                already_present = any([opt in previous_args for opt in opts])
                hide = self.show_only_unused and already_present and not param.multiple

                # Show only shortest opt
                if (
                    self.shortest_only
                    and not incomplete  # just typed a space
                    # not selecting a value for a longer version of this option
                    and args[-1] not in opts
                ):
                    opts = [min(opts, key=len)]

                for option in opts:
                    # We want to make sure if this parameter was called
                    # If we are inside a parameter that was called, we want to show only
                    # relevant choices
                    if option in current_args:  # noqa: E203
                        param_called = True
                        break

                    elif option.startswith(incomplete) and not hide:
                        choices.append(
                            Completion(
                                str(option),
                                -len(incomplete),
                                display_meta=str(param.help or ""),
                            )
                        )

                if param_called:
                    choices = self._get_completion_from_params(
                        autocomplete_ctx, args, param, incomplete
                    )
                    break

            elif isinstance(param, click.Argument):
                choices.extend(
                    self._get_completion_from_params(
                        autocomplete_ctx, args, param, incomplete
                    )
                )

        return choices

    def get_completions(
        self, document: Document, complete_event: Optional[CompleteEvent] = None
    ) -> Generator[Completion, Any, None]:
        # Code analogous to click._bashcomplete.do_complete

        args = split_arg_string(document.text_before_cursor, posix=False)

        choices: list[Completion] = []
        cursor_within_command = (
            document.text_before_cursor.rstrip() == document.text_before_cursor
        )

        if document.text_before_cursor.startswith(("!", ":")):
            return

        if args and cursor_within_command:
            # We've entered some text and no space, give completions for the
            # current word.
            incomplete = args.pop()
        else:
            # We've not entered anything, either at all or for the current
            # command, so give all relevant completions for this context.
            incomplete = ""

        if self.parsed_args != args:
            self.parsed_args = args
            try:
                self.parsed_ctx = _resolve_context(args, self.ctx)
            except Exception:
                return  # autocompletion for nonexistent cmd can throw here
            self.ctx_command = self.parsed_ctx.command

        if getattr(self.ctx_command, "hidden", False):
            return

        try:
            choices.extend(
                self._get_completion_for_cmd_args(
                    self.ctx_command, incomplete, self.parsed_ctx, args
                )
            )

            if isinstance(self.ctx_command, click.MultiCommand):
                incomplete_lower = incomplete.lower()

                for name in self.ctx_command.list_commands(self.parsed_ctx):
                    command = self.ctx_command.get_command(self.parsed_ctx, name)
                    if getattr(command, "hidden", False):
                        continue

                    elif name.lower().startswith(incomplete_lower):
                        choices.append(
                            Completion(
                                str(name),
                                -len(incomplete),
                                display_meta=getattr(command, "short_help", ""),
                            )
                        )

        except Exception as e:
            click.echo(f"{type(e).__name__}: {str(e)}")

        # If we are inside a parameter that was called, we want to show only
        # relevant choices
        # if param_called:
        #     choices = param_choices

        yield from choices
