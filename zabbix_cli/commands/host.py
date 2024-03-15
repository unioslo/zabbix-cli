from __future__ import annotations

import ipaddress
from typing import List
from typing import Optional

import typer

from zabbix_cli._v2_compat import ARGS_POSITIONAL
from zabbix_cli.app import app
from zabbix_cli.app import Example
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.exceptions import ZabbixNotFoundError
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.enums import AgentAvailable
from zabbix_cli.pyzabbix.enums import InterfaceConnectionMode
from zabbix_cli.pyzabbix.enums import InterfaceType
from zabbix_cli.pyzabbix.enums import InventoryMode
from zabbix_cli.pyzabbix.enums import MonitoringStatus
from zabbix_cli.pyzabbix.enums import SNMPAuthProtocol
from zabbix_cli.pyzabbix.enums import SNMPPrivProtocol
from zabbix_cli.pyzabbix.enums import SNMPSecurityLevel
from zabbix_cli.utils.args import parse_list_arg


HELP_PANEL = "Host"


@app.command(name="create_host", rich_help_panel=HELP_PANEL)
def create_host(
    ctx: typer.Context,
    args: Optional[List[str]] = ARGS_POSITIONAL,
    # FIXME: specify hostname as only positional arg!
    hostname_or_ip: str = typer.Option(
        ...,
        "--host",
        "--ip",
        help="Hostname or IP",
    ),
    hostgroups: Optional[str] = typer.Option(
        None,
        "--hostgroups",
        help=("Hostgroup name(s) or ID(s). Comma-separated."),
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
    # Options below are new in V3:
    no_default_hostgroup: bool = typer.Option(
        False,
        "--no-default-hostgroup",
        help="Do not add host to default host group.",
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
) -> None:
    """Create a host.

    Always adds the host to the default host group unless --no-default-hostgroup
    is specified.
    """
    # NOTE: this was one of the first commands ported over to V3, and as such
    # it uses a lot of V2 semantics and patterns. It should be changed to have
    # less implicit behavior such as default hostgroups.
    from zabbix_cli.models import Result
    from zabbix_cli.pyzabbix.types import HostInterface

    if args:
        if len(args) != 4:
            exit_err("create_host takes exactly 4 positional arguments.")
        hostname_or_ip = args[0]
        hostgroups = args[1]
        proxy = args[2]
        status = MonitoringStatus(args[3])

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
    hg_args = []  # type: List[str]
    if not no_default_hostgroup and app.state.config.app.default_hostgroups:
        info(
            f"Will add host to default host group(s): {', '.join(app.state.config.app.default_hostgroups)}"
        )
        hg_args.extend(app.state.config.app.default_hostgroups)
    if hostgroups:
        hostgroup_args = parse_list_arg(hostgroups)
        hg_args.extend(hostgroup_args)
    hgs = [app.state.client.get_hostgroup(hg) for hg in set(hg_args)]
    if not hgs:
        raise ZabbixCLIError("Unable to create a host without at least one host group.")

    # Find a proxy (No match = monitored by zabbix server)
    try:
        prox = app.state.client.get_random_proxy(pattern=proxy)
    except ZabbixNotFoundError:
        prox = None

    if app.state.client.host_exists(hostname_or_ip):
        exit_err(f"Host {hostname_or_ip} already exists.")

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


@app.command(
    name="create_host_interface",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Create an SNMPv2 interface on host 'foo.example.com' with derived DNS name 'foo.example.com (default)",
            "create_host_interface foo.example.com",
        ),
        Example(
            "Create an SNMPv2 interface on host 'foo.example.com' with IP connection",
            "create_host_interface foo.example.com --type snmp --ip 127.0.0.1",
        ),
        Example(
            "Create an SNMPv2 interface on host 'foo.example.com' with different DNS name",
            "create_host_interface foo.example.com --type snmp --dns agent.example.com",
        ),
        Example(
            "Create an SNMPv2 interface on host 'foo' with both IP and DNS, using DNS as enabled agent address",
            "create_host_interface foo --type snmp --connection dns --dns foo.example.com --ip 127.0.0.1",
        ),
        Example(
            "Create an SNMPv3 interface on host 'foo.example.com'",
            "create_host_interface foo.example.com --type snmp --snmp-version 3 --snmp-context-name mycontext --snmp-security-name myuser --snmp-security-level authpriv  --snmp-auth-protocol MD5 --snmp-auth-passphrase mypass --snmp-priv-protocol DES --snmp-priv-passphrase myprivpass",
        ),
        Example(
            "Create an Agent interface on host 'foo.example.com'",
            "create_host_interface foo.example.com --type agent",
        ),
    ],
)
def create_host_interface(
    ctx: typer.Context,
    hostname: str = typer.Argument(
        ...,
        help="Name of host to create interface on.",
        show_default=False,
    ),
    connection: Optional[InterfaceConnectionMode] = typer.Option(
        None,
        "--connection",
        help="Interface connection mode. Required if both --ip and --dns are specified.",
        case_sensitive=False,
    ),
    type_: InterfaceType = typer.Option(
        InterfaceType.SNMP,
        "--type",
        help="Interface type. SNMP enables --snmp-* options.",
        case_sensitive=False,
    ),
    port: Optional[str] = typer.Option(
        None,
        "--port",
        help="Interface port. Defaults to 10050 for agent, 161 for SNMP, 623 for IPMI, and 12345 for JMX.",
    ),
    ip: Optional[str] = typer.Option(
        None,
        "--ip",
        help="IP address of interface.",
        show_default=False,
    ),
    dns: Optional[str] = typer.Option(
        None,
        "--dns",
        help="DNS address of interface.",
        show_default=False,
    ),
    default: bool = typer.Option(
        True, "--default/--no-default", help="Whether this is the default interface."
    ),
    snmp_version: int = typer.Option(
        2,
        "--snmp-version",
        help="SNMP version.",
        min=1,
        max=3,
        show_default=False,
    ),
    snmp_bulk: bool = typer.Option(
        True,
        "--snmp-bulk/--no-snmp-bulk",
        help="Use bulk SNMP requests.",
    ),
    snmp_community: str = typer.Option(
        "${SNMP_COMMUNITY}",
        "--snmp-community",
        help="SNMPv{1,2} community.",
        show_default=False,
    ),
    snmp_max_repetitions: int = typer.Option(
        10,
        "--snmp-max-repetitions",
        help="Max repetitions for SNMPv{2,3} bulk requests.",
        min=1,
    ),
    snmp_security_name: Optional[str] = typer.Option(
        None,
        "--snmp-security-name",
        help="SNMPv3 security name.",
        show_default=False,
    ),
    snmp_context_name: Optional[str] = typer.Option(
        None,
        "--snmp-context-name",
        help="SNMPv3 context name.",
        show_default=False,
    ),
    snmp_security_level: Optional[SNMPSecurityLevel] = typer.Option(
        None,
        "--snmp-security-level",
        help="SNMPv3 security level.",
        show_default=False,
        case_sensitive=False,
    ),
    snmp_auth_protocol: Optional[SNMPAuthProtocol] = typer.Option(
        None,
        "--snmp-auth-protocol",
        help="SNMPv3 auth protocol (authNoPriv & authPriv).",
        show_default=False,
        case_sensitive=False,
    ),
    snmp_auth_passphrase: Optional[str] = typer.Option(
        None,
        "--snmp-auth-passphrase",
        help="SNMPv3 auth passphrase (authNoPriv & authPriv).",
        show_default=False,
    ),
    snmp_priv_protocol: Optional[SNMPPrivProtocol] = typer.Option(
        None,
        "--snmp-priv-protocol",
        help="SNMPv3 priv protocol (authPriv)",
        show_default=False,
        case_sensitive=False,
    ),
    snmp_priv_passphrase: Optional[str] = typer.Option(
        None,
        "--snmp-priv-passphrase",
        help="SNMPv3 priv passphrase (authPriv).",
        show_default=False,
    ),
    # V2-style positional args (deprecated)
    args: Optional[List[str]] = ARGS_POSITIONAL,
) -> None:
    """Create a host interface.

    Creates an SNMPv2 interface by default. Use --type to specify a different type.
    One of --dns and --ip is required. If both are specified, --connection is required.

    [b]NOTE:[/] Can only create secondary host interfaces for interfaces of types
    that already have a default interface. (API limitation)
    """
    from zabbix_cli.models import Result
    from zabbix_cli.pyzabbix.types import CreateHostInterfaceDetails

    # Handle V2 positional args (deprecated)
    if args:
        if len(args) != 6:  # 7 - 1 (hostname)
            exit_err(
                "create_host_interface takes exactly 6 positional arguments (deprecated)."
            )

        connection = InterfaceConnectionMode(args[0])
        type_ = InterfaceType(args[1])
        port = args[2]
        ip = args[3]
        dns = args[4]
        default = args[5] == "1"

    # Determine connection
    if not connection:
        if ip and dns:
            exit_err("Cannot specify both IP and DNS address without --connection.")
        elif ip:
            connection = InterfaceConnectionMode.IP
        else:
            connection = InterfaceConnectionMode.DNS
            if not dns:
                dns = hostname
    use_ip = connection == InterfaceConnectionMode.IP

    # Use default port for type if not specified
    if port is None:
        port = type_.get_port()

    host = app.state.client.get_host(hostname, select_interfaces=True)
    for interface in host.interfaces:
        if not interface.type == type_.as_api_value():
            continue
        if interface.main and interface.interfaceid:
            info(
                f"Host already has a default {type_} interface. It will be set to non-default."
            )
            default = False
            break
    else:
        # No default interface of this type found
        info(f"No default {type_} interface found. Setting new interface as default.")
        default = True

    details = None  # type: CreateHostInterfaceDetails | None
    if type_ == InterfaceType.SNMP:
        details = CreateHostInterfaceDetails(
            version=snmp_version,
            community=snmp_community,
            bulk=int(snmp_bulk),
        )

        if snmp_version > 1:
            details.max_repetitions = snmp_max_repetitions

        # V3-specific options
        if snmp_version == 3:
            if snmp_security_name:
                details.securityname = snmp_security_name
            if snmp_context_name:
                details.contextname = snmp_context_name
            if snmp_security_level:
                details.securitylevel = snmp_security_level.as_api_value()
            # authNoPriv and authPriv:
            if snmp_security_level != SNMPSecurityLevel.NO_AUTH_NO_PRIV:
                if snmp_auth_protocol:
                    details.authprotocol = snmp_auth_protocol.as_api_value()
                if snmp_auth_passphrase:
                    details.authpassphrase = snmp_auth_passphrase
                # authPriv:
                if snmp_security_level == SNMPSecurityLevel.AUTH_PRIV:
                    if snmp_priv_protocol:
                        details.privprotocol = snmp_priv_protocol.as_api_value()
                    if snmp_priv_passphrase:
                        details.privpassphrase = snmp_priv_passphrase

    ifaceid = app.state.client.create_host_interface(
        host=host,
        main=default,
        type=type_,
        use_ip=use_ip,
        ip=ip,
        dns=dns,
        port=str(port),
        details=details,
    )
    render_result(Result(message=f"Created host interface with ID {ifaceid}."))


