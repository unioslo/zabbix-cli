"""Module for running commands in bulk from a file.

Uses a very rudimentary parser to parse commands from a file, then
passes them to typer.Context.invoke() to run them.
"""

from __future__ import annotations

import logging
import shlex
from pathlib import Path
from typing import Dict
from typing import List
from typing import Union

import click.core
import typer.core
from pydantic import BaseModel
from pydantic import Field

from zabbix_cli.exceptions import CommandFileError
from zabbix_cli.utils.commands import get_command_by_name
from zabbix_cli.utils.fs import read_file

logger = logging.getLogger(__name__)


class LineParseError(CommandFileError):
    """Line cannot be parsed."""


# NOTE: These are named *Error, but should not be considered errors
# We should always catch them. They are used for flow control + testing.


class SkippableLineError(LineParseError):
    """Line will be skipped during parsing."""


class EmptyLineError(SkippableLineError):
    """Line is empty."""


class CommentLineError(SkippableLineError):
    """Line is a comment."""


KwargType = Union[str, bool, int, float, None]


class BulkCommand(BaseModel):
    """A command to be run in bulk."""

    command: str
    kwargs: Dict[str, Union[KwargType, List[KwargType]]] = Field(default_factory=dict)

    @classmethod
    def from_line(cls, line: str, ctx: typer.Context) -> BulkCommand:
        """Parse a command line into a BulkCommand."""
        line = line.strip()
        if not line:
            raise EmptyLineError("Cannot parse empty line")
        if line.startswith("#"):
            raise CommentLineError("Cannot parse comment line")
        tokens = shlex.split(line, comments=True)

        cmd_name = tokens.pop(0)
        cmd = get_command_by_name(ctx, cmd_name)
        if not cmd.name:
            raise LineParseError(f"Invalid command {cmd_name}")

        args: List[str] = []
        kwargs: Dict[
            str, KwargType | List[KwargType]
        ] = {}  # TODO: support other types. ints, floats, bools

        next_is_kwarg = False  # next token is a value for an option
        next_param = None  # param for next token
        for token in tokens:
            if token.startswith("#"):
                break  # encountered comment, no more tokens

            # If we are expecting a keyword argument, set it
            if next_is_kwarg and next_param:
                if not next_param.name:
                    raise LineParseError(f"Unnamed parameter {next_param}")
                if next_param.multiple:
                    if next_param.name not in kwargs:
                        kwargs[next_param.name] = []
                    kwargs[next_param.name].append(token)  # type: ignore # guaranteed to be list
                else:
                    kwargs[next_param.name] = token
                next_is_kwarg = False
                next_param = None
            elif token.startswith("-") and len(token) > 1:
                for param in cmd.params:
                    if not param.name:
                        continue
                    if token in param.opts or token in param.secondary_opts:
                        if param.type == click.BOOL:
                            # We have a flag with no argument (maybe????)
                            if param.secondary_opts and token in param.secondary_opts:
                                kwargs[param.name] = False
                            else:
                                kwargs[param.name] = True
                        else:
                            next_is_kwarg = True
                            next_param = param
                        break
                else:
                    raise LineParseError(f"Invalid option {token}")
            else:
                args.append(token)

        # Validate kwargs
        # If a kwarg has no argument, it should be set to True (?)
        for param in cmd.params:
            if isinstance(param, typer.core.TyperArgument):
                if param.name and args:
                    # Check if param takes a single argument
                    if param.nargs == 1:
                        # assume the first argument is the first positional argument (???)
                        kwargs[param.name] = args.pop(0)
                    # Param takes multiple arguments
                    else:
                        # If nargs != 1, we should have a list of arguments
                        if param.name not in kwargs:
                            kwargs[param.name] = []
                        # NOTE: using temp vars to convince type checker we have a list
                        kw = kwargs[param.name]
                        if not isinstance(kw, list):
                            kw = [kw]
                        kw.extend(args)
                        kwargs[param.name] = kw
                        # NOTE: why? What is the purpose of resetting args here?
                        # Should we only pop off the number of arguments we need?
                        # And if nargs == 0, we pop of all of them?
                        args = []
                elif param.required:
                    raise CommandFileError(
                        f"Missing required positional argument {param.human_readable_name} for command {cmd.name}"
                    )
            elif isinstance(param, typer.core.TyperOption):
                if param.required and param.name not in kwargs:
                    opts = "/".join(f"{p}" for p in param.opts)
                    raise CommandFileError(
                        f"Missing required option {opts} for command {cmd.name}"
                    )

        return cls(command=cmd.name, kwargs=kwargs)

    # def __str__(self) -> str:
    #     # NOTE: flags are printed incorrectly here
    #     return (
    #         f"{self.command} {' '.join(f'--{k} {v}' for k, v in self.kwargs.items())}"
    #     )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self}>"


class BulkRunner:
    def __init__(self, ctx: typer.Context, file: Path) -> None:
        self.ctx = ctx
        self.file = file

    # TODO: some sort of permissive mode here where a command can fail?
    def run_bulk(self) -> None:
        """Run commands in bulk from a file where each line is a CLI command
        with arguments and options.

        Each line must succeed for the next line to be run.
        If a line fails, the command will exit with a non-zero exit code.

        Raises:
            CommandFileError: If command file cannot be parsed or a command fails.

        Example::

        ```bash
        $ cat /tmp/commands.txt

        # We can add comments and empty lines

        # We can use old-form positional arguments
        create_host test000001.example.net All-manual-hosts .+ 1

        # Or new-form keyword arguments
        create_host test000002.example.net --hostgroup All-manual-hosts --proxy .+ --status 1
        ```
        """
        commands = self.load_command_file()
        for command in commands:
            try:
                # TODO: get the command here
                cmd = get_command_by_name(self.ctx, command.command)
                self.ctx.invoke(cmd, **command.kwargs)
            except (SystemExit, typer.Exit) as e:  # others?
                logger.debug("Bulk command %s exited: %s", command, e)
            except Exception as e:
                raise CommandFileError(f"Error running command {command}: {e}") from e
            else:
                logger.info("Bulk command %s succeeded", command)

    # TODO (pederhan): future improvement: support non-strict parsing
    # discard lines that cannot be parsed, but continue parsing the rest

    def load_command_file(self) -> List[BulkCommand]:
        """Parse the contents of a command file."""
        contents = read_file(self.file)
        lines: List[BulkCommand] = []
        for lineno, line in enumerate(contents.splitlines(), start=1):
            try:
                lines.append(BulkCommand.from_line(line, self.ctx))
            except SkippableLineError:
                pass  # These are expected
            except Exception as e:
                raise CommandFileError(
                    f"Unable to parse line {lineno} '{line}'. {e}"
                ) from e
        return lines


def run_bulk(ctx: typer.Context, file: Path) -> None:
    runner = BulkRunner(ctx, file)
    runner.run_bulk()
