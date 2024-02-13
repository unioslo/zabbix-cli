"""Commands to view and manage macros."""
from __future__ import annotations

import hashlib
import random
from contextlib import suppress
from typing import Dict
from typing import List
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union

import rich.box
import typer
from pydantic import computed_field
from pydantic import Field
from pydantic import field_validator

from zabbix_cli._v2_compat import ARGS_POSITIONAL
from zabbix_cli.app import app
from zabbix_cli.exceptions import ZabbixAPIException
from zabbix_cli.exceptions import ZabbixNotFoundError
from zabbix_cli.models import AggregateResult
from zabbix_cli.models import META_KEY_JOIN_CHAR
from zabbix_cli.models import Result
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import success
from zabbix_cli.output.console import warning
from zabbix_cli.output.prompts import bool_prompt
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.types import GUIAccess
from zabbix_cli.pyzabbix.types import HostGroup
from zabbix_cli.pyzabbix.types import TemplateGroup
from zabbix_cli.pyzabbix.types import User
from zabbix_cli.pyzabbix.types import Usergroup
from zabbix_cli.pyzabbix.types import UserMedia
from zabbix_cli.pyzabbix.types import ZabbixRight
from zabbix_cli.utils.args import parse_bool_arg
from zabbix_cli.utils.args import parse_list_arg
from zabbix_cli.utils.args import UsergroupPermission
from zabbix_cli.utils.args import UserRole
from zabbix_cli.utils.utils import get_gui_access
from zabbix_cli.utils.utils import get_permission
from zabbix_cli.utils.utils import get_usergroup_status


if TYPE_CHECKING:
    from typing import Any  # noqa: F401
    from zabbix_cli.models import ColsRowsType  # noqa: F401
    from zabbix_cli.models import RowContent  # noqa: F401
    from zabbix_cli.models import RowsType  # noqa: F401

# # `zabbix-cli host user <cmd>`
# user_cmd = StatefulApp(
#     name="user",
#     help="Host user commands.",
# )
# app.add_subcommand(user_cmd)

HELP_PANEL = "User"


def get_random_password() -> str:
    x = hashlib.md5()
    x.update(str(random.randint(1, 1000000)).encode("ascii"))
    return x.hexdigest()


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
    # Legacy V2 positional args
    args: Optional[List[str]] = ARGS_POSITIONAL,
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
        password = get_random_password()
    if not role:
        role = UserRole.from_prompt(default=UserRole.USER.value)

    if autologin is None:
        autologin = bool_prompt("Enable auto-login", default=False)

    if autologout is None:
        # Can also be time unit with suffix (0s, 15m, 1h, 1d, etc.)
        autologout = str_prompt("User session lifetime", default="86400")

    if not groups:
        groups = str_prompt("Groups (comma-separated)", default="", empty_ok=True)
    grouplist = parse_list_arg(groups)
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


