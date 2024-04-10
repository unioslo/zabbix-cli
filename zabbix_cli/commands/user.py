"""Commands to view and manage macros."""

from __future__ import annotations

import logging
from contextlib import suppress
from typing import List
from typing import Optional
from typing import TYPE_CHECKING
from typing import TypeVar

import typer
from strenum import StrEnum

from zabbix_cli._v2_compat import ARGS_POSITIONAL
from zabbix_cli.app import app
from zabbix_cli.app import Example
from zabbix_cli.exceptions import ZabbixAPIException
from zabbix_cli.exceptions import ZabbixNotFoundError
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import success
from zabbix_cli.output.console import warning
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.enums import GUIAccess
from zabbix_cli.pyzabbix.enums import UsergroupPermission
from zabbix_cli.pyzabbix.enums import UserRole
from zabbix_cli.utils.args import parse_bool_arg
from zabbix_cli.utils.args import parse_list_arg


if TYPE_CHECKING:
    from typing import Any  # noqa: F401
    from zabbix_cli.models import ColsRowsType  # noqa: F401
    from zabbix_cli.models import RowContent  # noqa: F401
    from zabbix_cli.models import RowsType  # noqa: F401
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
    username: str = typer.Argument(..., help="Username of the user to create."),
    first_name: Optional[str] = typer.Option(
        None, "--firstname", help="First name of the user to create."
    ),
    last_name: Optional[str] = typer.Option(
        None, "--lastname", help="Last name of the user to create."
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
    args: Optional[List[str]] = ARGS_POSITIONAL,
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
    username: str = typer.Argument(..., help="Username of the user to update"),
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
        None, "--autologin/--no-autologin", help="Enable/disable auto-login"
    ),
    autologout: Optional[str] = typer.Option(
        None,
        help="User session lifetime in seconds. Set to 0 to never expire. Can be a time unit with suffix (0s, 15m, 1h, 1d, etc.)",
    ),
    # Legacy V2 positional args
    args: Optional[List[str]] = ARGS_POSITIONAL,
) -> None:
    """Update a user.

    Use [command]add_user_to_usergroup[/command] and [command]remove_user_from_usergroup[/command] to manage user groups."""
    from zabbix_cli.models import Result

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


@app.command("remove_user", rich_help_panel=HELP_PANEL)
def remove_user(
    ctx: typer.Context,
    username: str = typer.Argument(..., help="Username to remove."),
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
    username: str = typer.Argument(..., help="Username of user"),
) -> None:
    """Show a user."""
    user = app.state.client.get_user(username)
    render_result(user)


@app.command("show_users", rich_help_panel=HELP_PANEL)
def show_users(
    ctx: typer.Context,
    limit: Optional[int] = typer.Option(
        None, "--limit", help="Limit the number of users shown."
    ),
    username: Optional[str] = typer.Option(
        None, "--username", help="Filter users by username. Supports wildcards."
    ),
    role: Optional[UserRole] = typer.Option(
        None,
        "--role",
        help="Filter users by role.",
        case_sensitive=False,
    ),
) -> None:
    """Show all users."""
    from zabbix_cli.models import AggregateResult

    search = bool(username or role)
    users = app.state.client.get_users(username=username, role=role, search=search)
    if limit:
        users = users[: abs(limit)]
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


