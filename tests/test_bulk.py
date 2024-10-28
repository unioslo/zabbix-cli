from __future__ import annotations

from pathlib import Path

import pytest
import typer
from inline_snapshot import snapshot
from zabbix_cli.app.app import StatefulApp
from zabbix_cli.bulk import BulkCommand
from zabbix_cli.bulk import BulkRunner
from zabbix_cli.bulk import BulkRunnerMode
from zabbix_cli.bulk import CommandResult
from zabbix_cli.bulk import CommentLine
from zabbix_cli.bulk import EmptyLine
from zabbix_cli.exceptions import CommandFileError
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import exit_ok
from zabbix_cli.output.console import info


@pytest.mark.parametrize(
    "line, expect",
    [
        pytest.param(
            "show_zabbixcli_config",
            BulkCommand(args=["show_zabbixcli_config"], line="show_zabbixcli_config"),
            id="simple",
        ),
        pytest.param(
            "create_user username name surname passwd role autologin autologout groups",
            BulkCommand(
                args=[
                    "create_user",
                    "username",
                    "name",
                    "surname",
                    "passwd",
                    "role",
                    "autologin",
                    "autologout",
                    "groups",
                ],
                line="create_user username name surname passwd role autologin autologout groups",
            ),
            id="Legacy positional args",
        ),
        pytest.param(
            "create_user username --firstname name --lastname surname --passwd mypass --role 1  --autologin --autologout 86400 --groups '1,2'",
            BulkCommand(
                args=[
                    "create_user",
                    "username",
                    "--firstname",
                    "name",
                    "--lastname",
                    "surname",
                    "--passwd",
                    "mypass",
                    "--role",
                    "1",
                    "--autologin",
                    "--autologout",
                    "86400",
                    "--groups",
                    "1,2",
                ],
                line="create_user username --firstname name --lastname surname --passwd mypass --role 1  --autologin --autologout 86400 --groups '1,2'",
            ),
            id="args and kwargs",
        ),
        pytest.param(
            "create_user username myname --passwd mypass surname",
            BulkCommand(
                args=[
                    "create_user",
                    "username",
                    "myname",
                    "--passwd",
                    "mypass",
                    "surname",
                ],
                line="create_user username myname --passwd mypass surname",
            ),
            id="kwarg between args",
        ),
        pytest.param(
            "create_user myuser --firstname myname --passwd mypasswd --role 1 # comment here --option value",
            BulkCommand(
                args=[
                    "create_user",
                    "myuser",
                    "--firstname",
                    "myname",
                    "--passwd",
                    "mypasswd",
                    "--role",
                    "1",
                ],
                line="create_user myuser --firstname myname --passwd mypasswd --role 1 # comment here --option value",
            ),
            id="Trailing comment",
        ),
        pytest.param(
            "",
            BulkCommand(),
            id="fails (empty)",
            marks=pytest.mark.xfail(raises=EmptyLine, strict=True),
        ),
        pytest.param(
            "#",
            BulkCommand(),
            id="fails (comment symbol)",
            marks=pytest.mark.xfail(raises=CommentLine, strict=True),
        ),
        pytest.param(
            "# create_user myuser myname mypasswd --role 1",
            BulkCommand(),
            id="fails (commented out line)",
            marks=pytest.mark.xfail(raises=CommentLine, strict=True),
        ),
    ],
)
def test_bulk_command_from_line(line: str, expect: BulkCommand) -> None:
    assert BulkCommand.from_line(line) == expect


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
            BulkCommand(
                args=["show_zabbixcli_config"],
                line="show_zabbixcli_config # next line will be blank",
                line_number=2,
            ),
            BulkCommand(
                args=[
                    "create_user",
                    "username",
                    "--firstname",
                    "name",
                    "--lastname",
                    "surname",
                    "mypass",
                    "1",
                    "1",
                    "86400",
                    "1,2",
                ],
                line="create_user username --firstname name --lastname surname mypass 1 1 86400 1,2",
                line_number=4,
            ),
            BulkCommand(
                args=[
                    "create_user",
                    "username",
                    "--firstname",
                    "name",
                    "--lastname",
                    "surname",
                    "--passwd",
                    "mypass",
                    "--role",
                    "1",
                    "--autologin",
                    "--autologout",
                    "86400",
                    "--groups",
                    "1,2",
                ],
                line="create_user username --firstname name --lastname surname --passwd mypass --role 1  --autologin --autologout 86400 --groups '1,2'",
                line_number=5,
            ),
            BulkCommand(
                args=[
                    "create_user",
                    "username",
                    "--firstname",
                    "name",
                    "--lastname",
                    "surname",
                    "--passwd",
                    "mypass",
                ],
                line="create_user username --firstname name --lastname surname --passwd mypass # trailing comment",
                line_number=7,
            ),
            BulkCommand(
                args=[
                    "acknowledge_event",
                    "123,456,789",
                    "--message",
                    "foo message",
                    "--close",
                ],
                line='acknowledge_event 123,456,789 --message "foo message" --close',
                line_number=9,
            ),
            BulkCommand(
                args=["show_templategroup", "mygroup", "--no-templates"],
                line="show_templategroup mygroup --no-templates",
                line_number=11,
            ),
            BulkCommand(
                args=["show_host", "*.example.com", "--no-maintenance", "--monitored"],
                line="show_host *.example.com --no-maintenance --monitored",
                line_number=13,
            ),
            BulkCommand(
                args=["show_host", "*.example.com", "--active", "available"],
                line="show_host *.example.com --active available",
                line_number=15,
            ),
            BulkCommand(
                args=["show_host", "*.example.com", "--active", "0"],
                line="show_host *.example.com --active 0",
                line_number=17,
            ),
            BulkCommand(
                args=["show_host", "*.example.com", "--active", "1"],
                line="show_host *.example.com --active 1",
                line_number=18,
            ),
            BulkCommand(
                args=["show_host", "*.example.com", "--active", "2"],
                line="show_host *.example.com --active 2",
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
        """\
# comment
show_host "*.example.com # Missing closing quote
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
show_host *.example.com --active 0
show_host "*.example.com # Missing closing quote
create_host foo.example.com --hostgroup "Linux servers"
"""
    )
    b = BulkRunner(ctx, file, mode=BulkRunnerMode.SKIP)
    commands = b.load_command_file()
    assert len(commands) == 2  # show_host, create_host
    assert len(b.executions) == 0
    assert len(b.skipped) == 2  # comment, invalid command

    # First line is comment
    # Second line is invalid command
    result = b.skipped[1]
    assert result.command == snapshot(
        BulkCommand(
            line='show_host "*.example.com # Missing closing quote', line_number=3
        )
    )
    assert result.result == CommandResult.SKIPPED
    assert repr(result.error) == snapshot("ValueError('No closing quotation')")
    assert result.line_number == snapshot(3)


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
            == "zabbix_cli.exceptions.CommandFileError: Command failed: [command]exits_error[/]"
        )
    else:
        assert "zabbix_cli.exceptions.CommandFileError: 1 commands failed:\nLine 4: exits_error (1)"
