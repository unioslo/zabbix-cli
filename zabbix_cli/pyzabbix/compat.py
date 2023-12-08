"""Compatibility functions to support different Zabbix API versions."""
from __future__ import annotations

from typing import Literal

from packaging.version import Version

# TODO (pederhan): rewrite these functions as some sort of declarative data
# structure that can be used to determine correct parameters based on version
# if we end up with a lot of these functions. For now, this is fine.
# OR we could turn it into a mixin class?

# Compatibility methods for Zabbix API objects properties and method parameter names (same thing)
# Returns the appropriate property name for the given Zabbix version.
#
# FORMAT: <object>_<property>
# EXAMPLE: user_name() (User object, name property)
#
# DEV NOTE: All functions follow the same pattern:
# Early return if the version is older than the version where the property
# was deprecated, otherwise return the new property name as the default.


def host_proxyid(version: Version) -> Literal["proxy_hostid", "proxyid"]:
    # https://support.zabbix.com/browse/ZBXNEXT-8500
    # https://www.zabbix.com/documentation/7.0/en/manual/api/changes#host
    if version.release < (7, 0, 0):
        return "proxy_hostid"
    return "proxyid"


def host_available(version: Version) -> Literal["available", "active_available"]:
    # TODO: find out why this was changed and what it signifies
    # NO URL YET
    if version.release < (6, 4, 0):
        return "available"
    return "active_available"


def login_user_name(version: Version) -> Literal["user", "username"]:
    # https://support.zabbix.com/browse/ZBXNEXT-8085
    # Deprecated in 5.4.0, removed in 6.4.0
    # login uses different parameter names than the User object before 6.4
    # From 6.4 and onwards, login and user.<method> use the same parameter names
    # See: user_name
    if version.release < (5, 4, 0):
        return "user"
    return "username"


def proxy_name(version: Version) -> Literal["host", "name"]:
    # https://support.zabbix.com/browse/ZBXNEXT-8500
    # https://www.zabbix.com/documentation/7.0/en/manual/api/changes#proxy
    if version.release < (7, 0, 0):
        return "host"
    return "name"


def user_name(version: Version) -> Literal["alias", "username"]:
    # https://support.zabbix.com/browse/ZBXNEXT-8085
    # Deprecated in 5.4, removed in 6.4
    # However, historically we have used "alias" as the parameter name
    # pre-6.0.0, so we maintain that behavior here
    if version.release < (6, 0, 0):
        return "alias"
    return "username"


### API params
# API parameter functions are in the following format:
# param_<object>_<method>_<param>
# So to get the "groups" parameter for the "host.get" method, you would call:
# param_host_get_groups()


def param_host_get_groups(
    version: Version
) -> Literal["selectHostGroups", "selectGroups"]:
    # https://support.zabbix.com/browse/ZBXNEXT-2592
    # hhttps://www.zabbix.com/documentation/6.2/en/manual/api/changes_6.0_-_6.2#host
    if version.release < (6, 2, 0):
        return "selectGroups"
    return "selectHostGroups"
