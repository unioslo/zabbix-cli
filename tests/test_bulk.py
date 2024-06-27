from __future__ import annotations

from pathlib import Path
from typing import Type

import pytest
import typer
from zabbix_cli.bulk import BulkCommand
from zabbix_cli.bulk import BulkRunner
from zabbix_cli.bulk import CommentLineError
from zabbix_cli.bulk import EmptyLineError

# from zabbix_cli.bulk import load_command_file
from zabbix_cli.exceptions import ZabbixCLIFileNotFoundError


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
                },
            ),
            id="Trailing comment",
        ),
        pytest.param(
            "",
            BulkCommand(command=""),
            id="fails (empty)",
            marks=pytest.mark.xfail(raises=EmptyLineError, strict=True),
        ),
        pytest.param(
            "#",
            BulkCommand(command=""),
            id="fails (comment symbol)",
            marks=pytest.mark.xfail(raises=CommentLineError, strict=True),
        ),
        pytest.param(
            "# create_user myuser myname mypasswd --role 1",
            BulkCommand(command=""),
            id="fails (commented out line)",
            marks=pytest.mark.xfail(raises=CommentLineError, strict=True),
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
    assert commands[0] == BulkCommand(command="show_zabbixcli_config")
    assert commands[1] == BulkCommand(
        command="create_user",
        kwargs={
            "username": "username",
            "first_name": "name",
            "last_name": "surname",
            "args": ["mypass", "1", "1", "86400", "1,2"],
        },
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
        },
    )
    assert commands[3] == BulkCommand(
        command="create_user",
        kwargs={
            "username": "username",
            "first_name": "name",
            "last_name": "surname",
            "password": "mypass",
        },
    )
    assert commands[4] == BulkCommand(
        command="acknowledge_event",
        kwargs={
            "event_ids": "123,456,789",
            "message": "foo message",
            "close": True,
        },
    )
    assert commands[5] == BulkCommand(
        command="show_templategroup",
        kwargs={
            "templategroup": "mygroup",
            "templates": False,
        },
    )


@pytest.mark.parametrize(
    "exc_type",
    [FileNotFoundError, ZabbixCLIFileNotFoundError],
)
def test_load_command_file_not_found(
    tmp_path: Path, ctx: typer.Context, exc_type: Type[Exception]
) -> None:
    """Test loading a command file that does not exist.

    Can be caught with built-in FileNotFoundError or with our own exception type.
    """
    file = tmp_path / "commands.txt"
    b = BulkRunner(ctx, file)
    with pytest.raises(exc_type):
        b.load_command_file()
