from __future__ import annotations

from typing import Any
from typing import List
from typing import TYPE_CHECKING

from pydantic import Field
from pydantic import field_validator
from typing_extensions import TypedDict

from zabbix_cli.models import TableRenderable
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import HostGroup
from zabbix_cli.utils.utils import get_hostgroup_flag
from zabbix_cli.utils.utils import get_hostgroup_type

if TYPE_CHECKING:
    from zabbix_cli.models import ColsRowsType
    from zabbix_cli.models import RowsType  # noqa: F401


class AddHostsToHostGroup(TableRenderable):
    """Result type for `add_host_to_hostgroup` and `remove_host_from_hostgroup` commands."""

    hostgroup: str
    hosts: List[str]

    @classmethod
    def from_result(
        cls,
        hosts: List[Host],
        hostgroup: HostGroup,
    ) -> AddHostsToHostGroup:
        to_add = set()  # names of templates to link
        for host in hosts:
            for hg_host in hostgroup.hosts:
                if host.host == hg_host.host:
                    break
            else:
                to_add.add(host.host)
        return cls(
            hostgroup=hostgroup.name,
            hosts=sorted(to_add),
        )


class RemoveHostsFromHostGroup(TableRenderable):
    """Result type for `remove_host_from_hostgroup`."""

    hostgroup: str
    hosts: List[str]

    @classmethod
    def from_result(
        cls,
        hosts: List[Host],
        hostgroup: HostGroup,
    ) -> RemoveHostsFromHostGroup:
        to_remove = set()  # names of templates to link
        for host in hosts:
            for hg_host in hostgroup.hosts:
                if host.host == hg_host.host:
                    to_remove.add(host.host)
                    break
        return cls(
            hostgroup=hostgroup.name,
            hosts=sorted(to_remove),
        )


class ExtendHostgroupResult(TableRenderable):
    """Result type for `extend_hostgroup` command."""

    source: str
    destination: List[str]
    hosts: List[str]

    @classmethod
    def from_result(
        cls, source: HostGroup, destination: List[HostGroup]
    ) -> ExtendHostgroupResult:
        return cls(
            source=source.name,
            destination=[dst.name for dst in destination],
            hosts=[host.host for host in source.hosts],
        )


class MoveHostsResult(TableRenderable):
    """Result type for `move_hosts` command."""

    source: str
    destination: str
    hosts: List[str]

    @classmethod
    def from_result(cls, source: HostGroup, destination: HostGroup) -> MoveHostsResult:
        return cls(
            source=source.name,
            destination=destination.name,
            hosts=[host.host for host in source.hosts],
        )


class HostGroupDeleteResult(TableRenderable):
    groups: List[str]


class HostGroupHost(TypedDict):
    hostid: str
    host: str


class HostGroupResult(TableRenderable):
    """Result type for hostgroup."""

    groupid: str
    name: str
    hosts: List[HostGroupHost] = []
    flags: str
    internal: str = Field(
        get_hostgroup_type(0),
        serialization_alias="type",  # Dumped as "type" to mimick V2 behavior
    )

    @classmethod
    def from_hostgroup(cls, hostgroup: HostGroup) -> HostGroupResult:
        return cls(
            groupid=hostgroup.groupid,
            name=hostgroup.name,
            flags=hostgroup.flags,  # type: ignore # validator
            internal=hostgroup.internal,  # type: ignore # validator
            hosts=[
                HostGroupHost(hostid=host.hostid, host=host.host)
                for host in hostgroup.hosts
            ],
        )

    # Mimicks old behavior by also writing the string representation of the
    # flags and internal fields to the serialized output.
    @field_validator("flags", mode="before")
    @classmethod
    def _get_flag_str(cls, v: Any) -> Any:
        if isinstance(v, int):
            return get_hostgroup_flag(v)
        else:
            return v

    @field_validator("internal", mode="before")
    @classmethod
    def _get_type_str(cls, v: Any) -> Any:
        if isinstance(v, int):
            return get_hostgroup_type(v)
        else:
            return v

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["GroupID", "Name", "Flag", "Type", "Hosts"]
        rows = [
            [
                self.groupid,
                self.name,
                self.flags,
                self.internal,
                ", ".join([host["host"] for host in self.hosts]),
            ]
        ]  # type: RowsType
        return cols, rows


class HostGroupPermissions(TableRenderable):
    """Result type for hostgroup permissions."""

    groupid: str
    name: str
    permissions: List[str]

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["GroupID", "Name", "Permissions"]
        rows = [[self.groupid, self.name, "\n".join(self.permissions)]]  # type: RowsType
        return cols, rows
