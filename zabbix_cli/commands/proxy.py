from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import NamedTuple
from typing import Optional

import typer

from zabbix_cli.app import Example
from zabbix_cli.app import app
from zabbix_cli.exceptions import ZabbixAPICallError
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.output.console import error
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.console import success
from zabbix_cli.output.render import render_result
from zabbix_cli.utils.args import get_hostgroup_hosts
from zabbix_cli.utils.args import parse_int_list_arg
from zabbix_cli.utils.args import parse_list_arg
from zabbix_cli.utils.utils import compile_pattern

if TYPE_CHECKING:
    from zabbix_cli.app import StatefulApp
    from zabbix_cli.pyzabbix.types import Host
    from zabbix_cli.pyzabbix.types import Proxy

HELP_PANEL = "Proxy"
HELP_PANEL_GROUP = "Proxy Group"


class PrevProxyHosts(NamedTuple):
    hosts: list[Host]
    proxy: Optional[Proxy] = None


def ensure_proxy_group_support() -> None:
    if app.state.client.version.major < 7:
        exit_err("Proxy groups require Zabbix 7.0 or later.")


def group_hosts_by_proxy(
    app: StatefulApp, hosts: list[Host], default_proxy_id: str = ""
) -> dict[str, PrevProxyHosts]:
    """Group hosts by the proxy they had prior to the update."""
    proxy_ids: set[str] = set()
    for host in hosts:
        if host.proxyid:
            proxy_ids.add(host.proxyid)

    # Fetch proxies for all observed proxy IDs
    proxy_mapping: dict[str, PrevProxyHosts] = {}
    for proxy_id in proxy_ids:
        try:
            p = app.state.client.get_proxy(proxy_id)
        except ZabbixAPICallError as e:
            # Should be nigh-impossible, but someone might delete the proxy
            # while the command is running
            error(f"{e}")
            p = None
        proxy_mapping[proxy_id] = PrevProxyHosts(hosts=[], proxy=p)
    # The default is a special case - no prev proxy exists for these hosts
    proxy_mapping[default_proxy_id] = PrevProxyHosts(hosts=[], proxy=None)

    for host in hosts:
        if not host.proxyid:
            host_proxyid = default_proxy_id
        else:
            host_proxyid = host.proxyid
        proxy_mapping[host_proxyid].hosts.append(host)

    # No hosts without previous proxy - remove from mapping
    if not proxy_mapping[default_proxy_id].hosts:
        del proxy_mapping[default_proxy_id]

    return proxy_mapping


@app.command(name="clear_host_proxy", rich_help_panel=HELP_PANEL)
def clear_host_proxy(
    ctx: typer.Context,
    hostname: str = typer.Argument(
        help="Hostnames. Comma-separated Supports wildcards.",
        show_default=False,
    ),
    dryrun: bool = typer.Option(False, help="Preview changes"),
) -> None:
    """Clear the proxy for one or more hosts.

    Sets the hosts to be monitored by the Zabbix server instead of a proxy.
    """
    # NOTE: this command is _VERY_ similar to `update_host_proxy`
    #       can we refactor them to avoid code duplication?
    from zabbix_cli.commands.results.proxy import ClearHostProxyResult
    from zabbix_cli.models import AggregateResult
    from zabbix_cli.output.console import error
    from zabbix_cli.output.console import info

    hostnames = parse_list_arg(hostname)
    hosts = app.state.client.get_hosts(*hostnames, search=True)

    to_update = [host for host in hosts if host.proxyid]
    if not dryrun:
        with app.status("Clearing host proxies..."):
            if not to_update:
                exit_err("No matching hosts have a proxy assigned.")
            try:
                app.state.client.clear_host_proxies(to_update)
            except Exception as e:
                error(f"Failed to clear proxies for hosts: {e}")

    proxy_map = group_hosts_by_proxy(app, to_update)

    render_result(
        AggregateResult(
            empty_ok=True,
            result=[
                ClearHostProxyResult.from_result(
                    hosts=prev.hosts,
                    source_proxy=prev.proxy,
                )
                for _, prev in proxy_map.items()
            ],
        )
    )

    total_hosts = len(hosts)
    if dryrun:
        info(f"Would clear proxy for {total_hosts} hosts.")
    else:
        success(f"Cleared proxy for {total_hosts} hosts.")


