from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Optional

from pydantic import Field
from pydantic import computed_field
from pydantic import field_validator
from typing_extensions import Literal

from zabbix_cli.models import ColsRowsType
from zabbix_cli.models import TableRenderable
from zabbix_cli.pyzabbix.enums import MaintenanceType
from zabbix_cli.pyzabbix.types import TimePeriod


class CreateMaintenanceDefinitionResult(TableRenderable):
    """Result type for `create_maintenance_definition` command."""

    maintenance_id: str


class ShowMaintenancePeriodsResult(TableRenderable):
    maintenanceid: str = Field(title="Maintenance ID")
    name: str
    timeperiods: list[TimePeriod]
    hosts: list[str]
    groups: list[str]


class ShowMaintenanceDefinitionsResult(TableRenderable):
    """Result type for `show_maintenance_definitions` command."""

    maintenanceid: str
    name: str
    type: Optional[int]
    active_till: datetime
    description: Optional[str]
    hosts: list[str]
    groups: list[str]

    @computed_field
    @property
    def state(self) -> Literal["Active", "Expired"]:
        now_time = datetime.now(tz=self.active_till.tzinfo)
        if self.active_till > now_time:
            return "Active"
        return "Expired"

    @computed_field
    @property
    def maintenance_type(self) -> str:
        return MaintenanceType.string_from_value(self.type)

    @field_validator("active_till", mode="before")
    @classmethod
    def validate_active_till(cls, v: Any) -> datetime:
        if v is None:
            return datetime.now()
        return v

    @property
    def state_str(self) -> str:
        if self.state == "Active":
            color = "green"
        else:
            color = "red"
        return f"[{color}]{self.state}[/]"

    @property
    def maintenance_type_str(self) -> str:
        # FIXME: This is very brittle! We are beholden to self.maintenance_type...
        if "With DC" in self.maintenance_type:
            color = "green"
        else:
            color = "red"
        return f"[{color}]{self.maintenance_type}[/]"

    def __cols_rows__(self) -> ColsRowsType:
        return (
            [
                "ID",
                "Name",
                "Type",
                "Active till",
                "Hosts",
                "Host groups",
                "State",
                "Description",
            ],
            [
                [
                    self.maintenanceid,
                    self.name,
                    self.maintenance_type_str,
                    self.active_till.strftime("%Y-%m-%d %H:%M"),
                    ", ".join(self.hosts),
                    ", ".join(self.groups),
                    self.state_str,
                    self.description or "",
                ]
            ],
        )
