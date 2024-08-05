from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Dict
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Set

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
from zabbix_cli.utils.args import parse_int_list_arg
from zabbix_cli.utils.args import parse_list_arg
from zabbix_cli.utils.utils import compile_pattern

if TYPE_CHECKING:
    from zabbix_cli.app import StatefulApp
    from zabbix_cli.pyzabbix.types import Host
    from zabbix_cli.pyzabbix.types import Proxy

HELP_PANEL = "Proxy"


class PrevProxyHosts(NamedTuple):
    hosts: List[Host]
    proxy: Optional[Proxy] = None


def group_hosts_by_proxy(
    app: StatefulApp, hosts: List[Host], default_proxy_id: str = ""
) -> Dict[str, PrevProxyHosts]:
    """Group hosts by the proxy they had prior to the update."""
    proxy_ids: Set[str] = set()
    for host in hosts:
        if host.proxyid:
            proxy_ids.add(host.proxyid)

    # Fetch proxies for all observed proxy IDs
    proxy_mapping: Dict[str, PrevProxyHosts] = {}
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


@app.command(name="update_host_proxy", rich_help_panel=HELP_PANEL)
def update_host_proxy(
    ctx: typer.Context,
    hostname: str = typer.Argument(
        help="Hostnames. Comma-separated Supports wildcards."
    ),
    proxy: str = typer.Argument(help="Proxy name. Supports wildcards."),
    dryrun: bool = typer.Option(False, help="Preview changes", is_flag=True),
) -> None:
    """Assign one or more hosts to a proxy. Supports wildcards for both hosts and proxy.

    If multiple proxies match the proxy name, the first match is used.
    """
    from zabbix_cli.commands.results.proxy import UpdateHostProxyResult
    from zabbix_cli.models import AggregateResult
    from zabbix_cli.output.console import error
    from zabbix_cli.output.console import info

    hostnames = parse_list_arg(hostname)
    hosts = app.state.client.get_hosts(*hostnames, search=True)
    dest_proxy = app.state.client.get_proxy(proxy)

    to_update: List[Host] = []
    for host in hosts:
        if host.proxyid != dest_proxy.proxyid:
            to_update.append(host)

    updated: List[Host] = []
    fail: List[Host] = []
    if not dryrun:
        with app.status("Updating host proxies...") as status:
            for host in to_update:
                status.update(f"Updating {host.host}...")
                if host.proxyid and host.proxyid == dest_proxy.proxyid:
                    info(f"Host {host.host!r} already has proxy {dest_proxy.name!r}")
                    continue
                try:
                    app.state.client.update_host_proxy(host, dest_proxy)
                    updated.append(host)
                except Exception as e:
                    fail.append(host)
                    error(f"Failed to update host {host.host!r}: {e}")
    else:
        updated = to_update
    # TODO: report failed hosts

    proxy_hosts = group_hosts_by_proxy(app, updated)

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


