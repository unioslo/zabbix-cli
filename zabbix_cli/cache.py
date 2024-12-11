"""Simple in-memory caching of frequently used Zabbix objects."""

# TODO: add on/off toggle for caching
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Optional

from zabbix_cli.exceptions import ZabbixCLIError

if TYPE_CHECKING:
    from zabbix_cli.pyzabbix.client import ZabbixAPI


class ZabbixCache:
    """In-memory cache of frequently used Zabbix objects."""

    def __init__(self, client: ZabbixAPI) -> None:
        self.client = client
        self._hostgroup_name_cache: dict[str, str] = {}
        """Mapping of hostgroup names to hostgroup IDs"""

        self._hostgroup_id_cache: dict[str, str] = {}
        """Mapping of hostgroup IDs to hostgroup names"""

        self._templategroup_name_cache: dict[str, str] = {}
        """Mapping of templategroup names to templategroup IDs"""

        self._templategroup_id_cache: dict[str, str] = {}  # NOTE: unused
        """Mapping of templategroup IDs to templategroup names"""

    def populate(self) -> None:
        try:
            self._populate_hostgroup_cache()
            self._populate_templategroup_cache()
        except Exception as e:
            raise ZabbixCLIError(f"Failed to populate Zabbix cache: {e}")

    def _populate_hostgroup_cache(self) -> None:
        """Populates the hostgroup caches with data from the Zabbix API."""
        hostgroups = self.client.hostgroup.get(output=["name", "groupid"])
        self._hostgroup_name_cache = {
            hostgroup["name"]: hostgroup["groupid"] for hostgroup in hostgroups
        }
        self._hostgroup_id_cache = {
            hostgroup["groupid"]: hostgroup["name"] for hostgroup in hostgroups
        }

    def _populate_templategroup_cache(self) -> None:
        """Populates the templategroup caches with data from the Zabbix API
        on Zabbix >= 6.2.0.
        """
        if self.client.version.release < (6, 2, 0):
            logging.debug(
                "Skipping template group caching. API version is %s",
                self.client.version,
            )
            return

        templategroups = self.client.templategroup.get(output=["name", "groupid"])
        self._templategroup_name_cache = {
            templategroup["name"]: templategroup["groupid"]
            for templategroup in templategroups
        }
        self._templategroup_id_cache = {
            templategroup["groupid"]: templategroup["name"]
            for templategroup in templategroups
        }

    def get_hostgroup_name(self, hostgroup_id: str) -> Optional[str]:
        """Returns the name of a host group given its ID."""
        return self._hostgroup_id_cache.get(hostgroup_id)

    def get_hostgroup_id(self, hostgroup_name: str) -> Optional[str]:
        """Returns the ID of a host group given its name."""
        return self._hostgroup_name_cache.get(hostgroup_name)

    def get_templategroup_name(self, templategroup_id: str) -> Optional[str]:
        """Returns the name of a template group given its ID."""
        return self._templategroup_id_cache.get(templategroup_id)

    def get_templategroup_id(self, templategroup_name: str) -> Optional[str]:
        """Returns the ID of a template group given its name."""
        return self._templategroup_name_cache.get(templategroup_name)
