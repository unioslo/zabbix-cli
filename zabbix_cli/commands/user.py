"""Commands for managing users."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Optional
from typing import TypeVar

import typer
from strenum import StrEnum

from zabbix_cli._v2_compat import ARGS_POSITIONAL
from zabbix_cli.app import Example
from zabbix_cli.app import app
from zabbix_cli.exceptions import ZabbixNotFoundError
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import warning
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.enums import UserRole
from zabbix_cli.utils.args import check_at_least_one_option_set
from zabbix_cli.utils.args import parse_bool_arg
from zabbix_cli.utils.args import parse_list_arg

if TYPE_CHECKING:
    from typing import Protocol

    class UsergroupLike(Protocol):
        name: str
        usrgrpid: str

    UsergroupLikeT = TypeVar("UsergroupLikeT", bound=UsergroupLike)


HELP_PANEL = "User"


def get_random_password() -> str:
    import hashlib
    import random

    x = hashlib.md5()
    x.update(str(random.randint(1, 1000000)).encode("ascii"))
    return x.hexdigest()


@app.command("create_user", rich_help_panel=HELP_PANEL)
def create_user(
    ctx: typer.Context,
    username: str = typer.Argument(
        help="Username of the user to create.",
        show_default=False,
    ),
    first_name: Optional[str] = typer.Option(
        None, "--firstname", help="First name of the user to create."
    ),
    last_name: Optional[str] = typer.Option(
        None, "--lastname", "--surname", help="Last name of the user to create."
    ),
    password: Optional[str] = typer.Option(
        None,
        "--passwd",
        help="Password of the user to create. Set to '-' to prompt for password. Generates random password if omitted.",
    ),
    role: UserRole = typer.Option(
        UserRole.USER,
        "--role",
        help="Role of the user.",
        case_sensitive=False,
    ),
    autologin: bool = typer.Option(False, help="Enable auto-login for the user."),
    autologout: str = typer.Option(
        "86400",
        help="User session lifetime in seconds. Set to 0 to never expire. Can be a time unit with suffix (0s, 15m, 1h, 1d, etc.)",
    ),
    groups: Optional[str] = typer.Option(
        None, help="Comma-separated list of group IDs to add the user to."
    ),
    # Legacy V2 positional args
    args: Optional[list[str]] = ARGS_POSITIONAL,
) -> None:
    """Create a user."""
    from zabbix_cli.models import Result
    from zabbix_cli.pyzabbix.types import User

    try:
        app.state.client.get_user(username)
        exit_err(f"User {username!r} already exists.")
    except ZabbixNotFoundError:
        pass

    if args:
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

    if password == "-":
        password = str_prompt("Password", password=True)
    elif not password:
        # Generate random password
        password = get_random_password()

    grouplist = parse_list_arg(groups)
    # FIXME: add to default user group if no user group passed in
    ugroups = [app.state.client.get_usergroup(ug) for ug in grouplist]

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


@app.command(
    "create_notification_user",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Create a notification user for email reporting",
            "create_notification_user user@example.com Email",
        ),
    ],
)
def create_notification_user(
    ctx: typer.Context,
    sendto: str = typer.Argument(
        help="Email address, SMS number, jabber address, etc.",
        show_default=False,
    ),
    mediatype: str = typer.Argument(
        help="A media type name or ID defined in Zabbix. Case-sensitive.",
        show_default=False,
    ),
    remarks: Optional[str] = typer.Option(
        None,
        "--remarks",
        help="Remarks about the notification user to include in username (max 20 chars).",
    ),
    username: Optional[str] = typer.Option(
        None,
        "--username",
        help="Override generated username. Ignores --remarks.",
    ),
    usergroups: Optional[str] = typer.Option(
        None,
        "--usergroups",
        help="Comma-separated list of usergroups to add the user to. Overrides user groups in config file.",
    ),
    # Legacy V2 args
    args: Optional[list[str]] = ARGS_POSITIONAL,
) -> None:
    # TODO: Improve phrasing of this help text. "Defining media for usergroup"???
    """Create a notification user.

    Notification users can be used to send notifications when a Zabbix
    event happens.

    Sometimes we need to send a notification to a place not owned by any
    user in particular, e.g. an email list or jabber channel but Zabbix does
    not provide a way to define a media for a user group.

    This is the reason we use [i]notification users[/]. They are users nobody
    owns, but that can be used by other users to send notifications to the
    media defined in the notification user profile.

    Run [command]show_media_types[/command] to get a list of available media types.

    Adds the user to the default user group and default notification user group
    unless [option]--usergroups[/option] is specified.
    """
    from zabbix_cli.models import Result
    from zabbix_cli.pyzabbix.types import User
    from zabbix_cli.pyzabbix.types import UserMedia

    if args:
        # Old args format: <sendto> <mediatype> <remarks>
        # We already have sendto and mediatype, so we are left with 1 arg.
        if len(args) != 1:
            exit_err(
                "Invalid number of positional arguments. Please use options instead."
            )
        remarks = args[0]
    remarks = remarks or ""

    # Generate username
    if username and remarks:
        warning("Both --username and --remarks specified. Ignoring --remarks.")

    username = get_notification_user_username(username, sendto, remarks)

    # Check if user exists (it should not)
    try:
        app.state.client.get_user(username)
        exit_err(f"User {username!r} already exists.")
    except ZabbixNotFoundError:
        pass

    # Check if media type exists (it should)
    try:
        mt = app.state.client.get_mediatype(mediatype)
    except ZabbixNotFoundError:
        exit_err(
            f"Media type {mediatype!r} does not exist. Run [command]show_media_types[/command] command to get a list of available media types."
        )

    # Parse user groups args or use defaults
    if usergroups:
        ug_list = parse_list_arg(usergroups)
    else:
        ug_list: list[str] = []
        ug_list.extend(app.state.config.app.default_notification_users_usergroups)
        ug_list.extend(app.state.config.app.default_create_user_usergroups)
    with app.status("Fetching user group(s)..."):
        ugroups = [app.state.client.get_usergroup(ug) for ug in set(ug_list)]

    user_media = [
        UserMedia(
            mediatypeid=mt.mediatypeid,
            sendto=sendto,
            active=0,  # enabled
            severity=63,  # all
            period="1-7,00:00-24:00",  # 24/7
        )
    ]

    with app.status("Creating user..."):
        userid = app.state.client.create_user(
            username=username,
            password=get_random_password(),
            role=UserRole.USER,
            autologin=False,
            autologout="3600",
            usergroups=ugroups,
            media=user_media,
        )

    render_result(
        Result(
            message=f"Created notification user {username!r} ({userid}).",
            result=User(userid=userid, username=username),
        ),
    )


@app.command("remove_user", rich_help_panel=HELP_PANEL)
def remove_user(
    ctx: typer.Context,
    username: str = typer.Argument(
        help="Username to remove.",
        show_default=False,
    ),
) -> None:
    """Remove a user."""
    from zabbix_cli.models import Result

    user = app.state.client.get_user(username)
    app.state.client.delete_user(user)
    render_result(
        Result(
            message=f"Deleted user {user.name!r} ({user.userid}).",
            result=user,
        ),
    )


@app.command("show_user", rich_help_panel=HELP_PANEL)
def show_user(
    ctx: typer.Context,
    username: str = typer.Argument(
        help="Username of user",
        show_default=False,
    ),
) -> None:
    """Show a user."""
    user = app.state.client.get_user(username)
    render_result(user)


class UserSorting(StrEnum):
    NAME = "name"
    ID = "id"
    ROLE = "role"


@app.command("show_users", rich_help_panel=HELP_PANEL)
def show_users(
    ctx: typer.Context,
    username_or_id: Optional[str] = typer.Argument(
        None,
        help="Filter by username or ID. Supports wildcards.",
        show_default=False,
    ),
    role: Optional[UserRole] = typer.Option(
        None,
        "--role",
        help="Filter by role.",
        case_sensitive=False,
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", help="Limit the number of users shown."
    ),
    sort: Optional[UserSorting] = typer.Option(
        UserSorting.NAME,
        "--sort",
        help="Sort by field.",
    ),
) -> None:
    """Show all users.

    Users can be filtered by name, ID, or role."""
    from zabbix_cli.models import AggregateResult
    from zabbix_cli.pyzabbix.compat import user_name

    us = parse_list_arg(username_or_id)

    # TODO: move this to the client somehow
    #       This is also clumsy, because we want users to pass in
    #       "name", "id", or "role" as arguments to the command,
    #       but the API expects "userid", "name", or "roleid"
    sorting = None
    if sort:
        if sort == UserSorting.ROLE:
            sorting = "roleid"
        elif sort == UserSorting.ID:
            sorting = "userid"
        else:
            sorting = user_name(app.state.client.version)

    with app.status("Fetching users..."):
        users = app.state.client.get_users(
            *us, role=role, limit=limit, sort_field=sorting, sort_order="ASC"
        )
    render_result(AggregateResult(result=users))


def get_notification_user_username(
    username: Optional[str], sendto: str, remarks: str
) -> str:
    """Generate a username for a notification user."""
    username = username.strip().replace(" ", "_") if username else ""
    remarks = remarks.strip()[:20].replace(" ", "_")
    sendto = sendto.strip().replace(".", "-")
    if username:
        return username
    username = "notification-user"
    if remarks:
        username += f"-{remarks}"
    return f"{username}-{sendto}"


@app.command(
    "update_user",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Assign new first and last name",
            "update_user jdoe --firstname John --lastname Doe",
        ),
        Example(
            "Promote user to admin",
            "update_user jdoe --role Admin",
        ),
        Example(
            "Update user's password, prompt for passwords",
            "update_user jdoe --passwd - --old-passwd -",
        ),
        Example(
            "Update user's password, generate random new password",
            "update_user jdoe --passwd ? --old-passwd -",
        ),
        Example(
            "Disable autologin for user",
            "update_user jdoe --no-autologin",
        ),
    ],
)
def update_user(
    ctx: typer.Context,
    username: str = typer.Argument(
        help="Username of the user to update",
        show_default=False,
    ),
    first_name: Optional[str] = typer.Option(
        None, "--firstname", help="New first name."
    ),
    last_name: Optional[str] = typer.Option(None, "--lastname", help="New last name."),
    new_password: Optional[str] = typer.Option(
        None,
        "--passwd",
        "--new-passwd",
        help="New password for user. Set to '-' to prompt for password, '?' to generate a random password.",
    ),
    old_password: Optional[str] = typer.Option(
        None,
        "--old-passwd",
        help="Existing password, required if --passwd is used. Set to '-' to prompt for password.",
    ),
    role: Optional[UserRole] = typer.Option(
        None,
        "--role",
        help="User role.",
        case_sensitive=False,
    ),
    autologin: Optional[bool] = typer.Option(
        None,
        "--autologin/--no-autologin",
        help="Enable/disable auto-login",
        show_default=False,
    ),
    autologout: Optional[str] = typer.Option(
        None,
        help="User session lifetime in seconds. Set to 0 to never expire. Can be a time unit with suffix (0s, 15m, 1h, 1d, etc.)",
    ),
    # Legacy V2 positional args
    args: Optional[list[str]] = ARGS_POSITIONAL,
) -> None:
    """Update a user.

    Use [command]add_user_to_usergroup[/command] and [command]remove_user_from_usergroup[/command] to manage user groups.
    """
    from zabbix_cli.models import Result

    check_at_least_one_option_set(ctx)

    user = app.state.client.get_user(username)

    if new_password == "-":
        new_password = str_prompt("New password", password=True)
    elif new_password == "?":
        new_password = get_random_password()

    if new_password:
        if not old_password:
            exit_err("Old password is required when changing password.")
        if old_password == "-":
            old_password = str_prompt("Old password", password=True)

    app.state.client.update_user(
        user,
        current_password=old_password,
        new_password=new_password,
        first_name=first_name,
        last_name=last_name,
        role=role,
        autologin=autologin,
        autologout=autologout,
    )
    render_result(
        Result(
            message=f"Updated user {user.name!r} ({user.userid}).",
            result=user,
        ),
    )
