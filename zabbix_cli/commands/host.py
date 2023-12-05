from __future__ import annotations

import ipaddress
from enum import Enum
from typing import List
from typing import Optional

import typer
from strenum import StrEnum

from zabbix_cli.app import app
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.exceptions import ZabbixNotFoundError
from zabbix_cli.models import Result
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.prompts import bool_prompt
from zabbix_cli.output.prompts import int_prompt
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix import compat
from zabbix_cli.pyzabbix.types import ParamsType
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


class ChoiceMixin(Enum):
    @classmethod
    def choices(cls) -> List[str]:
        return [str(e) for e in cls]


# TODO: add factory function for creating choice enums from mappings


class InterfaceConnectionMode(StrEnum, ChoiceMixin):
    """Interface connection mode.

    Controls the value of `useip` when creating interfaces in the API."""

    DNS = "DNS"
    IP = "IP"

    @classmethod
    def _missing_(cls, value: object) -> InterfaceConnectionMode:
        """Supports Zabbix API-style interface connection mode values."""
        for k, v in InterfaceConnectionModeMapping.items():
            if v == value:
                return k
        raise ZabbixCLIError(f"Invalid interface connection mode {value!r}.")

    def as_api_value(self) -> str:
        """Return the Zabbix API value for this interface connection mode."""
        return InterfaceConnectionModeMapping[self]


InterfaceConnectionModeMapping = {
    InterfaceConnectionMode.DNS: "0",
    InterfaceConnectionMode.IP: "1",
}


class InterfaceType(StrEnum, ChoiceMixin):
    """Interface type."""

    AGENT = "Agent"
    SNMP = "SNMP"
    IPMI = "IPMI"
    JMX = "JMX"

    @classmethod
    def _missing_(cls, value: object) -> InterfaceType:
        """Supports Zabbix API-style interface type values."""
        for k, v in InterfaceTypeMapping.items():
            if v == value:
                return k
        raise ZabbixCLIError(f"Invalid interface type {value!r}.")

    def as_api_value(self) -> str:
        """Return the Zabbix API value for this interface type."""
        return InterfaceTypeMapping[self]


# TODO: add tests to ensure this is always in sync with InterfaceType
InterfaceTypeMapping = {
    InterfaceType.AGENT: "1",
    InterfaceType.SNMP: "2",
    InterfaceType.IPMI: "3",
    InterfaceType.JMX: "4",
}

InterfacePortMapping = {
    InterfaceType.AGENT: 10050,
    InterfaceType.SNMP: 161,
    InterfaceType.IPMI: 623,
    InterfaceType.JMX: 12345,
}


class SNMPSecurityLevel(StrEnum, ChoiceMixin):
    # Match casing from Zabbix API
    NO_AUTH_NO_PRIV = "noAuthNoPriv"
    AUTH_NO_PRIV = "authNoPriv"
    AUTH_PRIV = "authPriv"

    @classmethod
    def _missing_(cls, value: object) -> SNMPSecurityLevel:
        """Supports Zabbix API-style interface type values."""
        for k, v in SNMPSecurityLevelMapping.items():
            if v == value:
                return k
        raise ZabbixCLIError(f"Invalid interface type {value!r}.")

    def as_api_value(self) -> str:
        """Return the Zabbix API value for this interface type."""
        return SNMPSecurityLevelMapping[self]


SNMPSecurityLevelMapping = {
    SNMPSecurityLevel.NO_AUTH_NO_PRIV: "0",
    SNMPSecurityLevel.AUTH_NO_PRIV: "1",
    SNMPSecurityLevel.AUTH_PRIV: "2",
}


class SNMPAuthProtocol(StrEnum, ChoiceMixin):
    """Authentication protocol for SNMPv3."""

    MD5 = "MD5"
    SHA1 = "SHA1"  # <6.0 only
    # >=6.0 only:
    SHA224 = "SHA224"
    SHA256 = "SHA256"
    SHA384 = "SHA384"
    SHA512 = "SHA512"

    @classmethod
    def _missing_(cls, value: object) -> SNMPAuthProtocol:
        """Supports Zabbix API-style interface type values."""
        for k, v in SNMPAuthProtocolMapping.items():
            if v == value:
                return k
        raise ZabbixCLIError(f"Invalid auth protocol {value!r}.")

    def as_api_value(self) -> str:
        """Return the Zabbix API value for this interface type."""
        return SNMPAuthProtocolMapping[self]


SNMPAuthProtocolMapping = {
    SNMPAuthProtocol.MD5: "0",
    SNMPAuthProtocol.SHA1: "1",
    SNMPAuthProtocol.SHA224: "2",
    SNMPAuthProtocol.SHA256: "3",
    SNMPAuthProtocol.SHA384: "4",
    SNMPAuthProtocol.SHA512: "5",
}


