from __future__ import annotations

from typing import Optional

import typer

from zabbix_cli.app import Example
from zabbix_cli.app import app
from zabbix_cli.commands.common.args import OPTION_LIMIT
from zabbix_cli.output.console import error
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.console import success
from zabbix_cli.output.formatting.grammar import pluralize as p
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.enums import UsergroupPermission
from zabbix_cli.utils.args import parse_hostgroups_arg
from zabbix_cli.utils.args import parse_hosts_arg
from zabbix_cli.utils.args import parse_list_arg

HELP_PANEL = "Host Group"


@app.command(
    "add_host_to_hostgroup",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Add a host to a host group",
            "add_host_to_hostgroup 'My host' 'My host group'",
        ),
        Example(
            "Add multiple hosts to a host group",
            "add_host_to_hostgroup 'host1,host2' 'My host group'",
        ),
        Example(
            "Add multiple hosts to multiple host groups",
            "add_host_to_hostgroup 'host1,host2' 'My host group,Another group'",
        ),
    ],
)
def add_host_to_hostgroup(
    ctx: typer.Context,
    hostnames_or_ids: str = typer.Argument(
        help="Host names or IDs. Comma-separated. Supports wildcards.",
        metavar="HOSTS",
        show_default=False,
    ),
    hostgroups: str = typer.Argument(
        help="Host group names or IDs. Comma-separated. Supports wildcards.",
        metavar="HOSTGROUPS",
        show_default=False,
    ),
    dryrun: bool = typer.Option(
        False,
        "--dryrun",
        help="Preview changes",
    ),
) -> None:
    """Add hosts to host groups.

    Host name and group arguments are interpreted as IDs if they are numeric.
    """
    import itertools

    from zabbix_cli.commands.results.hostgroup import AddHostsToHostGroup
    from zabbix_cli.models import AggregateResult

    hosts = parse_hosts_arg(app, hostnames_or_ids)
    hgs = parse_hostgroups_arg(app, hostgroups, select_hosts=True)
    if not dryrun:
        with app.status("Adding hosts to host groups..."):
            app.state.client.add_hosts_to_hostgroups(hosts, hgs)

    result: list[AddHostsToHostGroup] = []
    for hg in hgs:
        r = AddHostsToHostGroup.from_result(hosts, hg)
        if not r.hosts:
            continue
        result.append(r)

    total_hosts = len(set(itertools.chain.from_iterable((r.hosts) for r in result)))
    total_hgs = len(result)

    if not total_hosts:
        exit_err("No hosts to add.")

    render_result(AggregateResult(result=result))
    base_msg = f"{p('host', total_hosts)} to {p('host group', total_hgs)}"
    if dryrun:
        info(f"Would add {base_msg}.")
    else:
        success(f"Added {base_msg}.")


@app.command(
    "create_hostgroup",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Create a host group with default user group permissions",
            "create_hostgroup 'My Host Group'",
        ),
        Example(
            "Create a host group with specific RO and RW groups",
            "create_hostgroup 'My Host Group' --ro-groups users --rw-groups admins",
        ),
        Example(
            "Create a host group with no user group permissions",
            "create_hostgroup 'My Host Group' --no-usergroup-permissions",
        ),
    ],
)
def create_hostgroup(
    hostgroup: str = typer.Argument(
        help="Name of host group.",
        show_default=False,
    ),
    rw_groups: Optional[str] = typer.Option(
        None,
        "--rw-groups",
        help="User group(s) to give read/write permissions. Comma-separated.",
    ),
    ro_groups: Optional[str] = typer.Option(
        None,
        "--ro-groups",
        help="User group(s) to give read-only permissions. Comma-separated.",
    ),
    no_usergroup_permissions: bool = typer.Option(
        False,
        "--no-usergroup-permissions",
        help="Do not assign user group permissions.",
    ),
) -> None:
    """Create a new host group.

    Assigns default user group permissions by default.

    * [option]--rw-groups[/] defaults to config option [configopt]app.default_admin_usergroups[/].
    * [option]--ro-groups[/] defaults to config option [configopt]app.default_create_user_usergroups[/].
    * Use [option]--no-usergroup-permissions[/] to create a group without any user group permissions.
    """
    from zabbix_cli.models import Result

    if app.state.client.hostgroup_exists(hostgroup):
        exit_err(f"Host group {hostgroup!r} already exists.")

    with app.status("Creating host group..."):
        hostgroup_id = app.state.client.create_hostgroup(hostgroup)

    app_config = app.state.config.app

    rw_grps: list[str] = []
    ro_grps: list[str] = []
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
        exit_err(f"Failed to create host group {hostgroup!r}.")

    render_result(Result(message=f"Created host group {hostgroup} ({hostgroup_id})."))


