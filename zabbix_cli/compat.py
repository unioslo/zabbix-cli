"""Compatibility functions for different Zabbix versions."""

from packaging.version import Version

# TODO (pederhan): rewrite these functions as some sort of declarative data
# structure that can be used to determine correct parameters based on version
# if we end up with a lot of these functions. For now, this is fine.


# Compatibility methods for Zabbix API objects properties and method parameter names (same thing)
# Format: <object>_<property>_by_version
# Example: user_name_by_version (User object, name property)

def host_proxyid_by_version(version: Version) -> str:
    # https://support.zabbix.com/browse/ZBXNEXT-8500
    # https://www.zabbix.com/documentation/7.0/en/manual/api/changes#host
    if version.release < (7, 0, 0):
        return "proxy_hostid"
    return "proxyid" # defaults to new parameter name


def proxy_name_by_version(version: Version) -> str:
    # https://support.zabbix.com/browse/ZBXNEXT-8500
    # https://www.zabbix.com/documentation/7.0/en/manual/api/changes#proxy
    if version.release < (7, 0, 0):
        return "host"
    return "name" # defaults to new parameter name


def user_name_by_version(version: Version) -> str:
    # https://support.zabbix.com/browse/ZBXNEXT-8085
    if version.release < (5, 4, 0):
        return 'user'
    return 'username' # defaults to new parameter name