@app.command("create_notification_user", rich_help_panel=HELP_PANEL)
def create_notification_user(
    ctx: typer.Context,
    sendto: Optional[str] = typer.Argument(
        None,
        help="E-mail address, SMS number, jabber address, etc.",
        show_default=False,
    ),
    mediatype: Optional[str] = typer.Argument(
        None,
        help="A media type defined in Zabbix. E.g. [green]'Email'[/green]. [yellow]WARNING: Case sensitive![/yellow]",
        show_default=False,
    ),
    remarks: Optional[str] = typer.Option(
        None,
        "--remarks",
        help="Remarks about the notification user to include in username (max 20 chars).",
    ),
    usergroups: Optional[str] = typer.Option(
        None,
        "--usergroups",
        help="Comma-separated list of usergroups to add the user to. Overrides user groups in config file.",
    ),
    username: Optional[str] = typer.Option(
        None,
        "--username",
        help="Override generated username. Ignores --remarks.",
    ),
    # Legacy V2 args
    args: Optional[List[str]] = ARGS_POSITIONAL,
) -> None:
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

    The configuration file option [green]default_notification_users_usergroup[/green]
    must be configured if [green]--usergroups[/green] is not specified.
    """
    if args:
        # Old args format: <sendto> <mediatype> <remarks>
        # We already have sendto and mediatype, so we are left with 1 arg.
        if len(args) != 1:
            exit_err(
                "Invalid number of positional arguments. Please use options instead."
            )
        remarks = args[0]
    remarks = remarks or ""

    if not sendto:
        sendto = str_prompt("Send to")

    if not mediatype:
        mediatype = str_prompt("Media type")

    # Generate username
    if username and remarks:
        warning("Both --username and --remarks specified. Ignoring --remarks.")

    if username:
        username = username.strip()
    elif remarks.strip() == "":
        username = "notification-user-" + sendto.replace(".", "-")
    else:
        username = (
            "notification-user-"
            + remarks.strip()[:20].replace(" ", "_")
            + "-"
            + sendto.replace(".", "-")
        )

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

    with app.status("Fetching usergroup(s)"):
        if usergroups:
            ug_list = parse_list_arg(usergroups)
        else:
            ug_list = app.state.config.app.default_notification_users_usergroups
        if not ug_list:
            exit_err(
                "No usergroups specified. "
                "Please specify usergroups with the --usergroups option "
                "or configure [green]default_notification_users_usergroup[/green] "
                "in the config file."
            )
        ugroups = [app.state.client.get_usergroup(ug) for ug in ug_list]
        if not ugroups:
            exit_err("No usergroups found.")

    user_media = [
        UserMedia(
            mediatypeid=mt.mediatypeid,
            sendto=sendto,
            active=0,  # enabled
            severity=63,  # all
            period="1-7,00:00-24:00",  # 24/7
        )
    ]

    with app.status("Creating user"):
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


class UgroupUpdateUsersResult(TableRenderable):
    usergroups: List[str]
    users: List[str]

    def __cols_rows__(self) -> ColsRowsType:
        return (
            ["Usergroups", "Users"],
            [["\n".join(self.usergroups), ", ".join(self.users)]],
        )


class UsergroupAddUsers(UgroupUpdateUsersResult):
    __title__ = "Added Users"


class UsergroupRemoveUsers(UgroupUpdateUsersResult):
    __title__ = "Removed Users"


@app.command("add_user_to_usergroup", rich_help_panel=HELP_PANEL)
def add_user_to_usergroup(
    ctx: typer.Context,
    usernames: Optional[str] = typer.Argument(
        None, help="Comma-separated list of usernames"
    ),
    usergroups: Optional[str] = typer.Argument(
        None,
        help="Comma-separated list of user groups to add the users to. [yellow]WARNING: Case sensitive![/yellow]]",
    ),
) -> None:
    """Adds user(s) to usergroup(s).

    Ignores users not in user groups. Users and groups must exist."""
    # FIXME: requires support for IDs for parity with V2
    if not usernames:
        usernames = str_prompt("Usernames")
    unames = parse_list_arg(usernames)

    if not usergroups:
        usergroups = str_prompt("User groups")
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
    usernames: Optional[str] = typer.Argument(
        None, help="Comma-separated list of usernames to remove."
    ),
    usergroups: Optional[str] = typer.Argument(
        None,
        help="Comma-separated list of user groups to remove the users from. [yellow]WARNING: Case sensitive![/yellow]]",
    ),
) -> None:
    """Removes user(s) from usergroup(s).

    Ignores users not in user groups. Users and groups must exist."""
    # FIXME: requires support for IDs for parity with V2
    if not usernames:
        usernames = str_prompt("Usernames")
    unames = parse_list_arg(usernames)

    if not usergroups:
        usergroups = str_prompt("User groups")
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
    usergroup: Optional[str] = typer.Argument(
        None, help="Name of the user group to create."
    ),
    gui_access: Optional[GUIAccess] = typer.Argument(
        None, help="GUI access for the group.."
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

    if not usergroup:
        usergroup = str_prompt("User group")

    if not gui_access:
        gui_access = GUIAccess.from_prompt(default=GUIAccess.DEFAULT)

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


class GroupRights(TableRenderable):
    __box__ = rich.box.MINIMAL

    groups: Union[Dict[str, HostGroup], Dict[str, TemplateGroup]] = Field(
        default_factory=dict,
    )

    rights: List[ZabbixRight] = Field(
        default_factory=list,
        description="Group rights for the user group.",
    )

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["Name", "Permission"]
        rows = []  # type: RowsType
        for right in self.rights:
            group = self.groups.get(right.id, None)
            if group:
                group_name = group.name
            else:
                group_name = "Unknown"
            rows.append([group_name, str(UsergroupPermission(right.permission))])
        return cols, rows


class ShowUsergroupResult(TableRenderable):
    usrgrpid: str
    name: str
    gui_access: str = Field(..., json_schema_extra={"header": "GUI Access"})
    status: str
    users: List[str] = Field(
        default_factory=list, json_schema_extra={META_KEY_JOIN_CHAR: ", "}
    )
    hostgroup_rights: List[ZabbixRight] = []
    templategroup_rights: List[ZabbixRight] = []

    @classmethod
    def from_usergroup(cls, usergroup: Usergroup) -> ShowUsergroupResult:
        return cls(
            name=usergroup.name,
            usrgrpid=usergroup.usrgrpid,
            gui_access=usergroup.gui_access_str,
            status=usergroup.users_status_str,
            users=[user.username for user in usergroup.users],
        )

    @field_validator("gui_access")
    @classmethod
    def _validate_gui_access(cls, v: Any) -> str:
        if isinstance(v, int):
            return get_gui_access(v)
        return v

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: Any) -> str:
        if isinstance(v, int):
            return get_usergroup_status(v)
        return v


class ShowUsergroupPermissionsResult(Usergroup):
    hostgroups: Dict[str, HostGroup] = Field(
        default_factory=dict,
        exclude=True,
        description="Host groups the user group has access to. Used to render host group rights.",
    )
    templategroups: Dict[str, TemplateGroup] = Field(
        default_factory=dict,
        exclude=True,
        description="Mapping of all template groups. Used to render template group rights.",
    )

    @classmethod
    def from_usergroup(
        cls,
        usergroup: Usergroup,
        hostgroups: list[HostGroup],
        templategroups: list[TemplateGroup],
    ) -> ShowUsergroupPermissionsResult:
        ug = cls.model_validate(usergroup, from_attributes=True)
        if hostgroups:
            ug.hostgroups = {hg.groupid: hg for hg in hostgroups}
        if templategroups:
            ug.templategroups = {tg.groupid: tg for tg in templategroups}
        return ug

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["ID", "Name", "Host Group Rights"]
        row = [self.usrgrpid, self.name]  # type: RowContent

        # Host group rights table
        row.append(
            GroupRights(groups=self.hostgroups, rights=self.hostgroup_rights).as_table()
        )

        # Template group rights table
        if self.zabbix_version.release >= (6, 2, 0):
            cols.append("Template Group Rights")
            row.append(
                GroupRights(
                    groups=self.templategroups, rights=self.templategroup_rights
                ).as_table()
            )
        return cols, [row]


@app.command("show_usergroup", rich_help_panel=HELP_PANEL)
def show_usergroup(
    ctx: typer.Context,
    usergroup: List[str] = typer.Argument(
        None, help="Name of the user group to show. Supports wildcards. Can be repeated"
    ),
) -> None:
    """Show details for one or more user groups."""
    if not usergroup:
        usergroup = parse_list_arg(str_prompt("User group"))
    usergroups = app.state.client.get_usergroups(
        *usergroup, select_users=True, select_rights=True, search=True
    )
    res = []
    for ugroup in usergroups:
        res.append(ShowUsergroupResult.from_usergroup(ugroup))
    render_result(AggregateResult(result=res))


@app.command("show_usergroups", rich_help_panel=HELP_PANEL)
def show_usergroups(ctx: typer.Context) -> None:
    """Show all user groups."""
    usergroups = app.state.client.get_usergroups(select_users=True, search=True)
    res = []
    for ugroup in usergroups:
        res.append(ShowUsergroupResult.from_usergroup(ugroup))
    render_result(AggregateResult(result=res))


@app.command("show_usergroup_permissions", rich_help_panel=HELP_PANEL)
def show_usergroup_permissions(
    ctx: typer.Context,
    usergroup: str = typer.Argument(
        ..., help="Name of user group. Comma-separated. Supports wildcards."
    ),
) -> None:
    """Show permissions for one or more user groups."""
    # NOTE: this command breaks JSON output compatibility with V2
    # In V2, rights were serialized as a string in the format of "<NAME> (<RO/RW/DENY>)"
    # under the key "permissions".
    # In V3, we follow the API and serialize it as a list of dicts under the key
    # "rights" in <6.2.0 and "hostgroup_rights" and "templategroup_rights" in >=6.2.0
    ugs = parse_list_arg(usergroup)
    usergroups = app.state.client.get_usergroups(*ugs, select_rights=True, search=True)

    if not usergroups:
        exit_err("No user groups found.")

    hostgroups = app.state.client.get_hostgroups()
    if app.state.client.version.release >= (6, 2, 0):
        templategroups = app.state.client.get_templategroups()
    else:
        templategroups = []
    res = []
    for ugroup in usergroups:
        res.append(
            ShowUsergroupPermissionsResult.from_usergroup(
                ugroup, hostgroups=hostgroups, templategroups=templategroups
            )
        )
    render_result(AggregateResult(result=res))


class AddUsergroupPermissionsResult(TableRenderable):
    usergroup: str
    hostgroups: List[str]
    templategroups: List[str]
    permission: UsergroupPermission

    @computed_field  # type: ignore # computed field on @property
    @property
    def permission_str(self) -> str:
        return get_permission(self.permission.as_api_value())

    def __cols_rows__(self) -> ColsRowsType:
        return (
            [
                "Usergroup",
                "Host Groups",
                "Template Groups",
                "Permission",
            ],
            [
                [
                    self.usergroup,
                    ", ".join(self.hostgroups),
                    ", ".join(self.templategroups),
                    self.permission_str,
                ],
            ],
        )


# NOTE: {add,update}_usergroup_permissions seem to be the exact same command in V2. Keeping that here.
@app.command("add_usergroup_permissions", rich_help_panel=HELP_PANEL)
@app.command("update_usergroup_permissions", rich_help_panel=HELP_PANEL)
def add_usergroup_permissions(
    ctx: typer.Context,
    usergroup: Optional[str] = typer.Argument(
        None, help="User group to give permissions to."
    ),
    hostgroups: Optional[str] = typer.Option(
        None,
        "--hostgroups",
        help="Comma-separated list of host group names. [yellow]WARNING: Case sensitive![/yellow]]",
    ),
    templategroups: Optional[str] = typer.Option(
        None,
        "--templategroups",
        help="Comma-separated list of template group names. [yellow]WARNING: Case sensitive![/yellow]]",
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

    if not usergroup:
        usergroup = str_prompt("User group")

    # Only prompt if no group options
    if not hostgroups and not templategroups:
        hostgroups = str_prompt("Host groups", empty_ok=True, default="")
    hgroups = parse_list_arg(hostgroups)

    # Ditto
    if not templategroups and not hostgroups:
        templategroups = str_prompt("Template groups", empty_ok=True, default="")
    tgroups = parse_list_arg(templategroups)

    if not hgroups and not tgroups:
        exit_err("At least one host group or template group must be specified.")

    if not permission:
        permission = UsergroupPermission.from_prompt()

    if hgroups:
        with app.status("Adding host group permissions"):
            try:
                app.state.client.update_usergroup_rights(
                    usergroup, hgroups, permission, hostgroup=True
                )
            except ZabbixAPIException as e:
                exit_err(f"Failed to add host group permissions: {e}")
        success("Added host group permissions.")

    if tgroups:
        with app.status("Adding template group permissions"):
            try:
                app.state.client.update_usergroup_rights(
                    usergroup, tgroups, permission, hostgroup=False
                )
            except ZabbixAPIException as e:
                exit_err(f"Failed to add template group permissions: {e}")
        success("Added template group permissions.")

    render_result(
        AddUsergroupPermissionsResult(
            usergroup=usergroup,
            hostgroups=hgroups,
            templategroups=tgroups,
            permission=permission,
        ),
    )