@app.command(
    name="update_host_interface",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Update the IP address of interface 123.",
            "update_host_interface 123 --ip 127.0.0.1",
        ),
        Example(
            "Change connection type of interface 123 to IP.",
            "update_host_interface 123 --connection ip",
        ),
        Example(
            "Change SNMP community of interface 234 to 'public'.",
            "update_host_interface 234 --snmp-community public",
        ),
    ],
)
def update_host_interface(
    ctx: typer.Context,
    interface_id: str = typer.Argument(
        ...,
        help="ID of interface to update.",
        show_default=False,
    ),
    connection: Optional[InterfaceConnectionMode] = typer.Option(
        None,
        "--connection",
        help="Interface connection mode.",
        case_sensitive=False,
    ),
    port: Optional[str] = typer.Option(
        None,
        "--port",
        help="Interface port.",
    ),
    ip: Optional[str] = typer.Option(
        None,
        "--ip",
        help="IP address of interface.",
        show_default=False,
    ),
    dns: Optional[str] = typer.Option(
        None,
        "--dns",
        help="DNS address of interface.",
        show_default=False,
    ),
    default: bool = typer.Option(
        True, "--default/--no-default", help="Default interface."
    ),
    snmp_version: Optional[int] = typer.Option(
        None,
        "--snmp-version",
        help="SNMP version.",
        min=1,
        max=3,
        show_default=False,
    ),
    snmp_bulk: Optional[bool] = typer.Option(
        None,
        "--snmp-bulk/--no-snmp-bulk",
        help="Use bulk SNMP requests.",
    ),
    snmp_community: Optional[str] = typer.Option(
        None,
        "--snmp-community",
        help="SNMPv{1,2} community.",
        show_default=False,
    ),
    snmp_max_repetitions: Optional[int] = typer.Option(
        None,
        "--snmp-max-repetitions",
        help="Max repetitions for SNMPv{2,3} bulk requests.",
        min=1,
    ),
    snmp_security_name: Optional[str] = typer.Option(
        None,
        "--snmp-security-name",
        help="SNMPv3 security name.",
        show_default=False,
    ),
    snmp_context_name: Optional[str] = typer.Option(
        None,
        "--snmp-context-name",
        help="SNMPv3 context name.",
        show_default=False,
    ),
    snmp_security_level: Optional[SNMPSecurityLevel] = typer.Option(
        None,
        "--snmp-security-level",
        help="SNMPv3 security level.",
        show_default=False,
        case_sensitive=False,
    ),
    snmp_auth_protocol: Optional[SNMPAuthProtocol] = typer.Option(
        None,
        "--snmp-auth-protocol",
        help="SNMPv3 auth protocol (authNoPriv & authPriv).",
        show_default=False,
        case_sensitive=False,
    ),
    snmp_auth_passphrase: Optional[str] = typer.Option(
        None,
        "--snmp-auth-passphrase",
        help="SNMPv3 auth passphrase (authNoPriv & authPriv).",
        show_default=False,
    ),
    snmp_priv_protocol: Optional[SNMPPrivProtocol] = typer.Option(
        None,
        "--snmp-priv-protocol",
        help="SNMPv3 priv protocol (authPriv)",
        show_default=False,
        case_sensitive=False,
    ),
    snmp_priv_passphrase: Optional[str] = typer.Option(
        None,
        "--snmp-priv-passphrase",
        help="SNMPv3 priv passphrase (authPriv).",
        show_default=False,
    ),
) -> None:
    """Update a host interface.

    Host interface type cannot be changed.
    """
    from zabbix_cli.models import Result
    from zabbix_cli.pyzabbix.types import UpdateHostInterfaceDetails

    interface = app.state.client.get_hostinterface(interface_id)

    details = UpdateHostInterfaceDetails(
        version=snmp_version,
        community=snmp_community,
        bulk=int(snmp_bulk) if snmp_bulk is not None else None,
        max_repetitions=snmp_max_repetitions,
        securityname=snmp_security_name,
        contextname=snmp_context_name,
        securitylevel=snmp_security_level.as_api_value()
        if snmp_security_level
        else None,
        authprotocol=snmp_auth_protocol.as_api_value() if snmp_auth_protocol else None,
        authpassphrase=snmp_auth_passphrase,
        privprotocol=snmp_priv_protocol.as_api_value() if snmp_priv_protocol else None,
        privpassphrase=snmp_priv_passphrase,
    )

    if connection:
        if connection == InterfaceConnectionMode.IP:
            use_ip = True
        elif connection == InterfaceConnectionMode.DNS:
            use_ip = False
    else:
        use_ip = None

    app.state.client.update_host_interface(
        interface,
        main=default,
        use_ip=use_ip,
        ip=ip,
        dns=dns,
        port=port,
        details=details,
    )
    render_result(Result(message=f"Updated host interface ({interface_id})."))


