from __future__ import annotations

import itertools
import logging
import random
from typing import List
from typing import Optional

import typer
from pydantic import BaseModel
from pydantic import model_serializer

from zabbix_cli.app import app
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.models import ColsRowsType
from zabbix_cli.models import Result
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import success
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import Proxy
from zabbix_cli.utils.args import parse_int_list_arg
from zabbix_cli.utils.utils import compile_pattern


HELP_PANEL = "Proxy"


class UpdateHostProxyResult(BaseModel):
    """Result type for `update_host_proxy` command."""

    source: Optional[str] = None
    """ID of the source (old) proxy."""
    destination: Optional[str] = None
    """ID of the destination (new) proxy."""


@app.command(name="update_host_proxy", rich_help_panel=HELP_PANEL)
def update_host_proxy(
    ctx: typer.Context,
    hostname_or_id: Optional[str] = typer.Argument(None, help="Hostname or ID"),
    proxy_name: Optional[str] = typer.Argument(
        None, help="Name of new proxy for host."
    ),
) -> None:
    """Change the proxy for a host."""
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


@app.command(name="move_proxy_hosts", rich_help_panel=HELP_PANEL)
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
    """Move hosts from one proxy to another."""
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
            message=f"Moved {len(hosts)} hosts from {source_proxy.name!r} to {destination_proxy.name!r}",
            result=MoveProxyHostsResult(
                source=source_proxy.proxyid,
                destination=destination_proxy.proxyid,
                hosts=[host.host for host in hosts],
            ),
        )
    )


class LBProxy(BaseModel):
    """A load balanced proxy."""

    proxy: Proxy
    hosts: List[Host] = []
    weight: int
    count: int = 0

    @model_serializer
    def ser_model(self):
        return {
            "name": self.proxy.name,
            "proxyid": self.proxy.proxyid,
            "weight": self.weight,
            "count": self.count,
            "hosts": [h.host for h in self.hosts],
        }


class LBProxyResult(TableRenderable):
    """Result type for `load_balance_proxy_hosts` command."""

    proxies: List[LBProxy]

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["Proxy", "Weight", "Hosts"]
        rows = []
        for proxy in self.proxies:
            rows.append([proxy.proxy.name, str(proxy.weight), str(len(proxy.hosts))])
        return cols, rows


@app.command(name="load_balance_proxy_hosts", rich_help_panel=HELP_PANEL)
def load_balance_proxy_hosts(
    ctx: typer.Context,
    proxies: Optional[str] = typer.Argument(
        None,
        help="Comma delimited list of proxies to share hosts between.",
        metavar="[proxy1,proxy2,...]",
        show_default=False,
    ),
    weight: Optional[str] = typer.Argument(
        None,
        help="Optional comma delimited list of weights for each proxy.",
        metavar="[weight1,weight2,...]",
        show_default=False,
    ),
) -> None:
    """Spreads hosts between multiple proxies.

    Hosts are determined based on the hosts assigned to the given proxies.
    Weighting for the load balancing is optional, and defaults to equal weights.

    To load balance hosts evenly between two proxies:
        [green]load_balance_proxy_hosts proxy1,proxy2[/green]

    To place twice as many hosts on proxy1 as proxy2:
        [green]load_balance_proxy_hosts proxy1,proxy2 2,1[/green]

    Multiple proxies and weights can be specified:
        [green]load_balance_proxy_hosts proxy1,proxy2,proxy3 1,1,2[/green]
    """
    if not proxies:
        # TODO: add some sort of multi prompt for this
        proxies = str_prompt("Proxies")
    if not weight:
        weight = str_prompt(
            "Weights (optional)", empty_ok=True, default="", show_default=False
        )

    proxy_names = [p.strip() for p in proxies.split(",")]
    if weight:
        weights = parse_int_list_arg(weight)
    else:
        weights = [1] * len(proxy_names)  # default to equal weights

    # Ensure arguments are valid
    if len(proxy_names) != len(weights):
        exit_err("Number of proxies must match number of weights.")
    elif len(proxy_names) < 2:
        exit_err("Must specify at least two proxies to load balance.")
    elif all(w == 0 for w in weights):
        exit_err("All weights cannot be zero.")

    # *_list` var are ugly, but we already have proxies, so...
    proxy_list = [app.state.client.get_proxy(p, select_hosts=True) for p in proxy_names]

    # Make sure list of proxies is in same order we specified them
    if not all(p.name == n for p, n in zip(proxy_list, proxy_names)):
        # TODO: Manually sort list and try again here (it shouldn't happen though!)
        exit_err("Returned list of proxies does not match specified list.")

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