@app.command("extend_hostgroup", rich_help_panel=HELP_PANEL)
def extend_hostgroup(
    src_group: str = typer.Argument(
        help="Group to get hosts from.",
        show_default=False,
    ),
    dest_group: str = typer.Argument(
        help="Group(s) to add hosts to. Comma-separated. Supports wildcards.",
        show_default=False,
    ),
    dryrun: bool = typer.Option(
        False,
        "--dryrun",
        help="Show hosts and groups without making changes.",
    ),
) -> None:
    """Add all hosts from a host group to other host groups.

    The source group is not modified. Existing hosts in the destination group(s)
    are not removed or modified.
    """
    from zabbix_cli.commands.results.hostgroup import ExtendHostgroupResult

    dest_args = parse_list_arg(dest_group)
    src = app.state.client.get_hostgroup(src_group, select_hosts=True)
    dest = app.state.client.get_hostgroups(*dest_args, select_hosts=True)

    if not dest:
        exit_err(f"No host groups found matching {dest_group!r}.")
    if not src.hosts:
        exit_err(f"No hosts found in host group {src_group!r}.")

    # TODO: calculate the number of hosts that would be added like the other commands
    if not dryrun:
        app.state.client.add_hosts_to_hostgroups(src.hosts, dest)
        success(
            f"Copied {len(src.hosts)} hosts from {src.name!r} to {len(dest)} groups."
        )
    else:
        info(f"Would copy {len(src.hosts)} hosts from {src.name!r}:")
    render_result(ExtendHostgroupResult.from_result(src, dest))


@app.command("move_hosts", rich_help_panel=HELP_PANEL)
def move_hosts(
    src_group: str = typer.Argument(
        help="Group to move hosts from.",
        show_default=False,
    ),
    dest_group: str = typer.Argument(
        help="Group to move hosts to.",
        show_default=False,
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
    from zabbix_cli.commands.results.hostgroup import MoveHostsResult

    src = app.state.client.get_hostgroup(src_group, select_hosts=True)
    dest = app.state.client.get_hostgroup(dest_group, select_hosts=True)

    if not src.hosts:
        exit_err(f"No hosts found in host group {src_group!r}.")

    # TODO: calculate the number of hosts that would be added like the other commands
    if dryrun:
        info(f"Would move {len(src.hosts)} hosts to {dest.name!r}:")
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


@app.command(
    "remove_host_from_hostgroup",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Remove a host to a host group",
            "remove_host_from_hostgroup 'My host' 'My host group'",
        ),
        Example(
            "Remove multiple hosts from a host group",
            "remove_host_from_hostgroup 'host1,host2' 'My host group'",
        ),
        Example(
            "Remove multiple hosts from multiple host groups",
            "remove_host_from_hostgroup 'host1,host2' 'My host group,Another group'",
        ),
    ],
)
def remove_host_from_hostgroup(
    hostnames_or_ids: str = typer.Argument(
        help="Host names or IDs. Comma-separated. Supports wildcards.",
        metavar="HOSTS",
        show_default=False,
    ),
    hostgroups: str = typer.Argument(
        help="Host group names or IDs. Comma-separated. Supports wildcards.",
        metavar="HOSTGROUPS",
        show_default=False,
    ),
    dryrun: bool = typer.Option(
        False,
        "--dryrun",
        help="Preview changes",
    ),
) -> None:
    """Remove hosts from host groups."""
    import itertools

    from zabbix_cli.commands.results.hostgroup import RemoveHostsFromHostGroup
    from zabbix_cli.models import AggregateResult

    hosts = parse_hosts_arg(app, hostnames_or_ids)
    hgs = parse_hostgroups_arg(app, hostgroups, select_hosts=True)
    if not dryrun:
        with app.status("Removing hosts from host groups..."):
            app.state.client.remove_hosts_from_hostgroups(hosts, hgs)

    result: list[RemoveHostsFromHostGroup] = []
    for hg in hgs:
        r = RemoveHostsFromHostGroup.from_result(hosts, hg)
        if not r.hosts:
            continue
        result.append(r)

    total_hosts = len(set(itertools.chain.from_iterable((r.hosts) for r in result)))
    total_hgs = len(result)

    render_result(AggregateResult(result=result))
    base_msg = f"{p('host', total_hosts)} from {p('host group', total_hgs)}"
    if dryrun:
        info(f"Would remove {base_msg}.")
    else:
        success(f"Removed {base_msg}.")