@app.command(
    name="load_balance_proxy_hosts",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Load balance hosts evenly between two proxies",
            "load_balance_proxy_hosts proxy1,proxy2",
        ),
        Example(
            "Place twice as many hosts on proxy1 as proxy2",
            "load_balance_proxy_hosts proxy1,proxy2 2,1",
        ),
        Example(
            "Load balance hosts evenly between three proxies",
            "load_balance_proxy_hosts proxy1,proxy2,proxy3",
        ),
        Example(
            "Load balance hosts unevenly between three proxies",
            "load_balance_proxy_hosts proxy1,proxy2,proxy3 1,1,2",
        ),
    ],
)
def load_balance_proxy_hosts(
    ctx: typer.Context,
    proxy: str = typer.Argument(
        help="Comma delimited list of proxies to share hosts between.",
        metavar="<proxy1,proxy2,...>",
        show_default=False,
    ),
    weight: Optional[str] = typer.Argument(
        None,
        help="Weights for each proxy. Comma-separated. Defaults to equal weights.",
        metavar="[weight1,weight2,...]",
        show_default=False,
    ),
) -> None:
    """Spread hosts between multiple proxies.

    Hosts are determined by the hosts monitored by the given proxies
    Hosts monitored by other proxies or not monitored at all are not affected.

    Weighting for the load balancing is optional, and defaults to equal weights.
    Number of proxies must match number of weights if specified.
    """
    import itertools
    import random

    from zabbix_cli.commands.results.proxy import LBProxy
    from zabbix_cli.commands.results.proxy import LBProxyResult

    proxy_names = [p.strip() for p in proxy.split(",")]
    if weight:
        weights = parse_int_list_arg(weight)
    else:
        weights = [1] * len(proxy_names)  # default to equal weights

    if len(proxy_names) != len(weights):
        exit_err("Number of proxies must match number of weights.")
    elif len(proxy_names) < 2:
        exit_err("Must specify at least two proxies to load balance.")
    elif all(w == 0 for w in weights):
        exit_err("All weights cannot be zero.")

    # Fetch proxies one by one to ensure each one exists
    proxies = [app.state.client.get_proxy(p, select_hosts=True) for p in proxy_names]

    # TODO: Make sure list of proxies is in same order we specified them?

    all_hosts = list(itertools.chain.from_iterable(p.hosts for p in proxies))
    if not all_hosts:
        exit_err("Proxies have no hosts to load balance.")
    logging.debug(f"Found {len(all_hosts)} hosts to load balance.")

    lb_proxies = {
        p.proxyid: LBProxy(proxy=p, weight=w) for p, w in zip(proxies, weights)
    }
    for host in all_hosts:
        p = random.choices(proxies, weights=weights, k=1)[0]
        lb_proxies[p.proxyid].hosts.append(host)

    # Abort on failure
    try:
        for lb_proxy in lb_proxies.values():
            n_hosts = len(lb_proxy.hosts)
            logging.debug(
                "Proxy '%s' has %d hosts after balancing.",
                lb_proxy.proxy.name,
                n_hosts,
            )
            if not n_hosts:
                logging.debug(
                    "Proxy '%s' has no hosts after balancing.", lb_proxy.proxy.name
                )
                continue
            logging.debug(f"Moving {n_hosts} hosts to proxy {lb_proxy.proxy.name!r}")

            app.state.client.move_hosts_to_proxy(
                hosts=lb_proxy.hosts,
                proxy=lb_proxy.proxy,
            )
            lb_proxy.count = n_hosts
    except Exception as e:
        raise ZabbixCLIError(f"Failed to load balance hosts: {e}") from e

    render_result(LBProxyResult(proxies=list(lb_proxies.values())))
    # HACK: render_result doesn't print a message for table results
    success(f"Load balanced {len(all_hosts)} hosts between {len(proxies)} proxies.")


