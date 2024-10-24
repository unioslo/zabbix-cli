from __future__ import annotations

from pathlib import Path

import pytest
import typer
from inline_snapshot import snapshot
from zabbix_cli.app.app import StatefulApp
from zabbix_cli.bulk import BulkCommand
from zabbix_cli.bulk import BulkRunner
from zabbix_cli.bulk import BulkRunnerMode
from zabbix_cli.bulk import CommandExecution
from zabbix_cli.bulk import CommandResult
from zabbix_cli.bulk import CommentLine
from zabbix_cli.bulk import EmptyLine
from zabbix_cli.exceptions import CommandFileError
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import exit_ok
from zabbix_cli.output.console import info


@pytest.mark.parametrize(
    "line, expect",
    [
        pytest.param(
            "show_zabbixcli_config",
            BulkCommand(command="show_zabbixcli_config", kwargs={}),
            id="simple",
        ),
        pytest.param(
            "create_user username name surname passwd role autologin autologout groups",
            BulkCommand(
                command="create_user",
                kwargs={
                    "username": "username",
                    "args": [
                        "name",
                        "surname",
                        "passwd",
                        "role",
                        "autologin",
                        "autologout",
                        "groups",
                    ],
                },
            ),
            id="Legacy positional args",
        ),
        pytest.param(
            "create_user username --firstname name --lastname surname --passwd mypass --role 1  --autologin --autologout 86400 --groups '1,2'",
            BulkCommand(
                command="create_user",
                kwargs={
                    "username": "username",
                    "first_name": "name",
                    "last_name": "surname",
                    "password": "mypass",
                    "role": "1",
                    "autologin": True,
                    "autologout": "86400",
                    "groups": "1,2",
                    "args": [],
                },
            ),
            id="args and kwargs",
        ),
        pytest.param(
            "create_user username myname --passwd mypass surname",
            BulkCommand(
                command="create_user",
                kwargs={
                    "username": "username",
                    "password": "mypass",
                    "args": ["myname", "surname"],
                },
            ),
            id="kwarg between args",
        ),
        pytest.param(
            "create_user myuser --firstname myname --passwd mypasswd --role 1 # comment here --option value",
            BulkCommand(
                command="create_user",
                kwargs={
                    "username": "myuser",
                    "first_name": "myname",
                    "password": "mypasswd",
                    "role": "1",
                    "args": [],
                },
            ),
            id="Trailing comment",
        ),
        pytest.param(
            "",
            BulkCommand(command=""),
            id="fails (empty)",
            marks=pytest.mark.xfail(raises=EmptyLine, strict=True),
        ),
        pytest.param(
            "#",
            BulkCommand(command=""),
            id="fails (comment symbol)",
            marks=pytest.mark.xfail(raises=CommentLine, strict=True),
        ),
        pytest.param(
            "# create_user myuser myname mypasswd --role 1",
            BulkCommand(command=""),
            id="fails (commented out line)",
            marks=pytest.mark.xfail(raises=CommentLine, strict=True),
        ),
    ],
)
def test_bulk_command_from_line(
    ctx: typer.Context, line: str, expect: BulkCommand
) -> None:
    assert BulkCommand.from_line(line, ctx) == expect


def test_load_command_file(tmp_path: Path, ctx: typer.Context) -> None:
    """Test loading a command file."""
    file = tmp_path / "commands.txt"
    file.write_text(
        """# comment
show_zabbixcli_config # next line will be blank

create_user username --firstname name --lastname surname mypass 1 1 86400 1,2
create_user username --firstname name --lastname surname --passwd mypass --role 1  --autologin --autologout 86400 --groups '1,2'
# comment explaining the next command
create_user username --firstname name --lastname surname --passwd mypass # trailing comment
# Command with flag
acknowledge_event 123,456,789 --message "foo message" --close
# Command with negative flag
show_templategroup mygroup --no-templates
# Command with optional boolean flags
show_host *.example.com --no-maintenance --monitored
# Command with enum option (human-readable string)
show_host *.example.com --active available
# Command with enum option (API values)
show_host *.example.com --active 0
show_host *.example.com --active 1
show_host *.example.com --active 2
# we will end with a blank line
"""
    )
    b = BulkRunner(ctx, file)
    commands = b.load_command_file()
    assert len(commands) == snapshot(11)
    assert commands == snapshot(
        [
            BulkCommand(command="show_zabbixcli_config", kwargs={}, line_number=2),
            BulkCommand(
                command="create_user",
                kwargs={
                    "username": "username",
                    "args": ["mypass", "1", "1", "86400", "1,2"],
                    "first_name": "name",
                    "last_name": "surname",
                },
                line_number=4,
            ),
            BulkCommand(
                command="create_user",
                kwargs={
                    "username": "username",
                    "args": [],
                    "first_name": "name",
                    "last_name": "surname",
                    "password": "mypass",
                    "role": "1",
                    "autologin": True,
                    "autologout": "86400",
                    "groups": "1,2",
                },
                line_number=5,
            ),
            BulkCommand(
                command="create_user",
                kwargs={
                    "username": "username",
                    "args": [],
                    "first_name": "name",
                    "last_name": "surname",
                    "password": "mypass",
                },
                line_number=7,
            ),
            BulkCommand(
                command="acknowledge_event",
                kwargs={
                    "event_ids": "123,456,789",
                    "args": [],
                    "message": "foo message",
                    "close": True,
                },
                line_number=9,
            ),
            BulkCommand(
                command="show_templategroup",
                kwargs={"templategroup": "mygroup", "templates": False},
                line_number=11,
            ),
            BulkCommand(
                command="show_host",
                kwargs={
                    "hostname_or_id": "*.example.com",
                    "maintenance": False,
                    "monitored": True,
                },
                line_number=13,
            ),
            BulkCommand(
                command="show_host",
                kwargs={"hostname_or_id": "*.example.com", "active": "available"},
                line_number=15,
            ),
            BulkCommand(
                command="show_host",
                kwargs={"hostname_or_id": "*.example.com", "active": "0"},
                line_number=17,
            ),
            BulkCommand(
                command="show_host",
                kwargs={"hostname_or_id": "*.example.com", "active": "1"},
                line_number=18,
            ),
            BulkCommand(
                command="show_host",
                kwargs={"hostname_or_id": "*.example.com", "active": "2"},
                line_number=19,
            ),
        ]
    )


