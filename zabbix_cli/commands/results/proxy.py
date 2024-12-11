from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Optional

from pydantic import BaseModel
from pydantic import Field
from pydantic import model_serializer
from typing_extensions import Self

from zabbix_cli.models import ColsRowsType
from zabbix_cli.models import MetaKey
from zabbix_cli.models import TableRenderable
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import HostList
from zabbix_cli.pyzabbix.types import Proxy
from zabbix_cli.pyzabbix.types import ProxyGroup

if TYPE_CHECKING:
    from zabbix_cli.models import ColsRowsType
    from zabbix_cli.models import RowsType


class BaseHostProxyResult(TableRenderable):
    source: str = Field(..., json_schema_extra={MetaKey.HEADER: "Source Proxy"})
    """Name of the old proxy."""
    hosts: list[str] = []
    """Name of the hosts that were updated."""


class UpdateHostProxyResult(BaseHostProxyResult):
    """Result type for `update_host_proxy` command."""

    destination: str = Field(
        ..., json_schema_extra={MetaKey.HEADER: "Destination Proxy"}
    )
    """Name of the new proxy"""

    @classmethod
    def from_result(
        cls,
        hosts: list[Host],
        source_proxy: Optional[Proxy],
        dest_proxy: Optional[Proxy],
    ) -> Self:
        return cls(
            source=source_proxy.name if source_proxy else "",
            destination=dest_proxy.name if dest_proxy else "",
            hosts=[h.host for h in hosts],
        )


class ClearHostProxyResult(BaseHostProxyResult):
    """Result type for `update_host_proxy` command."""

    @classmethod
    def from_result(
        cls,
        hosts: list[Host],
        source_proxy: Optional[Proxy],
    ) -> Self:
        return cls(
            source=source_proxy.name if source_proxy else "",
            hosts=[h.host for h in hosts],
        )


class MoveProxyHostsResult(TableRenderable):
    """Result type for `move_proxy_hosts` command."""

    source: Optional[str] = None
    """ID of the source (old) proxy."""
    destination: Optional[str] = None
    """ID of the destination (new) proxy."""
    hosts: list[str] = []


class LBProxy(BaseModel):
    """A load balanced proxy."""

    proxy: Proxy
    hosts: list[Host] = []
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

    proxies: list[LBProxy]

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["Proxy", "Weight", "Hosts"]
        rows: RowsType = []
        for proxy in self.proxies:
            rows.append([proxy.proxy.name, str(proxy.weight), str(len(proxy.hosts))])
        return cols, rows


class UpdateHostGroupProxyResult(TableRenderable):
    """Result type for `update_hostgroup_proxy` command."""

    proxy: str
    hosts: list[str] = []

    @classmethod
    def from_result(cls, proxy: Proxy, hosts: list[Host]) -> Self:
        return cls(proxy=proxy.name, hosts=[host.host for host in hosts])


class UpdateHostGroupProxyGroupResult(TableRenderable):
    """Result type for `update_hostgroup_proxygroup` command."""

    proxy_group: str
    hosts: list[str] = []

    @classmethod
    def from_result(cls, proxy_group: ProxyGroup, hosts: list[Host]) -> Self:
        return cls(proxy_group=proxy_group.name, hosts=[host.host for host in hosts])


class ShowProxiesResult(TableRenderable):
    """Result type for `show_proxy` command."""

    proxy: Proxy
    show_hosts: bool = Field(default=False, exclude=True)

    @classmethod
    def from_result(cls, proxy: Proxy, show_hosts: bool = False) -> Self:
        return cls(proxy=proxy, show_hosts=show_hosts)

    @property
    def hosts_fmt(self) -> str:
        if self.show_hosts:
            return ", ".join(f"{host.host}" for host in self.proxy.hosts)
        else:
            return str(len(self.proxy.hosts))

    def __cols_rows__(self) -> ColsRowsType:
        cols = [
            "Name",
            "Address",
            "Mode",
            "Hosts",
        ]

        rows: RowsType = [
            [
                self.proxy.name,
                str(self.proxy.address),
                self.proxy.mode,
                self.hosts_fmt,
            ]
        ]
        if self.zabbix_version.release >= (7, 0, 0):
            cols.extend(["Version", "Compatibility"])
            rows[0].extend([str(self.proxy.version), self.proxy.compatibility_rich])
        return cols, rows


class ShowProxyHostsResult(TableRenderable):
    proxy: Proxy
    hosts: HostList = []

    @classmethod
    def from_result(cls, proxy: Proxy) -> Self:
        # HACK: remove the list of hosts from the proxy and store it separately
        # so that we can render the proxy separately from the hosts
        hosts = proxy.hosts
        proxy.hosts = []
        return cls(proxy=proxy, hosts=hosts)

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["Proxy", "Hosts"]
        rows: RowsType = [
            [
                self.proxy.name,
                "\n".join(h.host for h in self.hosts),
            ]
        ]
        return cols, rows


class ShowProxyGroupHostsResult(TableRenderable):
    proxy_group: ProxyGroup
    hosts: HostList = []

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["Proxy Group", "Hosts"]
        rows: RowsType = [
            [
                self.proxy_group.name,
                "\n".join(h.host for h in self.hosts),
            ]
        ]
        return cols, rows
