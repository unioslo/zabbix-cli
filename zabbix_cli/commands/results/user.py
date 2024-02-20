from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List
from typing import Tuple
from typing import TYPE_CHECKING
from typing import Union

import rich
from pydantic import computed_field
from pydantic import Field
from pydantic import field_validator

from zabbix_cli.models import META_KEY_JOIN_CHAR
from zabbix_cli.models import TableRenderable
from zabbix_cli.pyzabbix.enums import UsergroupPermission
from zabbix_cli.pyzabbix.types import HostGroup
from zabbix_cli.pyzabbix.types import TemplateGroup
from zabbix_cli.pyzabbix.types import Usergroup
from zabbix_cli.pyzabbix.types import ZabbixRight
from zabbix_cli.utils.utils import get_gui_access
from zabbix_cli.utils.utils import get_permission
from zabbix_cli.utils.utils import get_usergroup_status

if TYPE_CHECKING:
    from zabbix_cli.models import ColsRowsType
    from zabbix_cli.models import RowsType  # noqa: F401
    from zabbix_cli.models import RowContent  # noqa: F401


class UgroupUpdateUsersResult(TableRenderable):
    usergroups: List[str]
    users: List[str]

    def __cols_rows__(self) -> ColsRowsType:
        return (
            ["Usergroups", "Users"],
            [["\n".join(self.usergroups), ", ".join(self.users)]],
        )


class UsergroupAddUsers(UgroupUpdateUsersResult):
    __title__ = "Added Users"


class UsergroupRemoveUsers(UgroupUpdateUsersResult):
    __title__ = "Removed Users"


class GroupRights(TableRenderable):
    __box__ = rich.box.MINIMAL

    groups: Union[Dict[str, HostGroup], Dict[str, TemplateGroup]] = Field(
        default_factory=dict,
    )

    rights: List[ZabbixRight] = Field(
        default_factory=list,
        description="Group rights for the user group.",
    )

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["Name", "Permission"]
        rows = []  # type: RowsType
        for right in self.rights:
            group = self.groups.get(right.id, None)
            if group:
                group_name = group.name
            else:
                group_name = "Unknown"
            rows.append([group_name, str(UsergroupPermission(right.permission))])
        return cols, rows


class ShowUsergroupResult(TableRenderable):
    usrgrpid: str = Field(..., json_schema_extra={"header": "ID"})
    name: str
    gui_access: str = Field(..., json_schema_extra={"header": "GUI Access"})
    status: str
    users: List[str] = Field(
        default_factory=list, json_schema_extra={META_KEY_JOIN_CHAR: ", "}
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
            return get_gui_access(v)
        return v

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: Any) -> str:
        if isinstance(v, int):
            return get_usergroup_status(v)
        return v


class ShowUsergroupPermissionsResult(TableRenderable):
    usrgrpid: str
    name: str
    hostgroups: Dict[str, HostGroup] = Field(
        default_factory=dict,
        exclude=True,
        description="Host groups the user group has access to. Used to render host group rights.",
    )
    templategroups: Dict[str, TemplateGroup] = Field(
        default_factory=dict,
        exclude=True,
        description="Mapping of all template groups. Used to render template group rights.",
    )
    hostgroup_rights: List[ZabbixRight] = []
    templategroup_rights: List[ZabbixRight] = []
    zabbix_version: Tuple[int, ...] = Field(..., exclude=True)

    @computed_field  # type: ignore # computed field on @property
    @property
    def usergroupid(self) -> str:
        """LEGACY: The field `usrgrpid` was called `usergroupid` in V2."""
        return self.usrgrpid

    @classmethod
    def from_usergroup(
        cls,
        usergroup: Usergroup,
        hostgroups: List[HostGroup],
        templategroups: List[TemplateGroup],
    ) -> ShowUsergroupPermissionsResult:
        cls.model_rebuild()  # TODO: can we avoid this?
        res = cls(
            usrgrpid=usergroup.usrgrpid,
            name=usergroup.name,
            hostgroups={hg.groupid: hg for hg in hostgroups},
            templategroups={tg.groupid: tg for tg in templategroups},
            zabbix_version=usergroup.zabbix_version.release,
            templategroup_rights=usergroup.templategroup_rights,
        )
        if res.zabbix_version >= (6, 2, 0):
            res.hostgroup_rights = usergroup.hostgroup_rights
        else:
            res.hostgroup_rights = usergroup.rights
        return res

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["ID", "Name", "Host Groups"]
        row = [self.usrgrpid, self.name]  # type: RowContent

        # Host group rights table
        row.append(
            GroupRights(groups=self.hostgroups, rights=self.hostgroup_rights).as_table()
        )

        # Template group rights table
        if self.zabbix_version >= (6, 2, 0):
            cols.append("Template Groups")
            row.append(
                GroupRights(
                    groups=self.templategroups, rights=self.templategroup_rights
                ).as_table()
            )
        return cols, [row]


class AddUsergroupPermissionsResult(TableRenderable):
    usergroup: str
    hostgroups: List[str]
    templategroups: List[str]
    permission: UsergroupPermission

    @computed_field  # type: ignore # computed field on @property
    @property
    def permission_str(self) -> str:
        return get_permission(self.permission.as_api_value())

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
