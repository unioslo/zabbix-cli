from __future__ import annotations

from typing import Optional

import typer

from zabbix_cli.app import app
from zabbix_cli.models import Result
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result


class ProxyResult(Result):
    """Result type for proxy commands."""

    old: Optional[str] = None
    """ID of the old proxy."""
    new: Optional[str] = None
    """ID of the new proxy."""


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
        ProxyResult(
            message=f"Updated proxy for host {host.host} to {proxy.name}",
            old=host.proxyid,
            new=proxy.proxyid,
        )
    )
