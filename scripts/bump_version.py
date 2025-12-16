from __future__ import annotations

import logging
import subprocess
import sys
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Sequence
from datetime import datetime
from enum import IntEnum
from enum import auto
from functools import wraps
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any
from typing import NamedTuple
from typing import NoReturn
from typing import Optional
from typing import Protocol

import typer
from rich.console import Console
from rich.panel import Panel
from strenum import StrEnum

logger = logging.getLogger(__name__)

console = Console()
err_console = Console(stderr=True, style="red")


class ExitCode(IntEnum):
    """Exit codes for the script."""

    ERROR = 1
    UNHANDLED_EXCEPTION = 3
    INTERRUPTED = 130


class VersionType(StrEnum):
    major = "major"
    minor = "minor"
    patch = "patch"


class ReleaseStage(StrEnum):
    # Release
    release = "release"

    # Alpha
    a = "a"
    alpha = "alpha"

    # Beta
    b = "b"
    beta = "beta"

    # Release Candidate
    c = "c"
    rc = "rc"
    pre = "pre"
    preview = "preview"

    # Revision / Post
    r = "r"
    rev = "rev"
    post = "post"

    # Dev
    dev = "dev"


class CommandCheck(NamedTuple):
    program: str
    command: Sequence[str]
    message: str


REQUIRED_COMMANDS = [
    CommandCheck(
        program="Hatch",
        command=["hatch", "--version"],
        message="Hatch is not installed. Please install it with `pip install hatch`.",
    ),
    CommandCheck(
        program="Git",
        command=["git", "--version"],
        message="Git is not installed. Please install it.",
    ),
]


def check_commands() -> None:
    """Checks that we have the necessary programs installed and available"""
    for command in REQUIRED_COMMANDS:
        try:
            subprocess.check_output(command.command)
        except FileNotFoundError:
            exit_err(f"{command.message} :x:", style="bold red")
        else:
            console.print(f"{command.program} :white_check_mark:")


def exit_err(
    msg: str, code: int = ExitCode.ERROR, style: Optional[str] = None
) -> NoReturn:
    """Print an error message and exit with the given code."""
    err_console.print(msg, style=style)
    sys.exit(code)


class State(IntEnum):
    OLD_VERSION = auto()  # before bumping version
    NEW_VERSION = auto()  # after bumping version
    MODIFY_CHANGELOG = auto()  # after modifying changelog
    GIT_ADD = auto()  # after git adding version file
    GIT_COMMIT = auto()  # after git commit
    GIT_TAG = auto()  # after git tag
    GIT_PUSH = auto()  # after git push

    @classmethod
    def __missing__(cls, value: Any) -> State:
        return State.OLD_VERSION

    @classmethod
    def ensure_contiguous(cls) -> None:
        """Ensure that enum values are contiguous and increment by 1"""
        # NOTE: this is just a sanity check that ensures we increment and
        # decrement the state machine correctly.
        if len(cls) != max(cls):  # starts at 1
            raise ValueError("Enum values must be contiguous")
        prev = None
        for st in cls:
            if prev is not None and st != prev + 1:
                raise ValueError("Enum values must increment by 1")
            prev = st


class StateMachine:
    def __init__(self) -> None:
        self.state = State.OLD_VERSION

    def forward(self) -> None:
        """Advance the state machine to the next state."""
        self.state = State(self.state.value + 1)

    def back(self) -> State:
        """Revert the state machine to the previous state."""
        self.state = State(self.state.value - 1)
        return self.state

    def rewind(self) -> Iterator[State]:
        """Iterate through all states in reverse order from the current state."""
        yield self.state
        while self.state != State.OLD_VERSION:
            yield self.back()


# I will not add proper type annotations to this decorator. If someone wants to do it, go ahead!
def advance(after: State) -> Any:
    """Advance state machine after a function call and check the expected state."""

    def decorator(f: Any) -> Any:
        @wraps(f)
        def inner(self: StateMachine, *args: Any, **kwargs: Any) -> Any:
            res = f(self, *args, **kwargs)
            # Only advance if we haven't run the function before.
            # In certain cases, we have to run git add twice, in which case
            # we cannot advance and and check the state on the second call.
            if after > self.state:
                self.forward()
                assert self.state == after, f"Expected state {after}, got {self.state}"
            return res

        return inner

    return decorator


class Runner(Protocol):
    def __call__(
        self, args: Sequence[str], *aargs: Any, **kwargs: Any
    ) -> CompletedProcess[bytes]: ...