@app.command(name="remove_host_interface", rich_help_panel=HELP_PANEL)
def remove_host_interface(
    ctx: typer.Context,
    interface_id: str = typer.Argument(
        ...,
        help="ID of interface to remove.",
        show_default=False,
    ),
) -> None:
    """Remove a host interface."""
    from zabbix_cli.models import Result

    app.state.client.delete_host_interface(interface_id)
    render_result(Result(message=f"Removed host interface ({interface_id})."))


@app.command(name="define_host_monitoring_status", rich_help_panel=HELP_PANEL)
def define_host_monitoring_status(
    hostname: str = typer.Argument(
        ...,
        help="Name of host",
        show_default=False,
    ),
    new_status: MonitoringStatus = typer.Argument(
        ...,
        help="Monitoring status",
        case_sensitive=False,
        show_default=False,
    ),
) -> None:
    """Monitor or unmonitor a host."""
    from zabbix_cli.models import Result

    host = app.state.client.get_host(hostname)
    app.state.client.update_host_status(host, new_status)
    render_result(
        Result(
            message=f"Updated host {hostname!r}. New monitoring status: {new_status}"
        )
    )


@app.command(name="remove_host", rich_help_panel=HELP_PANEL)
def remove_host(
    ctx: typer.Context,
    hostname: str = typer.Argument(..., help="Name of host to remove."),
) -> None:
    """Delete a host."""
    from zabbix_cli.models import Result

    host = app.state.client.get_host(hostname)
    app.state.client.delete_host(host.hostid)
    render_result(Result(message=f"Removed host {hostname!r}."))


