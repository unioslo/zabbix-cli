from __future__ import annotations

from datetime import datetime

import pytest
from zabbix_cli.pyzabbix.enums import ProxyGroupState
from zabbix_cli.pyzabbix.types import CreateHostInterfaceDetails
from zabbix_cli.pyzabbix.types import DictModel
from zabbix_cli.pyzabbix.types import Event
from zabbix_cli.pyzabbix.types import GlobalMacro
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import HostGroup
from zabbix_cli.pyzabbix.types import HostInterface
from zabbix_cli.pyzabbix.types import Image
from zabbix_cli.pyzabbix.types import ImportRules
from zabbix_cli.pyzabbix.types import Item
from zabbix_cli.pyzabbix.types import Macro
from zabbix_cli.pyzabbix.types import MacroBase
from zabbix_cli.pyzabbix.types import Maintenance
from zabbix_cli.pyzabbix.types import Map
from zabbix_cli.pyzabbix.types import MediaType
from zabbix_cli.pyzabbix.types import ProblemTag
from zabbix_cli.pyzabbix.types import Proxy
from zabbix_cli.pyzabbix.types import ProxyGroup
from zabbix_cli.pyzabbix.types import Role
from zabbix_cli.pyzabbix.types import Template
from zabbix_cli.pyzabbix.types import TemplateGroup
from zabbix_cli.pyzabbix.types import TimePeriod
from zabbix_cli.pyzabbix.types import Trigger
from zabbix_cli.pyzabbix.types import UpdateHostInterfaceDetails
from zabbix_cli.pyzabbix.types import User
from zabbix_cli.pyzabbix.types import Usergroup
from zabbix_cli.pyzabbix.types import UserMedia
from zabbix_cli.pyzabbix.types import ZabbixAPIBaseModel
from zabbix_cli.pyzabbix.types import ZabbixRight


@pytest.mark.parametrize(
    "model",
    [
        # TODO: replace with hypothesis tests when Pydantic v2 support is available
        # Test in order of definition in types.py
        ZabbixRight(permission=2, id="str"),
        User(userid="123", username="test"),
        Usergroup(name="test", usrgrpid="123", gui_access=0, users_status=0),
        Template(templateid="123", host="test"),
        TemplateGroup(groupid="123", name="test", uuid="test123"),
        HostGroup(name="test", groupid="123"),
        DictModel(),
        Host(hostid="123"),
        HostInterface(
            type=1, main=1, ip="127.0.0.1", dns="", port="10050", useip=1, bulk=1
        ),
        CreateHostInterfaceDetails(version=2),
        UpdateHostInterfaceDetails(),
        Proxy(proxyid="123", name="test", address="127.0.0.1"),
        ProxyGroup(
            proxy_groupid="123",
            name="test",
            description="yeah",
            failover_delay="60",
            min_online=1,
            state=ProxyGroupState.ONLINE,
        ),
        MacroBase(macro="foo", value="bar", type=0, description="baz"),
        Macro(
            hostid="123",
            hostmacroid="1234",
            macro="foo",
            value="bar",
            type=0,
            description="baz",
        ),
        GlobalMacro(
            globalmacroid="123g", macro="foo", value="bar", type=0, description="baz"
        ),
        Item(itemid="123"),
        Role(roleid="123", name="test", type=1, readonly=0),
        MediaType(mediatypeid="123", name="test", type=0),
        UserMedia(mediatypeid="123", sendto="foo@example.com"),
        TimePeriod(period=123, timeperiod_type=2),
        ProblemTag(tag="foo", operator=2, value="bar"),
        Maintenance(maintenanceid="123", name="test"),
        Event(
            eventid="source",
            object=1,
            objectid="123",
            source=2,
            acknowledged=0,
            clock=datetime.now(),
            name="test",
            severity=2,
        ),
        Trigger(triggerid="123"),
        Image(imageid="123", name="test", imagetype=1),
        Map(sysmapid="123", name="test", width=100, height=100),
        ImportRules.get(),
    ],
)
def test_model_dump(model: ZabbixAPIBaseModel) -> None:
    """Test that the model can be dumped to JSON."""
    try:
        model.model_dump_json()
    except Exception as e:
        pytest.fail(f"Failed to dump model {model} to JSON: {e}")

    try:
        model.model_dump_api()
    except Exception as e:
        pytest.fail(f"Failed to dump model {model} to API-compatible dict: {e}")

    try:
        model.model_dump()
    except Exception as e:
        pytest.fail(f"Failed to dump model {model} to dict: {e}")