class VersionBumper(StateMachine):
    run: Runner
    """Run a command in a subprocess.

    If dry_run is True, the command will be printed but not executed."""

    source_dir = Path("zabbix_cli")
    version_file = source_dir / "__about__.py"
    changelog_file = Path("CHANGELOG")
    changelog_file_bak = changelog_file.with_suffix(".bak")
    old_version: str | None = None
    new_version: str | None = None

    def __init__(
        self, target_version: str, push: bool, dry_run: bool, remote: str, branch: str
    ) -> None:
        super().__init__()
        self.target_version = target_version
        self.dry_run = dry_run
        self.push = push and not dry_run
        self.remote = remote
        self.branch = branch
        self.run = self.get_runner(dry_run)

    @property
    def tag(self) -> str:
        return f"{self.new_version}"

    def get_runner(self, dry_run: bool) -> Runner:
        def dryrun_subprocess_run(
            args: Sequence[str], *aargs: Iterable[str], **kwargs: str
        ) -> CompletedProcess[bytes]:
            """Wrapper around subprocess.run that prints the command and returns a dummy CompletedProcess"""
            args_quoted = [f"'{a}'" if " " in a else a for a in args]
            print(f"Running: {' '.join(args_quoted)}")
            return subprocess.CompletedProcess(
                args=args, returncode=0, stdout=b"", stderr=b""
            )

        if not dry_run:
            return subprocess.run

        lines = [
            "[bold]Running in dry-run mode.[/bold]",
            "Commands will not be executed.",
            "",
            "[bold]NOTE:[/bold] The previewed commands will show the current package version!",
        ]

        warning_console = Console(stderr=True, style="yellow")
        warning_console.print(
            Panel("\n".join(lines), title="Dry-run mode", expand=False)
        )
        return dryrun_subprocess_run

    def undo(self) -> None:
        for st in self.rewind():
            # from last to first
            # Best-effort cleanup
            try:
                if st == State.GIT_PUSH:
                    # probably nothing to clean up here
                    # we could do a git push --delete, but if it failed,
                    # it probably isn't in the upstream repo anyway
                    pass
                elif st == State.GIT_TAG:
                    if not self.new_version:
                        raise ValueError("No new version to untag.")
                    self.run(["git", "tag", "-d", self.tag])
                elif st == State.GIT_COMMIT:
                    # Undo last commit, but keep changes in the working directory
                    # --soft to keep changes in the working directory
                    self.run(["git", "reset", "--soft", "HEAD~"])
                elif st == State.GIT_ADD:
                    # Unstage changelog
                    self.run(["git", "restore", "--staged", str(self.changelog_file)])
                elif st == State.MODIFY_CHANGELOG:
                    # Revert the changes in the changelog file
                    if self.changelog_file_bak.exists():
                        self.changelog_file_bak.rename(self.changelog_file)
                elif st == State.NEW_VERSION:
                    # Hatch can't set the version to a lower than the current version
                    # so we have to revert the changes in the version file
                    self.run(["git", "checkout", "HEAD", str(self.version_file)])
            except Exception as e:
                print(f"Failed to revert state {self.state}: {e}", file=sys.stderr)
                raise e

    def cleanup(self) -> None:
        if self.changelog_file_bak.exists():
            self.changelog_file_bak.unlink()

    def bump(self) -> None:
        check_commands()
        self.state.ensure_contiguous()  # sanity check

        # TODO: * ensure we are on the correct branch
        #           `git rev-parse --abbrev-ref HEAD`
        #       * ensure we are up-to-date with the remote
        #           `git fetch upstream`

        # TODO: add decorator that advances state and checks expected state

        old_version = self.get_project_version()
        self.old_version = old_version

        self.set_version(self.target_version)
        # We have to re-fetch the new version after bumping, because
        # we might have used a version strategy rather than a specific version.
        # i.e. "major", "minor", "patch", "rc", etc.
        self.new_version = self.get_project_version()
        self.add_changelog_header(self.new_version)
        self.git_add()
        self.git_commit(self.new_version)
        self.git_tag(self.new_version)
        if self.push:
            self.git_push()

    def get_project_version(self) -> str:
        """Get the current project version from Hatch."""
        # NOTE: This is run directly with subprocess.check_output
        # instead of going through the run method, because we want to
        # actually call this command in dry-run mode as well.
        try:
            new_version = subprocess.check_output(["hatch", "version"]).decode().strip()
        except Exception as e:
            exit_err(f"Failed to get project version from Hatch: {e}")
        return new_version

    @advance(State.GIT_ADD)
    def git_add(self, *files: str) -> CompletedProcess[bytes]:
        p_git_add = self.run(
            [
                "git",
                "add",
                str(self.version_file.absolute()),
                str(self.changelog_file.absolute()),
                *files,
            ],
            capture_output=True,
        )
        if p_git_add.returncode != 0:
            exit_err(f"Failed to stage files: {p_git_add.stderr.decode()}")
        return p_git_add

    def get_pre_commit_files(self, msg: str) -> list[str]:
        files: list[str] = []
        for line in msg.splitlines():
            if line.startswith("Fixing "):
                _, _, file = line.partition("Fixing ")
                files.append(file)
        return files

    @advance(State.GIT_COMMIT)
    def git_commit(
        self, new_version: str, *, rerun: bool = False
    ) -> CompletedProcess[bytes]:
        p_git_commit = self.run(
            ["git", "commit", "-m", f"Bump version to {new_version}"],
            capture_output=True,
        )
        if p_git_commit.returncode != 0:
            # pre-commit might have modified our files
            msg = p_git_commit.stderr.decode()
            if "- hook id" in msg and not rerun:
                # re-run git-add and git-commit
                self.state = State(State.GIT_ADD - 1)
                # User might have added other files to the staging area
                # that pre-commit modified. We need to detect these files
                # and add them to the commit.
                files = self.get_pre_commit_files(msg)
                self.git_add(*files)
                self.git_commit(new_version, rerun=True)
            else:
                exit_err(f"Failed to commit version bump:\n{msg}")
        return p_git_commit

    @advance(State.GIT_TAG)
    def git_tag(self, new_version: str) -> CompletedProcess[bytes]:
        p_git_tag = self.run(["git", "tag", self.tag], capture_output=True)
        if p_git_tag.returncode != 0:
            exit_err(f"Failed to tag version: {p_git_tag.stderr.decode()}")
        return p_git_tag

    @advance(State.GIT_PUSH)
    def git_push(self) -> CompletedProcess[bytes]:
        p_git_push = self.run(
            ["git", "push", "--tags", self.remote, self.branch], capture_output=True
        )
        if p_git_push.returncode != 0:
            exit_err(f"Failed to push new version: {p_git_push.stderr.decode()}")
        return p_git_push

    @advance(State.MODIFY_CHANGELOG)
    def add_changelog_header(self, new_version: str) -> None:
        if self.dry_run:
            console.print(
                f"Would add changelog header for version {new_version} to {self.changelog_file}"
            )
            return

        changelog = self.changelog_file.read_text()
        self.changelog_file_bak.write_text(changelog)

        # Find the line containing the unreleased header
        lines = changelog.splitlines()
        index = next(
            iter(
                [
                    idx
                    for idx, line in enumerate(lines)
                    if line.startswith("## Unreleased")
                ],
            ),
            None,
        )
        if index is None:
            exit_err(f"Failed to find '## Unreleased' section in {self.changelog_file}")

        header = f"## [{new_version}](https://github.com/unioslo/zabbix-cli/tree/{new_version}) - {datetime.now().strftime('%Y-%m-%d')}"
        lines[index] = "<!-- ## Unreleased -->"  # comment out
        lines.insert(index + 1, f"\n{header}")  # insert after
        self.changelog_file.write_text("\n".join(lines))

    @advance(State.NEW_VERSION)
    def set_version(self, version: str) -> str:
        # We don't verify that the version arg is valid, we just pass it
        # to hatch and let it handle it.
        # Worst case scenario, we get a non-zero exit code and the script exits
        p_version = self.run(["hatch", "version", version], capture_output=True)
        if p_version.returncode != 0:
            exit_err(f"Failed to set version: {p_version.stderr.decode()}")
        return p_version.stdout.decode().strip()  # the new version


