from __future__ import annotations

import ipaddress
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import TYPE_CHECKING

import typer
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from zabbix_cli._v2_compat import ARGS_POSITIONAL
from zabbix_cli.app import app
from zabbix_cli.app import StatefulApp
from zabbix_cli.exceptions import ZabbixAPIException
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.exceptions import ZabbixNotFoundError
from zabbix_cli.models import AggregateResult
from zabbix_cli.models import ColsRowsType
from zabbix_cli.models import Result
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.prompts import bool_prompt
from zabbix_cli.output.prompts import int_prompt
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix import compat
from zabbix_cli.pyzabbix.types import AgentAvailable
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import MaintenanceStatus
from zabbix_cli.pyzabbix.types import MonitoringStatus
from zabbix_cli.pyzabbix.types import ParamsType
from zabbix_cli.utils.args import APIStr
from zabbix_cli.utils.args import APIStrEnum
from zabbix_cli.utils.args import ChoiceMixin
from zabbix_cli.utils.args import parse_list_arg
from zabbix_cli.utils.commands import ARG_HOSTNAME_OR_ID

if TYPE_CHECKING:
    from zabbix_cli.models import ColsType  # noqa: F401
    from zabbix_cli.models import RowsType  # noqa: F401

# FIXME: replace this with how we handle defaults/prompting in `create_host_interface`
DEFAULT_HOST_STATUS = "0"
DEFAULT_PROXY = ".+"


HELP_PANEL = "Host"

# `zabbix-cli host <cmd>`
host_cmd = StatefulApp(
    name="host",
    help="Host commands.",
)
# app.add_typer(host_cmd)


# `zabbix-cli host inventory <cmd>`
inventory_cmd = StatefulApp(
    name="inventory",
    help="Host inventory commands.",
)
host_cmd.add_subcommand(inventory_cmd)

# `zabbix-cli host interface <cmd>`
interface_cmd = StatefulApp(
    name="interface",
    help="Host interface commands.",
)
host_cmd.add_subcommand(interface_cmd)


