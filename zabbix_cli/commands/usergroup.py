"""Commands for managing user groups."""

from __future__ import annotations

import logging
from contextlib import suppress
from typing import TYPE_CHECKING
from typing import Optional
from typing import TypeVar

import typer
from strenum import StrEnum

from zabbix_cli._v2_compat import ARGS_POSITIONAL
from zabbix_cli.app import Example
from zabbix_cli.app import app
from zabbix_cli.commands.common.args import OPTION_LIMIT
from zabbix_cli.exceptions import ZabbixAPIException
from zabbix_cli.exceptions import ZabbixNotFoundError
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import success
from zabbix_cli.output.console import warning
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.enums import GUIAccess
from zabbix_cli.pyzabbix.enums import UsergroupPermission
from zabbix_cli.utils.args import parse_bool_arg
from zabbix_cli.utils.args import parse_list_arg

if TYPE_CHECKING:
    from typing import Protocol

    class UsergroupLike(Protocol):
        name: str
        usrgrpid: str

    UsergroupLikeT = TypeVar("UsergroupLikeT", bound=UsergroupLike)


class UsergroupSorting(StrEnum):
    NAME = "name"
    ID = "id"
    USERS = "users"


def sort_ugroups(
    ugroups: list[UsergroupLikeT], sort: UsergroupSorting
) -> list[UsergroupLikeT]:
    """Sort result types based on user group objects.

    I.e. we have some custom types that all share the samse attributes
    `name` and `usrgrpid`. This function sorts them based on the given
    sorting method."""
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

HELP_PANEL = "User Group"


@app.command("add_user_to_usergroup", rich_help_panel=HELP_PANEL)
def add_user_to_usergroup(
    ctx: typer.Context,
    usernames: str = typer.Argument(
        help="Usernames to add. Comma-separated.",
        show_default=False,
    ),
    usergroups: str = typer.Argument(
        help="User groups to add the users to. Comma-separated.",
        show_default=False,
    ),
) -> None:
    """Add users to usergroups.

    Ignores users not in user groups. Users and groups must exist.
    """
    from zabbix_cli.commands.results.usergroup import UsergroupAddUsers

    # FIXME: requires support for IDs for parity with V2
    unames = parse_list_arg(usernames)
    ugroups = parse_list_arg(usergroups)

    with app.status("Adding users to user groups..."):
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


# NOTE: {add,update}_usergroup_permissions seem to be the exact same command in V2. Keeping that here.
@app.command("add_usergroup_permissions", rich_help_panel=HELP_PANEL)
@app.command("update_usergroup_permissions", rich_help_panel=HELP_PANEL, hidden=True)
def add_usergroup_permissions(
    ctx: typer.Context,
    usergroup: str = typer.Argument(
        help="User group to give permissions to.",
        show_default=False,
    ),
    hostgroups: Optional[str] = typer.Option(
        None,
        "--hostgroup",
        help="Comma-separated list of host group names.",
    ),
    templategroups: Optional[str] = typer.Option(
        None,
        "--templategroup",
        help="Comma-separated list of template group names.",
    ),
    permission: Optional[UsergroupPermission] = typer.Option(
        None,
        "--permission",
        help="Permission to give to the user group.",
        case_sensitive=False,
    ),
    # Legacy V2 args
    args: Optional[list[str]] = ARGS_POSITIONAL,
) -> None:
    """Give a user group permissions to host/template groups.

    Run [command]show_hostgroups[/] to get a list of host groups, and
    [command]show_templategroups --no-templates[/] to get a list of template groups.
    """
    from zabbix_cli.commands.results.usergroup import AddUsergroupPermissionsResult

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
        permission = UsergroupPermission.from_prompt(
            default=UsergroupPermission.READ_WRITE
        )

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


