from __future__ import annotations

from typing import Type

import pytest
from zabbix_cli.pyzabbix.enums import AckStatus
from zabbix_cli.pyzabbix.enums import ActiveInterface
from zabbix_cli.pyzabbix.enums import APIStr
from zabbix_cli.pyzabbix.enums import APIStrEnum
from zabbix_cli.pyzabbix.enums import DataCollectionMode
from zabbix_cli.pyzabbix.enums import EventStatus
from zabbix_cli.pyzabbix.enums import ExportFormat
from zabbix_cli.pyzabbix.enums import GUIAccess
from zabbix_cli.pyzabbix.enums import HostgroupFlag
from zabbix_cli.pyzabbix.enums import HostgroupType
from zabbix_cli.pyzabbix.enums import InterfaceConnectionMode
from zabbix_cli.pyzabbix.enums import InterfaceType
from zabbix_cli.pyzabbix.enums import InventoryMode
from zabbix_cli.pyzabbix.enums import ItemType
from zabbix_cli.pyzabbix.enums import MacroType
from zabbix_cli.pyzabbix.enums import MaintenanceStatus
from zabbix_cli.pyzabbix.enums import MaintenanceType
from zabbix_cli.pyzabbix.enums import MaintenanceWeekType
from zabbix_cli.pyzabbix.enums import MonitoredBy
from zabbix_cli.pyzabbix.enums import MonitoringStatus
from zabbix_cli.pyzabbix.enums import ProxyCompatibility
from zabbix_cli.pyzabbix.enums import ProxyGroupState
from zabbix_cli.pyzabbix.enums import ProxyMode
from zabbix_cli.pyzabbix.enums import ProxyModePre70
from zabbix_cli.pyzabbix.enums import SNMPAuthProtocol
from zabbix_cli.pyzabbix.enums import SNMPPrivProtocol
from zabbix_cli.pyzabbix.enums import SNMPSecurityLevel
from zabbix_cli.pyzabbix.enums import TriggerPriority
from zabbix_cli.pyzabbix.enums import UsergroupPermission
from zabbix_cli.pyzabbix.enums import UserRole
from zabbix_cli.pyzabbix.enums import ValueType

APISTR_ENUMS = [
    AckStatus,
    ActiveInterface,
    DataCollectionMode,
    EventStatus,
    GUIAccess,
    HostgroupFlag,
    HostgroupType,
    InterfaceConnectionMode,
    InterfaceType,
    InventoryMode,
    ItemType,
    MacroType,
    MaintenanceStatus,
    MaintenanceType,
    MaintenanceWeekType,
    MonitoredBy,
    MonitoringStatus,
    ProxyCompatibility,
    ProxyGroupState,
    ProxyMode,
    ProxyModePre70,
    SNMPSecurityLevel,
    SNMPAuthProtocol,
    SNMPPrivProtocol,
    TriggerPriority,
    UsergroupPermission,
    UserRole,
    ValueType,
]


@pytest.mark.parametrize("enum", APISTR_ENUMS)
def test_apistrenum(enum: Type[APIStrEnum]) -> None:
    assert enum.__members__
    members = list(enum)
    assert members
    for member in members:
        # Narrow down type
        assert isinstance(member, enum)
        assert isinstance(member.value, str)
        assert isinstance(member.value, APIStr)

        # Methods
        assert member.as_api_value() is not None
        assert member.__choice_name__ is not None
        assert member.__fmt_name__()  # non-empty string

        # Test instantiation
        assert enum(member) == member
        assert enum(member.value) == member
        # NOTE: to support multiple versions of the Zabbix API, some enums
        # have multiple members with the same API value, and we cannot blindly
        # test instantiation with the API value for those specific enums.
        # To not overcomplicate things, we just skip that test for the affected members
        if member in (SNMPPrivProtocol.AES, SNMPPrivProtocol.AES128):
            continue
        assert enum(member.as_api_value()) == member
        assert enum(member.value.api_value) == member

        # Test string_from_value
        for value in [member.as_api_value(), member.value]:
            s = enum.string_from_value(value)
            if member.name != "UNKNOWN":
                assert "Unknown" not in s, f"{value} can't be converted to string"
            assert s == member.as_status()


def test_interfacetype() -> None:
    # We already test normal behavior in test_apistrenum, check special behavior here
    for member in InterfaceType:
        assert member.value.metadata
        assert member.get_port()
    assert InterfaceType.AGENT.get_port() == "10050"
    assert InterfaceType.SNMP.get_port() == "161"
    assert InterfaceType.IPMI.get_port() == "623"
    assert InterfaceType.JMX.get_port() == "12345"


def test_exportformat() -> None:
    assert ExportFormat.PHP not in ExportFormat.get_importables()
    assert ExportFormat("json") == ExportFormat("JSON")
    assert ExportFormat("xml") == ExportFormat("XML")
    assert ExportFormat("yaml") == ExportFormat("YAML")
    assert ExportFormat.JSON in ExportFormat.get_importables()
    assert ExportFormat.XML in ExportFormat.get_importables()
    assert ExportFormat.YAML in ExportFormat.get_importables()
