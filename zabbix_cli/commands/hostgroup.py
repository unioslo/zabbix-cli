from __future__ import annotations

from typing import Any
from typing import List
from typing import Optional
from typing import Tuple
from typing import TYPE_CHECKING

import typer
from pydantic import Field
from pydantic import field_validator
from typing_extensions import TypedDict

from zabbix_cli.app import app
from zabbix_cli.app import Example
from zabbix_cli.commands.host import HELP_PANEL
from zabbix_cli.models import AggregateResult
from zabbix_cli.models import Result
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import error
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.console import success
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import HostGroup
from zabbix_cli.utils.args import parse_list_arg
from zabbix_cli.utils.args import UsergroupPermission
from zabbix_cli.utils.utils import get_hostgroup_flag
from zabbix_cli.utils.utils import get_hostgroup_type
from zabbix_cli.utils.utils import get_permission

if TYPE_CHECKING:
    from zabbix_cli.models import ColsRowsType
    from zabbix_cli.models import RowsType  # noqa: F401


@app.command("add_host_to_hostgroup", rich_help_panel=HELP_PANEL)
def add_host_to_hostgroup(
    ctx: typer.Context,
    hostnames: Optional[str] = typer.Option(
        None, help="Hostnames or IDs. Separate values with commas."
    ),
    hostgroups: Optional[str] = typer.Option(
        None, help="Hostnames or IDs. Separate values with commas."
    ),
) -> None:
    """Adds one or more hosts to one or more host groups.

    Host{name,group} arguments are interpreted as IDs if they are numeric.
    """
    hosts, hgs = _parse_hostname_hostgroup_args(hostnames, hostgroups)
    query = {
        "hosts": [{"hostid": host.hostid} for host in hosts],
        "groups": [{"groupid": hg.groupid} for hg in hgs],
    }
    try:
        app.state.client.hostgroup.massadd(**query)
    except Exception as e:
        exit_err(f"Failed to add hosts to hostgroups: {e}")
    hnames = ", ".join(host.host for host in hosts)
    hgnames = ", ".join(hg.name for hg in hgs)
    render_result(Result(message=f"Added host(s) {hnames} to hostgroup(s) {hgnames}."))


def _parse_hostname_hostgroup_args(
    hostnames: Optional[str], hostgroups: Optional[str]
) -> Tuple[List[Host], List[HostGroup]]:
    """Helper function for parsing hostnames and hostgroups args."""
    # Prompt for missing arguments
    if not hostnames:
        hostnames = str_prompt("Host name(s)")
    hostname_args = parse_list_arg(hostnames)
    if not hostname_args:
        exit_err("No host names specified.")

    if not hostgroups:
        hostgroups = str_prompt("Host group(s)")
    hostgroup_args = parse_list_arg(hostgroups)
    if not hostgroup_args:
        exit_err("No host groups specified.")

    host_models = [app.state.client.get_host(hn) for hn in hostname_args]
    hg_models = [app.state.client.get_hostgroup(hg) for hg in hostgroup_args]

    return host_models, hg_models


