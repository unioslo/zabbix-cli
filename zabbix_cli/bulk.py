"""Module for running commands in bulk from a file.

Uses a very rudimentary parser to parse commands from a file, then
passes them to typer.Context.invoke() to run them.
"""

from __future__ import annotations

import logging
import shlex
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Counter
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence
from typing import Union

import click
import click.core
import typer
import typer.core
from pydantic import BaseModel
from pydantic import Field
from typing_extensions import Self

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
KwargsDict = Dict[str, Union[KwargType, Sequence[KwargType]]]


@dataclass
class ParsedOption:
    """Represents a parsed command line option."""

    name: str
    value: Union[KwargType, Sequence[KwargType]]
    is_multiple: bool = False


class BulkCommand(BaseModel):
    """A command to be run in bulk."""

    command: str
    kwargs: Dict[
        str,
        Union[KwargType, Sequence[KwargType]],
    ] = Field(default_factory=dict)
    line_number: int

    @classmethod
    def from_line(cls, line: str, lineno: int, ctx: typer.Context) -> Self:
        """Parse a command line into a BulkCommand."""
        # Early returns for empty lines and comments
        line = line.strip()
        if not line:
            raise EmptyLineError("Cannot parse empty line")
        if line.startswith("#"):
            raise CommentLineError("Cannot parse comment line")

        # Split the line into tokens, handling quotes and comments
        tokens = shlex.split(line, comments=True)
        if not tokens:
            raise LineParseError("No command specified")

        # Get the command and validate it exists
        cmd_name = tokens[0]
        cmd = get_command_by_name(ctx, cmd_name)
        if not cmd.name:
            raise LineParseError(f"Invalid command {cmd_name}")

        # Create parameter lookup tables for easier access
        param_by_opt = {
            opt: param
            for param in cmd.params
            if param.name
            for opt in (list(param.opts) + list(param.secondary_opts))
        }
        positional_params = [
            p for p in cmd.params if isinstance(p, typer.core.TyperArgument)
        ]

        parsed_options: Dict[str, ParsedOption] = {}
        positional_args: List[str] = []

        # Parse options and arguments
        i = 1
        while i < len(tokens):
            token = tokens[i]

            # Handle options
            if token.startswith("-") and len(token) > 1:
                if token not in param_by_opt:
                    raise LineParseError(f"Invalid option {token}")

                param = param_by_opt[token]
                if not param.name:
                    raise LineParseError(f"Unnamed parameter {param}")

                # Handle boolean flags
                if param.type == click.BOOL:
                    value = True
                    if param.secondary_opts and token in param.secondary_opts:
                        value = False
                    parsed_options[param.name] = ParsedOption(param.name, value)
                    i += 1
                    continue

                # Handle options that take values
                if i + 1 >= len(tokens):
                    raise LineParseError(f"Missing value for option {token}")

                value = tokens[i + 1]
                if param.multiple:
                    if param.name not in parsed_options:
                        parsed_options[param.name] = ParsedOption(
                            param.name, [], is_multiple=True
                        )
                    parsed_options[param.name].value.append(value)  # type: ignore
                else:
                    parsed_options[param.name] = ParsedOption(param.name, value)
                i += 2
            else:
                positional_args.append(token)
                i += 1

        # Process positional arguments
        kwargs: KwargsDict = {}
        remaining_args = positional_args.copy()

        for param in positional_params:
            if not param.name:
                continue

            if param.required and not remaining_args:
                raise CommandFileError(
                    f"Missing required positional argument {param.human_readable_name}"
                )

            if param.nargs == 1 and remaining_args:
                kwargs[param.name] = remaining_args.pop(0)
            elif param.nargs != 1:
                value = (
                    remaining_args
                    if param.nargs == -1
                    else remaining_args[: param.nargs]
                )
                kwargs[param.name] = value
                remaining_args = remaining_args[len(value) :]

        # Add parsed options to kwargs
        for opt in parsed_options.values():
            kwargs[opt.name] = opt.value

        # Validate required options
        for param in cmd.params:
            if isinstance(param, typer.core.TyperOption) and param.required:
                if param.name not in kwargs:
                    opts = "/".join(str(p) for p in param.opts)
                    raise CommandFileError(f"Missing required option {opts}")

        return cls(command=cmd.name, kwargs=kwargs, line_number=lineno)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self}>"


class CommandResult(Enum):
    """Result of a command execution."""

    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


@dataclass
class CommandExecution:
    """Represents the execution of a single command."""

    command: BulkCommand
    result: CommandResult
    error: Optional[BaseException] = None
    line_number: Optional[int] = None


class BulkRunnerMode(Enum):
    """Mode of operation for BulkRunner."""

    STRICT = "strict"  # Stop on first error
    CONTINUE = "continue"  # Continue on errors, report at end
    SKIP_ERRORS = "skip_errors"  # Skip lines that can't be parsed