@app.command(name="clear_host_proxy", rich_help_panel=HELP_PANEL)
def clear_host_proxy(
    ctx: typer.Context,
    hostname: str = typer.Argument(
        help="Hostnames. Comma-separated Supports wildcards."
    ),
    dryrun: bool = typer.Option(False, help="Preview changes", is_flag=True),
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
    proxy_src: str = typer.Argument(None, help="Proxy to move hosts from."),
    proxy_dst: str = typer.Argument(None, help="Proxy to move hosts to."),
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

    hosts = app.state.client.get_hosts(proxyid=source_proxy.proxyid)
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
    proxies: str = typer.Argument(
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
    """Spreads hosts between multiple proxies.

    Hosts are determined by the hosts monitored by the given proxies
    Hosts monitored by other proxies or not monitored at all are not affected.

    Weighting for the load balancing is optional, and defaults to equal weights.
    Number of proxies must match number of weights if specified.
    """
    import itertools
    import random

    from zabbix_cli.commands.results.proxy import LBProxy
    from zabbix_cli.commands.results.proxy import LBProxyResult

    proxy_names = [p.strip() for p in proxies.split(",")]
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

    # *_list` vars are ugly, but we already have proxies, so...
    proxy_list = [app.state.client.get_proxy(p, select_hosts=True) for p in proxy_names]

    # TODO: Make sure list of proxies is in same order we specified them?

    all_hosts = list(itertools.chain.from_iterable(p.hosts for p in proxy_list))
    if not all_hosts:
        exit_err("Proxies have no hosts to load balance.")
    logging.debug(f"Found {len(all_hosts)} hosts to load balance.")

    lb_proxies = {
        p.proxyid: LBProxy(proxy=p, weight=w) for p, w in zip(proxy_list, weights)
    }
    for host in all_hosts:
        p = random.choices(proxy_list, weights=weights, k=1)[0]
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
    success(f"Load balanced {len(all_hosts)} hosts between {len(proxy_list)} proxies.")


@app.command(name="update_hostgroup_proxy")
def update_hostgroup_proxy(
    ctx: typer.Context,
    hostgroup: str = typer.Argument(
        help="Host group(s). Comma-separated. Supports wildcards."
    ),
    proxy: str = typer.Argument(help="Proxy to assign. Supports wildcards."),
    dryrun: bool = typer.Option(False, help="Preview changes.", is_flag=True),
) -> None:
    """Assign a proxy to all hosts in one or more host groups."""
    from zabbix_cli.commands.results.proxy import UpdateHostGroupProxyResult
    from zabbix_cli.output.console import error
    from zabbix_cli.output.console import warning

    prx = app.state.client.get_proxy(proxy)

    hostgroup_names = parse_list_arg(hostgroup)
    hostgroups = app.state.client.get_hostgroups(
        *hostgroup_names, select_hosts=True, search=True
    )
    # Get all hosts from all host groups
    # Some hosts can be in multiple host groups - ensure no dupes
    hosts: List[Host] = []
    seen: Set[str] = set()
    for hg in hostgroups:
        for host in hg.hosts:
            if host.host not in seen:
                hosts.append(host)
                seen.add(host.host)

    to_update: List[Host] = []
    for host in hosts:
        if host.proxyid != prx.proxyid:
            to_update.append(host)

    # Sort hosts by host group
    updated: List[Host] = []
    fail: List[Host] = []
    if not dryrun:
        with app.status("Updating host proxies...") as status:
            for host in to_update:
                status.update(f"Updating {host.host}...")
                try:
                    app.state.client.update_host_proxy(host, prx)
                    updated.append(host)
                except Exception as e:
                    fail.append(host)
                    error(f"Failed to update host {host.host!r}: {e}")
        if not updated and not fail:
            warning("No hosts were updated.")
    else:
        updated = to_update
    render_result(UpdateHostGroupProxyResult.from_result(prx, updated))

    total_hosts = len(updated)
    if dryrun:
        info(f"Would update proxy for {total_hosts} hosts.")
    else:
        success(f"Updated proxy for {total_hosts} hosts.")
        # TODO: report failed hosts


@app.command(name="show_proxies", rich_help_panel=HELP_PANEL)
def show_proxies(
    ctx: typer.Context,
    hosts: bool = typer.Option(
        False,
        "--hosts",
        help="Show hostnames of each host.",
        is_flag=True,
    ),
    name_or_id: Optional[str] = typer.Argument(
        None, help="Filter by proxy name or ID. Comma-separated. Supports wildcards."
    ),
) -> None:
    """Show all proxies.

    Shows number of hosts for each proxy unless --hosts is passed in,
    in which case the hostnames of each host is displayed instead.
    """
    from zabbix_cli.commands.results.proxy import ShowProxiesResult
    from zabbix_cli.models import AggregateResult

    names_or_ids = parse_list_arg(name_or_id) if name_or_id else None

    proxies = app.state.client.get_proxies(
        *names_or_ids or "*",
        select_hosts=True,
    )
    render_result(
        AggregateResult(
            result=[ShowProxiesResult.from_result(p, show_hosts=hosts) for p in proxies]
        )
    )
