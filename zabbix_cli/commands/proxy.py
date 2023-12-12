from __future__ import annotations

import itertools
import logging
import random
from typing import List
from typing import Optional
from typing import TYPE_CHECKING

import typer
from pydantic import BaseModel

from zabbix_cli.app import app
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.models import Result
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.utils.utils import compile_pattern
from zabbix_cli.utils.utils import convert_int

if TYPE_CHECKING:
    from zabbix_cli.pyzabbix.types import Proxy  # noqa: F401


class UpdateHostProxyResult(BaseModel):
    """Result type for `update_host_proxy` command."""

    source: Optional[str] = None
    """ID of the source (old) proxy."""
    destination: Optional[str] = None
    """ID of the destination (new) proxy."""


@app.command(name="update_host_proxy")
def update_host_proxy(
    ctx: typer.Context,
    hostname_or_id: Optional[str] = typer.Argument(None, help="Hostname or ID"),
    proxy_name: Optional[str] = typer.Argument(None, help="Name of proxy to update"),
) -> None:
    if not hostname_or_id:
        hostname_or_id = str_prompt("Hostname or ID")
    if not proxy_name:
        proxy_name = str_prompt("Proxy name")
    proxy = app.state.client.get_proxy(proxy_name)
    host = app.state.client.get_host(hostname_or_id)

    if host.proxyid and host.proxyid == proxy.proxyid:
        exit_err(f"Host {host} already has proxy {proxy.name!r}")

    app.state.client.update_host_proxy(host, proxy)
    render_result(
        Result(
            message=f"Updated proxy for host {host} to {proxy.name!r}",
            result=UpdateHostProxyResult(
                source=host.proxyid,
                destination=proxy.proxyid,
            ),
        )
    )


class MoveProxyHostsResult(UpdateHostProxyResult):
    """Result type for `move_proxy_hosts` command."""

    hosts: List[str] = []


@app.command(name="move_proxy_hosts")
def move_proxy_hosts(
    ctx: typer.Context,
    proxy_src: Optional[str] = typer.Argument(None, help="Proxy to move hosts from."),
    proxy_dst: Optional[str] = typer.Argument(None, help="Proxy to move hosts to."),
    # Hidden arg to match V2 (legacy) command signature
    host_filter_arg: Optional[str] = typer.Argument(
        None, help="Filter hosts to move.", hidden=True
    ),
    # Prefer --filter over positional arg
    host_filter: Optional[str] = typer.Option(
        None, "--filter", help="Pattern to filter hosts to move by."
    ),
) -> None:
    if not proxy_src:
        proxy_src = str_prompt("Source proxy")
    if not proxy_dst:
        proxy_dst = str_prompt("Destination proxy")
    # We don't prompt for host filter, because it's optional
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

    # Do filtering client-side
    if filter_pattern:
        hosts = [host for host in hosts if filter_pattern.match(host.host)]
        if not hosts:
            exit_err(f"No hosts matched filter {hfilter!r}.")

    app.state.client.move_hosts_to_proxy(hosts, destination_proxy)

    render_result(
        Result(
            message=f"Moved {len(hosts)} host(s) from {source_proxy.name!r} to {destination_proxy.name!r}",
            result=MoveProxyHostsResult(
                source=source_proxy.proxyid,
                destination=destination_proxy.proxyid,
                hosts=[host.host for host in hosts],
            ),
        )
    )


class LoadBalancedProxy(BaseModel):
    proxyid: str
    name: str
    weight: int


class ProxySpec(BaseModel):
    id: str
    name: str
    weight: int
    count: int = 0


class LoadBalanceProxyHostsResult(BaseModel):
    """Result type for `load_balance_proxy_hosts` command."""

    hosts: List[str] = []
    proxies: List[ProxySpec] = []


@app.command(name="load_balance_proxy_hosts")
def load_balance_proxy_hosts(
    ctx: typer.Context,
    proxies: Optional[str] = typer.Argument(
        None,
        help="Comma delimited list of proxies to share hosts between.",
        metavar="[proxy1,proxy2,...]",
    ),
    # Prefer --weight over positional arg
    weight: Optional[str] = typer.Argument(
        None,
        # "--weight",
        help="Optional comma delimited list of weights for each proxy.",
        metavar="[weight1,weight2,...]",
    ),
) -> None:
    if not proxies:
        # TODO: add some sort of multi prompt for this
        proxies = str_prompt("Proxies")
    if not weight:
        weight = str_prompt(
            "Weights (optional)", empty_ok=True, default="", show_default=False
        )

    proxy_names = [p.strip() for p in proxies.split(",")]
    if weight:
        weights = list(map(convert_int, (w.strip() for w in weight.split(","))))
    else:
        weights = [1] * len(proxy_names)  # default to equal weights

    if len(proxy_names) != len(weights):
        exit_err("Number of proxies must match number of weights.")
    elif len(proxy_names) < 2:
        exit_err("Must specify at least two proxies to load balance.")

    # I kind of hate `*_list` vars, but we already have proxies, so...
    proxy_list = [app.state.client.get_proxy(p, select_hosts=True) for p in proxy_names]

    # Make sure list of proxies is in same order we specified them
    if not all(p.name == n for p, n in zip(proxy_list, proxy_names)):
        # TODO: Manually sort list and try again here (it shouldn't happen though!)
        exit_err("Returned list of proxies does not match specified list.")

    all_hosts = list(itertools.chain.from_iterable(p.hosts for p in proxy_list))
    if not all_hosts:
        exit_err("Proxies have no hosts to load balance.")
    logging.debug(f"Found {len(all_hosts)} hosts to load balance.")

    # Mapping of proxy name to stats for each proxy
    proxy_specs = {
        p.name: ProxySpec(id=p.proxyid, name=p.name, weight=w)
        for p, w in zip(proxy_list, weights)
    }

    # FIXME: this is a MESS!
    host_map = {host.hostid: host for host in all_hosts}
    host_proxy_relation = {}  # type: dict[str, Proxy] # hostid -> Proxy (unhashable type Host)
    for host in all_hosts:
        # Assign random proxy to host based on weights
        host_proxy_relation[host.hostid] = random.choices(
            proxy_list, weights=weights, k=1
        )[0]

    # Abort on failure
    try:
        for proxy in proxy_list:
            hostids = []  #  type: list[str] # list of hostids to move to proxy
            logging.debug(f"Proxy {proxy.name!r} has {len(proxy.hosts)} hosts.")
            for hostid, proxy in host_proxy_relation.items():
                if proxy.proxyid == proxy.proxyid:
                    hostids.append(hostid)
            if not hostids:
                logging.debug(f"Proxy {proxy.name!r} has no hosts.")
                continue
            logging.debug(f"Moving {len(hostids)} hosts to proxy {proxy.name!r}")

            app.state.client.move_hosts_to_proxy(
                # blind indexing is a bit scary, but the keys SHOULD be valid!
                hosts=[host_map[hostid] for hostid in hostids],
                proxy=proxy,
            )
            proxy_specs[proxy.name].count = len(hostids)
    except Exception as e:
        raise ZabbixCLIError(f"Failed to load balance hosts: {e}") from e

    render_result(
        Result(
            message=f"Load balanced {len(all_hosts)} host(s) between {len(proxy_list)} proxies.",
            result=LoadBalanceProxyHostsResult(
                proxies=[spec for spec in proxy_specs.values()],
                hosts=[host.host for host in all_hosts],
            ),
        )
    )