def main(
    version: str = typer.Argument(
        ...,
        help="Version bump to perform or new version to set.",
        metavar="["
        + "|".join(VersionType)
        + "|x.y.z],["
        + "|".join(ReleaseStage)
        + "]",
        show_default=False,
    ),
    push: bool = typer.Option(
        True,
        "--push/--no-push",
        help="Push the created tag and commmit to the remote repository automatically.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the commands that would be run without executing them.",
        is_flag=True,
    ),
    branch: str = typer.Option(
        "master",
        "--branch",
        help="The remote branch to push to.",
    ),
    remote: str = typer.Option(
        "upstream",
        "--remote",
        help="The remote repository to push to.",
    ),
) -> None:
    """Bump the version of the project and create a new git tag.

    If using --no-push, remember to also push the tag manually:
    `git push --tags upstream main`.

    Examples:
    $ python bump_version.py minor

    $ python bump_version.py major,rc

    $ python bump_version.py 1.2.3 # generally don't use this
    """
    bumper = VersionBumper(
        target_version=version,
        push=push,
        dry_run=dry_run,
        remote=remote,
        branch=branch,
    )
    try:
        bumper.bump()
    except KeyboardInterrupt:
        bumper.undo()
        exit_err("Bump cancelled by user.", code=ExitCode.INTERRUPTED)
    except Exception as e:
        bumper.undo()
        logger.exception(e)
        sys.exit(ExitCode.UNHANDLED_EXCEPTION)
    else:
        console.print(
            f"Successfully bumped version from {bumper.old_version} to {bumper.new_version} :tada:"
        )
    finally:
        bumper.cleanup()


if __name__ == "__main__":
    typer.run(main)
