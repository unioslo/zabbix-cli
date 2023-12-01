from __future__ import annotations

from typing import List
from typing import Optional

import typer

from zabbix_cli.app import app
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.prompts import str_prompt
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
    """Adds one/several hosts to one/several hostgroups.

    Host{name,group} arguments are interpreted as IDs if they are numeric.
    """
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

    hostgroups_arg = []  # type: list[dict[str, str]]
    hostnames_arg = []

    for hostgroup in hostgroups.strip().split(","):
        hostgroup = hostgroup.strip()
        if hostgroup.isdigit():
            groupid = hostgroup
        else:
            groupid = app.state.client.get_hostgroup_id(hostgroup)
        hostgroups_arg.append({"groupid": groupid})

    for hostname in hostnames.strip().split(","):
        hostname = hostname.strip()
        if hostname.isdigit():
            hostid = hostname
        else:
            hostid = app.state.client.get_host_id(hostname)
        hostnames_arg.append({"hostid": hostid})
    query = {"hosts": hostnames_arg, "groups": hostgroups_arg}
    try:
        app.state.client.hostgroup.massadd(**query)
    except Exception as e:
        exit_err(f"Failed to add hosts to hostgroups: {e}")
    info(f"Added hosts {hostnames} to hostgroups {hostgroups}.")


@app.command("create_hostgroup")
def create_hostgroup(
    hostgroup: str = typer.Argument(None, help="Name of host group.")
) -> None:
    """Create a new host group."""
    if not hostgroup:
        hostgroup = str_prompt("Host group name")

    if app.state.client.hostgroup_exists(hostgroup):
        exit_err(f"Host group {hostgroup} already exists.")

    # Create the host group
    try:
        app.state.client.hostgroup.create(name=hostgroup)
    except Exception as e:
        exit_err(f"Failed to create host group {hostgroup}: {e}")
    else:
        info(f"Created host group {hostgroup}.")

    # Give host group rights to default user groups
    app.state.client.update_usergroup()


@app.command("remove_host_from_hostgroup")
def remove_host_from_hostgroup() -> None:
    pass


@app.command("show_hostgroup")
def show_hostgroup() -> None:
    pass


@app.command("show_hostgroup_permissions")
def show_hostgroup_permissions() -> None:
    pass


@app.command("show_hostgroups")
def show_hostgroups() -> None:
    pass