@app.command(
    "create_hostgroup",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Create a host group with default user group permissions",
            "zabbix-cli create_hostgroup 'My Host Group'",
        ),
        Example(
            "Create a host group with specific RO and RW groups",
            "zabbix-cli create_hostgroup 'My Host Group' --ro-groups users --rw-groups admins",
        ),
        Example(
            "Create a host group with no user group permissions",
            "zabbix-cli create_hostgroup 'My Host Group' --no-usergroup-permissions",
        ),
    ],
)
def create_hostgroup(
    hostgroup: str = typer.Argument(None, help="Name of host group."),
    rw_groups: Optional[str] = typer.Option(
        None,
        help="User group(s) to give read/write permissions. Comma-separated.",
    ),
    ro_groups: Optional[str] = typer.Option(
        None,
        help="User group(s) to give read-only permissions. Comma-separated.",
    ),
    no_usergroup_permissions: bool = typer.Option(
        False,
        "--no-usergroup-permissions",
        help="Do not assign user group permissions.",
    ),
) -> None:
    """Create a new host group.

    Assigns permissions for user groups defined in configuration file
    unless --no-usergroup-permissions is specified.

    The user groups can be overridden with the --rw-groups and --ro-groups.
    """
    if not hostgroup:
        hostgroup = str_prompt("Host group name")

    if app.state.client.hostgroup_exists(hostgroup):
        exit_err(f"Host group {hostgroup!r} already exists.")

    # Create the host group
    hostgroup_id = app.state.client.create_hostgroup(hostgroup)
    info(f"Creating host group {hostgroup} ({hostgroup_id}).")

    app_config = app.state.config.app

    rw_grps = []  # type: list[str]
    ro_grps = []  # type: list[str]
    if not no_usergroup_permissions:
        rw_grps = parse_list_arg(rw_groups) or app_config.default_admin_usergroups
        ro_grps = parse_list_arg(ro_groups) or app_config.default_create_user_usergroups

    try:
        # Admin group(s) gets Read/Write
        for usergroup in rw_grps:
            app.state.client.update_usergroup_rights(
                usergroup, [hostgroup], UsergroupPermission.READ_WRITE, hostgroup=True
            )
            info(f"Assigned Read/Write permission for user group {usergroup!r}")
        # Default group(s) gets Read
        for usergroup in ro_grps:
            app.state.client.update_usergroup_rights(
                usergroup, [hostgroup], UsergroupPermission.READ_ONLY, hostgroup=True
            )
            info(f"Assigned Read-only permission for user group {usergroup!r}")
    except Exception as e:
        # All or nothing. Delete group if we fail to assign permissions.
        error(f"Failed to assign permissions to host group {hostgroup!r}: {e}")
        info("Deleting host group...")
        app.state.client.delete_hostgroup(hostgroup_id)

    render_result(Result(message=f"Created host group {hostgroup} ({hostgroup_id})."))


class HostGroupDeleteResult(TableRenderable):
    groups: List[str]


@app.command("remove_hostgroup", rich_help_panel=HELP_PANEL)
def delete_hostgroup(
    hostgroup: str = typer.Argument(
        ..., help="Name of host group(s) to delete. Comma-separated."
    ),
) -> None:
    """Delete a host group."""
    hostgroup_names = parse_list_arg(hostgroup)

    hostgroups = [app.state.client.get_hostgroup(hg) for hg in hostgroup_names]

    for hg in hostgroups:
        app.state.client.delete_hostgroup(hg.groupid)

    render_result(
        Result(
            message=f"Host group {hostgroup!r} deleted.",
            result=HostGroupDeleteResult(groups=hostgroup_names),
        ),
    )


@app.command("remove_host_from_hostgroup", rich_help_panel=HELP_PANEL)
def remove_host_from_hostgroup(
    hostnames: Optional[str] = typer.Argument(
        None,
        help="Host names or IDs. Separate values with commas.",
    ),
    hostgroups: Optional[str] = typer.Argument(
        None,
        help="Host group names or IDs. Separate values with commas.",
    ),
) -> None:
    """Remove one or more hosts from one or more host groups."""
    hosts, hgs = _parse_hostname_hostgroup_args(hostnames, hostgroups)
    query = {
        "hostids": [host.hostid for host in hosts],
        "groupids": [hg.groupid for hg in hgs],
    }
    try:
        app.state.client.hostgroup.massremove(**query)
    except Exception as e:
        exit_err(f"Failed to remove hosts from hostgroups: {e}")
    hnames = ", ".join(host.host for host in hosts)
    hgnames = ", ".join(hg.name for hg in hgs)
    # TODO: add list of hostnames and host groups to the result
    render_result(
        Result(message=f"Removed host(s) {hnames} from hostgroup(s) {hgnames}.")
    )


class ExtendHostgroupResult(TableRenderable):
    """Result type for `extend_hostgroup` command."""

    source: str
    destination: List[str]
    hosts: List[str]

    @classmethod
    def from_result(
        cls, source: HostGroup, destination: List[HostGroup]
    ) -> ExtendHostgroupResult:
        return cls(
            source=source.name,
            destination=[dst.name for dst in destination],
            hosts=[host.host for host in source.hosts],
        )