@app.command(name="show_host", rich_help_panel=HELP_PANEL)
def show_host(
    ctx: typer.Context,
    hostname_or_id: str = typer.Argument(..., help="Hostname or ID."),
    # This is the legacy filter argument from V2
    filter_legacy: Optional[str] = typer.Argument(None, hidden=True),
    agent: Optional[AgentAvailable] = typer.Option(
        None,
        "--agent",
        "--available",
        help="Agent availability status.",
        case_sensitive=False,
    ),
    maintenance: Optional[bool] = typer.Option(
        None,
        "--maintenance/--no-maintenance",
        help="Maintenance status.",
    ),
    monitored: Optional[bool] = typer.Option(
        None,
        "--monitored/--no-monitored",
        help="Monitoring status.",
    ),
) -> None:
    """Show a specific host."""
    from zabbix_cli.commands.results.host import HostFilterArgs

    args = HostFilterArgs.from_command_args(
        filter_legacy, agent, maintenance, monitored
    )

    host = app.state.client.get_host(
        hostname_or_id,
        select_groups=True,
        select_templates=True,
        sort_field="host",
        sort_order="ASC",
        search=True,  # we allow wildcard patterns
        maintenance=args.maintenance_status,
        monitored=args.status,
        agent_status=args.available,
    )

    render_result(host)


