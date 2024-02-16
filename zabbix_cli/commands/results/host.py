from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict

from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.pyzabbix.enums import AgentAvailable
from zabbix_cli.pyzabbix.enums import MaintenanceStatus
from zabbix_cli.pyzabbix.enums import MonitoringStatus


# TODO: don't use BaseModel for this
# Use a normal class with __init__ instead
class HostFilterArgs(BaseModel):
    """Unified processing of old filter string and new filter options."""

    available: Optional[AgentAvailable] = None
    maintenance_status: Optional[MaintenanceStatus] = None
    status: Optional[MonitoringStatus] = None

    model_config = ConfigDict(validate_assignment=True)

    @classmethod
    def from_command_args(
        cls,
        filter_legacy: Optional[str],
        agent: Optional[AgentAvailable],
        maintenance: Optional[bool],
        monitored: Optional[bool],
    ) -> HostFilterArgs:
        args = cls()
        if filter_legacy:
            items = filter_legacy.split(",")
            for item in items:
                try:
                    key, value = (s.strip("'\"") for s in item.split(":"))
                except ValueError as e:
                    raise ZabbixCLIError(
                        f"Failed to parse filter argument at: {item!r}"
                    ) from e
                if key == "available":
                    args.available = value  # type: ignore # validator converts it
                elif key == "maintenance":
                    args.maintenance_status = value  # type: ignore # validator converts it
                elif key == "status":
                    args.status = value  # type: ignore # validator converts it
        else:
            if agent is not None:
                args.available = agent
            if monitored is not None:
                # Inverted API values (0 = ON, 1 = OFF) - use enums directly
                args.status = MonitoringStatus.ON if monitored else MonitoringStatus.OFF
            if maintenance is not None:
                args.maintenance_status = (
                    MaintenanceStatus.ON if maintenance else MaintenanceStatus.OFF
                )
        return args