@app.command(
    name="move_proxy_hosts",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Move all hosts from one proxy to another",
            "move_proxy_hosts proxy1 proxy2",
        ),
        Example(
            "Move all hosts with names matching a regex pattern",
            "move_proxy_hosts proxy1 proxy2 --filter '$www.*'",
        ),
    ],
)
def move_proxy_hosts(
    ctx: typer.Context,
    proxy_src: str = typer.Argument(
        help="Proxy to move hosts from.",
        show_default=False,
    ),
    proxy_dst: str = typer.Argument(
        help="Proxy to move hosts to.",
        show_default=False,
    ),
    # Prefer --filter over positional arg
    host_filter: Optional[str] = typer.Option(
        None, "--filter", help="Regex pattern of hosts to move."
    ),
    # LEGACY: matches old command signature (deprecated)
    host_filter_arg: Optional[str] = typer.Argument(
        None, help="Filter hosts to move.", hidden=True
    ),
) -> None:
    """Move hosts from one proxy to another."""
    from zabbix_cli.commands.results.proxy import MoveProxyHostsResult
    from zabbix_cli.models import Result

    hfilter = host_filter_arg or host_filter
    if hfilter:  # Compile before we fetch to fail fast
        filter_pattern = compile_pattern(hfilter)
    else:
        filter_pattern = None

    source_proxy = app.state.client.get_proxy(proxy_src)
    destination_proxy = app.state.client.get_proxy(proxy_dst)

    hosts = app.state.client.get_hosts(proxy=source_proxy)
    if not hosts:
        exit_err(f"Source proxy {source_proxy.name!r} has no hosts.")

    # Do filtering client-side to get full regex support
    if filter_pattern:
        hosts = [host for host in hosts if filter_pattern.match(host.host)]
        if not hosts:
            exit_err(f"No hosts matched filter {hfilter!r}.")

    app.state.client.move_hosts_to_proxy(hosts, destination_proxy)

    render_result(
        Result(
            message=f"Moved {len(hosts)} hosts from {source_proxy.name!r} to {destination_proxy.name!r}",
            result=MoveProxyHostsResult(
                source=source_proxy.proxyid,
                destination=destination_proxy.proxyid,
                hosts=[host.host for host in hosts],
            ),
        )
    )


@app.command(name="show_proxies", rich_help_panel=HELP_PANEL)
def show_proxies(
    ctx: typer.Context,
    name_or_id: Optional[str] = typer.Argument(
        None,
        help="Filter by proxy name or ID. Comma-separated. Supports wildcards.",
        show_default=False,
    ),
    hosts: bool = typer.Option(
        False,
        "--hosts",
        help="Show hostnames of each host for every proxy.",
    ),
) -> None:
    """Show all proxies.

    Shows number of hosts for each proxy unless [option]--hosts[/] is passed in,
    in which case the hostnames of each host are displayed instead.
    """
    from zabbix_cli.commands.results.proxy import ShowProxiesResult
    from zabbix_cli.models import AggregateResult

    names_or_ids = parse_list_arg(name_or_id)

    with app.status("Fetching proxies..."):
        proxies = app.state.client.get_proxies(
            *names_or_ids,
            select_hosts=True,
        )
    render_result(
        AggregateResult(
            result=[ShowProxiesResult.from_result(p, show_hosts=hosts) for p in proxies]
        )
    )


@app.command(name="show_proxy_hosts", rich_help_panel=HELP_PANEL)
def show_proxy_hosts(
    ctx: typer.Context,
    proxy: str = typer.Argument(
        help="Proxy name or ID. Supports wildcards.",
        show_default=False,
    ),
) -> None:
    """Show all hosts with for a given proxy."""
    from zabbix_cli.commands.results.proxy import ShowProxyHostsResult

    with app.status("Fetching proxy..."):
        prox = app.state.client.get_proxy(proxy, select_hosts=True)

    render_result(ShowProxyHostsResult.from_result(prox))


@app.command(name="update_host_proxy", rich_help_panel=HELP_PANEL)
def update_host_proxy(
    ctx: typer.Context,
    hostname: str = typer.Argument(
        help="Hostnames. Comma-separated Supports wildcards.",
        show_default=False,
    ),
    proxy: str = typer.Argument(
        help="Proxy name. Supports wildcards.",
        show_default=False,
    ),
    dryrun: bool = typer.Option(
        False,
        help="Preview changes",
    ),
) -> None:
    """Assign hosts to a proxy.

    Supports wildcards for both hosts and proxy names.
    If multiple proxies match the proxy name, the first match is used.
    """
    from zabbix_cli.commands.results.proxy import UpdateHostProxyResult
    from zabbix_cli.models import AggregateResult
    from zabbix_cli.output.console import info

    hostnames = parse_list_arg(hostname)
    hosts = app.state.client.get_hosts(*hostnames, search=True)
    dest_proxy = app.state.client.get_proxy(proxy)

    to_update: list[Host] = []
    for host in hosts:
        if host.proxyid != dest_proxy.proxyid:
            to_update.append(host)

    if not dryrun:
        with app.status("Updating host proxies..."):
            hostids = app.state.client.update_hosts_proxy(to_update, dest_proxy)
    else:
        hostids = [host.hostid for host in to_update]

    updated = set(hostids)
    updated_hosts = [host for host in to_update if host.hostid in updated]

    proxy_hosts = group_hosts_by_proxy(app, updated_hosts)

    render_result(
        AggregateResult(
            empty_ok=True,
            result=[
                UpdateHostProxyResult.from_result(
                    hosts=prev.hosts,
                    source_proxy=prev.proxy,
                    dest_proxy=dest_proxy,
                )
                for _, prev in proxy_hosts.items()
            ],
        )
    )

    total_hosts = len(updated)
    if dryrun:
        info(f"Would update proxy for {total_hosts} hosts.")
    else:
        success(f"Updated proxy for {total_hosts} hosts.")


