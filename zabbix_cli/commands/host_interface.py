from __future__ import annotations

from typing import Optional

import typer

from zabbix_cli._v2_compat import ARGS_POSITIONAL
from zabbix_cli.app import Example
from zabbix_cli.app import app
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.enums import InterfaceConnectionMode
from zabbix_cli.pyzabbix.enums import InterfaceType
from zabbix_cli.pyzabbix.enums import SNMPAuthProtocol
from zabbix_cli.pyzabbix.enums import SNMPPrivProtocol
from zabbix_cli.pyzabbix.enums import SNMPSecurityLevel
from zabbix_cli.utils.args import check_at_least_one_option_set

HELP_PANEL = "Host Interface"


@app.command(
    name="create_host_interface",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Create an SNMPv2 interface on host 'foo.example.com' with derived DNS name 'foo.example.com' (default)",
            "create_host_interface foo.example.com",
        ),
        Example(
            "Create an SNMPv2 interface on host 'foo.example.com' with IP connection",
            "create_host_interface foo.example.com --type snmp --ip 127.0.0.1",
        ),
        Example(
            "Create an SNMPv2 interface on host 'foo.example.com' with different DNS name",
            "create_host_interface foo.example.com --type snmp --dns snmp.example.com",
        ),
        Example(
            "Create an SNMPv2 interface on host 'foo' with both IP and DNS, using DNS as enabled address",
            "create_host_interface foo --type snmp --connection dns --dns snmp.example.com --ip 127.0.0.1",
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
    args: Optional[list[str]] = ARGS_POSITIONAL,
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
                f"Host already has a default {type_} interface. New interface will be created as non-default."
            )
            default = False
            break
    else:
        # No default interface of this type found
        info(f"No default {type_} interface found. Setting new interface as default.")
        default = True

    details: Optional[CreateHostInterfaceDetails] = None
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


@app.command(name="remove_host_interface", rich_help_panel=HELP_PANEL)
def remove_host_interface(
    ctx: typer.Context,
    interface_id: str = typer.Argument(
        help="ID of interface to remove.",
        show_default=False,
    ),
) -> None:
    """Remove a host interface."""
    from zabbix_cli.models import Result

    app.state.client.delete_host_interface(interface_id)
    render_result(Result(message=f"Removed host interface ({interface_id})."))


@app.command(name="show_host_interfaces", rich_help_panel=HELP_PANEL)
def show_host_interfaces(
    hostname_or_id: str = typer.Argument(
        help="Hostname or ID",
        show_default=False,
    ),
) -> None:
    """Show host interfaces."""
    from zabbix_cli.models import AggregateResult

    host = app.state.client.get_host(hostname_or_id, select_interfaces=True)
    render_result(AggregateResult(result=host.interfaces))


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
        show_default=False,
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

    check_at_least_one_option_set(ctx)

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