class BulkResultCounter(Counter[CommandResult]):
    pass


class BulkRunner:
    def __init__(
        self,
        ctx: typer.Context,
        file: Path,
        mode: BulkRunnerMode = BulkRunnerMode.STRICT,
    ) -> None:
        self.ctx = ctx
        self.file = file
        self.mode = mode
        self.executions: List[CommandExecution] = []

    @contextmanager
    def _command_context(self, command: BulkCommand, line_number: Optional[int] = None):
        """Context manager for command execution with proper error handling."""
        try:
            yield
            self.executions.append(
                CommandExecution(
                    command, CommandResult.SUCCESS, line_number=line_number
                )
            )
            logger.info("Command succeeded: %s", command)
        except (SystemExit, typer.Exit) as e:
            self.executions.append(
                CommandExecution(
                    command, CommandResult.FAILURE, error=e, line_number=line_number
                )
            )
            logger.debug("Command exited: %s - %s", command, e)
            if self.mode == BulkRunnerMode.STRICT:
                raise CommandFileError(f"Command failed: {command}") from e
        except Exception as e:
            self.executions.append(
                CommandExecution(
                    command, CommandResult.FAILURE, error=e, line_number=line_number
                )
            )
            logger.error("Command failed: %s - %s", command, e)
            if self.mode == BulkRunnerMode.STRICT:
                raise CommandFileError(f"Command failed: {command}") from e

    def run_bulk(self) -> Counter[CommandResult]:
        """Run commands in bulk from a file where each line is a CLI command.

        Returns:
            Dict[CommandResult, int]: Count of commands by result status
        Raises:
            CommandFileError: If command file cannot be parsed or a command fails (in STRICT mode)

        Example:

        ```bash
        $ cat /tmp/commands.txt

        # We can add comments and empty lines

        # We can use old-form positional arguments
        create_host test000001.example.net All-manual-hosts .+ 1

        # Or new-form keyword arguments
        create_host test000002.example.net --hostgroup All-manual-hosts --proxy .+ --status 1
        """
        commands = self.load_command_file()

        for command in commands:
            cmd = get_command_by_name(self.ctx, command.command)
            with self._command_context(command, command.line_number):
                self.ctx.invoke(cmd, **command.kwargs)

        # Generate summary
        results: Counter[CommandResult] = Counter()
        for execution in self.executions:
            results[execution.result] += 1

        # Log summary
        total = sum(results.values())
        logger.info(
            "Bulk execution complete. Total: %d, Succeeded: %d, Failed: %d, Skipped: %d",
            total,
            results[CommandResult.SUCCESS],
            results[CommandResult.FAILURE],
            results[CommandResult.SKIPPED],
        )

        # In CONTINUE mode, raise error if any commands failed
        if self.mode == BulkRunnerMode.CONTINUE and results[CommandResult.FAILURE] > 0:
            failed_commands = [
                f"Line {e.line_number}: {e.command} ({e.error})"
                for e in self.executions
                if e.result == CommandResult.FAILURE
            ]
            raise CommandFileError(
                f"{results[CommandResult.FAILURE]} commands failed:\n"
                + "\n".join(failed_commands)
            )

        return results

    def load_command_file(self) -> List[BulkCommand]:
        """Parse the contents of a command file."""
        try:
            contents = read_file(self.file)
        except Exception as e:
            raise CommandFileError(f"Could not read command file: {e}") from e

        commands: List[BulkCommand] = []

        for lineno, line in enumerate(contents.splitlines(), start=1):
            try:
                command = BulkCommand.from_line(line, lineno, self.ctx)
                commands.append(command)
            except SkippableLineError:
                self.executions.append(
                    CommandExecution(
                        BulkCommand(
                            command="", kwargs={}, line_number=lineno
                        ),  # dummy command
                        CommandResult.SKIPPED,
                        line_number=lineno,
                    )
                )
            except Exception as e:
                if self.mode == BulkRunnerMode.SKIP_ERRORS:
                    logger.warning("Skipping invalid line %d: %s", lineno, e)
                    self.executions.append(
                        CommandExecution(
                            BulkCommand(
                                command=line.strip(), kwargs={}, line_number=lineno
                            ),
                            CommandResult.FAILURE,
                            error=e,
                            line_number=lineno,
                        )
                    )
                else:
                    raise CommandFileError(
                        f"Unable to parse line {lineno} '{line}': {e}"
                    ) from e

        return commands


def run_bulk(ctx: typer.Context, file: Path) -> None:
    runner = BulkRunner(ctx, file, mode=BulkRunnerMode.SKIP_ERRORS)
    runner.run_bulk()
