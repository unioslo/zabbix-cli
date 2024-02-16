from __future__ import annotations

from typing import List
from typing import Optional
from typing import TYPE_CHECKING

from pydantic import BaseModel
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
