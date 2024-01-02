"""Commands to view and manage macros."""
from __future__ import annotations

import hashlib
import random
from typing import Optional
from typing import TYPE_CHECKING

import typer

from zabbix_cli.app import app
from zabbix_cli.exceptions import ZabbixNotFoundError
from zabbix_cli.models import AggregateResult
from zabbix_cli.models import Result
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import warning
from zabbix_cli.output.prompts import bool_prompt
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.types import User
from zabbix_cli.utils.args import parse_bool_arg
from zabbix_cli.utils.args import parse_list_arg
from zabbix_cli.utils.args import UserRole
from zabbix_cli.utils.commands import ARG_POSITIONAL


if TYPE_CHECKING:
    from typing import Any  # noqa: F401

# # `zabbix-cli host user <cmd>`
# user_cmd = StatefulApp(
#     name="user",
#     help="Host user commands.",
# )
# app.add_subcommand(user_cmd)

HELP_PANEL = "User"


class ShowUsermacroTemplateListResult(TableRenderable):
    macro: str
    value: Optional[str] = None
    templateid: str
    template: str

    def __cols__(self) -> list[str]:
        return ["Macro", "Value", "Template ID", "Template"]


@app.command("create_user", rich_help_panel=HELP_PANEL)
def create_user(
    ctx: typer.Context,
    username: Optional[str] = typer.Argument(
        None, help="Username of the user to create."
    ),
    args: Optional[str] = ARG_POSITIONAL,  # legacy
    first_name: Optional[str] = typer.Option(
        None, help="First name of the user to create."
    ),
    last_name: Optional[str] = typer.Option(
        None, help="Last name of the user to create."
    ),
    password: Optional[str] = typer.Option(
        None,
        help="Password of the user to create. Set to '-' to prompt for password. Generates random password if omitted.",
    ),
    role: Optional[UserRole] = typer.Option(
        None,
        "--role",
        help="Role of the user.",
        case_sensitive=False,
    ),
    autologin: Optional[bool] = typer.Option(
        None, help="Enable auto-login for the user."
    ),
    autologout: Optional[str] = typer.Option(
        None,
        help="User session lifetime in seconds. Set to 0 to never expire. Can be a time unit with suffix (0s, 15m, 1h, 1d, etc.)",
    ),
    groups: Optional[str] = typer.Option(
        None, help="Comma-separated list of group IDs to add the user to."
    ),
) -> None:
    """Create a user.

    Prompts for missing values.
    Leave prompt values empty to not set values.
    """
    # TODO: add new options
    if not username:
        username = str_prompt("Username")

    try:
        app.state.client.get_user(username)
        exit_err(f"User {username!r} already exists.")
    except ZabbixNotFoundError:
        pass

    if args:
        warning("Positional arguments are deprecated. Please use options instead.")
        # Old args format: <username>  <first_name> <last_name> <password> <type> <autologin> <autologout> <usergroups>
        # We already have username, so we are left with 7 args.
        # In V2, we either expected NO positional args or ALL of them.
        # So we just match that behavior here.
        if len(args) != 7:
            exit_err(
                "Invalid number of positional arguments. Please use options instead."
            )
        first_name = args[0]
        last_name = args[1]
        password = args[2]
        role = UserRole(args[3])
        autologin = parse_bool_arg(args[4])
        autologout = args[5]
        groups = args[6]

    if not first_name:
        first_name = str_prompt("First name", default="", empty_ok=True)

    if not last_name:
        last_name = str_prompt("Last name", default="", empty_ok=True)

    if password == "-":
        password = str_prompt("Password", password=True)
    elif not password:
        # Generate random password
        x = hashlib.md5()
        x.update(str(random.randint(1, 1000000)).encode("ascii"))
        password = x.hexdigest()

    if not role:
        role = UserRole.from_prompt(default=UserRole.USER.value)

    if autologin is None:
        autologin = bool_prompt("Enable auto-login", default=False)

    if autologout is None:
        # Can also be time unit with suffix (0s, 15m, 1h, 1d, etc.)
        autologout = str_prompt("User session lifetime", default="86400")

    if not groups:
        groups = str_prompt("Groups (comma-separated)", default="", empty_ok=True)
    grplist = parse_list_arg(groups)
    # Fetch groups to ensure they exist (and to get their IDs)
    ugroups = [app.state.client.get_usergroup(g) for g in grplist]
    userid = app.state.client.create_user(
        username,
        password,
        first_name=first_name,
        last_name=last_name,
        role=role,
        autologin=autologin,
        autologout=autologout,
        usergroups=ugroups,
    )
    render_result(
        Result(
            message=f"Created user {username!r} ({userid}).",
            result=User(userid=str(userid), username=username),
        ),
    )


@app.command("remove_user", rich_help_panel=HELP_PANEL)
def remove_user(
    ctx: typer.Context,
    username: Optional[str] = typer.Argument(None, help="Username to remove."),
) -> None:
    """Remove a user."""
    if not username:
        username = str_prompt("Username")
    userid = app.state.client.delete_user(username)
    render_result(
        Result(
            message=f"Deleted user {username!r} ({userid}).",
            result=User(userid=str(userid), username=username),
        ),
    )


@app.command("show_user", rich_help_panel=HELP_PANEL)
def show_user(
    ctx: typer.Context,
    username: Optional[str] = typer.Argument(None, help="Username of user"),
) -> None:
    """Show a user."""
    if not username:
        username = str_prompt("Username")
    user = app.state.client.get_user(username)
    render_result(user)


@app.command("show_users", rich_help_panel=HELP_PANEL)
def show_users(
    ctx: typer.Context,
    limit: Optional[int] = typer.Option(
        None, "--limit", help="Limit the number of users shown."
    ),
    username: Optional[str] = typer.Option(
        None, "--username", help="Filter users by username. Wildcards supported."
    ),
    role: Optional[UserRole] = typer.Option(
        None,
        "--role",
        help="Filter users by role.",
        case_sensitive=False,
    ),
) -> None:
    """Show all users."""
    kwargs = {}  # type: dict[str, Any]
    if username or role:
        kwargs["search"] = True
    if username:
        kwargs["username"] = username
    if role:
        kwargs["role"] = role
    users = app.state.client.get_users(**kwargs)
    if limit:
        users = users[: abs(limit)]
    render_result(AggregateResult(result=users))