@app.command("extend_hostgroup", rich_help_panel=HELP_PANEL)
def extend_hostgroup(
    src_group: str = typer.Argument(
        ...,
        help="Group to get hosts from.",
    ),
    dest_group: str = typer.Argument(
        ...,
        help="Group(s) to add hosts to. Comma-separated. Wildcards supported.",
    ),
    dryrun: bool = typer.Option(
        False,
        "--dryrun",
        help="Show hosts and groups without making changes.",
    ),
) -> None:
    """Add all hosts from a host group to other host group(s).

    The source group is not modified. Existing hosts in the destination group(s)
    are not removed or modified."""
    dest_args = parse_list_arg(dest_group)
    src = app.state.client.get_hostgroup(src_group, select_hosts=True)
    dest = app.state.client.get_hostgroups(*dest_args, select_hosts=True)

    if not dest:
        exit_err(f"No host groups found matching {dest_group!r}.")
    if not src.hosts:
        exit_err(f"No hosts found in host group {src_group!r}.")

    if not dryrun:
        app.state.client.add_hosts_to_hostgroups(src.hosts, dest)
        success(
            f"Copied {len(src.hosts)} hosts from {src.name!r} to {len(dest)} groups."
        )
    else:
        info(f"Would copy {len(src.hosts)} hosts from {src.name!r}:")
    render_result(ExtendHostgroupResult.from_result(src, dest))


class MoveHostsResult(TableRenderable):
    """Result type for `move_hosts` command."""

    source: str
    destination: str
    hosts: List[str]

    @classmethod
    def from_result(cls, source: HostGroup, destination: HostGroup) -> MoveHostsResult:
        return cls(
            source=source.name,
            destination=destination.name,
            hosts=[host.host for host in source.hosts],
        )


@app.command("move_hosts", rich_help_panel=HELP_PANEL)
def move_hosts(
    src_group: str = typer.Argument(
        ...,
        help="Group to move hosts from.",
    ),
    dest_group: str = typer.Argument(
        ...,
        help="Group to move hosts to.",
    ),
    rollback: bool = typer.Option(
        True,
        "--rollback/--no-rollback",
        help="Rollback changes if hosts cannot be removed from source group afterwards.",
    ),
    dryrun: bool = typer.Option(
        False,
        "--dryrun",
        help="Show hosts and groups without making changes.",
    ),
) -> None:
    """Move all hosts from one host group to another."""
    src = app.state.client.get_hostgroup(src_group, select_hosts=True)
    dest = app.state.client.get_hostgroup(dest_group, select_hosts=True)

    if not src.hosts:
        exit_err(f"No hosts found in host group {src_group!r}.")

    if dryrun:
        info(f"Would copy {len(src.hosts)} hosts from {src.name!r}:")
    else:
        app.state.client.add_hosts_to_hostgroups(src.hosts, [dest])
        info(f"Added hosts to {dest.name!r}")
        try:
            app.state.client.remove_hosts_from_hostgroups(src.hosts, [src])
        except Exception as e:
            if rollback:
                error(
                    f"Failed to remove hosts from {src.name!r}. Attempting to roll back changes."
                )
                app.state.client.remove_hosts_from_hostgroups(src.hosts, [dest])
            raise e
        else:
            info(f"Removed hosts from {src.name!r}.")
        success(f"Moved {len(src.hosts)} hosts from {src.name!r} to {dest.name!r}.")

    render_result(MoveHostsResult.from_result(src, dest))


class HostGroupHostResult(TypedDict):
    hostid: str
    host: str


