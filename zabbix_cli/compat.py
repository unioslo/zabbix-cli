"""Compatibility functions for different Zabbix versions."""
from __future__ import annotations

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


def host_proxyid(version: Version) -> str:
    # https://support.zabbix.com/browse/ZBXNEXT-8500
    # https://www.zabbix.com/documentation/7.0/en/manual/api/changes#host
    if version.release < (7, 0, 0):
        return "proxy_hostid"
    return "proxyid"


def login_user_name(version: Version) -> str:
    # https://support.zabbix.com/browse/ZBXNEXT-8085
    # Deprecated in 5.4.0, removed in 6.4.0
    # login uses different parameter names than the User object before 6.4
    # From 6.4 and onwards, login and user.<method> use the same parameter names
    # See: user_name
    if version.release < (5, 4, 0):
        return "user"
    return "username"


def proxy_name(version: Version) -> str:
    # https://support.zabbix.com/browse/ZBXNEXT-8500
    # https://www.zabbix.com/documentation/7.0/en/manual/api/changes#proxy
    if version.release < (7, 0, 0):
        return "host"
    return "name"


def user_name(version: Version) -> str:
    # https://support.zabbix.com/browse/ZBXNEXT-8085
    # Deprecated in 5.4, removed in 6.4
    # However, historically we have used "alias" as the parameter name
    # pre-6.0.0, so we maintain that behavior here
    if version.release < (6, 0, 0):
        return "alias"
    return "username"
