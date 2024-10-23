from __future__ import annotations

from pathlib import Path

import pytest
import typer
from zabbix_cli.bulk import BulkCommand
from zabbix_cli.bulk import BulkRunner
from zabbix_cli.bulk import CommentLine
from zabbix_cli.bulk import EmptyLine
from zabbix_cli.exceptions import CommandFileError


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
# we will end with a blank line
"""
    )
    b = BulkRunner(ctx, file)
    commands = b.load_command_file()
    assert len(commands) == 6
    assert commands[0] == BulkCommand(command="show_zabbixcli_config", line_number=2)
    assert commands[1] == BulkCommand(
        command="create_user",
        kwargs={
            "username": "username",
            "first_name": "name",
            "last_name": "surname",
            "args": ["mypass", "1", "1", "86400", "1,2"],
        },
        line_number=4,
    )
    assert commands[2] == BulkCommand(
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
        line_number=5,
    )
    assert commands[3] == BulkCommand(
        command="create_user",
        kwargs={
            "username": "username",
            "first_name": "name",
            "last_name": "surname",
            "password": "mypass",
            "args": [],
        },
        line_number=7,
    )
    assert commands[4] == BulkCommand(
        command="acknowledge_event",
        kwargs={
            "event_ids": "123,456,789",
            "message": "foo message",
            "close": True,
            "args": [],
        },
        line_number=9,
    )
    assert commands[5] == BulkCommand(
        command="show_templategroup",
        kwargs={
            "templategroup": "mygroup",
            "templates": False,
        },
        line_number=11,
    )


def test_load_command_file_not_found(tmp_path: Path, ctx: typer.Context) -> None:
    """Test loading a command file that does not exist."""
    file = tmp_path / "commands.txt"
    assert not file.exists()
    b = BulkRunner(ctx, file)
    with pytest.raises(CommandFileError):
        b.load_command_file()