@app.command(name="update_hostgroup_proxy", rich_help_panel=HELP_PANEL)
def update_hostgroup_proxy(
    ctx: typer.Context,
    hostgroup: str = typer.Argument(
        help="Host group(s). Comma-separated. Supports wildcards.",
        show_default=False,
    ),
    proxy: str = typer.Argument(
        help="Proxy to assign. Supports wildcards.",
        show_default=False,
    ),
    dryrun: bool = typer.Option(False, help="Preview changes."),
) -> None:
    """Assign a proxy to all hosts in one or more host groups."""
    from zabbix_cli.commands.results.proxy import UpdateHostGroupProxyResult
    from zabbix_cli.output.console import warning

    prx = app.state.client.get_proxy(proxy)

    hosts = get_hostgroup_hosts(app, hostgroup)
    to_update: list[Host] = []
    for host in hosts:
        if host.proxyid != prx.proxyid:
            to_update.append(host)

    if not dryrun:
        if not to_update:
            exit_err("All hosts already have the specified proxy.")
        with app.status("Updating host proxies..."):
            hostids = app.state.client.update_hosts_proxy(to_update, prx)
        if not hostids:
            warning("No hosts were updated.")
    else:
        hostids = [host.hostid for host in to_update]

    updated_hosts = [host for host in to_update if host.hostid in hostids]
    render_result(UpdateHostGroupProxyResult.from_result(prx, updated_hosts))

    total_hosts = len(hostids)
    if dryrun:
        info(f"Would update proxy for {total_hosts} hosts.")
    else:
        success(f"Updated proxy for {total_hosts} hosts.")


@app.command(
    name="add_proxy_to_group",
    rich_help_panel=HELP_PANEL_GROUP,
    examples=[
        Example(
            "Add a proxy to a proxy group",
            "add_proxy_to_group proxy1 group1 192.168.0.2 10051",
        )
    ],
)
def add_proxy_to_group(
    ctx: typer.Context,
    name_or_id: str = typer.Argument(
        help="Name or ID of proxy to add.",
        show_default=False,
    ),
    proxy_group: str = typer.Argument(
        help="Name or ID of proxy group to add proxy to.",
        show_default=False,
    ),
    local_address: Optional[str] = typer.Argument(
        None,
        help="Address for active agents.",
        show_default=False,
    ),
    local_port: Optional[str] = typer.Argument(
        None,
        help="Address for active agents.",
        show_default=False,
    ),
) -> None:
    """Add a proxy to a proxy group.

    Requires a local address and port for active agent redirection if
    if the proxy does not have it set.
    """
    ensure_proxy_group_support()

    proxy = app.state.client.get_proxy(name_or_id)

    # Determine address + port
    local_address = local_address or proxy.local_address
    if not local_address:
        exit_err(f"Proxy {proxy.name} requires a local address for active agents.")
    local_port = local_port or proxy.local_port
    if not local_port:
        exit_err(f"Proxy {proxy.name} requires a local port for active agents.")

    group = app.state.client.get_proxy_group(proxy_group)
    app.state.client.add_proxy_to_group(proxy, group, local_address, local_port)

    success(f"Added proxy {proxy.name!r} to group {group.name!r}.")


@app.command(name="remove_proxy_from_group", rich_help_panel=HELP_PANEL_GROUP)
def remove_proxy_from_group(
    ctx: typer.Context,
    name_or_id: str = typer.Argument(
        help="Name or ID of proxy to remove.",
        show_default=False,
    ),
) -> None:
    """Remove a proxy from a proxy group."""
    ensure_proxy_group_support()

    proxy = app.state.client.get_proxy(name_or_id)
    if proxy.proxy_groupid is None or proxy.proxy_groupid == "0":
        exit_err(f"Proxy {proxy.name!r} is not in a proxy group.")

    app.state.client.remove_proxy_from_group(proxy)

    success(f"Removed proxy {proxy.name!r} from group with ID {proxy.proxy_groupid}.")


