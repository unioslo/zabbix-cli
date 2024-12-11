from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING
from typing import Any
from typing import Union

import rich
import rich.box
from pydantic import Field
from pydantic import computed_field
from pydantic import field_validator
from pydantic import model_serializer

from zabbix_cli.models import MetaKey
from zabbix_cli.models import TableRenderable
from zabbix_cli.pyzabbix.enums import GUIAccess
from zabbix_cli.pyzabbix.enums import UsergroupPermission
from zabbix_cli.pyzabbix.enums import UsergroupStatus
from zabbix_cli.pyzabbix.types import HostGroup
from zabbix_cli.pyzabbix.types import TemplateGroup
from zabbix_cli.pyzabbix.types import Usergroup
from zabbix_cli.pyzabbix.types import ZabbixRight

if TYPE_CHECKING:
    from zabbix_cli.models import ColsRowsType
    from zabbix_cli.models import RowContent
    from zabbix_cli.models import RowsType


class UgroupUpdateUsersResult(TableRenderable):
    usergroups: list[str]
    users: list[str]

    def __cols_rows__(self) -> ColsRowsType:
        return (
            ["Usergroups", "Users"],
            [["\n".join(self.usergroups), ", ".join(self.users)]],
        )


class UsergroupAddUsers(UgroupUpdateUsersResult):
    __title__ = "Added Users"


class UsergroupRemoveUsers(UgroupUpdateUsersResult):
    __title__ = "Removed Users"


class AddUsergroupPermissionsResult(TableRenderable):
    usergroup: str
    hostgroups: list[str]
    templategroups: list[str]
    permission: UsergroupPermission

    @computed_field
    @property
    def permission_str(self) -> str:
        # FIXME: remove this? Serializing a Choice enum should dump the same value?
        return self.permission.as_status()

    def __cols_rows__(self) -> ColsRowsType:
        return (
            [
                "Usergroup",
                "Host Groups",
                "Template Groups",
                "Permission",
            ],
            [
                [
                    self.usergroup,
                    ", ".join(self.hostgroups),
                    ", ".join(self.templategroups),
                    self.permission_str,
                ],
            ],
        )


class ShowUsergroupResult(TableRenderable):
    usrgrpid: str = Field(..., json_schema_extra={MetaKey.HEADER: "ID"})
    name: str
    gui_access: str = Field(..., json_schema_extra={MetaKey.HEADER: "GUI Access"})
    status: str
    users: list[str] = Field(
        default_factory=list, json_schema_extra={MetaKey.JOIN_CHAR: ", "}
    )

    @classmethod
    def from_usergroup(cls, usergroup: Usergroup) -> ShowUsergroupResult:
        return cls(
            name=usergroup.name,
            usrgrpid=usergroup.usrgrpid,
            gui_access=usergroup.gui_access_str,
            status=usergroup.users_status_str,
            users=[user.username for user in usergroup.users],
        )

    @field_validator("gui_access")
    @classmethod
    def _validate_gui_access(cls, v: Any) -> str:
        if isinstance(v, int):
            return GUIAccess.string_from_value(v, with_code=False)
        return v

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: Any) -> str:
        if isinstance(v, int):
            return UsergroupStatus.string_from_value(v, with_code=False)
        return v


class GroupRights(TableRenderable):
    """Subtable for displaying group rights."""

    __box__ = rich.box.MINIMAL

    groups: Union[dict[str, HostGroup], dict[str, TemplateGroup]] = Field(
        default_factory=dict,
    )

    rights: list[ZabbixRight] = Field(
        default_factory=list,
        description="Group rights for the user group.",
    )

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["Name", "Permission"]
        rows: RowsType = []
        for right in self.rights:
            group = self.groups.get(right.id, None)
            if group:
                group_name = group.name
            else:
                group_name = "Unknown"
            rows.append([group_name, str(UsergroupPermission(right.permission))])
        return cols, rows


class ShowUsergroupPermissionsResult(TableRenderable):
    usrgrpid: str
    name: str
    hostgroups: dict[str, HostGroup] = Field(
        default_factory=dict,
        exclude=True,
        description="Host groups the user group has access to. Used to render host group rights.",
    )
    templategroups: dict[str, TemplateGroup] = Field(
        default_factory=dict,
        exclude=True,
        description="Mapping of all template groups. Used to render template group rights.",
    )
    hostgroup_rights: list[ZabbixRight] = []
    templategroup_rights: list[ZabbixRight] = []

    @model_serializer
    def model_ser(self) -> dict[str, Any]:
        """LEGACY: Include the permission strings in the serialized output if
        we have legacy JSON output enabled.
        """
        d: dict[str, Any] = {
            "usrgrpid": self.usrgrpid,
            "name": self.name,
            "hostgroup_rights": self.hostgroup_rights,
            "templategroup_rights": self.templategroup_rights,
        }
        if self.legacy_json_format:
            d["permissions"] = self.permissions
            d["usergroupid"] = self.usrgrpid
        return d

    @property
    def permissions(self) -> list[str]:
        """LEGACY: The field `hostgroup_rights` was called `permissions` in V2."""
        r: list[str] = []

        def permission_str(
            right: ZabbixRight, groups: Mapping[str, Union[HostGroup, TemplateGroup]]
        ) -> str:
            group = groups.get(right.id, None)
            if group:
                group_name = group.name
            else:
                group_name = "Unknown"
            perm = UsergroupPermission.string_from_value(
                right.permission, with_code=True
            )
            return f"{group_name} ({perm})"

        for right in self.hostgroup_rights:
            r.append(permission_str(right, self.hostgroups))
        for right in self.templategroup_rights:
            r.append(permission_str(right, self.templategroups))
        return r

    @classmethod
    def from_usergroup(
        cls,
        usergroup: Usergroup,
        hostgroups: list[HostGroup],
        templategroups: list[TemplateGroup],
    ) -> ShowUsergroupPermissionsResult:
        cls.model_rebuild()  # TODO: can we avoid this?
        res = cls(
            usrgrpid=usergroup.usrgrpid,
            name=usergroup.name,
            hostgroups={hg.groupid: hg for hg in hostgroups},
            templategroups={tg.groupid: tg for tg in templategroups},
            templategroup_rights=usergroup.templategroup_rights,
        )
        if res.zabbix_version.release >= (6, 2, 0):
            res.hostgroup_rights = usergroup.hostgroup_rights
        else:
            res.hostgroup_rights = usergroup.rights
        return res

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["ID", "Name", "Host Groups"]
        row: RowContent = [self.usrgrpid, self.name]

        # Host group rights table
        row.append(
            GroupRights(groups=self.hostgroups, rights=self.hostgroup_rights).as_table()
        )

        # Template group rights table
        if self.zabbix_version.release >= (6, 2, 0):
            cols.append("Template Groups")
            row.append(
                GroupRights(
                    groups=self.templategroups, rights=self.templategroup_rights
                ).as_table()
            )
        return cols, [row]
