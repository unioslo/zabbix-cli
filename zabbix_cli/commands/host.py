from __future__ import annotations

import ipaddress
from typing import List
from typing import Optional
from typing import TYPE_CHECKING

import typer
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from zabbix_cli._v2_compat import ARGS_POSITIONAL
from zabbix_cli.app import app
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.exceptions import ZabbixNotFoundError
from zabbix_cli.models import AggregateResult
from zabbix_cli.models import ColsRowsType
from zabbix_cli.models import Result
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.types import AgentAvailable
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import HostInterface
from zabbix_cli.pyzabbix.types import HostInterfaceDetails
from zabbix_cli.pyzabbix.types import InterfaceConnectionMode
from zabbix_cli.pyzabbix.types import InterfaceType
from zabbix_cli.pyzabbix.types import InventoryMode
from zabbix_cli.pyzabbix.types import MaintenanceStatus
from zabbix_cli.pyzabbix.types import MonitoringStatus
from zabbix_cli.pyzabbix.types import SNMPAuthProtocol
from zabbix_cli.pyzabbix.types import SNMPPrivProtocol
from zabbix_cli.pyzabbix.types import SNMPSecurityLevel
from zabbix_cli.utils.args import parse_list_arg
from zabbix_cli.utils.commands import ARG_HOSTNAME_OR_ID

if TYPE_CHECKING:
    from zabbix_cli.models import ColsType  # noqa: F401
    from zabbix_cli.models import RowsType  # noqa: F401


HELP_PANEL = "Host"


@app.command(name="create_host", rich_help_panel=HELP_PANEL)
def create_host(
    ctx: typer.Context,
    args: Optional[List[str]] = ARGS_POSITIONAL,
    # FIXME: specify hostname as only positional arg!
    hostname_or_ip: Optional[str] = typer.Option(
        None,
        "--host",
        "--ip",
        help="Hostname or IP",
    ),
    hostgroups: Optional[str] = typer.Option(
        None,
        "--hostgroups",
        help=(
            "Hostgroup names or IDs. "
            "One can define several values in a comma separated list. "
            "Command will fail if both --hostgroups option and "
            "[green]default_hostgroup[/] in config are empty. "
        ),
    ),
    proxy: Optional[str] = typer.Option(
        ".+",
        "--proxy",
        help=(
            "Proxy server used to monitor the host. "
            "Supports regular expressions to define a group of proxies, "
            "from which one will be selected randomly. "
            "Selects a random proxy from the list of available proxies if "
            "no proxy is specified. "
        ),
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
    if args:
        if len(args) != 4:
            exit_err("create_host takes exactly 4 positional arguments.")
        hostname_or_ip = args[0]
        hostgroups = args[1]
        proxy = args[2]
        status = MonitoringStatus(args[3])
    if not hostname_or_ip:
        hostname_or_ip = str_prompt("Hostname or IP")
    if not hostgroups:
        hostgroups = str_prompt(
            "Hostgroup(s)", default="", show_default=False, empty_ok=True
        )

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
            type=1,
            main=True,
            useip=useip,
            ip=interface_ip,
            dns=interface_dns,
            port="10050",
        )
    ]

    # Determine host group IDs
    hg_args = []
    if not no_default_hostgroup and app.state.config.app.default_hostgroups:
        hg_args.extend(app.state.config.app.default_hostgroups)
    # TODO: add some sort of plural prompt so we don't have to split manually
    if hostgroups:
        hostgroup_args = parse_list_arg(hostgroups)
        hg_args.extend(hostgroup_args)
    hgs = [app.state.client.get_hostgroup(hg) for hg in hg_args]
    if not hgs:
        raise ZabbixCLIError("Unable to create a host without at least one host group.")

    # Find a proxy (No match = monitored by zabbix server)
    try:
        prox = app.state.client.get_random_proxy(pattern=proxy)
    except ZabbixNotFoundError:
        prox = None

    try:
        app.state.client.get_host(hostname_or_ip)
    except ZabbixNotFoundError:
        pass  # OK: host does not exist
    except Exception as e:
        raise ZabbixCLIError(f"Error while checking if host exists: {e}")
    else:
        raise ZabbixCLIError(f"Host {hostname_or_ip} already exists.")

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
    # TODO: cache host ID


