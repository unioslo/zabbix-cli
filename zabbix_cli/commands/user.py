"""Commands to view and manage macros."""
from __future__ import annotations

import hashlib
import random
from typing import Optional
from typing import TYPE_CHECKING

import typer

from zabbix_cli.app import app
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import warning
from zabbix_cli.output.prompts import bool_prompt
from zabbix_cli.output.prompts import int_prompt
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.utils.args import parse_bool_arg
from zabbix_cli.utils.args import parse_int_arg
from zabbix_cli.utils.args import UserType
from zabbix_cli.utils.commands import ARG_POSITIONAL


if TYPE_CHECKING:
    pass

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
    type_: Optional[UserType] = typer.Option(
        UserType.USER, "--type", help="Type of the user to create."
    ),
    autologin: Optional[bool] = typer.Option(
        None, help="Enable auto-login for the user."
    ),
    autologout: Optional[int] = typer.Option(
        None, help="User session lifetime. Set to 0 to never expire."
    ),
    groups: Optional[str] = typer.Option(
        None, help="Comma-separated list of group IDs to add the user to."
    ),
) -> None:
    """Create a user."""
    if not username:
        username = str_prompt("Username")
    if args:
        warning("Positional arguments are deprecated. Please use options instead.")
        # Old args format: <username>  <first_name> <last_name> <password> <type> <autologin> <autologout> <usergroups>
        # We already have username, so we are left with 7 args.
        # In V2, we either expected NO positional args or ALL of them.
        if len(args) != 7:
            exit_err(
                "Invalid number of positional arguments. Please use options instead."
            )
        first_name = args[0]
        last_name = args[1]
        password = args[2]
        type_ = UserType(args[3])
        autologin = parse_bool_arg(args[4])
        autologout = parse_int_arg(args[5])
        groups = args[6]

    if not first_name:
        first_name = str_prompt("First name", default=None, empty_ok=True)
    if not last_name:
        last_name = str_prompt("Last name", default=None, empty_ok=True)

    if password == "-":
        password = str_prompt("Password", password=True)
    elif not password:
        x = hashlib.md5()
        x.update(str(random.randint(1, 1000000)).encode("ascii"))
        password = x.hexdigest()

    if not type_:
        type_ = UserType.from_prompt(default=UserType.USER)

    if autologin is None:
        autologin = bool_prompt("Enable auto-login", default=False)

    if autologout is None:
        autologout = int_prompt("User session lifetime", default=86400)

    if not groups:
        groups = str_prompt("Groups (comma-separated)", default=None, empty_ok=True)

    # TODODODODODODODOODOODOD: use ctx.params to find out which args are set and which are not
    # That way we can show defaults in command signature instead of having None!!


@app.command("remove_user", rich_help_panel=HELP_PANEL)
def remove_user(ctx: typer.Context) -> None:
    """Remove a user."""


@app.command("show_user", rich_help_panel=HELP_PANEL)
def show_user(ctx: typer.Context) -> None:
    """Show a user."""


@app.command("show_users", rich_help_panel=HELP_PANEL)
def show_users(ctx: typer.Context) -> None:
    """Show all users."""
