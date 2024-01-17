from __future__ import annotations

from pathlib import Path
from typing import Type

import pytest

from zabbix_cli.bulk import BulkCommand
from zabbix_cli.bulk import CommandFileNotFoundError
from zabbix_cli.bulk import CommentLineError
from zabbix_cli.bulk import EmptyLineError
from zabbix_cli.bulk import load_command_file
from zabbix_cli.exceptions import CommandFileError


@pytest.mark.parametrize(
    "line, expect",
    [
        pytest.param(
            "show_zabbixcli_config",
            BulkCommand(command="show_zabbixcli_config", args=[], kwargs={}),
            id="simple",
        ),
        pytest.param(
            "create_user username name surname passwd type autologin autologout groups",
            BulkCommand(
                command="create_user",
                args=[
                    "username",
                    "name",
                    "surname",
                    "passwd",
                    "type",
                    "autologin",
                    "autologout",
                    "groups",
                ],
                kwargs={},
            ),
            id="with_args",
        ),
        pytest.param(
            "create_user username name surname --passwd mypass --type 1  --autologin 0 --autologout 86400 --groups '1,2'",
            BulkCommand(
                command="create_user",
                args=[
                    "username",
                    "name",
                    "surname",
                ],
                kwargs={
                    "passwd": "mypass",
                    "type": "1",
                    "autologin": "0",
                    "autologout": "86400",
                    "groups": "1,2",
                },
            ),
            id="args and kwargs",
        ),
        pytest.param(
            "create_user username --name myname surname --passwd mypass",
            BulkCommand(
                command="create_user",
                args=[
                    "username",
                    "surname",
                ],
                kwargs={
                    "name": "myname",
                    "passwd": "mypass",
                },
            ),
            id="kwarg between args",
        ),
        pytest.param(
            "create_user myuser myname mypasswd --type 1 # comment here --option value",
            BulkCommand(
                command="create_user",
                args=["myuser", "myname", "mypasswd"],
                kwargs={"type": "1"},
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
            "# create_user myuser myname mypasswd --type 1",
            BulkCommand(command=""),
            id="fails (commented out line)",
            marks=pytest.mark.xfail(raises=CommentLineError, strict=True),
        ),
    ],
)
def test_bulk_command_from_line(line: str, expect: BulkCommand) -> None:
    assert BulkCommand.from_line(line) == expect


def test_load_command_file(tmp_path: Path) -> None:
    """Test loading a command file."""
    file = tmp_path / "commands.txt"
    file.write_text(
        """# comment
show_zabbixcli_config # next line will be blank

create_user username name surname passwd type autologin autologout groups
create_user username name surname --passwd mypass --type 1  --autologin 0 --autologout 86400 --groups '1,2'
# comment explaining the next command
create_user username --name myname surname --passwd mypass # trailing comment
# Command with flag
acknowledge_event 123,456,789 --message "foo message" --close
# Command with negative flag
show_templategroup mygroup --no-templates
# we will end with a blank line
"""
    )

    commands = load_command_file(file)
    assert commands == [
        BulkCommand(command="show_zabbixcli_config", args=[], kwargs={}),
        BulkCommand(
            command="create_user",
            args=[
                "username",
                "name",
                "surname",
                "passwd",
                "type",
                "autologin",
                "autologout",
                "groups",
            ],
            kwargs={},
        ),
        BulkCommand(
            command="create_user",
            args=[
                "username",
                "name",
                "surname",
            ],
            kwargs={
                "passwd": "mypass",
                "type": "1",
                "autologin": "0",
                "autologout": "86400",
                "groups": "1,2",
            },
        ),
        BulkCommand(
            command="create_user",
            args=[
                "username",
                "surname",
            ],
            kwargs={
                "name": "myname",
                "passwd": "mypass",
            },
        ),
        BulkCommand(
            command="acknowledge_event",
            args=[
                "123,456,789",
            ],
            kwargs={
                "message": "foo message",
                "close": True,
            },
        ),
        BulkCommand(
            command="show_templategroup",
            args=[
                "mygroup",
            ],
            kwargs={
                "templates": False,
            },
        ),
    ]


@pytest.mark.parametrize(
    "exc_type",
    [FileNotFoundError, CommandFileError, CommandFileNotFoundError],
)
def test_load_command_file_not_found(tmp_path: Path, exc_type: Type[Exception]) -> None:
    """Test loading a command file that does not exist.

    Can be caught with built-in FileNotFoundError or with our own exception types."""
    file = tmp_path / "commands.txt"
    with pytest.raises(exc_type):
        load_command_file(file)


def test_load_command_file_shortform_fails(tmp_path: Path) -> None:
    """Test that a command file with a short-form option fails."""
    file = tmp_path / "commands.txt"
    file.write_text(
        """# comment
show_zabbixcli_config # next line will be blank

create_user username name surname -P passwd
"""
    )
    with pytest.raises(CommandFileError) as exc_info:
        load_command_file(file)

    msg = exc_info.exconly()
    assert "short-form" in msg.casefold()
    assert "line 4" in msg.casefold()
    assert "create_user username name surname -P passwd" in msg  # test casing too
