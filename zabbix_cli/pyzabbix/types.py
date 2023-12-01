"""Type definitions for Zabbix API objects.


Since we are supporting multiple versions of the Zabbix API at the same time,
we don't operate with very strict type definitions. Some definitions are
TypedDicts, while others are Pydantic models. All models are able to
take extra fields, since we don't know (or always care) which fields are
present in which API versions.

It's not type-safe, but it's better than nothing. In the future, we might
want to look into defining Pydantic models that can accommodate multiple
Zabbix versions.
"""
from __future__ import annotations

from enum import Enum
from typing import TypedDict

from pydantic import BaseModel
from pydantic import ConfigDict


class UsergroupPermission(Enum):
    """Usergroup permission levels."""

    DENY = 0
    READ_ONLY = 2
    READ_WRITE = 3


class ZabbixAPIBaseModel(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="allow")


class ZabbixRight(TypedDict):
    permission: int
    id: str


class Usergroup(ZabbixAPIBaseModel):
    name: str
    usrgrpid: str  # technically not required, but we always fetch it
    rights: list[ZabbixRight] = []
    hostgroup_rights: list[ZabbixRight] = []
    templategroup_rights: list[ZabbixRight] = []