@app.command("create_usergroup", rich_help_panel=HELP_PANEL)
def create_usergroup(
    ctx: typer.Context,
    usergroup: str = typer.Argument(
        help="Name of the user group to create.",
        show_default=False,
    ),
    gui_access: GUIAccess = typer.Option(
        GUIAccess.DEFAULT.value, "--gui", help="GUI access for the group."
    ),
    disabled: bool = typer.Option(
        False,
        "--disabled",
        help="Create the user group in a disabled state.",
    ),
    # V2 legacy args
    args: Optional[list[str]] = ARGS_POSITIONAL,
) -> None:
    """Create a user group."""
    # We already have name and GUI access, so we expect 1 more arg at most
    if args:
        if len(args) != 1:
            exit_err(
                "Invalid number of positional arguments. Please use options instead."
            )
        disabled = parse_bool_arg(args[0])

    with suppress(ZabbixNotFoundError):
        app.state.client.get_usergroup(usergroup)
        exit_err(f"User group {usergroup!r} already exists.")

    with app.status("Creating user group"):
        usergroupid = app.state.client.create_usergroup(
            usergroup, gui_access=gui_access, disabled=disabled
        )
    success(f"Created user group {usergroup!r} ({usergroupid}).")


@app.command("remove_user_from_usergroup", rich_help_panel=HELP_PANEL)
def remove_user_from_usergroup(
    ctx: typer.Context,
    usernames: str = typer.Argument(
        help="Usernames to remove. Comma-separated.",
        show_default=False,
    ),
    usergroups: str = typer.Argument(
        help="User groups to remove the users from. Comma-separated.",
        show_default=False,
    ),
) -> None:
    """Remove users from usergroups.

    Ignores users not in user groups. Users and groups must exist.
    """
    from zabbix_cli.commands.results.usergroup import UsergroupRemoveUsers

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
        help="Name or ID of the user group(s) to show. Comma-separated. Supports wildcards.",
        show_default=False,
    ),
    sort: UsergroupSorting = OPTION_SORT_UGROUPS,
) -> None:
    """Show one or more user groups by name or ID."""
    _do_show_usergroups(usergroup, sort)


@app.command(
    "show_usergroups",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Show all user groups",
            "show_usergroups",
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
def show_usergroups(
    ctx: typer.Context,
    usergroup: Optional[str] = typer.Argument(
        None,
        help="Name or ID of the user group(s) to show. Comma-separated. Supports wildcards.",
        show_default=False,
    ),
    sort: UsergroupSorting = OPTION_SORT_UGROUPS,
    limit: Optional[int] = OPTION_LIMIT,
) -> None:
    """Show all suser groups.

    Can be filtered by name or ID."""
    _do_show_usergroups(usergroup, sort=sort, limit=limit)


def _do_show_usergroups(
    usergroup: Optional[str],
    sort: UsergroupSorting,
    limit: Optional[int] = None,
) -> None:
    from zabbix_cli.commands.results.usergroup import ShowUsergroupResult
    from zabbix_cli.models import AggregateResult

    ugs = parse_list_arg(usergroup)
    with app.status("Fetching user groups..."):
        usergroups = app.state.client.get_usergroups(
            *ugs, select_users=True, search=True, limit=limit
        )
    res: list[ShowUsergroupResult] = []
    for ugroup in usergroups:
        res.append(ShowUsergroupResult.from_usergroup(ugroup))
    # NOTE: why client-side sorting?
    res = sort_ugroups(res, sort)
    render_result(AggregateResult(result=res))


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
        help="Name of user group. Comma-separated. Supports wildcards.",
        show_default=False,
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
    from zabbix_cli.commands.results.usergroup import ShowUsergroupPermissionsResult
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
    res: list[ShowUsergroupPermissionsResult] = []
    for ugroup in usergroups:
        res.append(
            ShowUsergroupPermissionsResult.from_usergroup(
                ugroup, hostgroups=hostgroups, templategroups=templategroups
            )
        )
    render_result(AggregateResult(result=sort_ugroups(res, sort)))