@app.command("create_notification_user", rich_help_panel=HELP_PANEL)
def create_notification_user(
    ctx: typer.Context,
    sendto: str = typer.Argument(
        ...,
        help="E-mail address, SMS number, jabber address, etc.",
        show_default=False,
    ),
    mediatype: str = typer.Argument(
        ...,
        help="A media type defined in Zabbix.",
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
    args: Optional[List[str]] = ARGS_POSITIONAL,
) -> None:
    # TODO: Improve phrasing of this help text. "Defining media for usergroup"???
    """Create a notification user.

    Notification users can be used to send notifications when a Zabbix
    event happens.

    Sometimes we need to send a notification to a place not owned by any
    user in particular, e.g. an email list or jabber channel but Zabbix has
    not the possibility of defining media for a usergroup.

    This is the reason we use *notification users*. They are users nobody
    owns, but that can be used by other users to send notifications to the
    media defined in the notification user profile.

    Run [green]show_media_types[/green] to get a list of available media types.

    Falls back on the user group defined in the config file if no user groups are specified.
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
            f"Media type {mediatype!r} does not exist. Run [green]show_media_types[/green] command to get a list of available media types."
        )

    with app.status("Fetching usergroup(s)..."):
        if usergroups:
            ug_list = parse_list_arg(usergroups)
        else:
            ug_list = app.state.config.app.default_notification_users_usergroups
        ugroups = [app.state.client.get_usergroup(ug) for ug in ug_list]

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


@app.command("add_user_to_usergroup", rich_help_panel=HELP_PANEL)
def add_user_to_usergroup(
    ctx: typer.Context,
    usernames: str = typer.Argument(..., help="Usernames to add. Comma-separated."),
    usergroups: Optional[str] = typer.Argument(
        None,
        help="User groups to add the users to. Comma-separated.",
    ),
) -> None:
    """Adds user(s) to usergroup(s).

    Ignores users not in user groups. Users and groups must exist."""
    from zabbix_cli.commands.results.user import UsergroupAddUsers

    # FIXME: requires support for IDs for parity with V2
    unames = parse_list_arg(usernames)
    ugroups = parse_list_arg(usergroups)

    with app.status("Adding users to user groups"):
        users = [app.state.client.get_user(u) for u in unames]
        for ugroup in ugroups:
            try:
                app.state.client.add_usergroup_users(ugroup, users)
            except ZabbixAPIException as e:
                exit_err(f"Failed to add users to user group {ugroup!r}: {e}")

    render_result(
        UsergroupAddUsers(
            usergroups=ugroups,
            users=[u.username for u in users],
        ),
    )
    success("Added users to user groups.")


@app.command("remove_user_from_usergroup", rich_help_panel=HELP_PANEL)
def remove_user_from_usergroup(
    ctx: typer.Context,
    usernames: str = typer.Argument(..., help="Usernames to remove. Comma-separated."),
    usergroups: str = typer.Argument(
        ...,
        help="User groups to remove the users from. Comma-separated.",
    ),
) -> None:
    """Removes user(s) from usergroup(s).

    Ignores users not in user groups. Users and groups must exist."""
    from zabbix_cli.commands.results.user import UsergroupRemoveUsers

    # FIXME: requires support for IDs for parity with V2
    unames = parse_list_arg(usernames)
    ugroups = parse_list_arg(usergroups)

    with app.status("Removing users from user groups"):
        users = [app.state.client.get_user(u) for u in unames]
        for ugroup in ugroups:
            try:
                app.state.client.remove_usergroup_users(ugroup, users)
            except ZabbixAPIException as e:
                exit_err(f"Failed to remove users from user group {ugroup!r}: {e}")

    render_result(
        UsergroupRemoveUsers(
            usergroups=ugroups,
            users=[u.username for u in users],
        ),
    )
    success("Removed users from user groups.")


@app.command("create_usergroup", rich_help_panel=HELP_PANEL)
def create_usergroup(
    ctx: typer.Context,
    usergroup: str = typer.Argument(..., help="Name of the user group to create."),
    gui_access: GUIAccess = typer.Option(
        GUIAccess.DEFAULT.value, "--gui", help="GUI access for the group."
    ),
    disabled: bool = typer.Option(
        False,
        "--disabled",
        is_flag=True,
        help="Create the user group in a disabled state.",
    ),
    # V2 legacy args
    args: Optional[List[str]] = ARGS_POSITIONAL,
) -> None:
    """Create a user group."""
    # We already have name and GUI access, so we expect 1 more arg at most
    if args:
        if len(args) != 1:
            exit_err(
                "Invalid number of positional arguments. Please use options instead."
            )
        disabled = parse_bool_arg(args[0])

    # Check if group exists already
    with suppress(ZabbixNotFoundError):
        app.state.client.get_usergroup(usergroup)
        exit_err(f"User group {usergroup!r} already exists.")

    # Create group
    with app.status("Creating user group"):
        usergroupid = app.state.client.create_usergroup(
            usergroup, gui_access=gui_access, disabled=disabled
        )
    success(f"Created user group {usergroup!r} ({usergroupid}).")


class UsergroupSorting(StrEnum):
    NAME = "name"
    ID = "id"
    USERS = "users"


def sort_ugroups(
    ugroups: List[UsergroupLikeT], sort: UsergroupSorting
) -> List[UsergroupLikeT]:
    if sort == UsergroupSorting.NAME:
        return sorted(ugroups, key=lambda ug: ug.name)
    elif sort == UsergroupSorting.ID:
        # NOTE: this can fail if user group IDs are not integers (API returns strings)
        # We should potentially just coerce them to ints in the model
        try:
            return sorted(ugroups, key=lambda ug: int(ug.usrgrpid))
        except Exception as e:
            logging.error(f"Failed to sort user groups by ID: {e}")
            # Fall back on unsorted (likely sorted by ID anyway)
    return ugroups


OPTION_SORT_UGROUPS = typer.Option(
    UsergroupSorting.NAME,
    "--sort",
    help="Sort by field.",
    case_sensitive=False,
)


@app.command(
    "show_usergroup",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Show user group 'Admins'",
            "show_usergroup Admins",
        ),
        Example(
            "Show user groups 'Admins' and 'Operators'",
            "show_usergroup Admins,Operators",
        ),
        Example(
            "Show all user groups containing 'web' sorted by ID",
            "show_usergroup '*web*' --sort id",
        ),
    ],
)
def show_usergroup(
    ctx: typer.Context,
    usergroup: str = typer.Argument(
        ...,
        help="Name of the user group(s) to show. Comma-separated. Supports wildcards.",
    ),
    sort: UsergroupSorting = OPTION_SORT_UGROUPS,
) -> None:
    """Show details for user group(s)."""
    from zabbix_cli.commands.results.user import ShowUsergroupResult
    from zabbix_cli.models import AggregateResult

    ugs = parse_list_arg(usergroup)
    usergroups = app.state.client.get_usergroups(
        *ugs, select_users=True, select_rights=True, search=True
    )
    res = []
    for ugroup in usergroups:
        res.append(ShowUsergroupResult.from_usergroup(ugroup))

    render_result(AggregateResult(result=sort_ugroups(res, sort)))


@app.command("show_usergroups", rich_help_panel=HELP_PANEL)
def show_usergroups(
    ctx: typer.Context, sort: UsergroupSorting = OPTION_SORT_UGROUPS
) -> None:
    """Show all user groups."""
    from zabbix_cli.commands.results.user import ShowUsergroupResult
    from zabbix_cli.models import AggregateResult

    usergroups = app.state.client.get_usergroups(select_users=True, search=True)
    res = []
    for ugroup in usergroups:
        res.append(ShowUsergroupResult.from_usergroup(ugroup))
    render_result(AggregateResult(result=sort_ugroups(res, sort)))


@app.command(
    "show_usergroup_permissions",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Show permissions for user group 'Admins'",
            "show_usergroup_permissions Admins",
        ),
        Example(
            "Show permissions for user groups 'Admins' and 'Operators'",
            "show_usergroup_permissions Admins,Operators",
        ),
        Example(
            "Show permissions for all user groups sorted by ID",
            "show_usergroup_permissions * --sort id",
        ),
    ],
)
def show_usergroup_permissions(
    ctx: typer.Context,
    usergroup: str = typer.Argument(
        ..., help="Name of user group. Comma-separated. Supports wildcards."
    ),
    sort: UsergroupSorting = OPTION_SORT_UGROUPS,
) -> None:
    """Show permissions for one or more user groups."""
    # FIXME: URGENT Does not work properly in 6.0.22

    # NOTE: this command breaks JSON output compatibility with V2
    # In V2, rights were serialized as a string in the format of "<NAME> (<RO/RW/DENY>)"
    # under the key "permissions".
    # In V3, we follow the API and serialize it as a list of dicts under the key
    # "rights" in <6.2.0 and "hostgroup_rights" and "templategroup_rights" in >=6.2.0
    from zabbix_cli.commands.results.user import ShowUsergroupPermissionsResult
    from zabbix_cli.models import AggregateResult

    ugs = parse_list_arg(usergroup)
    usergroups = app.state.client.get_usergroups(*ugs, select_rights=True, search=True)

    if not usergroups:
        exit_err("No user groups found.")

    with app.status("Fetching host groups..."):
        hostgroups = app.state.client.get_hostgroups()
    if app.state.client.version.release >= (6, 2, 0):
        with app.status("Fetching template groups..."):
            templategroups = app.state.client.get_templategroups()
    else:
        templategroups = []
    res = []  # type: list[ShowUsergroupPermissionsResult]
    for ugroup in usergroups:
        res.append(
            ShowUsergroupPermissionsResult.from_usergroup(
                ugroup, hostgroups=hostgroups, templategroups=templategroups
            )
        )
    render_result(AggregateResult(result=sort_ugroups(res, sort)))


# NOTE: {add,update}_usergroup_permissions seem to be the exact same command in V2. Keeping that here.
@app.command("add_usergroup_permissions", rich_help_panel=HELP_PANEL)
@app.command("update_usergroup_permissions", rich_help_panel=HELP_PANEL)
def add_usergroup_permissions(
    ctx: typer.Context,
    usergroup: str = typer.Argument(..., help="User group to give permissions to."),
    hostgroups: Optional[str] = typer.Option(
        None,
        "--hostgroups",
        help="Comma-separated list of host group names.",
    ),
    templategroups: Optional[str] = typer.Option(
        None,
        "--templategroups",
        help="Comma-separated list of template group names.",
    ),
    permission: Optional[UsergroupPermission] = typer.Option(
        None,
        "--permission",
        help="Permission to give to the user group.",
        case_sensitive=False,
    ),
    # Legacy V2 args
    args: Optional[List[str]] = ARGS_POSITIONAL,
) -> None:
    """Gives a user group permissions to host groups and template groups.

    Run [green]show_hostgroups[/] to get a list of host groups, and
    [green]show_templategroups --no-templates[/] to get a list of template groups.
    """
    from zabbix_cli.commands.results.user import AddUsergroupPermissionsResult

    # Legacy positional args: <usergroup> <hostgroups> <permission>
    # We already have usergroup as positional arg, so we are left with 2 args.
    if args:
        warning("Positional arguments are deprecated. Please use options instead.")
        if len(args) != 2:
            exit_err(
                "Invalid number of positional arguments. Please use options instead."
            )
        hostgroups = hostgroups or args[0]
        permission = permission or UsergroupPermission(args[1])

    hgroups = parse_list_arg(hostgroups)
    tgroups = parse_list_arg(templategroups)

    if not hgroups and not tgroups:
        exit_err("At least one host group or template group must be specified.")

    if not permission:
        permission = UsergroupPermission.from_prompt()

    if hgroups:
        with app.status("Adding host group permissions..."):
            app.state.client.update_usergroup_rights(
                usergroup, hgroups, permission, hostgroup=True
            )
        success("Added host group permissions.")

    if tgroups:
        with app.status("Adding template group permissions..."):
            app.state.client.update_usergroup_rights(
                usergroup, tgroups, permission, hostgroup=False
            )
        success("Added template group permissions.")

    render_result(
        AddUsergroupPermissionsResult(
            usergroup=usergroup,
            hostgroups=hgroups,
            templategroups=tgroups,
            permission=permission,
        ),
    )