@app.command("remove_hostgroup", rich_help_panel=HELP_PANEL)
def delete_hostgroup(
    hostgroup: str = typer.Argument(
        help="Name of host group(s) to delete. Comma-separated.",
        show_default=False,
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Remove host group even if it contains hosts.",
    ),
) -> None:
    """Delete a host group."""
    from zabbix_cli.commands.results.hostgroup import HostGroupDeleteResult
    from zabbix_cli.models import Result

    hostgroup_names = parse_list_arg(hostgroup)

    hostgroups = [
        app.state.client.get_hostgroup(hg, select_hosts=True) for hg in hostgroup_names
    ]

    for hg in hostgroups:
        if hg.hosts and not force:
            exit_err(
                f"Host group {hg.name!r} contains {p('host', len(hg.hosts))}. Use --force to delete."
            )
        app.state.client.delete_hostgroup(hg.groupid)

    render_result(
        Result(
            message=f"Host group {hostgroup!r} deleted.",
            result=HostGroupDeleteResult(groups=hostgroup_names),
        ),
    )


@app.command("show_hostgroup", rich_help_panel=HELP_PANEL)
def show_hostgroup(
    ctx: typer.Context,
    hostgroup: str = typer.Argument(
        help="Name of host group.",
        show_default=False,
    ),
) -> None:
    """Show details of a host group."""
    from zabbix_cli.commands.results.hostgroup import HostGroupResult

    hg = app.state.client.get_hostgroup(hostgroup, select_hosts=True)
    render_result(HostGroupResult.from_hostgroup(hg))


# TODO: match V2 behavior
@app.command(
    "show_hostgroups",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Show all host groups",
            "show_hostgroups --limit 0",
        ),
        Example(
            "Show all host groups starting with 'Web-'",
            "show_hostgroups 'Web-*'",
        ),
        Example(
            "Show host groups with 'web' in the name",
            "show_hostgroups '*web*'",
        ),
    ],
)
def show_hostgroups(
    name: Optional[str] = typer.Argument(
        help="Name of host group(s). Comma-separated. Supports wildcards.",
        show_default=False,
    ),
    select_hosts: bool = typer.Option(
        True, "--hosts/--no-hosts", help="Show hosts in each host group."
    ),
    limit: int = OPTION_LIMIT,
) -> None:
    """Show details for host groups.

    Limits results to 20 by default. Fetching all host groups with hosts can be extremely slow."""
    from zabbix_cli.commands.results.hostgroup import HostGroupResult
    from zabbix_cli.models import AggregateResult

    names = parse_list_arg(name)

    with app.status("Fetching host groups..."):
        hostgroups = app.state.client.get_hostgroups(
            *names,
            select_hosts=select_hosts,
            search=True,
            sort_field="name",
            sort_order="ASC",
            limit=limit,
        )
    render_result(
        AggregateResult(
            result=[HostGroupResult.from_hostgroup(hg) for hg in hostgroups]
        )
    )


@app.command("show_hostgroup_permissions", rich_help_panel=HELP_PANEL)
def show_hostgroup_permissions(
    hostgroups: str = typer.Argument(
        help="Host group name(s). Comma-separated. Supports wildcards.",
        show_default=False,
    ),
) -> None:
    """Show usergroups with permissions for the given hostgroup.

    Shows permissions for all host groups by default.
    """
    from zabbix_cli.commands.results.hostgroup import HostGroupPermissions
    from zabbix_cli.models import AggregateResult

    hg_names = parse_list_arg(hostgroups)

    with app.status("Fetching host groups..."):
        usergroups = app.state.client.get_usergroups()
        hgs = app.state.client.get_hostgroups(
            *hg_names,
            sort_field="name",
            sort_order="ASC",
            select_hosts=False,
            search=True,
        )

    result: list[HostGroupPermissions] = []
    for hg in hgs:
        permissions: list[str] = []
        for usergroup in usergroups:
            if app.api_version >= (6, 2, 0):
                rights = usergroup.hostgroup_rights
            else:
                rights = usergroup.rights
            for right in rights:
                if right.id == hg.groupid:
                    perm = UsergroupPermission.string_from_value(right.permission)
                    permissions.append(f"{usergroup.name} ({perm})")
                    break
        result.append(
            HostGroupPermissions(
                groupid=hg.groupid,
                name=hg.name,
                permissions=permissions,
            )
        )
    return render_result(AggregateResult(result=result))
