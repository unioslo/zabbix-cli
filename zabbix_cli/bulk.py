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
from zabbix_cli.exceptions import ZabbixCLIError


logger = logging.getLogger(__name__)


# All these exception inherit from the base ZabbixCLIError type, which means
# they are caught by the default exception handler. But we define more
# granular exception types here, so that we can test errors more accurately.


class LineParseError(CommandFileError):
    """Raised when a line cannot be parsed."""


class EmptyLineError(LineParseError):
    """Raised when a line is empty."""


class CommentLineError(LineParseError):
    """Raised when a line is a comment."""


class CommandFileNotFoundError(FileNotFoundError, CommandFileError):
    """Raised when a command file is not found."""


KwargType = Union[str, bool, int, float, None]


class BulkCommand(BaseModel):
    """A command to be run in bulk."""

    command: str
    args: List[str] = Field(default_factory=list)
    kwargs: Dict[str, KwargType] = Field(default_factory=dict)

    @classmethod
    def from_line(cls, line: str) -> BulkCommand:
        """Parse a command line into a BulkCommand."""
        line = line.strip()
        if not line:
            raise EmptyLineError("Cannot parse empty line")
        if line.startswith("#"):
            raise CommentLineError("Cannot parse comment line")
        elements = shlex.split(line, comments=True)

        command = elements[0]
        args = []  # type: list[str]
        kwargs = {}  # type: dict[str, KwargType] # TODO: support other types. ints, floats, bools

        next_is_kwarg = False
        next_kwarg = None  # type: str | None
        for arg in elements[1:]:
            if next_is_kwarg and next_kwarg:
                kwargs[next_kwarg] = arg
                next_is_kwarg = False
                next_kwarg = None
            # NOTE: when we encounter a dash its len must be >= 1 so that
            # FIXME: Potential bug here with regads to parsing negative numbers
            # passed in as arguments. `-1` will be parsed as a kwarg, but then followed
            # by no arguments.
            elif arg.startswith("-") and len(arg) > 1:
                kwarg = arg.lstrip("-")
                if not kwarg:
                    raise LineParseError(f"Invalid keyword argument {arg}")
                elif len(kwarg) == 1:
                    raise LineParseError(f"Short-form options are not supported: {arg}")
                next_kwarg = kwarg
                next_is_kwarg = True
                # TODO: support kwargs that can be specified multiple times
                # by appending to a list
                # Alternatively, always use a list?

                # Assume option is flag.
                # This value is overwritten if an argument follows next.
                kwargs[next_kwarg] = not kwarg.startswith("no-")
            else:
                args.append(arg)

        # TODO: validate kwargs
        # If a kwarg has no argument, it should be set to True (?)
        return cls(command=command, args=args, kwargs=kwargs)

    def __str__(self) -> str:
        return f"{self.command} {' '.join(self.args)} {' '.join(f'--{k} {v}' for k, v in self.kwargs.items())}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self}>"


def load_command_file(file: Path) -> List[BulkCommand]:
    """Load a command file. Returns a list of commands"""
    contents = _read_command_file(file)
    return parse_command_file_contents(contents)


# TODO: some sort of permissive mode here where a command can fail?
def run_bulk(ctx: typer.Context, file: Path) -> None:
    """Run commands in bulk from a file where each line is a CLI command
    with arguments and options.

    Each line must succeed for the next line to be run.
    If a line fails, the command will exit with a non-zero exit code.

    Args:
        ctx (typer.Context): Context passed from the main callback
        file (Path): Path to the command file

    Raises:
        CommandFileError: If command file cannot be parsed or a command fails.

    Example::

    ```bash
    $ cat /tmp/commands.txt

    # We can add comments and empty lines

    # We can use old-form positional arguments
    create_host test000001.example.net All-manual-hosts .+ 1

    # Or new-form keyword arguments
    create_host --host test000002.example.net --hostgroup All-manual-hosts --proxy .+ --status 1
    ```
    """
    commands = load_command_file(file)
    for command in commands:
        try:
            # TODO: get the command here
            cmd = get_command_by_name(ctx, command.command)
            ctx.invoke(cmd, *command.args, **command.kwargs)
        except (SystemExit, typer.Exit) as e:  # others?
            logger.debug("Bulk command %s exited: %s", command, e)
        except Exception as e:
            raise CommandFileError(f"Error running command {command}: {e}") from e
        else:
            logger.info("Bulk command %s succeeded", command)


def get_command_by_name(ctx: typer.Context, name: str) -> click.core.Command:
    """Get a CLI command given its name."""
    if not isinstance(ctx.command, typer.core.TyperGroup):
        raise ZabbixCLIError("Bulk commands not launched from a group context.")
    command = ctx.command.commands.get(name)
    if not command:
        raise ZabbixCLIError(f"Command {name} not found.")
    return command


def _read_command_file(file: Path) -> str:
    """Attempts to read the contents of a command file."""
    if not file.exists():
        raise CommandFileNotFoundError(f"File {file} does not exist")
    if not file.is_file():
        raise CommandFileError(f"{file} is not a file")
    try:
        return file.read_text()
    except OSError as e:
        raise CommandFileError(f"Unable to read file {file}") from e


# TODO (pederhan): future improvement: support non-strict parsing
# discard lines that cannot be parsed, but continue parsing the rest


def parse_command_file_contents(contents: str) -> List[BulkCommand]:
    """Parse the contents of a command file."""
    lines = []
    for lineno, line in enumerate(contents.splitlines(), start=1):
        try:
            lines.append(BulkCommand.from_line(line))
        except (EmptyLineError, CommentLineError):
            pass  # These are expected
        except Exception as e:
            raise CommandFileError(
                f"Unable to parse line {lineno} '{line}'. {e}"
            ) from e
    return lines
