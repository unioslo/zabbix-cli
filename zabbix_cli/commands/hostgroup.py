from __future__ import annotations

from typing import Any
from typing import List
from typing import Optional
from typing import Tuple

import typer
from pydantic import Field
from pydantic import field_validator
from typing_extensions import TypedDict

from zabbix_cli.app import app
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.models import AggregateResult
from zabbix_cli.models import ColsRowsType
from zabbix_cli.models import Result
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import HostGroup
from zabbix_cli.utils.args import UsergroupPermission
from zabbix_cli.utils.commands import ARG_POSITIONAL
from zabbix_cli.utils.utils import get_hostgroup_flag
from zabbix_cli.utils.utils import get_hostgroup_type
from zabbix_cli.utils.utils import get_permission


V2_HNHG_METAVAR = "<hostnames> <hostgroups>"


@app.command("add_host_to_hostgroup", options_metavar=V2_HNHG_METAVAR)
def add_host_to_hostgroup(
    ctx: typer.Context,
    args: List[str] = ARG_POSITIONAL,
    hostnames: Optional[str] = typer.Option(
        None, "--hostnames", help="Hostnames or IDs. Separate values with commas."
    ),
    hostgroups: Optional[str] = typer.Option(
        None, "--hostnames", help="Hostnames or IDs. Separate values with commas."
    ),
) -> None:
    """Adds one or more hosts to one or more host groups.

    Host{name,group} arguments are interpreted as IDs if they are numeric.
    """
    hosts, hgs = _parse_hostname_hostgroup_args(args, hostnames, hostgroups)
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
    args: List[str], hostnames: Optional[str], hostgroups: Optional[str]
) -> Tuple[List[Host], List[HostGroup]]:
    """Helper function for parsing hostnames and hostgroups from args.
    Args take presedence over options.

    Processes V2 style positional args as well as the named options
    `--hostnames` and `--hostgroups`.
    """
    if args and len(args) != 2:
        exit_err("Command takes two positional arguments <hostnames> <hostgroups>.")
    elif not args and not (hostnames and hostgroups):
        exit_err("Command requires both hostname(s) and hostgroup(s).")

    # FIXME: should args take precedence over options?
    # Is there a legitimate use case for mixing args (deprecated) and options?
    if args:  # guaranteed to be len 2
        hostnames, hostgroups = args

    # Prompt for missing arguments
    if not hostnames:
        hostnames = str_prompt("Host name(s)")
    if not hostgroups:
        hostgroups = str_prompt("Host group(s)")

    host_models = []  # type: list[Host]
    hg_models = []  # type: list[HostGroup]

    for hostname in hostnames.strip().split(","):
        host_models.append(app.state.client.get_host(hostname))

    for hostgroup in hostgroups.strip().split(","):
        hg_models.append(app.state.client.get_hostgroup(hostgroup))

    return host_models, hg_models


@app.command("create_hostgroup")
def create_hostgroup(
    hostgroup: str = typer.Argument(None, help="Name of host group."),
    # TODO: add option to re-run to fix permissions?
    # TODO: add option to specify permissions?
) -> None:
    """Create a new host group."""
    if not hostgroup:
        hostgroup = str_prompt("Host group name")

    if app.state.client.hostgroup_exists(hostgroup):
        exit_err(f"Host group {hostgroup!r} already exists.")

    # Create the host group
    try:
        res = app.state.client.hostgroup.create(name=hostgroup)
        if not res or not res.get("groupids", []):
            raise ZabbixCLIError(
                "Host group creation returned no data. Cannot assign permissions."
            )
        hostgroup_id = res["groupids"][0]
    except Exception as e:
        exit_err(f"Failed to create host group {hostgroup}: {e}")
    else:
        info(f"Created host group {hostgroup}.")

    # Give host group rights to default user groups
    # FIXME: extract this logic and perform this in ZabbixAPI
    # We really want to handle all this inside ZabbixAPI since it handles
    # errors and logs them, so that we can debug issues more easily.
    #
    # It should be trivial to add a method to ZabbixAPI that takes a usergroup
    # and a list of hostgroups+permissions.
    # The only question is whether to allow different permissions in the same
    # method call, or one method call per permission, i.e.:
    # ZabbixAPI.update_usergroup("ugroup", ["hgroup1", "hgroup2", "hgroup3"], "rw")
    # or
    # ZabbixAPI.update_usergroup("ugroup", [("hgroup1", "rw"), ("hgroup2", "ro")])
    try:
        # Admin group(s) gets Read/Write
        for usergroup in app.state.config.app.default_admin_usergroups:
            app.state.client.update_usergroup(
                usergroup,
                rights=[
                    {
                        "id": hostgroup_id,
                        "permission": UsergroupPermission.READ_WRITE.as_api_value(),
                    }
                ],
            )
            info(f"Assigned Read/Write permission for user group {usergroup!r}")
        # Default group(s) gets Read
        for usergroup in app.state.config.app.default_create_user_usergroups:
            app.state.client.update_usergroup(
                usergroup,
                rights=[
                    {
                        "id": hostgroup_id,
                        "permission": UsergroupPermission.READ_ONLY.as_api_value(),
                    }
                ],
            )
            info(f"Assigned Read-only permission for user group {usergroup!r}")

    except Exception as e:
        exit_err(f"Failed to assign permissions to host group {hostgroup!r}: {e}")

    render_result(
        Result(message=f"Host group ({hostgroup}) with ID: {hostgroup_id} created.")
    )


