from __future__ import annotations

import logging
from typing import Dict
from typing import List
from typing import Optional

import typer

from zabbix_cli.app import Example
from zabbix_cli.app import app
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import success
from zabbix_cli.output.render import render_result
from zabbix_cli.utils.args import parse_int_list_arg
from zabbix_cli.utils.args import parse_list_arg
from zabbix_cli.utils.utils import compile_pattern

HELP_PANEL = "Proxy"


@app.command(name="update_host_proxy", rich_help_panel=HELP_PANEL)
def update_host_proxy(
    ctx: typer.Context,
    hostname: str = typer.Argument(
        ..., help="Hostnames. Comma-separated Supports wildcards."
    ),
    proxy: str = typer.Argument(..., help="Proxy name. Supports wildcards."),
    # TODO: add dryrun option
) -> None:
    """Assign one or more hosts to a proxy. Supports wildcards for both hosts and proxy.

    If multiple proxies match the proxy name, the first match is used."""
    from zabbix_cli.commands.results.proxy import UpdateHostProxyResult
    from zabbix_cli.models import AggregateResult
    from zabbix_cli.output.console import error
    from zabbix_cli.output.console import info
    from zabbix_cli.pyzabbix.types import Host

    hostnames = parse_list_arg(hostname)
    hosts = app.state.client.get_hosts(*hostnames, search=True)
    proxy_ = app.state.client.get_proxy(proxy)

    updated: List[Host] = []
    fail: List[Host] = []
    with app.status("Updating host proxies...") as status:
        for host in hosts:
            status.update(f"Updating {host.host}...")
            if host.proxyid and host.proxyid == proxy_.proxyid:
                info(f"Host {host.host!r} already has proxy {proxy_.name!r}")
                continue
            try:
                app.state.client.update_host_proxy(host, proxy_)
                updated.append(host)
            except Exception as e:
                fail.append(host)
                error(f"Failed to update host {host.host!r}: {e}")

    # TODO: report failed hosts

    # Group results by previous proxy
    proxy_map: Dict[str, List[Host]] = {}
    for host in updated:
        proxy_map.setdefault(host.proxyid or "0", []).append(host)

    render_result(
        AggregateResult(
            message=f"Updated proxy for {len(hosts)}.",
            result=[
                UpdateHostProxyResult.from_result(
                    hosts=hosts,
                    source_proxyid=prev_proxy,
                    dest_proxyid=proxy_.proxyid,
                )
                for prev_proxy, hosts in proxy_map.items()
            ],
        )
    )


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
        ...,
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

    # *_list` var are ugly, but we already have proxies, so...
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


@app.command(name="show_proxies", rich_help_panel=HELP_PANEL)
def show_proxies(
    ctx: typer.Context,
    hosts: bool = typer.Option(
        False,
        "--hosts",
        help="Show hostnames of each host.",
        is_flag=True,
    ),
) -> None:
    """Show all proxies.

    Shows number of hosts for each proxy unless --hosts is passed in."""
    from zabbix_cli.commands.results.proxy import ShowProxiesResult
    from zabbix_cli.models import AggregateResult

    proxies = app.state.client.get_proxies(select_hosts=True)
    render_result(
        AggregateResult(
            result=[ShowProxiesResult.from_result(p, show_hosts=hosts) for p in proxies]
        )
    )
