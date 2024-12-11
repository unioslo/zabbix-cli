"""Module for running commands in bulk from a file.

Uses a very rudimentary parser to parse commands from a file, then
passes them to typer.Context.invoke() to run them.
"""

from __future__ import annotations

import logging
import shlex
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
import typer.core
from pydantic import BaseModel
from pydantic import Field
from strenum import StrEnum
from typing_extensions import Self

from zabbix_cli.exceptions import CommandFileError
from zabbix_cli.output.console import warning
from zabbix_cli.state import get_state
from zabbix_cli.utils.fs import read_file

logger = logging.getLogger(__name__)


class LineParseError(CommandFileError):
    """Line cannot be parsed."""


# NOTE: these exceptions are used for control flow only
class SkippableLine(LineParseError):
    """Line will be skipped during parsing."""


class EmptyLine(SkippableLine):
    """Line is empty."""


class CommentLine(SkippableLine):
    """Line is a comment."""


class BulkCommand(BaseModel):
    """A command to be run in bulk."""

    args: list[str] = Field(default_factory=list)
    line: str = ""  # original line from file
    line_number: int = 0

    def __str__(self) -> str:
        if self.line:
            return self.line
        return " ".join(self.args)

    @classmethod
    def from_line(cls, line: str, line_number: int = 0) -> Self:
        """Parse a command line into a BulkCommand."""
        # Early returns for empty lines and comments
        line = line.strip()
        if not line:
            raise EmptyLine("Cannot parse empty line")
        if line.startswith("#"):
            raise CommentLine("Cannot parse comment line")

        # Split the line into tokens, handling quotes and comments
        args = shlex.split(line, comments=True)
        if not args:
            raise LineParseError("No command specified")
        return cls(args=args, line=line, line_number=line_number)

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


class BulkRunnerMode(StrEnum):
    """Mode of operation for BulkRunner."""

    STRICT = "strict"  # Stop on first error
    CONTINUE = "continue"  # Continue on errors, report at end
    SKIP = "skip"  # Skip lines that can't be parsed


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
        self.executions: list[CommandExecution] = []
        """Commands that were executed."""
        self.skipped: list[CommandExecution] = []
        """Lines that were skipped during parsing."""

    @contextmanager
    def _command_context(self, command: BulkCommand):
        """Context manager for command execution with proper error handling."""

        def add_success() -> None:
            self.executions.append(
                CommandExecution(
                    command, CommandResult.SUCCESS, line_number=command.line_number
                )
            )
            logger.info("Command succeeded: %s", command)

        def add_failure(e: BaseException) -> None:
            self.executions.append(
                CommandExecution(
                    command,
                    CommandResult.FAILURE,
                    error=e,
                    line_number=command.line_number,
                )
            )
            if self.mode == BulkRunnerMode.STRICT:
                raise CommandFileError(
                    f"Command failed: [command]{command}[/]: {e}"
                ) from e
            else:
                logger.error("Command failed: %s - %s", command, e)

        try:
            yield
            add_success()
        except (SystemExit, typer.Exit) as e:
            # If we get return code 0 on an exit, we consider it a success
            code = e.code if isinstance(e, SystemExit) else e.exit_code
            if code == 0:
                add_success()
            else:
                add_failure(e)
        except Exception as e:
            add_failure(e)

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
        # top-level Click command group for the application
        # Contains all commands defined via @app.command()
        group = self.ctx.command

        commands = self.load_command_file()
        for command in commands:
            with group.make_context(None, command.args, parent=self.ctx) as ctx:
                with self._command_context(command):
                    group.invoke(ctx)

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
                f"Line {e.line_number}: [command]{e.command}[/] [i]({e.error})[/]"
                for e in self.executions
                if e.result == CommandResult.FAILURE
            ]
            raise CommandFileError(
                f"{results[CommandResult.FAILURE]} commands failed:\n"
                + "\n".join(failed_commands)
            )

        return results

    def load_command_file(self) -> list[BulkCommand]:
        """Parse the contents of a command file."""
        try:
            contents = read_file(self.file)
        except Exception as e:
            raise CommandFileError(f"Could not read command file: {e}") from e

        commands: list[BulkCommand] = []

        def add_skipped(
            line: str, line_number: int, error: Optional[BaseException] = None
        ) -> None:
            self.skipped.append(
                CommandExecution(
                    BulkCommand(line=line, line_number=line_number),
                    CommandResult.SKIPPED,
                    error=error,
                    line_number=line_number,
                )
            )

        for lineno, line in enumerate(contents.splitlines(), start=1):
            try:
                command = BulkCommand.from_line(line, line_number=lineno)
                commands.append(command)
            except SkippableLine:
                logger.debug("Skipping line %d: %s", lineno, line)
                add_skipped(line, lineno)
            except Exception as e:
                if self.mode == BulkRunnerMode.SKIP:
                    add_skipped(line, lineno, e)
                    warning(
                        f"Ignoring invalid line {lineno}: [i default]{line}[/] ({e})"
                    )
                else:
                    raise CommandFileError(
                        f"Unable to parse line {lineno} '{line}': {e}"
                    ) from e

        return commands


def run_bulk(ctx: typer.Context, file: Path, mode: BulkRunnerMode) -> None:
    state = get_state()
    runner = BulkRunner(ctx, file, mode)
    try:
        state.bulk = True
        runner.run_bulk()
    finally:
        state.bulk = False
        state.logout_on_exit()
        logger.debug("Bulk execution complete.")