@app.command(
    name="show_proxy_groups",
    rich_help_panel=HELP_PANEL_GROUP,
    examples=[
        Example(
            "Show all proxy groups",
            "show_proxy_groups",
        ),
        Example(
            "Show proxy groups with a specific proxy",
            "show_proxy_groups --proxy proxy1",
        ),
        Example(
            "Show proxy groups with either proxy1 or proxy2",
            "show_proxy_groups --proxy proxy1,proxy2",
        ),
    ],
)
def show_proxy_groups(
    ctx: typer.Context,
    name_or_id: Optional[str] = typer.Argument(
        None,
        help="Filter by proxy name or ID. Comma-separated. Supports wildcards.",
        show_default=False,
    ),
    proxies: Optional[str] = typer.Option(
        None,
        "--proxy",
        help="Show only groups containing these proxies. Comma-separated.",
    ),
) -> None:
    """Show all proxy groups and their proxies.

    Optionally takes in a list of names or IDs to filter by.
    """
    from zabbix_cli.models import AggregateResult

    ensure_proxy_group_support()

    names_or_ids = parse_list_arg(name_or_id)
    proxy_names = parse_list_arg(proxies)

    with app.status("Fetching proxy groups..."):
        # Fetch proxies if specified
        proxy_list = [app.state.client.get_proxy(p) for p in proxy_names]
        groups = app.state.client.get_proxy_groups(
            *names_or_ids,
            proxies=proxy_list,
            select_proxies=True,
        )

    render_result(AggregateResult(result=groups))


@app.command(name="show_proxy_group_hosts", rich_help_panel=HELP_PANEL_GROUP)
def show_proxy_group_hosts(
    ctx: typer.Context,
    proxygroup: str = typer.Argument(
        help="Proxy group name or ID. Supports wildcards.",
        show_default=False,
    ),
) -> None:
    """Show all hosts in a proxy group."""
    from zabbix_cli.commands.results.proxy import ShowProxyGroupHostsResult

    ensure_proxy_group_support()

    with app.status("Fetching proxy groups...") as status:
        group = app.state.client.get_proxy_group(proxygroup)
        status.update("Fetching hosts...")
        hosts = app.state.client.get_hosts(proxy_group=group)

    render_result(ShowProxyGroupHostsResult(proxy_group=group, hosts=hosts))


@app.command(name="update_hostgroup_proxygroup", rich_help_panel=HELP_PANEL_GROUP)
def update_hostgroup_proxygroup(
    ctx: typer.Context,
    hostgroup: str = typer.Argument(
        help="Host group(s). Comma-separated. Supports wildcards.",
        show_default=False,
    ),
    proxygroup: str = typer.Argument(
        help="Proxy group to assign. Supports wildcards.",
        show_default=False,
    ),
    dryrun: bool = typer.Option(False, help="Preview changes."),
) -> None:
    """Assign a proxy group to all hosts in one or more host groups."""
    from zabbix_cli.commands.results.proxy import UpdateHostGroupProxyGroupResult
    from zabbix_cli.output.console import warning

    ensure_proxy_group_support()

    grp = app.state.client.get_proxy_group(proxygroup)

    hosts = get_hostgroup_hosts(app, hostgroup)
    to_update: list[Host] = []
    for host in hosts:
        if host.proxy_groupid != grp.proxy_groupid:
            to_update.append(host)

    # Sort hosts by host group
    updated: list[str] = []  # list of host IDs
    if not dryrun:
        if not to_update:
            exit_err("All hosts already have the specified proxy group.")
        with app.status("Updating hosts..."):
            updated = app.state.client.add_hosts_to_proxygroup(to_update, grp)
        if not updated:
            warning("No hosts were updated.")
    else:
        updated = [host.hostid for host in to_update]

    updated_hosts = [host for host in to_update if host.hostid in updated]
    render_result(UpdateHostGroupProxyGroupResult.from_result(grp, updated_hosts))

    total_hosts = len(updated)
    if dryrun:
        info(f"Would update proxy group for {total_hosts} hosts.")
    else:
        success(f"Updated proxy group for {total_hosts} hosts.")