@app.command("remove_host_from_hostgroup", options_metavar=V2_HNHG_METAVAR)
def remove_host_from_hostgroup(
    args: List[str] = ARG_POSITIONAL,
    hostnames: Optional[str] = typer.Option(
        None, "--hostnames", help="Hostnames or IDs. Separate values with commas."
    ),
    hostgroups: Optional[str] = typer.Option(
        None,
        "--hostgroups",
        help="Host group names or IDs. Separate values with commas.",
    ),
) -> None:
    hosts, hgs = _parse_hostname_hostgroup_args(args, hostnames, hostgroups)
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


class HostGroupHostResult(TypedDict):
    hostid: str
    host: str


class HostGroupResult(Result):  # FIXME: inherit from TableRenderable instead
    """Result type for hostgroup."""

    groupid: str
    name: str
    hosts: List[HostGroupHostResult] = []
    flags: str
    internal: str = Field(
        get_hostgroup_type(0),
        serialization_alias="type",  # Dumped as "type" to mimick V2 behavior
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
        row = [
            self.groupid,
            self.name,
            self.flags,
            self.internal,
            ", ".join([host["host"] for host in self.hosts]),
        ]
        return cols, [row]


@app.command("show_hostgroup")
def show_hostgroup(
    hostgroup: str = typer.Argument(None, help="Name of host group."),
) -> None:
    """Show details of a host group."""
    if not hostgroup:
        hostgroup = str_prompt("Host group name")

    try:
        hg = app.state.client.get_hostgroup(hostgroup, select_hosts=True)
    except Exception as e:
        exit_err(f"Failed to get host group {hostgroup!r}: {e}")

    render_result(HostGroupResult(**hg.model_dump()))


class HostGroupPermissions(TableRenderable):
    """Result type for hostgroup permissions."""

    groupid: str
    name: str
    permissions: List[str]

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["GroupID", "Name", "Permissions"]
        row = [self.groupid, self.name, "\n".join(self.permissions)]
        return cols, [row]


class HostGroupPermissionsResult(AggregateResult[HostGroupPermissions]):
    pass


@app.command("show_hostgroup_permissions")
def show_hostgroup_permissions(
    hostgroup_arg: Optional[str] = typer.Argument(
        None, help="HostGroup name. Supports wildcards."
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
        sortorder="ASC",
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
                if right["id"] == hostgroup.groupid:
                    permissions.append(
                        f"{usergroup.name} ({get_permission(right['permission'])})"
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


class HostGroupsResult(AggregateResult):
    result: List[HostGroupResult] = []  # type: ignore # make generic?


# TODO: match V2 behavior
@app.command("show_hostgroups")
def show_hostgroups() -> None:
    """Show details for all host groups."""
    try:
        hostgroups = app.state.client.get_hostgroups(
            "*", select_hosts=True, search=True, sort_field="name", sort_order="ASC"
        )
    except Exception as e:
        exit_err(f"Failed to get all host groups: {e}")

    render_result(
        HostGroupsResult(
            result=[HostGroupResult(**hg.model_dump()) for hg in hostgroups]
        )
    )