class SNMPPrivProtocol(StrEnum, ChoiceMixin):
    """Privacy protocol for SNMPv3."""

    DES = "DES"
    AES = "AES"  # < 6.0 only
    # >=6.0 only:
    AES128 = "AES128"
    AES192 = "AES192"
    AES256 = "AES256"
    AES192C = "AES192C"
    AES256C = "AES256C"

    @classmethod
    def _missing_(cls, value: object) -> SNMPPrivProtocol:
        """Supports Zabbix API-style interface type values."""
        for k, v in SNMPPrivProtocolMapping.items():
            if v == value:
                return k
        raise ZabbixCLIError(f"Invalid privacy protocol {value!r}.")

    def as_api_value(self) -> str:
        """Return the equivalent Zabbix API value."""
        return SNMPPrivProtocol[self]


SNMPPrivProtocolMapping = {
    SNMPPrivProtocol.DES: "0",
    SNMPPrivProtocol.AES: "1",  # <6.0
    SNMPPrivProtocol.AES128: "1",  # >=6.0
    SNMPPrivProtocol.AES192: "2",
    SNMPPrivProtocol.AES256: "3",
    SNMPPrivProtocol.AES192C: "4",
    SNMPPrivProtocol.AES256C: "5",
}


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
    snmp_auth_protocol: Optional[str] = typer.Option(
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
    snmp_priv_protocol: Optional[str] = typer.Option(
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
        t = str_prompt("Interface type", choices=InterfaceType.choices())
        type_ = InterfaceType(t)
    if default is None:
        default = bool_prompt("Default interface?", default=True)

    if port is None:
        port = InterfacePortMapping.get(type_, None)
        if port is None:
            raise ZabbixCLIError(f"Invalid interface type {type_!r}.")

    # FIXME: optimize this. We call the API twice here.
    if not app.state.client.host_exists(hostname):
        exit_err(
            f"Host {hostname!r} does not exist. Host Interface can not be created."
        )
    host = app.state.client.get_host(hostname)

    # NOTE: for consistency we should probably handle this inside pyzabbix.ZabbixAPI,
    # but creating a clean abstraction for that, when this is the only place
    # we create host interfaces, is probably not worth it.
    query: ParamsType = {
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
        query["ip"] = address
    else:
        query["dns"] = address

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
                sec_inp = str_prompt(
                    "SNMPv3 security level",
                    default=SNMPSecurityLevel.NO_AUTH_NO_PRIV,
                    choices=SNMPSecurityLevel.choices(),
                )
                snmp_security_level = SNMPSecurityLevel(sec_inp)
            if snmp_security_level != SNMPSecurityLevel.NO_AUTH_NO_PRIV:
                auth_proto = str_prompt(
                    "SNMPv3 auth protocol",
                    default=SNMPAuthProtocol.MD5,
                    choices=SNMPAuthProtocol.choices(),
                )
                details["authprotocol"] = SNMPAuthProtocol(auth_proto).as_api_value()
                details["authpassphrase"] = str_prompt(
                    "SNMPv3 auth passphrase",
                    default="",
                    password=True,
                    empty_ok=True,
                )
                if snmp_security_level == SNMPSecurityLevel.AUTH_PRIV:
                    proto = str_prompt(
                        "SNMPv3 privacy protocol",
                        default=SNMPPrivProtocol.DES,
                        choices=SNMPPrivProtocol.choices(),
                    )
                    details["privprotocol"] = SNMPPrivProtocol(proto).as_api_value()
                    details["privpassphrase"] = str_prompt(
                        "SNMPv3 privacy passphrase",
                        default="",
                        password=True,
                        empty_ok=True,
                    )
        # V1/V2 options
        else:
            if not snmp_community:
                snmp_community = str_prompt(
                    "SNMP community", default="${SNMP_COMMUNITY}"
                )
                details["community"] = snmp_community

        # Filter out None values and convert to strings
        query["details"] = {k: str(v) for k, v in details.items() if v is not None}

    # query = {
    #     "hostid": "10562",
    #     "main": "0",
    #     "type": "1",
    #     "useip": "1",
    #     "ip": "127.0.0.1",
    #     "dns": "",
    #     "port": "10050",
    # }

    try:
        resp = app.state.client.hostinterface.create(**query)
    except Exception as e:
        raise ZabbixCLIError(f"Failed to create host interface: {e}") from e
    else:
        ifaces = resp.get("interfaceids", [])
        render_result(
            Result(
                message=f"Created host interface with ID {ifaces[0] if ifaces else 'unknown'}."
            )
        )


@app.command(name="define_host_monitoring_status")
def define_host_monitoring_status() -> None:
    pass


@app.command(name="define_host_usermacro")
def define_host_usermacro() -> None:
    pass


@app.command(name="remove_host")
def remove_host() -> None:
    pass


@app.command(name="show_host")
def show_host() -> None:
    pass


@app.command(name="show_hosts")
def show_hosts() -> None:
    pass


@app.command(name="show_host_inventory")
def show_host_inventory() -> None:
    pass


@app.command(name="show_host_usermacros")
def show_host_usermacros() -> None:
    pass