@app.command(name="show_hosts", rich_help_panel=HELP_PANEL)
def show_hosts(
    ctx: typer.Context,
    # This is the legacy filter argument from V2
    agent: Optional[AgentAvailable] = typer.Option(
        None,
        "--agent",
        "--available",
        help="Agent availability status.",
        case_sensitive=False,
    ),
    maintenance: Optional[bool] = typer.Option(
        None,
        "--maintenance/--no-maintenance",
        help="Maintenance status.",
    ),
    monitored: Optional[bool] = typer.Option(
        None,
        "--monitored/--unmonitored",
        help="Monitoring status.",
    ),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        help="Limit number of results.",
    ),
    # V2 Legacy filter argument
    filter_legacy: Optional[str] = typer.Argument(None, hidden=True),
    # TODO: add sorting mode?
) -> None:
    """Show all hosts.

    Hosts can be filtered by agent, monitoring and maintenance status.
    Hosts are sorted by name.
    """
    from zabbix_cli.models import AggregateResult
    from zabbix_cli.commands.results.host import HostFilterArgs

    args = HostFilterArgs.from_command_args(
        filter_legacy, agent, maintenance, monitored
    )
    hosts = app.state.client.get_hosts(
        "*",
        select_groups=True,
        select_templates=True,
        sort_field="host",
        sort_order="ASC",
        search=True,  # we use a wildcard pattern here!
        maintenance=args.maintenance_status,
        monitored=args.status,
        agent_status=args.available,
    )
    if limit:
        hosts = hosts[: abs(limit)]
    render_result(AggregateResult(result=hosts))


@app.command(name="show_host_interfaces", rich_help_panel=HELP_PANEL)
def show_host_interfaces(
    hostname_or_id: str = typer.Argument(..., help="Hostname or ID"),
) -> None:
    """Show host interfaces."""
    from zabbix_cli.models import AggregateResult

    host = app.state.client.get_host(hostname_or_id, select_interfaces=True)
    render_result(AggregateResult(result=host.interfaces))


@app.command(name="show_host_inventory", rich_help_panel=HELP_PANEL)
def show_host_inventory(
    hostname_or_id: str = typer.Argument(..., help="Hostname or ID"),
) -> None:
    """Show host inventory details for a specific host."""
    # TODO: support undocumented filter argument from V2
    # TODO: Add mapping of inventory keys to human readable names (Web GUI names)
    host = app.state.client.get_host(hostname_or_id, select_inventory=True)
    render_result(host.inventory)


@app.command(name="update_host_inventory", rich_help_panel=HELP_PANEL)
def update_host_inventory(
    ctx: typer.Context,
    hostname_or_id: str = typer.Argument(..., help="Hostname or ID of host."),
    key: str = typer.Argument(..., help="Inventory key"),
    value: str = typer.Argument(..., help="Inventory value"),
) -> None:
    """Update a host inventory field.

    Inventory fields in the API do not always match Web GUI field names.
    Use `zabbix-cli -o json show_host_inventory <hostname>` to see the available fields.
    """
    from zabbix_cli.models import Result

    host = app.state.client.get_host(hostname_or_id)
    to_update = {key: value}
    app.state.client.update_host_inventory(host, to_update)
    render_result(Result(message=f"Updated inventory field {key!r} for host {host}."))
