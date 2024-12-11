from __future__ import annotations

import ipaddress
from typing import Optional

import typer

from zabbix_cli._v2_compat import ARGS_POSITIONAL
from zabbix_cli.app import Example
from zabbix_cli.app import app
from zabbix_cli.commands.common.args import OPTION_LIMIT
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.exceptions import ZabbixNotFoundError
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.enums import ActiveInterface
from zabbix_cli.pyzabbix.enums import InterfaceType
from zabbix_cli.pyzabbix.enums import InventoryMode
from zabbix_cli.pyzabbix.enums import MonitoringStatus
from zabbix_cli.utils.args import check_at_least_one_option_set
from zabbix_cli.utils.args import parse_list_arg

HELP_PANEL = "Host"


@app.command(name="create_host", rich_help_panel=HELP_PANEL)
def create_host(
    ctx: typer.Context,
    hostname_or_ip: str = typer.Argument(
        help="Hostname or IP",
        show_default=False,
    ),
    hostgroups: Optional[str] = typer.Option(
        None,
        "--hostgroup",
        help="Hostgroup name(s) or ID(s). Comma-separated.",
    ),
    proxy: Optional[str] = typer.Option(
        ".+",
        "--proxy",
        help="Proxy server used to monitor the host. Supports regular expressions.",
    ),
    status: MonitoringStatus = typer.Option(
        MonitoringStatus.ON.value,
        "--status",
        help="Host monitoring status.",
    ),
    default_hostgroup: bool = typer.Option(
        True,
        "--default-hostgroup/--no-default-hostgroup",
        help="Add host to default host group(s) defined in config.",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        help="Visible name of the host. Uses hostname or IP if omitted.",
    ),
    description: Optional[str] = typer.Option(
        None,
        "--description",
        help="Description of the host.",
    ),
    # LEGACY: V2-style positional args
    args: Optional[list[str]] = ARGS_POSITIONAL,
) -> None:
    """Create a host.

    Always adds the host to the default host group unless --no-default-hostgroup
    is specified.

    Selects a random proxy by default unless [option]--proxy[/] [value]-[/] is specified.
    """
    # NOTE: this was one of the first commands ported over to V3, and as such
    # it uses a lot of V2 semantics and patterns. It should be changed to have
    # less implicit behavior such as default hostgroups.
    from zabbix_cli.models import Result
    from zabbix_cli.output.formatting.grammar import pluralize_no_count as pnc
    from zabbix_cli.pyzabbix.types import HostInterface
    from zabbix_cli.pyzabbix.utils import get_random_proxy

    if args:
        if len(args) != 3:
            # Hostname + legacy args = 4
            exit_err("create_host takes exactly 4 positional arguments.")
        hostgroups = args[0]
        proxy = args[1]
        status = MonitoringStatus(args[2])

    host_name = name or hostname_or_ip
    if app.state.client.host_exists(host_name):
        exit_err(f"Host {host_name!r} already exists")

    # Check if we are using a hostname or IP
    try:
        ipaddress.ip_address(hostname_or_ip)
    except ValueError:
        useip = False
        interface_ip = ""
        interface_dns = hostname_or_ip
    else:
        useip = True
        interface_ip = hostname_or_ip
        interface_dns = ""

    interfaces = [
        HostInterface(
            type=InterfaceType.AGENT.as_api_value(),
            main=True,
            useip=useip,
            ip=interface_ip,
            dns=interface_dns,
            port=InterfaceType.AGENT.get_port(),
        )
    ]

    # Determine host group IDs
    hg_args: list[str] = []

    # Default host groups from config
    def_hgs = app.state.config.app.default_hostgroups
    if default_hostgroup and def_hgs:
        grp = pnc("group", len(def_hgs))  # pluralize
        info(f"Will add host to default host {grp}: {', '.join(def_hgs)}")
        hg_args.extend(def_hgs)

    # Host group args
    if hostgroups:
        hostgroup_args = parse_list_arg(hostgroups)
        hg_args.extend(hostgroup_args)
    hgs = [app.state.client.get_hostgroup(hg) for hg in set(hg_args)]
    if not hgs:
        raise ZabbixCLIError("Unable to create a host without at least one host group.")

    # Find a proxy (No match = monitored by zabbix server)
    try:
        prox = get_random_proxy(app.state.client, pattern=proxy)
    except ZabbixNotFoundError:
        prox = None

    if app.state.client.host_exists(hostname_or_ip):
        exit_err(f"Host {hostname_or_ip!r} already exists.")

    host_id = app.state.client.create_host(
        host_name,
        groups=hgs,
        proxy=prox,
        status=status,
        interfaces=interfaces,
        inventory_mode=InventoryMode.AUTOMATIC,
        inventory={"name": hostname_or_ip},
        description=description,
    )
    render_result(Result(message=f"Created host {host_name!r} ({host_id})"))


@app.command(name="remove_host", rich_help_panel=HELP_PANEL)
def remove_host(
    ctx: typer.Context,
    hostname: str = typer.Argument(
        help="Name of host to remove.",
        show_default=False,
    ),
) -> None:
    """Delete a host."""
    from zabbix_cli.models import Result

    host = app.state.client.get_host(hostname)
    app.state.client.delete_host(host.hostid)
    render_result(Result(message=f"Removed host {hostname!r}."))


