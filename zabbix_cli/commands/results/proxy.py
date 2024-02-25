from __future__ import annotations

from typing import List
from typing import Optional
from typing import TYPE_CHECKING

from pydantic import BaseModel
from pydantic import Field
from pydantic import model_serializer

from zabbix_cli.models import TableRenderable
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import Proxy

if TYPE_CHECKING:
    from zabbix_cli.models import ColsRowsType
    from zabbix_cli.models import RowsType  # noqa: F401


class UpdateHostProxyResult(BaseModel):
    """Result type for `update_host_proxy` command."""

    source: Optional[str] = None
    """ID of the source (old) proxy."""
    destination: Optional[str] = None
    """ID of the destination (new) proxy."""


class MoveProxyHostsResult(UpdateHostProxyResult):
    """Result type for `move_proxy_hosts` command."""

    hosts: List[str] = []


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
        rows = []  # type: RowsType
        for proxy in self.proxies:
            rows.append([proxy.proxy.name, str(proxy.weight), str(len(proxy.hosts))])
        return cols, rows


class ShowProxiesResult(TableRenderable):
    """Result type for `show_proxy` command."""

    proxy: Proxy
    show_hosts: bool = Field(default=False, exclude=True)

    @model_serializer(when_used="json")
    def ser_model(self):
        return {
            "proxy": self.proxy.model_dump(mode="json", exclude={"hosts"}),
            "hosts": [h.model_simple_dump() for h in self.proxy.hosts],
        }

    @classmethod
    def from_result(cls, proxy: Proxy, show_hosts: bool = False) -> ShowProxiesResult:
        return cls(proxy=proxy, show_hosts=show_hosts)

    @property
    def hostnames(self) -> str:
        if self.show_hosts:
            return ", ".join(f"{host.host}" for host in self.proxy.hosts)
        else:
            return "..."

    def __cols_rows__(self) -> ColsRowsType:
        cols = [
            "Name",
            "Address",
            "Mode",
            "Hosts",
            "# Hosts",
        ]

        rows = [
            [
                self.proxy.name,
                str(self.proxy.address),
                self.proxy.mode,
                self.hostnames,
                str(len(self.proxy.hosts)),
            ]
        ]  # type: RowsType
        if self.zabbix_version.release >= (7, 0, 0):
            cols.extend(["Version", "Compatibility"])
            rows[0].extend([str(self.proxy.version), self.proxy.compatibility_rich])
        return cols, rows