class HostGroupResult(TableRenderable):
    """Result type for hostgroup."""

    groupid: str
    name: str
    hosts: List[HostGroupHostResult] = []
    flags: str
    internal: str = Field(
        get_hostgroup_type(0),
        serialization_alias="type",  # Dumped as "type" to mimick V2 behavior
    )

    @classmethod
    def from_hostgroup(cls, hostgroup: HostGroup) -> HostGroupResult:
        return cls(
            groupid=hostgroup.groupid,
            name=hostgroup.name,
            flags=hostgroup.flags,  # type: ignore # validator
            internal=hostgroup.internal,  # type: ignore # validator
            hosts=[
                HostGroupHostResult(hostid=host.hostid, host=host.host)
                for host in hostgroup.hosts
            ],
        )

    # Mimicks old behavior by also writing the string representation of the
    # flags and internal fields to the serialized output.
    @field_validator("flags", mode="before")
    @classmethod
    def _get_flag_str(cls, v: Any) -> Any:
        if isinstance(v, int):
            return get_hostgroup_flag(v)
        else:
            return v

    @field_validator("internal", mode="before")
    @classmethod
    def _get_type_str(cls, v: Any) -> Any:
        if isinstance(v, int):
            return get_hostgroup_type(v)
        else:
            return v

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["GroupID", "Name", "Flag", "Type", "Hosts"]
        rows = [
            [
                self.groupid,
                self.name,
                self.flags,
                self.internal,
                ", ".join([host["host"] for host in self.hosts]),
            ]
        ]  # type: RowsType
        return cols, rows


@app.command("show_hostgroup", rich_help_panel=HELP_PANEL)
def show_hostgroup(
    hostgroup: str = typer.Argument(None, help="Name of host group."),
) -> None:
    """Show details of a host group."""
    if not hostgroup:
        hostgroup = str_prompt("Host group name")
    hg = app.state.client.get_hostgroup(hostgroup, select_hosts=True)
    render_result(HostGroupResult.from_hostgroup(hg))


class HostGroupPermissions(TableRenderable):
    """Result type for hostgroup permissions."""

    groupid: str
    name: str
    permissions: List[str]

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["GroupID", "Name", "Permissions"]
        rows = [[self.groupid, self.name, "\n".join(self.permissions)]]  # type: RowsType
        return cols, rows


class HostGroupPermissionsResult(AggregateResult[HostGroupPermissions]):
    pass


@app.command("show_hostgroup_permissions", rich_help_panel=HELP_PANEL)
def show_hostgroup_permissions(
    hostgroup_arg: Optional[str] = typer.Argument(
        None, help="Host group name. Supports wildcards."
    ),
) -> None:
    """Show usergroups with permissions for the given hostgroup. Supports wildcards.

    Use "*" to list all host groups."""

    if not hostgroup_arg:
        hostgroup_arg = str_prompt("Host group")

    permissions = _get_hostgroup_permissions(hostgroup_arg)
    return render_result(AggregateResult(result=permissions))


def _get_hostgroup_permissions(hostgroup_arg: str) -> List[HostGroupPermissions]:
    if not hostgroup_arg:
        hostgroup_arg = str_prompt("Host group")

    usergroups = app.state.client.get_usergroups()
    hostgroups = app.state.client.get_hostgroups(
        hostgroup_arg,
        sort_field="name",
        sort_order="ASC",
        select_hosts=False,
        search=True,
    )

    hg_results = []
    for hostgroup in hostgroups:
        permissions = []
        for usergroup in usergroups:
            if app.api_version >= (6, 2, 0):
                rights = usergroup.hostgroup_rights
            else:
                rights = usergroup.rights
            for right in rights:
                if right.id == hostgroup.groupid:
                    permissions.append(
                        f"{usergroup.name} ({get_permission(right.permission)})"
                    )
                    break
        hg_results.append(
            HostGroupPermissions(
                groupid=hostgroup.groupid,
                name=hostgroup.name,
                permissions=permissions,
            )
        )
    return hg_results


# TODO: match V2 behavior
@app.command("show_hostgroups", rich_help_panel=HELP_PANEL)
def show_hostgroups() -> None:
    """Show details for all host groups."""
    hostgroups = app.state.client.get_hostgroups(
        "*", select_hosts=True, search=True, sort_field="name", sort_order="ASC"
    )
    render_result(
        AggregateResult(
            result=[HostGroupResult.from_hostgroup(hg) for hg in hostgroups]
        )
    )