@host_cmd.command(
    name="create",
    options_metavar="[hostname|IP] [hostgroups] [proxy] [status]",
    rich_help_panel=HELP_PANEL,
)
@app.command(name="create_host", rich_help_panel=HELP_PANEL, hidden=False)
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
        None,
        "--proxy",
        help=(
            "Proxy server used to monitor the host. "
            "Supports regular expressions to define a group of proxies, "
            "from which one will be selected randomly. "
            "Selects a random proxy from the list of available proxies if "
            "no proxy is specified. "
        ),
    ),
    status: Optional[str] = typer.Option(
        None,
        "--status",
        help="Status of the host. 0 - monitored host; 1 - unmonitored host.",
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
        status = args[3]
    if not hostname_or_ip:
        hostname_or_ip = str_prompt("Hostname or IP")
    if not hostgroups:
        hostgroups = str_prompt(
            "Hostgroup(s)", default="", show_default=False, empty_ok=True
        )
    if not proxy:
        proxy = str_prompt("Proxy", default=DEFAULT_PROXY)
    if not status:
        status = str_prompt(
            "Status", default=DEFAULT_HOST_STATUS
        )  # TODO: don't hardcode this

    # Check if we are using a hostname or IP
    try:
        ipaddress.ip_address(hostname_or_ip)
        useip = 1
        interface_ip = hostname_or_ip
        interface_dns = ""
    except ValueError:
        useip = 0
        interface_ip = ""
        interface_dns = hostname_or_ip

    interfaces = [
        {
            "type": 1,
            "main": 1,
            "useip": useip,
            "ip": interface_ip,
            "dns": interface_dns,
            "port": "10050",
        }
    ]

    # Determine host group IDs
    hostgroup_ids = []
    if not no_default_hostgroup and app.state.config.app.default_hostgroups:
        for hg in app.state.config.app.default_hostgroups:
            hostgroup_ids.append(app.state.client.get_hostgroup_id(hg))
    # TODO: add some sort of plural prompt so we don't have to split manually
    if hostgroups:
        hostgroup_args = parse_list_arg(hostgroups)
        # FIXME: this will fail if we pass in a hostgroup ID!
        for hg in hostgroup_args:
            hostgroup_ids.append(app.state.client.get_hostgroup_id(hg))
    if not hostgroup_ids:
        raise ZabbixCLIError("Unable to create a host without at least one host group.")
    hostgroup_id_params = [{"groupid": hostgroup_id} for hostgroup_id in hostgroup_ids]

    # Find a proxy (No match = monitored by zabbix server)
    try:
        random_proxy = app.state.client.get_random_proxy(pattern=proxy)
        proxy_id = random_proxy.proxyid
    except ZabbixNotFoundError:
        proxy_id = None

    try:
        app.state.client.get_host(hostname_or_ip)
    except ZabbixNotFoundError:
        pass  # OK: host does not exist
    except Exception as e:
        raise ZabbixCLIError(f"Error while checking if host exists: {e}")
    else:
        raise ZabbixCLIError(f"Host {hostname_or_ip} already exists.")

    host_name = name or hostname_or_ip
    query = {
        "host": host_name,
        "groups": hostgroup_id_params,
        compat.host_proxyid(app.state.client.version): proxy_id,
        "status": int(status),
        "interfaces": interfaces,
        "inventory_mode": 1,
        "inventory": {"name": hostname_or_ip},
        "description": description,
    }
    result = app.state.client.host.create(**query)
    render_result(
        Result(message=f"Created host {host_name!r} with ID {result['hostids'][0]}.")
    )
    # TODO: cache host ID


class InterfaceConnectionMode(ChoiceMixin[str], APIStrEnum):
    """Interface connection mode.

    Controls the value of `useip` when creating interfaces in the API."""

    DNS = APIStr("DNS", "0")
    IP = APIStr("IP", "1")


class InterfaceType(ChoiceMixin[str], APIStrEnum):
    """Interface type."""

    AGENT = APIStr("Agent", "1", metadata={"port": 10050})
    SNMP = APIStr("SNMP", "2", metadata={"port": 161})
    IPMI = APIStr("IPMI", "3", metadata={"port": 623})
    JMX = APIStr("JMX", "4", metadata={"port": 12345})

    # TODO: test to ensure we always catch all cases (i.e. error should never be thrown)
    def get_port(self: InterfaceType) -> int:
        """Returns the default port for the given interface type."""
        try:
            return int(self.value.metadata["port"])
        except KeyError:
            raise ZabbixCLIError(f"Unknown interface type: {self}")


class SNMPSecurityLevel(ChoiceMixin[str], APIStrEnum):
    __choice_name__ = "SNMPv3 security level"

    # Match casing from Zabbix API
    NO_AUTH_NO_PRIV = APIStr("noAuthNoPriv", "0")
    AUTH_NO_PRIV = APIStr("authNoPriv", "1")
    AUTH_PRIV = APIStr("authPriv", "2")


class SNMPAuthProtocol(ChoiceMixin[str], APIStrEnum):
    """Authentication protocol for SNMPv3."""

    __choice_name__ = "SNMPv3 auth protocol"

    MD5 = APIStr("MD5", "0")
    SHA1 = APIStr("SHA1", "1")
    # >=6.0 only:
    SHA224 = APIStr("SHA224", "2")
    SHA256 = APIStr("SHA256", "3")
    SHA384 = APIStr("SHA384", "4")
    SHA512 = APIStr("SHA512", "5")


class SNMPPrivProtocol(ChoiceMixin[str], APIStrEnum):
    """Privacy protocol for SNMPv3."""

    __choice_name__ = "SNMPv3 privacy protocol"

    DES = APIStr("DES", "0")
    AES = APIStr("AES", "1")  # < 6.0 only
    # >=6.0 only:
    AES128 = APIStr("AES128", "1")  # >= 6.0
    AES192 = APIStr("AES192", "2")
    AES256 = APIStr("AES256", "3")
    AES192C = APIStr("AES192C", "4")
    AES256C = APIStr("AES256C", "5")


class CreateHostInterfaceV2Args(NamedTuple):
    hostname: Optional[str] = None
    connection: Optional[str] = None
    type: Optional[str] = None
    port: Optional[str] = None
    address_ip: Optional[str] = None
    address_dns: Optional[str] = None
    default: Optional[str] = None


@interface_cmd.command(
    name="create",
    options_metavar="[hostname] [interface connection] [interface type] [interface port] [interface IP] [interface DNS] [default interface]",
    rich_help_panel=HELP_PANEL,
)
@app.command(
    name="create_host_interface",
    options_metavar="[hostname] [interface connection] [interface type] [interface port] [interface IP] [interface DNS] [default interface]",
    rich_help_panel=HELP_PANEL,
)
def create_host_interface(
    ctx: typer.Context,
    # Typer does not yet support NamedTuple arguments, so we use a list of
    args: Optional[List[str]] = ARGS_POSITIONAL,
    hostname: Optional[str] = typer.Option(
        None,
        "--hostname",
        help="Name of host to create interface on.",
        show_default=False,
    ),
    connection: InterfaceConnectionMode = typer.Option(
        InterfaceConnectionMode.DNS,
        "--connection",
        help="Interface connection mode.",
        case_sensitive=False,
    ),
    type_: Optional[InterfaceType] = typer.Option(
        None,
        "--type",
        help="Interface type. SNMP enables --snmp-* options.",
        case_sensitive=False,
    ),
    port: Optional[int] = typer.Option(
        None,
        "--port",
        help="Interface port. Defaults to 10050 for agent, 161 for SNMP, 623 for IPMI, and 12345 for JMX.",
    ),
    address: Optional[str] = typer.Option(
        None,
        "--address",
        help="IP address if IP connection, or DNS address if DNS connection.",
        show_default=False,
    ),
    default: Optional[bool] = typer.Option(
        None, "--default/--no-default", help="Whether this is the default interface."
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
) -> None:
    """Create a host interface.

    Prompts for required values if not specified.
    NOTE: V2-style positional args do not support SNMP options.
    Prefer using options over positional args.
    Positional args take precedence over options.
    """
    # Handle V2 positional args (deprecated)
    if args:
        a = CreateHostInterfaceV2Args(*args)
        if a.hostname:
            hostname = a.hostname
        if a.connection:
            connection = InterfaceConnectionMode(a.connection)
        if a.type:
            type_ = InterfaceType(a.type)
        if a.port:
            port = int(a.port)  # unsafe? use custom parser?
        address_ip = a.address_ip  # no parsing here
        address_dns = a.address_dns
        if a.default:
            default = a.default == "1"
        if connection == InterfaceConnectionMode.IP:
            address = address_ip
        else:
            address = address_dns

    # Changed from V2: Reduced number of prompts
    # Will only prompt for hostname, address, and default interface
    # Defaults are there for a reason...
    if not hostname:
        hostname = str_prompt("Hostname")
    if not address:
        if connection == InterfaceConnectionMode.IP:
            p = "IP"
            default_address = "127.0.0.1"
        else:
            p = "DNS"
            default_address = hostname
        address = str_prompt(f"Interface {p}", default=default_address)
    if type_ is None:
        type_ = InterfaceType.from_prompt()
    if default is None:
        default = bool_prompt("Default interface?", default=True)

    if port is None:
        port = type_.get_port()
    host = app.state.client.get_host(hostname)

    # NOTE: for consistency we should probably handle this inside pyzabbix.ZabbixAPI,
    # but creating a clean abstraction for that, when this is the only place
    # we create host interfaces, is probably not worth it.
    params: ParamsType = {
        # All API values are strings!
        "hostid": host.hostid,
        "main": str(int(default)),
        "type": type_.as_api_value(),
        "useip": connection.as_api_value(),
        "port": str(port),
        "ip": "",
        "dns": "",
    }
    if connection == InterfaceConnectionMode.IP:
        params["ip"] = address
    else:
        params["dns"] = address

    if type_ == InterfaceType.SNMP:
        # NOTE (pederhan): this block is a bit clumsy
        # We populate this dict with whatever types and None
        # then filter out None and convert to strings afterwards
        # Maybe better to have two different functions that gather this
        # information and define some TypedDict interfaces for the params?
        # E.g. Union[V1V2Params, V3Params]?
        details = {
            "version": snmp_version,
            "bulk": snmp_bulk,
            "community": snmp_community,
            "securityname": None,
            "contextname": None,
            "securitylevel": None,
            "authpassphrase": None,
            "privpassphrase": None,
            "authprotocol": None,
            "privprotocol": None,
        }
        if not snmp_version:
            snmp_version = int_prompt("SNMP version", default=2)
            details["version"] = str(snmp_version)
        if snmp_bulk is None:
            snmp_bulk = bool_prompt("Use SNMP bulk requests?", default=True)
        details["bulk"] = str(int(snmp_bulk))

        # V3-specific options
        if snmp_version == 3:
            if not snmp_security_name:
                snmp_security_name = str_prompt("SNMP security name")
            details["securityname"] = snmp_security_name
            if not snmp_context_name:
                snmp_context_name = str_prompt("SNMP context name")
            details["contextname"] = snmp_context_name
            if not snmp_security_level:
                snmp_security_level = SNMPSecurityLevel.from_prompt(
                    default=SNMPSecurityLevel.NO_AUTH_NO_PRIV
                )
            details["securitylevel"] = snmp_security_level.as_api_value()

            # authNoPriv and authPriv security levels:
            if snmp_security_level != SNMPSecurityLevel.NO_AUTH_NO_PRIV:
                if not snmp_auth_protocol:
                    snmp_auth_protocol = SNMPAuthProtocol.from_prompt(
                        default=SNMPAuthProtocol.MD5
                    )
                details["authprotocol"] = snmp_auth_protocol.as_api_value()

                if not snmp_auth_passphrase:
                    snmp_auth_passphrase = str_prompt(
                        "SNMPv3 auth passphrase",
                        default="",
                        password=True,
                        empty_ok=True,
                    )
                details["authpassphrase"] = snmp_auth_passphrase

                # authPriv security level only:
                if snmp_security_level == SNMPSecurityLevel.AUTH_PRIV:
                    if not snmp_priv_protocol:
                        snmp_priv_protocol = SNMPPrivProtocol.from_prompt(
                            default=SNMPPrivProtocol.DES
                        )
                    details["privprotocol"] = snmp_priv_protocol.as_api_value()
                    if not snmp_priv_passphrase:
                        snmp_priv_passphrase = str_prompt(
                            "SNMPv3 privacy passphrase",
                            default="",
                            password=True,
                            empty_ok=True,
                        )
                    details["privpassphrase"] = snmp_priv_passphrase
        # V1/V2 options
        else:
            if not snmp_community:
                snmp_community = str_prompt(
                    "SNMP community", default="${SNMP_COMMUNITY}"
                )
                details["community"] = snmp_community

        # Filter out None values and convert to strings
        params["details"] = {k: str(v) for k, v in details.items() if v is not None}

    try:
        resp = app.state.client.hostinterface.create(**params)
    except Exception as e:
        raise ZabbixAPIException("Failed to create host interface") from e
    else:
        ifaces = resp.get("interfaceids", [])
        render_result(
            Result(
                message=f"Created host interface with ID {ifaces[0] if ifaces else 'unknown'}."
            )
        )


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


@host_cmd.command(name="remove", rich_help_panel=HELP_PANEL)
@app.command(name="remove_host", rich_help_panel=HELP_PANEL, hidden=False)
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


@host_cmd.command(name="show", rich_help_panel=HELP_PANEL)
@app.command(name="show_host", rich_help_panel=HELP_PANEL, hidden=False)
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


@host_cmd.command(name="list", rich_help_panel=HELP_PANEL)
@app.command(name="show_hosts", rich_help_panel=HELP_PANEL, hidden=False)
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


@inventory_cmd.command(name="get", rich_help_panel=HELP_PANEL)
@app.command(name="show_host_inventory", rich_help_panel=HELP_PANEL, hidden=False)
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
