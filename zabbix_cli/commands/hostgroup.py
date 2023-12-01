from __future__ import annotations

from typing import List
from typing import Optional
from typing import Tuple

import typer

from zabbix_cli.app import app
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.models import Result
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import Hostgroup
from zabbix_cli.pyzabbix.types import UsergroupPermission
from zabbix_cli.utils.commands import ARG_POSITIONAL


@app.command("add_host_to_hostgroup", options_metavar="<hostnames> <hostgroups>")
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
    # if args and len(args) != 2:
    #     exit_err("Command takes two positional arguments <hostnames> <hostgroups>.")
    # elif not args and not (hostnames and hostgroups):
    #     exit_err("Command requires both hostname(s) and hostgroup(s).")

    # if args:
    #     hostnames, hostgroups = args
    # # Prompt for missing arguments
    # if not hostnames:
    #     hostnames = str_prompt("Host name(s)")
    # if not hostgroups:
    #     hostgroups = str_prompt("Host group(s)")

    # hostgroups_arg = []  # type: list[dict[str, str]]
    # hostnames_arg = []

    # for hostgroup in hostgroups.strip().split(","):
    #     hostgroup = hostgroup.strip()
    #     if hostgroup.isdigit():
    #         groupid = hostgroup
    #     else:
    #         groupid = app.state.client.get_hostgroup_id(hostgroup)
    #     hostgroups_arg.append({"groupid": groupid})

    # for hostname in hostnames.strip().split(","):
    #     hostname = hostname.strip()
    #     if hostname.isdigit():
    #         hostid = hostname
    #     else:
    #         hostid = app.state.client.get_host_id(hostname)
    #     hostnames_arg.append({"hostid": hostid})
    hosts, hgs = _do_process_hostname_hostgroup_args(args, hostnames, hostgroups)
    query = {
        "hosts": [{"hostid": host.hostid} for host in hosts],
        "groups": [{"groupid": hg.groupid} for hg in hgs],
    }
    try:
        app.state.client.hostgroup.massadd(**query)
    except Exception as e:
        exit_err(f"Failed to add hosts to hostgroups: {e}")
    hnames = ", ".join(host.name for host in hosts)
    hgnames = ", ".join(hg.name for hg in hgs)
    render_result(Result(message=f"Added host(s) {hnames} to hostgroup(s) {hgnames}."))


def _do_process_hostname_hostgroup_args(
    args: List[str], hostnames: Optional[str], hostgroups: Optional[str]
) -> Tuple[List[Host], List[Hostgroup]]:
    """Helper function for add_host_to_hostgroup and remove_host_from_hostgroup
    that processes V2 style positional args as well as --hostnames and --hostgroups
    options."""
    if args and len(args) != 2:
        exit_err("Command takes two positional arguments <hostnames> <hostgroups>.")
    elif not args and not (hostnames and hostgroups):
        exit_err("Command requires both hostname(s) and hostgroup(s).")

    if args:
        hostnames, hostgroups = args
    # Prompt for missing arguments
    if not hostnames:
        hostnames = str_prompt("Host name(s)")
    if not hostgroups:
        hostgroups = str_prompt("Host group(s)")

    host_models = []  # type: list[Host]
    hg_models = []  # type: list[Hostgroup]

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
    # TODO: possibly refactor and extract this logic?
    try:
        # Admin group(s) gets Read/Write
        for usergroup in app.state.config.app.default_admin_usergroups:
            app.state.client.update_usergroup(
                usergroup,
                rights=[
                    {
                        "id": hostgroup_id,
                        "permission": UsergroupPermission.READ_WRITE.value,
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
                        "permission": UsergroupPermission.READ_ONLY.value,
                    }
                ],
            )
            info(f"Assigned Read-only permission for user group {usergroup!r}")

    except Exception as e:
        exit_err(f"Failed to assign permissions to host group {hostgroup!r}: {e}")

    render_result(
        Result(message=f"Host group ({hostgroup}) with ID: {hostgroup_id} created.")
    )


@app.command("remove_host_from_hostgroup")
def remove_host_from_hostgroup(
    args: List[str] = ARG_POSITIONAL,
    hostnames: Optional[str] = typer.Option(
        None, "--hostnames", help="Hostnames or IDs. Separate values with commas."
    ),
    hostgroups: Optional[str] = typer.Option(
        None, "--hostnames", help="Hostnames or IDs. Separate values with commas."
    ),
) -> None:
    hosts, hgs = _do_process_hostname_hostgroup_args(args, hostnames, hostgroups)
    query = {
        "hostids": [host.hostid for host in hosts],
        "groupids": [hg.groupid for hg in hgs],
    }
    try:
        app.state.client.hostgroup.massremove(**query)
    except Exception as e:
        exit_err(f"Failed to remove hosts from hostgroups: {e}")
    hnames = ", ".join(host.name for host in hosts)
    hgnames = ", ".join(hg.name for hg in hgs)
    render_result(
        Result(message=f"Removed host(s) {hnames} from hostgroup(s) {hgnames}.")
    )


@app.command("show_hostgroup")
def show_hostgroup(
    hostgroup: str = typer.Argument(None, help="Name of host group."),
) -> None:
    """Show details of a host group."""
    if not hostgroup:
        hostgroup = str_prompt("Host group name")

    try:
        hg = app.state.client.get_hostgroup(hostgroup)
    except Exception as e:
        exit_err(f"Failed to get host group {hostgroup!r}: {e}")

    render_result(hg)


@app.command("show_hostgroup_permissions")
def show_hostgroup_permissions() -> None:
    pass


@app.command("show_hostgroups")
def show_hostgroups() -> None:
    pass
