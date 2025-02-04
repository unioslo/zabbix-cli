"""User result types."""

# NOTE: The user module was one of the first to be written, and thus
# most of the result rendering was implemented in the Pyzabbix models
# themselves instead of as result classes. That is why this module is
# (mostly) empty.
from __future__ import annotations

from zabbix_cli.models import AggregateResult
from zabbix_cli.models import ColsRowsType
from zabbix_cli.models import ColsType
from zabbix_cli.models import RowsType
from zabbix_cli.models import TableRenderable
from zabbix_cli.pyzabbix.types import Usergroup
from zabbix_cli.pyzabbix.types import UserMedia


class CreateNotificationUserResult(TableRenderable):
    """Result type for creating a notification user."""

    username: str
    userid: str
    media: list[UserMedia]
    usergroups: list[Usergroup]

    def __cols_rows__(self) -> ColsRowsType:
        cols: ColsType = [
            "User ID",
            "Username",
            "Media",
            "Usergroups",
        ]
        rows: RowsType = [
            [
                self.userid,
                self.username,
                AggregateResult(result=self.media).as_table(),
                "\n".join([ug.name for ug in self.usergroups]),
            ]
        ]
        return cols, rows
