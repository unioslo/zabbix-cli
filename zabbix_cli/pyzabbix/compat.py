"""Compatibility functions to support different Zabbix API versions."""

from __future__ import annotations

from typing import Literal

from packaging.version import Version

# TODO (pederhan): rewrite these functions as some sort of declarative data
# structure that can be used to determine correct parameters based on version
# if we end up with a lot of these functions. For now, this is fine.
# OR we could turn it into a mixin class?

# Compatibility methods for Zabbix API objects properties and method parameters.
# Returns the appropriate property name for the given Zabbix version.
#
# FORMAT: <object>_<property>
# EXAMPLE: user_name() (User object, name property)
#
# NOTE: All functions follow the same pattern:
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
        return "available"  # unsupported in < 6.4.0
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


def role_id(version: Version) -> Literal["roleid", "type"]:
    # https://support.zabbix.com/browse/ZBXNEXT-6148
    # https://www.zabbix.com/documentation/5.2/en/manual/api/changes_5.0_-_5.2#role
    if version.release < (5, 2, 0):
        return "type"
    return "roleid"


def user_name(version: Version) -> Literal["alias", "username"]:
    # https://support.zabbix.com/browse/ZBXNEXT-8085
    # Deprecated in 5.4, removed in 6.4
    # However, historically we have used "alias" as the parameter name
    # pre-6.0.0, so we maintain that behavior here
    if version.release < (6, 0, 0):
        return "alias"
    return "username"


def user_medias(version: Version) -> Literal["user_medias", "medias"]:
    # https://support.zabbix.com/browse/ZBX-17955
    # Deprecated in 5.2, removed in 6.4
    if version.release < (5, 2, 0):
        return "user_medias"
    return "medias"


def usergroup_hostgroup_rights(
    version: Version,
) -> Literal["rights", "hostgroup_rights"]:
    # https://support.zabbix.com/browse/ZBXNEXT-2592
    # https://www.zabbix.com/documentation/6.2/en/manual/api/changes_6.0_-_6.2
    # Deprecated in 6.2
    if version.release < (6, 2, 0):
        return "rights"
    return "hostgroup_rights"


# NOTE: can we remove this function? Or are we planning on using it to
# assign rights for templates?
def usergroup_templategroup_rights(
    version: Version,
) -> Literal["rights", "templategroup_rights"]:
    # https://support.zabbix.com/browse/ZBXNEXT-2592
    # https://www.zabbix.com/documentation/6.2/en/manual/api/changes_6.0_-_6.2
    # Deprecated in 6.2
    if version.release < (6, 2, 0):
        return "rights"
    return "templategroup_rights"


### API params
# API parameter functions are in the following format:
# param_<object>_<method>_<param>
# So to get the "groups" parameter for the "host.get" method, you would call:
# param_host_get_groups()


def param_host_get_groups(
    version: Version,
) -> Literal["selectHostGroups", "selectGroups"]:
    # https://support.zabbix.com/browse/ZBXNEXT-2592
    # hhttps://www.zabbix.com/documentation/6.2/en/manual/api/changes_6.0_-_6.2#host
    if version.release < (6, 2, 0):
        return "selectGroups"
    return "selectHostGroups"


def param_maintenance_create_groupids(
    version: Version,
) -> Literal["groupids", "groups"]:
    # https://support.zabbix.com/browse/ZBXNEXT-2592
    # https://www.zabbix.com/documentation/6.2/en/manual/api/changes_6.0_-_6.2#host
    if version.release < (6, 2, 0):
        return "groups"
    return "groupids"