@app.command(name="show_host", rich_help_panel=HELP_PANEL)
def show_host(
    ctx: typer.Context,
    hostname_or_id: str = typer.Argument(
        help="Hostname or ID.",
        show_default=False,
    ),
    active: Optional[ActiveInterface] = typer.Option(
        None,
        "--active",
        help="Active interface availability.",
        case_sensitive=False,
    ),
    maintenance: Optional[bool] = typer.Option(
        None,
        "--maintenance/--no-maintenance",
        help="Maintenance status.",
        show_default=False,
    ),
    monitored: Optional[bool] = typer.Option(
        None,
        "--monitored/--no-monitored",
        help="Monitoring status.",
        show_default=False,
    ),
    # This is the legacy filter argument from V2
    filter_legacy: Optional[str] = typer.Argument(None, hidden=True),
) -> None:
    """Show a specific host."""
    from zabbix_cli.commands.results.host import HostFilterArgs
    from zabbix_cli.pyzabbix.utils import get_proxy_map

    args = HostFilterArgs.from_command_args(
        filter_legacy, active, maintenance, monitored
    )

    host = app.state.client.get_host(
        hostname_or_id,
        select_groups=True,
        select_templates=True,
        select_interfaces=True,
        sort_field="host",
        sort_order="ASC",
        search=True,  # we allow wildcard patterns
        maintenance=args.maintenance_status,
        monitored=args.status,
        active_interface=args.active,
    )

    # HACK: inject proxy map to host for rendering
    # TODO: cache the proxy map for some time? In case we run show_host multiple times
    proxy_map = get_proxy_map(app.state.client)
    host.set_proxy(proxy_map)

    render_result(host)


@app.command(
    name="show_hosts",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Show all monitored (enabled) hosts",
            "show_hosts --monitored",
        ),
        Example(
            "Show all hosts with names ending in '.example.com'",
            "show_hosts '*.example.com'",
        ),
        Example(
            "Show all hosts with names ending in '.example.com' or '.example.net'",
            "show_hosts '*.example.com,*.example.net'",
        ),
        Example(
            "Show all hosts with names ending in '.example.com' or '.example.net'",
            "show_hosts '*.example.com,*.example.net'",
        ),
        Example(
            "Show all hosts from a given hostgroup",
            "show_hosts --hostgroup 'Linux servers'",
        ),
    ],
)
def show_hosts(
    ctx: typer.Context,
    hostname_or_id: Optional[str] = typer.Argument(
        None,
        help="Hostname pattern or ID to filter by. Comma-separated. Supports wildcards.",
        show_default=False,
    ),
    hostgroup: Optional[str] = typer.Option(
        None,
        "--hostgroup",
        help="Hostgroup name(s) or ID(s). Comma-separated.",
    ),
    active: Optional[ActiveInterface] = typer.Option(
        None,
        "--active",
        help="Active interface availability.",
        case_sensitive=False,
    ),
    maintenance: Optional[bool] = typer.Option(
        None,
        "--maintenance/--no-maintenance",
        help="Maintenance status.",
        show_default=False,
    ),
    monitored: Optional[bool] = typer.Option(
        None,
        "--monitored/--unmonitored",
        help="Monitoring status.",
        show_default=False,
    ),
    limit: int = OPTION_LIMIT,
    # V2 Legacy filter argument
    filter_legacy: Optional[str] = typer.Argument(None, hidden=True),
    # TODO: add sorting mode?
) -> None:
    """Show all hosts.

    Hosts can be filtered by agent, monitoring and maintenance status.
    Hosts are sorted by name.
    """
    from zabbix_cli.commands.results.host import HostFilterArgs
    from zabbix_cli.models import AggregateResult
    from zabbix_cli.pyzabbix.utils import get_proxy_map

    # Unified parsing of legacy and V3-style filter arguments
    args = HostFilterArgs.from_command_args(
        filter_legacy, active, maintenance, monitored
    )

    hostnames_or_ids = parse_list_arg(hostname_or_id)
    hgs = parse_list_arg(hostgroup)
    hostgroups = [app.state.client.get_hostgroup(hg) for hg in hgs]

    with app.status("Fetching hosts..."):
        hosts = app.state.client.get_hosts(
            *hostnames_or_ids,
            select_groups=True,
            select_templates=True,
            sort_field="host",
            sort_order="ASC",
            search=True,  # we use a wildcard pattern here!
            maintenance=args.maintenance_status,
            monitored=args.status,
            active_interface=args.active,
            limit=limit,
            hostgroups=hostgroups,
        )

    # HACK: inject proxy map for each host
    # By default, each host only has a proxy ID.
    # We need to determine inside each host object which
    # Proxy object to select
    proxy_map = get_proxy_map(app.state.client)
    for host in hosts:
        host.set_proxy(proxy_map)

    render_result(AggregateResult(result=hosts))


@app.command(name="update_host", rich_help_panel=HELP_PANEL)
def update_host(
    ctx: typer.Context,
    hostname_or_ip: str = typer.Argument(
        help="Hostname or IP",
        show_default=False,
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        help="Visible name of the host.",
    ),
    description: Optional[str] = typer.Option(
        None,
        "--description",
        help="Description of the host.",
    ),
) -> None:
    """Update basic information about a host.

    Other notable commands to update a host:

    - [command]add_host_to_hostgroup[/]
    - [command]create_host_interface[/]
    - [command]monitor_host[/]
    - [command]remove_host_from_hostgroup[/]
    - [command]update_host_interface[/]
    - [command]update_host_inventory[/]
    """
    from zabbix_cli.models import Result

    check_at_least_one_option_set(ctx)

    host = app.state.client.get_host(hostname_or_ip)
    app.state.client.update_host(
        host,
        name=name,
        description=description,
    )
    render_result(Result(message=f"Updated host {host}."))