@app.command(
    name="create_host_interface",
    # options_metavar="[hostname] [interface connection] [interface type] [interface port] [interface IP] [interface DNS] [default interface]",
    rich_help_panel=HELP_PANEL,
)
def create_host_interface(
    ctx: typer.Context,
    hostname: str = typer.Argument(
        ...,
        help="Name of host to create interface on.",
        show_default=False,
    ),
    connection: InterfaceConnectionMode = typer.Option(
        InterfaceConnectionMode.DNS,
        "--connection",
        help="Interface connection mode.",
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
        help="IP address. Must be specified if connection mode is IP.",
        show_default=False,
    ),
    dns: Optional[str] = typer.Option(
        None,
        "--dns",
        help="DNS address. Must be specified if connection mode is DNS.",
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
    ),
    snmp_auth_protocol: Optional[SNMPAuthProtocol] = typer.Option(
        None,
        "--snmp-auth-protocol",
        help="SNMPv3 auth protocol (authNoPriv & authPriv).",
        show_default=False,
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
    Agent address defaults to hostname if connection mode is DNS, and 127.0.0.1

    [b]NOTE:[/] Can only create secondary host interfaces for interfaces of types
    that already have a default interface. (API limitation)
    """
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

        # Changed from V2: Remove prompts
        hostname = str_prompt("Hostname")
    if connection == InterfaceConnectionMode.IP:
        use_ip = True
        ip = "127.0.0.1"
    else:
        use_ip = False
        dns = hostname

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
        info(f"No default {type_} interface found. Setting new interface to default.")
        default = True

    details = None  # type: HostInterfaceDetails | None
    if type_ == InterfaceType.SNMP:
        details = HostInterfaceDetails(
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

    ifaceid = app.state.client.create_hostinterface(
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


@app.command(name="define_host_monitoring_status", rich_help_panel=HELP_PANEL)
def define_host_monitoring_status(
    hostname: Optional[str] = typer.Argument(
        None,
        help="Name of host",
        show_default=False,
    ),
    new_status: Optional[MonitoringStatus] = typer.Argument(
        None,
        help="Monitoring status",
        case_sensitive=False,
        show_default=False,
    ),
) -> None:
    """Monitor or unmonitor a host."""
    if not hostname:
        hostname = str_prompt("Hostname")
    if new_status is None:
        new_status = MonitoringStatus.from_prompt()
    host = app.state.client.get_host(hostname)
    try:
        app.state.client.host.update(
            hostid=host.hostid,
            status=new_status.as_api_value(),
        )
    except Exception as e:
        raise ZabbixCLIError(f"Failed to update host: {e}") from e
    else:
        render_result(
            Result(message=f"Updated host {hostname!r}. New status: {new_status}")
        )


@app.command(name="remove_host", rich_help_panel=HELP_PANEL)
def remove_host(
    ctx: typer.Context,
    hostname: Optional[str] = typer.Argument(None, help="Name of host to remove."),
) -> None:
    """Delete a host."""
    if not hostname:
        hostname = str_prompt("Hostname")
    host = app.state.client.get_host(hostname)
    # TODO: delegate deletion to ZabbixAPI, so that cache is updated
    # after we delete the host.
    try:
        app.state.client.host.delete(host.hostid)
    except Exception as e:
        raise ZabbixCLIError(f"Failed to remove host {hostname!r}") from e
    else:
        render_result(Result(message=f"Removed host {hostname!r}."))


class HostFilterArgs(BaseModel):
    """Unified processing of old filter string and new filter options."""

    available: Optional[AgentAvailable] = None
    maintenance_status: Optional[MaintenanceStatus] = None
    status: Optional[MonitoringStatus] = None

    model_config = ConfigDict(validate_assignment=True)

    @classmethod
    def from_command_args(
        cls,
        filter_legacy: Optional[str],
        agent: Optional[AgentAvailable],
        maintenance: Optional[bool],
        monitored: Optional[bool],
    ) -> HostFilterArgs:
        args = cls()
        if filter_legacy:
            items = filter_legacy.split(",")
            for item in items:
                try:
                    key, value = (s.strip("'\"") for s in item.split(":"))
                except ValueError as e:
                    raise ZabbixCLIError(
                        f"Failed to parse filter argument at: {item!r}"
                    ) from e
                if key == "available":
                    args.available = value  # type: ignore # validator converts it
                elif key == "maintenance":
                    args.maintenance_status = value  # type: ignore # validator converts it
                elif key == "status":
                    args.status = value  # type: ignore # validator converts it
        else:
            if agent is not None:
                args.available = agent
            if monitored is not None:
                # Inverted API values (0 = ON, 1 = OFF) - use enums directly
                args.status = MonitoringStatus.ON if monitored else MonitoringStatus.OFF
            if maintenance is not None:
                args.maintenance_status = (
                    MaintenanceStatus.ON if maintenance else MaintenanceStatus.OFF
                )
        return args


class HostsResult(Result):
    # TODO: Just use AggregateResult instead?
    hosts: List[Host] = Field(default_factory=list)

    def __cols_rows__(self) -> ColsRowsType:
        cols = []  # type: ColsType
        rows = []  # type: RowsType
        for host in self.hosts:
            host_cols, host_rows = host.__cols_rows__()  # type: ignore # TODO: add test for this
            rows.extend(host_rows)
            if not cols:
                cols = host_cols
        return cols, rows


@app.command(name="show_host", rich_help_panel=HELP_PANEL)
def show_host(
    ctx: typer.Context,
    hostname_or_id: Optional[str] = ARG_HOSTNAME_OR_ID,
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
    if not hostname_or_id:
        hostname_or_id = str_prompt("Hostname or ID")

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
        "--monitored/--unmonitored",
        help="Monitoring status.",
    ),
    # TODO: add sorting mode?
) -> None:
    """Show all hosts.

    Hosts can be filtered by agent, monitoring and maintenance status.
    Hosts are sorted by name.
    """
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

    render_result(AggregateResult(result=hosts))


@app.command(name="show_host_interfaces", rich_help_panel=HELP_PANEL)
def show_host_interfaces(hostname_or_id: str = ARG_HOSTNAME_OR_ID) -> None:
    """Show host interfaces."""
    host = app.state.client.get_host(hostname_or_id, select_interfaces=True)
    render_result(AggregateResult(result=host.interfaces))


@app.command(name="show_host_inventory", rich_help_panel=HELP_PANEL)
def show_host_inventory(hostname_or_id: Optional[str] = ARG_HOSTNAME_OR_ID) -> None:
    """Show host inventory details for a specific host."""
    # TODO: support undocumented filter argument from V2
    # TODO: Add mapping of inventory keys to human readable names (Web GUI names)
    if not hostname_or_id:
        hostname_or_id = str_prompt("Hostname or ID")
    host = app.state.client.get_host(hostname_or_id, select_inventory=True)
    render_result(host.inventory)


@app.command(name="update_host_inventory", rich_help_panel=HELP_PANEL)
def update_host_inventory(
    ctx: typer.Context,
    hostname_or_id: Optional[str] = ARG_HOSTNAME_OR_ID,
    key: Optional[str] = typer.Argument(None, help="Inventory key"),
    value: Optional[str] = typer.Argument(None, help="Inventory value"),
) -> None:
    """Update a host inventory field.

    Inventory field do not always match Web GUI field names.
    Use `zabbix-cli -o json show_host_inventory <hostname>` to see the available fields.
    """
    if not hostname_or_id:
        hostname_or_id = str_prompt("Hostname or ID")
    if not key:
        key = str_prompt("Key")
    if not value:
        value = str_prompt("Value")

    host = app.state.client.get_host(hostname_or_id)
    try:
        app.state.client.host.update(
            hostid=host.hostid,
            inventory={key: value},
        )
    except Exception as e:
        raise ZabbixCLIError(
            f"Failed to update host inventory field {key!r} for host {host}"
        ) from e
    else:
        render_result(
            Result(message=f"Updated inventory field {key!r} for host {host}.")
        )