@pytest.mark.parametrize(
    "mode",
    [BulkRunnerMode.STRICT, BulkRunnerMode.CONTINUE],
)
def test_bulk_runner_mode_invalid_line_strict(
    tmp_path: Path, ctx: typer.Context, mode: BulkRunnerMode
) -> None:
    """Test loading a command file with invalid lines in strict/continue mode."""
    file = tmp_path / "commands.txt"
    file.write_text(
        """# comment
        21321asdasdadas # not a valid command
        """
    )
    b = BulkRunner(ctx, file, mode=mode)
    with pytest.raises(CommandFileError):
        b.load_command_file()


def test_bulk_runner_mode_invalid_line_skip(tmp_path: Path, ctx: typer.Context) -> None:
    """Test loading a command file with invalid lines in skip mode."""
    file = tmp_path / "commands.txt"
    file.write_text(
        """\
# comment
21321asdasdadas # not a valid command
"""
    )
    b = BulkRunner(ctx, file, mode=BulkRunnerMode.SKIP)
    commands = b.load_command_file()
    assert len(commands) == 0
    assert len(b.executions) == 0
    assert len(b.skipped) == 2  # comment, invalid
    expect = CommandExecution(
        BulkCommand(command="21321asdasdadas # not a valid command", line_number=2),
        CommandResult.SKIPPED,
        ZabbixCLIError("Command 21321asdasdadas not found."),
        line_number=2,
    )
    result = b.skipped[1]
    assert result.command == expect.command
    assert result.result == expect.result
    assert result.error.args == expect.error.args
    assert type(result.error) is type(expect.error)  # noqa
    assert result.line_number == expect.line_number


def test_load_command_file_not_found(tmp_path: Path, ctx: typer.Context) -> None:
    """Test loading a command file that does not exist."""
    file = tmp_path / "commands.txt"
    assert not file.exists()
    b = BulkRunner(ctx, file)
    with pytest.raises(CommandFileError):
        b.load_command_file()


@pytest.mark.parametrize("mode", [BulkRunnerMode.STRICT, BulkRunnerMode.CONTINUE])
def test_bulk_runner_exit_code_handling(
    tmp_path: Path, app: StatefulApp, ctx: typer.Context, mode: BulkRunnerMode
) -> None:
    """Test handling of exit codes."""
    file = tmp_path / "commands.txt"
    file.write_text(
        """\
# comment
no_exit
exits_ok
exits_error
"""
    )

    @app.command(name="exits_ok")
    def exits_ok() -> None:
        exit_ok("This command exits with code 0")

    @app.command(name="exits_error")
    def exits_error() -> None:
        exit_err("This command exits with code 1")

    @app.command(name="no_exit")
    def on_exit() -> None:
        info("We just print a message here")

    import typer
    import typer.core

    cmd = typer.main.get_command(app)
    ctx.command = cmd

    b = BulkRunner(ctx, file, mode)
    with pytest.raises(CommandFileError) as excinfo:
        b.run_bulk()

    assert len(b.executions) == 3
    assert b.executions[0].result == CommandResult.SUCCESS
    assert b.executions[1].result == CommandResult.SUCCESS
    assert b.executions[2].result == CommandResult.FAILURE

    # Differing error messages between strict and continue
    exc = excinfo.exconly()
    if mode == BulkRunnerMode.STRICT:
        assert (
            exc
            == "zabbix_cli.exceptions.CommandFileError: Command failed: command='exits_error' kwargs={} line_number=4"
        )
    else:
        assert "zabbix_cli.exceptions.CommandFileError: 1 commands failed:" in exc
        assert "Line 4: command='exits_error' kwargs={} line_number=4 (1)" in exc
