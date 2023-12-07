from __future__ import annotations

import ipaddress
from typing import cast
from typing import List
from typing import Optional

import typer

from zabbix_cli.app import app
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.exceptions import ZabbixNotFoundError
from zabbix_cli.models import Result
from zabbix_cli.output.prompts import bool_prompt
from zabbix_cli.output.prompts import int_prompt
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix import compat
from zabbix_cli.pyzabbix.types import ParamsType
from zabbix_cli.utils.args import APIStr
from zabbix_cli.utils.args import APIStrEnum
from zabbix_cli.utils.args import ChoiceMixin
from zabbix_cli.utils.commands import ARG_POSITIONAL


DEFAULT_HOST_STATUS = "0"
DEFAULT_PROXY = ".+"


@app.command(
    name="create_host", options_metavar="[hostname|IP] [hostgroups] [proxy] [status]"
)
def create_host(
    ctx: typer.Context,
    args: List[str] = ARG_POSITIONAL,
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
            "Command will fail if both default_hostgroup and hostgroups are empty. "
            "Will always add host to default host group."
        ),
    ),
    proxy: Optional[str] = typer.Option(
        None,
        "--proxy",
        help=(
            "Proxy server used to monitor the host. "
            "Supports regular expressions to define a group of proxies, "
            "from which one will be selected randomly. "
            "If no proxy is set, then a random proxy from the list of available "
            "proxies will be selected. "
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
    """Creates a host.

    Prefer using options over the positional arguments.

    Always adds the host to the default host group unless `--no-default-hostgroup`
    is specified.
    """
    if args:
        if len(args) != 4:
            raise ZabbixCLIError("create_host takes exactly 4 positional arguments.")
        else:
            hostname_or_ip = args[0]
            hostgroups = args[1]
            proxy = args[2]
            status = args[3]
    if not (hostname_or_ip and hostgroups and proxy and status):
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
        for hg in hostgroups.strip().split(","):
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


# TODO: add factory function for creating choice enums from mappings


class InterfaceConnectionMode(ChoiceMixin[str], APIStrEnum):
    """Interface connection mode.

    Controls the value of `useip` when creating interfaces in the API."""

    DNS = APIStr("DNS", "0")
    IP = APIStr("IP", "1")


class PortStr(APIStr[str]):
    port: int

    def __new__(cls, s: str, api_value: str, port: int) -> PortStr:
        # Why do we need a cast here but not in APIStr.__new__?
        obj = cast(PortStr, APIStr.__new__(cls, s, api_value))
        obj.port = port
        return obj


class InterfaceType(ChoiceMixin[str], APIStrEnum):
    """Interface type."""

    value: PortStr  # Must update type of value from APIStr to PortStr

    AGENT = PortStr("Agent", "1", port=10050)
    SNMP = PortStr("SNMP", "2", port=161)
    IPMI = PortStr("IPMI", "3", port=623)
    JMX = PortStr("JMX", "4", port=12345)

    @property
    def port(self) -> int:
        """Returns the default port for this interface type."""
        return self.value.port


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


@app.command(
    name="create_host_interface",
    options_metavar="[hostname] [interface connection] [interface type] [interface port] [interface IP] [interface DNS] [default interface]",
)
def create_host_interface(
    ctx: typer.Context,
    # NOTE: use unified parsing func for args and options?
    args: List[str] = ARG_POSITIONAL,
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
    """
    # Handle V2 positional args
    if args and len(args) == 7:
        if args[0]:
            hostname = args[0]
        if args[1]:
            connection = InterfaceConnectionMode(args[1])
        if args[2]:
            type_ = InterfaceType(args[2])
        if args[3]:
            port = int(args[3])  # unsafe? use custom parser?
        if args[4]:
            address_ip = args[4]  # no parsing here
        if args[5]:
            address_dns = args[5]
        if args[6]:
            default = args[6] == "1"
        if connection == InterfaceConnectionMode.IP:
            address = address_ip
        else:
            address = address_dns
    elif args:
        raise ZabbixCLIError(
            "create_host_interface takes exactly 7 positional arguments."
        )

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
        port = type_.port
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
            details["securityname"] = str_prompt("SNMP security name")
            details["contextname"] = str_prompt("SNMP context name")
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
        raise ZabbixCLIError(f"Failed to create host interface: {e}") from e
    else:
        ifaces = resp.get("interfaceids", [])
        render_result(
            Result(
                message=f"Created host interface with ID {ifaces[0] if ifaces else 'unknown'}."
            )
        )


# See: zabbix_cli.utils.args.OnOffChoice for why we re-define on/off enum here
class MonitoringStatus(ChoiceMixin[str], APIStrEnum):
    """Monitoring status is on/off."""

    ON = APIStr("on", "0")  # Yes, 0 is on, 1 is off...
    OFF = APIStr("off", "1")


@app.command(name="define_host_monitoring_status")
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


@app.command(name="define_host_usermacro")
def define_host_usermacro(
    hostname: Optional[str] = typer.Argument(None, help="Host to define macro for."),
    macro_name: Optional[str] = typer.Argument(
        None,
        help=(
            "Name of macro. "
            "Names will be converted to the Zabbix format, "
            "i.e. `site_url` becomes {$SITE_URL}."
        ),
    ),
    macro_value: Optional[str] = typer.Argument(None, help="Default value of macro."),
) -> None:
    """Create or update a host usermacro."""
    if not hostname:
        hostname = str_prompt("Hostname")
    if not macro_name:
        macro_name = str_prompt("Macro name")
    if not macro_value:
        macro_value = str_prompt("Macro value")
    host = app.state.client.get_host(hostname)

    # Determine if we should create or update macro
    try:
        macro = app.state.client.get_macro(host.hostid, macro_name)
    except ZabbixNotFoundError:
        macro_id = app.state.client.create_macro(host.hostid, macro_name, macro_value)
        action = "Created"
    else:
        macro_id = app.state.client.update_macro(macro.hostmacroid, macro_value)
        action = "Updated"

    render_result(
        Result(
            message=f"{action} macro {macro_name!r} with ID {macro_id} for host {hostname!r}."
        )
    )


@app.command(name="remove_host")
def remove_host(
    ctx: typer.Context,
    hostname: Optional[str] = typer.Argument(None, help="Name of host to remove."),
) -> None:
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


# def _parse_legacy_filter(filter: str) -> Tuple[...]:
#     """Parses the legacy filter argument from V2."""
#     pass


class AgentAvailabilityStatus(ChoiceMixin[int], APIStrEnum):
    """Agent availability status."""

    UNKNOWN = APIStr("unknown", 0)
    AVAILABLE = APIStr("available", 1)
    UNAVAILABLE = APIStr("unavailable", 2)


@app.command(name="show_host")
def show_host(
    ctx: typer.Context,
    hostname: str,
    # This is the legacy filter argument from V2
    filter_legacy: Optional[str] = typer.Argument(None, hidden=True),
    agent: Optional[AgentAvailabilityStatus] = typer.Option(
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
    print(ctx)


@app.command(name="show_hosts")
def show_hosts() -> None:
    pass


@app.command(name="show_host_inventory")
def show_host_inventory() -> None:
    pass


@app.command(name="show_host_usermacros")
def show_host_usermacros() -> None:
    pass
