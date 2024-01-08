#
# Most of the code in this file is from the project PyZabbix:
# https://github.com/lukecyca/pyzabbix
#
# We have modified the login method to be able to send an auth-token so
# we do not have to login again as long as the auth-token used is still
# active.
#
# We have also modified the output when an error happens to not show
# the username + password information.
#
from __future__ import annotations

import json
import logging
import random
import re
from typing import Any
from typing import Dict
from typing import List
from typing import Literal
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union

import requests
import urllib3
from packaging.version import Version

from zabbix_cli.cache import ZabbixCache
from zabbix_cli.exceptions import ZabbixAPIException
from zabbix_cli.exceptions import ZabbixNotFoundError
from zabbix_cli.pyzabbix import compat
from zabbix_cli.pyzabbix.types import GlobalMacro
from zabbix_cli.pyzabbix.types import GUIAccess
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import HostGroup
from zabbix_cli.pyzabbix.types import Item
from zabbix_cli.pyzabbix.types import Macro
from zabbix_cli.pyzabbix.types import Maintenance
from zabbix_cli.pyzabbix.types import MediaType
from zabbix_cli.pyzabbix.types import Proxy
from zabbix_cli.pyzabbix.types import Role
from zabbix_cli.pyzabbix.types import Template
from zabbix_cli.pyzabbix.types import TemplateGroup
from zabbix_cli.pyzabbix.types import User
from zabbix_cli.pyzabbix.types import Usergroup
from zabbix_cli.pyzabbix.types import UserMedia
from zabbix_cli.pyzabbix.types import ZabbixRight
from zabbix_cli.utils.args import UsergroupPermission
from zabbix_cli.utils.args import UserRole

if TYPE_CHECKING:
    from zabbix_cli.pyzabbix.types import MaintenanceStatus
    from zabbix_cli.pyzabbix.types import MonitoringStatus
    from zabbix_cli.pyzabbix.types import AgentAvailable
    from zabbix_cli.pyzabbix.types import ParamsType  # noqa: F401
    from zabbix_cli.pyzabbix.types import SortOrder  # noqa: F401
    from zabbix_cli.pyzabbix.types import ModifyHostParams  # noqa: F401
    from zabbix_cli.pyzabbix.types import ModifyGroupParams  # noqa: F401
    from zabbix_cli.pyzabbix.types import ModifyTemplateParams  # noqa: F401


class _NullHandler(logging.Handler):
    def emit(self, record):
        pass


logger = logging.getLogger(__name__)


class ZabbixAPI:
    def __init__(
        self,
        server: str = "http://localhost/zabbix",
        session: Optional[requests.Session] = None,
        timeout: Optional[int] = None,
    ):
        """
        Parameters:
            server: Base URI for zabbix web interface (omitting /api_jsonrpc.php)
            session: optional pre-configured requests.Session instance
            timeout: optional connect and read timeout in seconds, default: None (if you're using Requests >= 2.4 you can set it as tuple: "(connect, read)" which is used to set individual connect and read timeouts.)
        """

        if session:
            self.session = session
        else:
            self.session = requests.Session()

        # Default headers for all requests
        self.session.headers.update(
            {
                "Content-Type": "application/json-rpc",
                "User-Agent": "python/pyzabbix",
                "Cache-Control": "no-cache",
            }
        )

        self.auth = ""
        self.id = 0

        self.timeout = timeout

        self.url = server + "/api_jsonrpc.php"
        logger.info("JSON-RPC Server Endpoint: %s", self.url)

        # Attributes for properties
        self._version = None  # type: Version | None

        # Cache
        self.cache = ZabbixCache(self)

    def disable_ssl_verification(self):
        """Disables SSL verification and suppresses urllib3 SSL warning."""
        self.session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def login(
        self,
        user: Optional[str] = None,
        password: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> str:
        """
        Convenience method for logging into the API and storing the resulting
        auth token as an instance variable.
        """
        # The username kwarg was called "user" in Zabbix 5.2 and earlier.
        # This sets the correct kwarg for the version of Zabbix we're using.
        user_kwarg = {compat.login_user_name(self.version): user}

        if not auth_token:
            self.auth = self.user.login(**user_kwarg, password=password)
        else:
            self.auth = auth_token
            # TODO: confirm we are logged in here
            self.api_version()  # NOTE: useless? can we remove this?
        return self.auth

    def confimport(self, format="", source="", rules=""):
        """Alias for configuration.import because it clashes with
        Python's import reserved keyword"""

        return self.do_request(
            method="configuration.import",
            params={"format": format, "source": source, "rules": rules},
        )["result"]

    # TODO (pederhan): Use functools.cachedproperty when we drop 3.7 support
    @property
    def version(self) -> Version:
        """Alternate version of api_version() that caches version info
        as a Version object."""
        if self._version is None:
            self._version = Version(self.apiinfo.version())
        return self._version

    def api_version(self):
        return self.apiinfo.version()

    def do_request(self, method, params=None):
        request_json = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self.id,
        }

        # We don't have to pass the auth token if asking for the apiinfo.version
        if self.auth and method != "apiinfo.version":
            request_json["auth"] = self.auth

        # logger.debug(
        #     "Sending: %s", json.dumps(request_json, indent=4, separators=(",", ": "))
        # )

        response = self.session.post(
            self.url, data=json.dumps(request_json), timeout=self.timeout
        )

        # logger.debug("Response Code: %s", str(response.status_code))

        # NOTE: Getting a 412 response code means the headers are not in the
        # list of allowed headers.
        response.raise_for_status()

        if not len(response.text):
            raise ZabbixAPIException("Received empty response")

        try:
            response_json = json.loads(response.text)
        except ValueError:
            raise ZabbixAPIException("Unable to parse json: %s" % response.text)
        # logger.debug(
        #     "Response Body: %s",
        #     json.dumps(response_json, indent=4, separators=(",", ": ")),
        # )

        self.id += 1

        if "error" in response_json:  # some exception
            if (
                "data" not in response_json["error"]
            ):  # some errors don't contain 'data': workaround for ZBX-9340
                response_json["error"]["data"] = "No data"

            #
            # We do not want to get the password value in the error
            # message if the user uses a not valid username or
            # password.
            #

            if (
                response_json["error"]["data"]
                in (
                    "Login name or password is incorrect.",
                    "Incorrect user name or password or account is temporarily blocked.",  # >=6.4
                )
            ):
                msg = "Error {code}: {message}: {data}".format(
                    code=response_json["error"]["code"],
                    message=response_json["error"]["message"],
                    data=response_json["error"]["data"],
                )

            elif response_json["error"]["data"] == "Not authorized":
                msg = "Error {code}: {data}: {message}".format(
                    code=response_json["error"]["code"],
                    data=response_json["error"]["data"],
                    message=response_json["error"]["message"]
                    + "\n\n* Your API-auth-token has probably expired.\n"
                    + "* Try to login again with your username and password",
                )

            else:
                msg = "Error {code}: {message}: {data} while sending {json}".format(
                    code=response_json["error"]["code"],
                    message=response_json["error"]["message"],
                    data=response_json["error"]["data"],
                    json=str(request_json),
                )

            raise ZabbixAPIException(msg, response_json["error"]["code"])

        return response_json

    def populate_cache(self) -> None:
        """Populates the various caches with data from the Zabbix API."""
        # NOTE: Must be manually invoked. Can we do this in a thread?
        self.cache.populate()

    def get_hostgroup_name(self, hostgroup_id: str) -> str:
        """Returns the name of a host group given its ID."""
        hostgroup_name = self.cache.get_hostgroup_name(hostgroup_id)
        if hostgroup_name:
            return hostgroup_name
        resp = self.hostgroup.get(filter={"groupid": hostgroup_id}, output=["name"])
        if not resp:
            raise ZabbixNotFoundError(f"HostGroup with ID {hostgroup_id} not found")
        # TODO add result to cache
        return resp[0]["name"]

    def get_hostgroup_id(self, hostgroup_name: str) -> str:
        """Returns the ID of a host group given its name."""
        hostgroup_id = self.cache.get_hostgroup_id(hostgroup_name)
        if hostgroup_id:
            return hostgroup_id
        resp = self.hostgroup.get(filter={"name": hostgroup_name}, output=["name"])
        if not resp:
            raise ZabbixNotFoundError(f"Host group {hostgroup_name!r} not found")
        # TODO add result to cache
        return resp[0]["groupid"]

    def get_hostgroup(
        self,
        name_or_id: str,
        search: bool = False,
        select_hosts: bool = False,
        sort_order: SortOrder | None = None,
        sort_field: str | None = None,
    ) -> HostGroup:
        """Fetches a host group given its name or ID.

        Name or ID argument is interpeted as an ID if the argument is numeric.

        Uses filtering by default, but can be switched to searching by setting
        the `search` argument to True.

        Args:
            name_or_id (str): Name or ID of the host group.
            search (bool, optional): Search for host groups using the given pattern instead of filtering. Defaults to False.
            hosts (bool, optional): Fetch full information for each host in the group. Defaults to False.

        Raises:
            ZabbixNotFoundError: Group is not found.

        Returns:
            HostGroup: The host group object.
        """
        hostgroups = self.get_hostgroups(
            name_or_id,
            search=search,
            select_hosts=select_hosts,
            sort_order=sort_order,
            sort_field=sort_field,
        )
        if not hostgroups:
            raise ZabbixNotFoundError(f"Host group {name_or_id!r} not found")
        return hostgroups[0]

    def get_hostgroups(
        self,
        *names_or_ids: str,
        search: bool = False,
        select_hosts: bool = False,
        sort_order: SortOrder | None = None,
        sort_field: str | None = None,
    ) -> List[HostGroup]:
        """Fetches a list of host groups given its name or ID.

        Name or ID argument is interpeted as an ID if the argument is numeric.

        Uses filtering by default, but can be switched to searching by setting
        the `search` argument to True.

        Args:
            name_or_id (str): Name or ID of the host group.
            search (bool, optional): Search for host groups using the given pattern instead of filtering. Defaults to False.
            hosts (bool, optional): Fetch full information for each host in the group. Defaults to False.

        Raises:
            ZabbixNotFoundError: Group is not found.

        Returns:
            List[HostGroup]: List of host groups.
        """
        # HACK: don't filter if we have an asterisk (all templates)
        # TODO: refactor this along with other methods that take names or ids (or wildcards)
        params = {"output": "extend"}  # type: ParamsType

        if "*" in names_or_ids:
            names_or_ids = tuple()

        if names_or_ids:
            for name_or_id in names_or_ids:
                norid = name_or_id.strip()
                is_id = norid.isnumeric()
                norid_key = "groupid" if is_id else "name"
                if search and not is_id:
                    params["searchWildcardsEnabled"] = True
                    params.setdefault("search", {}).setdefault("name", []).append(  # type: ignore # bad annotation
                        name_or_id
                    )
                else:
                    params["filter"] = {norid_key: name_or_id}
        if select_hosts:
            params["selectHosts"] = "extend"
        if sort_order:
            params["sortorder"] = sort_order
        if sort_field:
            params["sortfield"] = sort_field

        resp = self.hostgroup.get(**params) or []
        return [HostGroup(**hostgroup) for hostgroup in resp]

    def get_templategroup(
        self,
        name_or_id: str,
        search: bool = False,
        select_templates: bool = False,
    ) -> TemplateGroup:
        """Fetches a template group given its name or ID.

        Name or ID argument is interpeted as an ID if the argument is numeric.

        Uses filtering by default, but can be switched to searching by setting
        the `search` argument to True.

        Args:
            name_or_id (str): Name or ID of the template group.
            search (bool, optional): Search for template groups using the given pattern instead of filtering. Defaults to False.
            select_templates (bool, optional): Fetch full information for each template in the group. Defaults to False.

        Raises:
            ZabbixNotFoundError: Group is not found.

        Returns:
            TemplateGroup: The template group object.
        """
        tgroups = self.get_templategroups(
            name_or_id, search=search, select_templates=select_templates
        )
        if not tgroups:
            raise ZabbixNotFoundError(f"Template group {name_or_id!r} not found")
        return tgroups[0]

    def get_templategroups(
        self,
        *names_or_ids: str,
        search: bool = False,
        select_templates: bool = False,
    ) -> List[TemplateGroup]:
        """Fetches a list of template groups, optionally filtered by name(s).

        Name or ID argument is interpeted as an ID if the argument is numeric.

        Uses filtering by default, but can be switched to searching by setting
        the `search` argument to True.

        Args:
            name_or_id (str): Name or ID of the template group.
            search (bool, optional): Search for template groups using the given pattern instead of filtering. Defaults to False.

        Raises:
            ZabbixNotFoundError: Group is not found.

        Returns:
            List[TemplateGroup]: List of template groups.
        """
        # FIXME: ensure we use searching correctly here
        # HACK: don't filter if we have an asterisk (all templates)
        # TODO: refactor this along with other methods that take names or ids (or wildcards)
        params = {"output": "extend"}  # type: ParamsType

        if "*" in names_or_ids:
            names_or_ids = tuple()

        if names_or_ids:
            for name_or_id in names_or_ids:
                norid = name_or_id.strip()
                is_id = norid.isnumeric()
                norid_key = "groupid" if is_id else "name"
                if search and not is_id:
                    params["searchWildcardsEnabled"] = True
                    params.setdefault("search", {}).setdefault("name", []).append(  # type: ignore # bad annotation
                        name_or_id
                    )
                else:
                    params["filter"] = {norid_key: name_or_id}

        if select_templates:
            params["selectTemplates"] = "extend"

        resp = self.templategroup.get(**params) or []
        return [TemplateGroup(**tgroup) for tgroup in resp]

    def get_host(
        self,
        name_or_id: str,
        select_groups: bool = False,
        select_templates: bool = False,
        select_inventory: bool = False,
        select_macros: bool = False,
        proxyid: Optional[str] = None,
        maintenance: Optional[MaintenanceStatus] = None,
        monitored: Optional[MonitoringStatus] = None,
        agent_status: Optional[AgentAvailable] = None,
        sort_field: Optional[str] = None,
        sort_order: Optional[SortOrder] = None,
        search: bool = False,
    ) -> Host:
        """Fetches a host given a name or id."""
        hosts = self.get_hosts(
            name_or_id,
            select_groups=select_groups,
            select_templates=select_templates,
            select_inventory=select_inventory,
            select_macros=select_macros,
            proxyid=proxyid,
            sort_field=sort_field,
            sort_order=sort_order,
            search=search,
            maintenance=maintenance,
            monitored=monitored,
            agent_status=agent_status,
        )
        if not hosts:
            raise ZabbixNotFoundError(
                f"Host {name_or_id!r} not found. Check your search pattern and filters."
            )
        if len(hosts) > 1:
            logger.debug(
                "Found multiple hosts matching %s, choosing first result: %s",
                name_or_id,
                hosts[0],
            )
        return hosts[0]

    def get_hosts(
        self,
        *names_or_ids: str,
        select_groups: bool = False,
        select_templates: bool = False,
        select_inventory: bool = False,
        select_macros: bool = False,
        proxyid: Optional[str] = None,
        # These params take special API values we don't want to evaluate
        # inside this method, so we delegate it to the enums.
        maintenance: Optional[MaintenanceStatus] = None,
        monitored: Optional[MonitoringStatus] = None,
        agent_status: Optional[AgentAvailable] = None,
        sort_field: Optional[str] = None,
        sort_order: Optional[Literal["ASC", "DESC"]] = None,
        search: Optional[
            bool
        ] = True,  # we generally always want to search when multiple hosts are requested
        # **filter_kwargs,
    ) -> List[Host]:
        """Fetches all hosts matching the given criteria(s).

        Hosts can be filtered by name or ID. Names and IDs cannot be mixed.
        If no criteria are given, all hosts are returned.

        A number of extra properties can be fetched for each host by setting
        the corresponding `select_*` argument to `True`. Each Host object
        will have the corresponding property populated.


        If `search=True`, only a single hostname pattern should be given;
        criterias are matched using logical AND (narrows down results).
        If `search=False`, multiple hostnames or IDs can be used.

        Args:
            select_groups (bool, optional): Include host (& template groups if >=6.2). Defaults to False.
            select_templates (bool, optional): Include templates. Defaults to False.
            select_inventory (bool, optional): Include inventory items. Defaults to False.
            select_macros (bool, optional): Include host macros. Defaults to False.
            proxyid (Optional[str], optional): Filter by proxy ID. Defaults to None.
            maintenance (Optional[MaintenanceStatus], optional): Filter by maintenance status. Defaults to None.
            monitored (Optional[MonitoringStatus], optional): Filter by monitoring status. Defaults to None.
            agent_status (Optional[AgentAvailable], optional): Filter by agent availability. Defaults to None.
            sort_field (Optional[str], optional): Sort hosts by the given field. Defaults to None.
            sort_order (Optional[Literal[ASC, DESC]], optional): Sort order. Defaults to None.
            search (Optional[bool], optional): Force positional arguments to be treated as a search pattern. Defaults to True.

        Raises:
            ZabbixAPIException: _description_

        Returns:
            List[Host]: _description_
        """

        params = {"output": "extend"}  # type: ParamsType
        filter_params = {}  # type: ParamsType

        # Filter by the given host name or ID if we have one
        if names_or_ids:
            id_mode = None  # type: Optional[bool]
            for name_or_id in names_or_ids:
                name_or_id = name_or_id.strip()
                is_id = name_or_id.isnumeric()
                if search is None:  # determine if we should search
                    search = not is_id

                # Set ID mode if we haven't already
                # and ensure we aren't mixing IDs and names
                if id_mode is None:
                    id_mode = is_id
                else:
                    if id_mode != is_id:
                        raise ZabbixAPIException("Cannot mix host names and IDs.")

                # Searching for IDs is pointless - never allow it
                # Logical AND for multiple unique identifiers is not possible
                if search and not is_id:
                    params["searchWildcardsEnabled"] = True
                    params.setdefault("search", {}).setdefault("host", []).append(  # type: ignore # bad annotation
                        name_or_id
                    )
                elif is_id:
                    params.setdefault("hostids", []).append(name_or_id)  # type: ignore
                else:
                    filter_params.setdefault("host", []).append(name_or_id)  # type: ignore # bad annotation

        # Filters are applied with a logical AND (narrows down)
        if proxyid:
            filter_params[compat.host_proxyid(self.version)] = proxyid
        if maintenance is not None:
            filter_params["maintenance_status"] = maintenance.as_api_value()
        if monitored is not None:
            filter_params["status"] = monitored.as_api_value()
        if agent_status is not None:
            filter_params[
                compat.host_available(self.version)
            ] = agent_status.as_api_value()

        if filter_params:  # Only add filter if we actually have filter params
            params["filter"] = filter_params

        if select_groups:
            # still returns the result under the "groups" property
            # even if we use the new 6.2 selectHostGroups param
            param = compat.param_host_get_groups(self.version)
            params[param] = "extend"
        if select_templates:
            params["selectParentTemplates"] = "extend"
        if select_inventory:
            params["selectInventory"] = "extend"
        if select_macros:
            params["selectMacros"] = "extend"
        if sort_field:
            params["sortfield"] = sort_field
        if sort_order:
            params["sortorder"] = sort_order

        resp = self.host.get(**params) or []
        # TODO add result to cache
        return [Host(**resp) for resp in resp]

    def host_exists(self, name_or_id: str) -> bool:
        """Checks if a host exists given its name or ID."""
        try:
            self.get_host(name_or_id)
        except ZabbixNotFoundError:
            return False
        except Exception as e:
            raise ZabbixAPIException(
                f"Unknown error when fetching host {name_or_id}: {e}"
            )
        else:
            return True

    def get_host_id(self, hostname: str) -> str:
        # FIXME: remove this method. we don't use it!
        # TODO: implement caching for hosts
        resp = self.host.get(filter={"host": hostname}, output=["hostid"])
        if not resp:
            raise ZabbixNotFoundError(f"Host with name {hostname!r} not found")
        return resp[0]["hostid"]

    def hostgroup_exists(self, hostgroup_name: str) -> bool:
        try:
            self.get_hostgroup_id(hostgroup_name)
        except ZabbixNotFoundError:
            return False
        except Exception as e:
            raise ZabbixAPIException(
                f"Unknown error when fetching host group {hostgroup_name}: {e}"
            )
        else:
            return True

    def get_usergroup(
        self,
        name: str,
        select_users: bool = False,
        select_rights: bool = False,
        search: bool = False,
    ) -> Usergroup:
        """Fetches a user group by name. Always fetches the full contents of the group."""
        groups = self.get_usergroups(
            name,
            select_users=select_users,
            select_rights=select_rights,
            search=search,
        )
        if not groups:
            raise ZabbixNotFoundError(f"User group {name!r} not found")
        return groups[0]

    def get_usergroups(
        self,
        *names: str,
        # See get_usergroup for why these are set to True by default
        select_users: bool = True,
        select_rights: bool = True,
        search: bool = False,
    ) -> List[Usergroup]:
        """Fetches all user groups. Optionally includes users and rights."""
        params = {
            "output": "extend",
        }  # type: ParamsType
        if "*" in names:
            names = tuple()
        if search:
            params["searchByAny"] = True  # Union search (default is intersection)
            params["searchWildcardsEnabled"] = True

        if names:
            for name in names:
                name = name.strip()
                if search:
                    params.setdefault("search", {}).setdefault("name", []).append(  # type: ignore # bad annotation
                        name
                    )
                else:
                    params["filter"] = {"name": name}

        # Rights were split into host and template group rights in 6.2.0
        if select_rights:
            if self.version.release >= (6, 2, 0):
                params["selectHostGroupRights"] = "extend"
                params["selectTemplateGroupRights"] = "extend"
            else:
                params["selectRights"] = "extend"
        if select_users:
            params["selectUsers"] = "extend"

        try:
            res = self.usergroup.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPIException(f"Unknown error when fetching user groups: {e}")
        else:
            return [Usergroup(**usergroup) for usergroup in res]

    def create_usergroup(
        self,
        usergroup_name: str,
        disabled: bool = False,
        gui_access: GUIAccess = GUIAccess.DEFAULT,
    ) -> str:
        """Creates a user group with the given name."""
        try:
            resp = self.usergroup.create(
                name=usergroup_name,
                users_status=int(disabled),
                gui_access=gui_access.as_api_value(),
            )
        except ZabbixAPIException as e:
            raise ZabbixAPIException(
                f"Failed to create user group {usergroup_name!r}: {e}"
            ) from e
        if not resp or not resp.get("usrgrpids"):
            raise ZabbixAPIException(
                "User group creation returned no data. Unable to determine if group was created."
            )
        return str(resp["usrgrpids"][0])

    # TODO: do any commands update both rights and users?
    # Can we split this into two methods?
    # The only benefit of combining them is to avoid multiple API calls
    # to fetch the usergroup and its users.
    def update_usergroup(
        self,
        usergroup_name: str,
        rights: Optional[List[ZabbixRight]] = None,
        userids: Optional[List[str]] = None,
    ) -> Optional[list]:
        """
        Merge update a usergroup.

        Updating usergroups without replacing current state (i.e. merge update) is hard.
        This function simplifies the process.

        The rights and userids provided are merged into the usergroup.
        """
        usergroup = self.get_usergroup(usergroup_name)

        if rights:
            # Get the current rights with ids from new rights filtered
            new_rights = [
                current_right
                for current_right in usergroup.rights
                if current_right["id"] not in [right["id"] for right in rights]
            ]  # type: list[ZabbixRight]
            new_rights.extend(rights)
            return self.usergroup.update(usrgrpid=usergroup.usrgrpid, rights=new_rights)

        if userids:
            current_userids = [user.userid for user in usergroup.users]  # type: list[str]
            # Make sure we only have unique ids
            new_userids = list(set(current_userids + userids))
            return self.usergroup.update(
                usrgrpid=usergroup.usrgrpid, userids=new_userids
            )

        return None

    def add_usergroup_users(self, usergroup_name: str, users: List[User]) -> None:
        """Add users to a user group. Ignores users already in the group."""
        self._update_usergroup_users(usergroup_name, users, remove=False)

    def remove_usergroup_users(self, usergroup_name: str, users: List[User]) -> None:
        """Remove users from a user group. Ignores users not in the group."""
        self._update_usergroup_users(usergroup_name, users, remove=True)

    def _update_usergroup_users(
        self, usergroup_name: str, users: List[User], remove: bool = False
    ) -> None:
        """Add/remove users from user group.

        Takes in the name of a user group instead of a `UserGroup` object
        to ensure the user group is fetched with `select_users=True`.
        """
        usergroup = self.get_usergroup(usergroup_name, select_users=True)

        params = {"usrgrpid": usergroup.usrgrpid}  # type: ParamsType

        # Add new IDs to existing and remove duplicates
        current_userids = [user.userid for user in usergroup.users]
        ids_update = [user.userid for user in users if user.userid]
        if remove:
            new_userids = list(set(current_userids) - set(ids_update))
        else:
            new_userids = list(set(current_userids + ids_update))

        if self.version.release >= (6, 0, 0):
            params["users"] = {"userid": uid for uid in new_userids}
        else:
            params["userids"] = new_userids  # type: ignore # fix annotations
        self.usergroup.update(usrgrpid=usergroup.usrgrpid, userids=new_userids)

    def update_usergroup_rights(
        self,
        usergroup_name: str,
        groups: Union[List[HostGroup], List[TemplateGroup]],
        permission: UsergroupPermission,
        hostgroup: bool,
    ) -> None:
        """Update usergroup rights for host or template groups."""
        usergroup = self.get_usergroup(usergroup_name, select_rights=True)

        params = {"usrgrpid": usergroup.usrgrpid}  # type: ParamsType

        if hostgroup:
            if self.version.release >= (6, 2, 0):
                hg_rights = usergroup.hostgroup_rights
            else:
                hg_rights = usergroup.rights
            new_rights = self._get_updated_rights(hg_rights, permission, groups)
            params[compat.usergroup_hostgroup_rights(self.version)] = new_rights  # type: ignore
        else:
            if self.version.release >= (6, 2, 0):
                tg_rights = usergroup.templategroup_rights
            else:
                tg_rights = usergroup.rights
            new_rights = self._get_updated_rights(tg_rights, permission, groups)
            params[compat.usergroup_templategroup_rights(self.version)] = new_rights  # type: ignore

    def _get_updated_rights(
        self,
        rights: List[ZabbixRight],
        permission: UsergroupPermission,
        groups: Union[List[HostGroup], List[TemplateGroup]],
    ) -> List[ZabbixRight]:
        new_rights = []  # List[ZabbixRight] # list of new rights to add
        rights = list(rights)  # copy rights (don't modify original)
        for group in groups:
            for right in rights:
                if right["id"] == group.groupid:
                    right["permission"] = permission.as_api_value()
                    break
            else:
                new_rights.append(
                    ZabbixRight(id=group.groupid, permission=permission.as_api_value())
                )
        rights.extend(new_rights)
        return rights

    def get_proxy(self, name: str, select_hosts: bool = False) -> Proxy:
        """Fetches a single proxy matching the given name."""
        proxies = self.get_proxies(name=name, select_hosts=select_hosts)
        if not proxies:
            raise ZabbixNotFoundError(f"Proxy {name!r} not found")
        return proxies[0]

    def get_proxies(
        self, name: Optional[str] = None, select_hosts: bool = False, **kwargs
    ) -> List[Proxy]:
        """Fetches all proxies."""
        params = {"output": "extend"}  # type: ParamsType
        if name:
            params.setdefault("search", {})[compat.proxy_name(self.version)] = name  # type: ignore
        if select_hosts:
            params["selectHosts"] = "extend"

        params.update(**kwargs)
        try:
            res = self.proxy.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPIException(f"Unknown error when fetching proxies: {e}")
        else:
            return [Proxy(**proxy) for proxy in res]

    def get_random_proxy(self, pattern: Optional[str] = None) -> Proxy:
        """Fetches a random proxy, optionally matching a regex pattern."""
        proxies = self.get_proxies()
        if not proxies:
            raise ZabbixNotFoundError("No proxies found")
        if pattern:
            try:
                re_pattern = re.compile(pattern)
            except re.error:
                raise ZabbixAPIException(f"Invalid proxy regex pattern: {pattern!r}")
            proxies = [proxy for proxy in proxies if re_pattern.match(proxy.name)]
            if not proxies:
                raise ZabbixNotFoundError(f"No proxies matching pattern {pattern!r}")
        return random.choice(proxies)

    def get_macro(
        self,
        host: Optional[Host] = None,
        macro_name: Optional[str] = None,
        search: bool = False,
        select_hosts: bool = False,
        select_templates: bool = False,
        sort_field: Optional[str] = "macro",
        sort_order: Optional[SortOrder] = None,
    ) -> Macro:
        """Fetches a macro given a host ID and macro name."""
        macros = self.get_macros(
            macro_name=macro_name,
            host=host,
            search=search,
            select_hosts=select_hosts,
            select_templates=select_templates,
            sort_field=sort_field,
            sort_order=sort_order,
        )
        if not macros:
            raise ZabbixNotFoundError("Macro not found")
        return macros[0]

    def get_hosts_with_macro(self, macro: str) -> List[Host]:
        """Fetches a macro given a host ID and macro name."""
        macros = self.get_macros(macro_name=macro)
        if not macros:
            raise ZabbixNotFoundError(f"Macro {macro!r} not found.")
        return macros[0].hosts

    def get_macros(
        self,
        macro_name: Optional[str] = None,
        host: Optional[Host] = None,
        search: bool = False,
        select_hosts: bool = False,
        select_templates: bool = False,
        sort_field: Optional[str] = "macro",
        sort_order: Optional[SortOrder] = None,
    ) -> List[Macro]:
        params = {"output": "extend"}  # type: ParamsType

        if host:
            params.setdefault("search", {})["hostids"] = host.hostid  # type: ignore

        if macro_name:
            params.setdefault("search", {})["macro"] = macro_name  # type: ignore

        # Enable wildcard searching if we have one or more search terms
        if params.get("search"):
            params["searchWildcardsEnabled"] = True

        if select_hosts:
            params["selectHosts"] = "extend"

        if select_templates:
            params["selectTemplates"] = "extend"

        if sort_field:
            params["sortfield"] = sort_field
        if sort_order:
            params["sortorder"] = sort_order
        try:
            result = self.usermacro.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPIException("Failed to retrieve macros") from e
        return [Macro(**macro) for macro in result]

    def get_global_macro(
        self,
        macro_name: Optional[str] = None,
        search: bool = False,
        sort_field: Optional[str] = "macro",
        sort_order: Optional[SortOrder] = None,
    ) -> Macro:
        """Fetches a global macro given a macro name."""
        macros = self.get_macros(
            macro_name=macro_name,
            search=search,
            sort_field=sort_field,
            sort_order=sort_order,
        )
        if not macros:
            raise ZabbixNotFoundError("Global macro not found")
        return macros[0]

    def get_global_macros(
        self,
        macro_name: Optional[str] = None,
        search: bool = False,
        sort_field: Optional[str] = "macro",
        sort_order: Optional[SortOrder] = None,
    ) -> List[GlobalMacro]:
        params = {"output": "extend", "globalmacro": True}  # type: ParamsType

        if macro_name:
            params.setdefault("search", {})["macro"] = macro_name  # type: ignore

        # Enable wildcard searching if we have one or more search terms
        if params.get("search"):
            params["searchWildcardsEnabled"] = True

        if sort_field:
            params["sortfield"] = sort_field
        if sort_order:
            params["sortorder"] = sort_order
        try:
            result = self.usermacro.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPIException("Failed to retrieve global macros") from e

        return [GlobalMacro(**macro) for macro in result]

    def create_macro(self, host: Host, macro: str, value: str) -> str:
        """Creates a macro given a host ID, macro name and value."""
        try:
            resp = self.usermacro.create(hostid=host.hostid, macro=macro, value=value)
        except ZabbixAPIException as e:
            raise ZabbixAPIException(
                f"Failed to create macro {macro!r} for host {host}"
            ) from e
        if not resp or not resp.get("hostmacroids"):
            raise ZabbixNotFoundError(
                f"No macro ID returned when creating macro {macro!r} for host {host}"
            )
        return resp["hostmacroids"][0]

    def create_global_macro(self, macro: str, value: str) -> str:
        """Creates a global macro given a macro name and value."""
        try:
            resp = self.usermacro.createglobal(macro=macro, value=value)
        except ZabbixAPIException as e:
            raise ZabbixAPIException(f"Failed to create global macro {macro!r}.") from e
        if not resp or not resp.get("globalmacroids"):
            raise ZabbixNotFoundError(
                f"No macro ID returned when creating global macro {macro!r}."
            )
        return resp["globalmacroids"][0]

    def update_macro(self, macroid: str, value: str) -> str:
        """Updates a macro given a macro ID and value."""
        try:
            resp = self.usermacro.update(hostmacroid=macroid, value=value)
        except ZabbixAPIException as e:
            raise ZabbixAPIException(f"Failed to update macro with ID {macroid}") from e
        if not resp or not resp.get("hostmacroids"):
            raise ZabbixNotFoundError(
                f"No macro ID returned when updating macro with ID {macroid}"
            )
        return resp["hostmacroids"][0]

    def update_host_inventory(self, host: Host, inventory: Dict[str, str]) -> str:
        """Updates a host inventory given a host ID and inventory."""
        try:
            resp = self.host.update(hostid=host.hostid, inventory=inventory)
        except ZabbixAPIException as e:
            raise ZabbixAPIException(
                f"Failed to update host inventory for host {host.host!r} (ID {host.hostid})"
            ) from e
        if not resp or not resp.get("hostids"):
            raise ZabbixNotFoundError(
                f"No host ID returned when updating inventory for host {host.host!r} (ID {host.hostid})"
            )
        return resp["hostids"][0]

    def update_host_proxy(self, host: Host, proxy: Proxy) -> str:
        """Updates a host proxy given a host ID and proxy."""
        params = {
            "hostid": host.hostid,
            compat.host_proxyid(self.version): proxy.proxyid,
        }
        try:
            resp = self.host.update(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPIException(
                f"Failed to update host proxy for host {host.host!r} (ID {host.hostid})"
            ) from e
        if not resp or not resp.get("hostids"):
            raise ZabbixNotFoundError(
                f"No host ID returned when updating proxy for host {host.host!r} (ID {host.hostid})"
            )
        return resp["hostids"][0]

    # NOTE: maybe passing in a list of hosts to this is overkill?
    # Just pass in a list of host IDs instead?
    def move_hosts_to_proxy(self, hosts: List[Host], proxy: Proxy) -> None:
        """Moves a list of hosts to a proxy."""
        params = {
            "hosts": [{"hostid": host.hostid} for host in hosts],
            compat.host_proxyid(self.version): proxy.proxyid,
        }  # type: ParamsType
        try:
            self.host.massupdate(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPIException(
                f"Failed to move hosts {[str(host) for host in hosts]} to proxy {proxy.name!r}"
            ) from e

    def get_template(
        self,
        template_name_or_id: str,
        select_hosts: bool = False,
        select_templates: bool = False,
        select_parent_templates: bool = False,
    ) -> Template:
        """Fetch a single template given its name or ID."""
        templates = self.get_templates(
            template_name_or_id,
            select_hosts=select_hosts,
            select_templates=select_templates,
            select_parent_templates=select_parent_templates,
        )
        if not templates:
            raise ZabbixNotFoundError(f"Template {template_name_or_id!r} not found")
        return templates[0]

    def get_templates(
        self,
        *template_names_or_ids: str,
        select_hosts: bool = False,
        select_templates: bool = False,
        select_parent_templates: bool = False,
    ) -> List[Template]:
        """Fetches one or more templates given a name or ID."""
        params = {"output": "extend"}  # type: ParamsType

        # HACK: don't filter if we have an asterisk (all templates)
        # TODO: refactor this along with other methods that take names or ids (or wildcards)
        if "*" in template_names_or_ids:
            template_names_or_ids = tuple()

        for name_or_id in template_names_or_ids:
            name_or_id = name_or_id.strip()
            is_id = name_or_id.isnumeric()
            if is_id:
                params.setdefault("templateids", []).append(name_or_id)  # type: ignore # bad annotation
            else:
                params.setdefault("filter", {}).setdefault("host", []).append(  # type: ignore # bad annotation
                    name_or_id
                )
                params.setdefault("searchWildcardsEnabled", True)
        if select_hosts:
            params["selectHosts"] = "extend"
        if select_templates:
            params["selectTemplates"] = "extend"
        if select_parent_templates:
            params["selectParentTemplates"] = "extend"
        try:
            templates = self.template.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPIException(
                f"Unknown error when fetching templates: {e}"
            ) from e
        return [Template(**template) for template in templates]

    def get_items(
        self,
        item_names_or_ids: Optional[List[str]] = None,  # NYI
        templates: Optional[List[Template]] = None,
        hosts: Optional[List[Template]] = None,  # NYI
        proxies: Optional[List[Proxy]] = None,  # NYI
        # TODO: implement interfaces
        # TODO: implement graphs
        # TODO: implement triggers
    ) -> List[Item]:
        params = {"output": "extend"}  # type: ParamsType
        if templates:
            params = {"templateids": [template.templateid for template in templates]}
        try:
            items = self.item.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPIException(f"Unknown error when fetching items: {e}") from e
        return [Item(**item) for item in items]

    def link_templates_to_hosts(
        self, templates: List[Template], hosts: List[Host]
    ) -> None:
        """Links one or more templates to one or more hosts.

        Args:
            templates (List[str]): A list of template names or IDs
            hosts (List[str]): A list of host names or IDs
        """
        if not templates:
            raise ZabbixAPIException("At least one template is required")
        if not hosts:
            raise ZabbixAPIException("At least one host is required")
        template_ids = [{"templateid": template.templateid} for template in templates]  # type: ModifyTemplateParams
        host_ids = [{"hostid": host.hostid} for host in hosts]  # type: ModifyHostParams
        try:
            self.host.massadd(templates=template_ids, hosts=host_ids)
        except ZabbixAPIException as e:
            raise ZabbixAPIException(f"Failed to link templates: {e}") from e

    def unlink_templates_from_hosts(
        self, templates: List[Template], hosts: List[Host]
    ) -> None:
        """Unlinks and clears one or more templates from one or more hosts.

        Args:
            templates (List[str]): A list of template names or IDs
            hosts (List[str]): A list of host names or IDs
        """
        if not templates:
            raise ZabbixAPIException("At least one template is required")
        if not hosts:
            raise ZabbixAPIException("At least one host is required")

        try:
            resp = self.host.massremove(
                hostids=[h.hostid for h in hosts],
                templateids_clear=[t.templateid for t in templates],
            )
        except ZabbixAPIException as e:
            raise ZabbixAPIException(
                f"Failed to unlink and clear templates: {e}"
            ) from e
        else:
            logger.debug("Unlink and clear templates response: %s", resp)

    # The reason we require a list of the actual objects instead of just names or
    # IDs, is that we need access to those objects in the command in order to render
    # the results properly, thus it's easier to just fetch them all there, and
    # then pass them in here. It does make the API a bit more cumbersome though.
    def link_templates_to_groups(
        self,
        templates: list[Template],
        groups: list[HostGroup] | List[TemplateGroup],
    ) -> None:
        """Links one or more templates to one or more host/template groups.

        Callers must ensure that the right type of group is passed in depending
        on the Zabbix version:
            * Host groups for Zabbix < 6.2
            * Template groups for Zabbix >= 6.2

        Args:
            templates (List[str]): A list of template names or IDs
            groups (list[HostGroup] | List[TemplateGroup]): A list of host/template groups
        """
        if not templates:
            raise ZabbixAPIException("At least one template is required")
        if not groups:
            raise ZabbixAPIException("At least one group is required")
        template_ids = [{"templateid": template.templateid} for template in templates]  # type: ModifyTemplateParams
        group_ids = [{"groupid": group.groupid} for group in groups]  # type: ModifyGroupParams
        try:
            self.template.massadd(templates=template_ids, groups=group_ids)
        except ZabbixAPIException as e:
            raise ZabbixAPIException(f"Failed to link templates: {e}") from e

    def unlink_templates_from_groups(
        self,
        templates: list[Template],
        groups: list[HostGroup] | List[TemplateGroup],
    ) -> None:
        """Unlinks one or more templates from one or more host/template groups.

        Callers must ensure that the right type of group is passed in depending
        on the Zabbix version:
            * Host groups for Zabbix < 6.2
            * Template groups for Zabbix >= 6.2

        Args:
            templates (List[str]): A list of template names or IDs
            groups (list[HostGroup] | List[TemplateGroup]): A list of host/template groups
        """
        if not templates:
            raise ZabbixAPIException("At least one template is required")
        if not groups:
            raise ZabbixAPIException("At least one group is required")
        template_ids = [template.templateid for template in templates]
        group_ids = [group.groupid for group in groups]
        try:
            self.template.massremove(
                templateids=template_ids,
                templateids_clear=template_ids,
                groupids=group_ids,
            )
        except ZabbixAPIException as e:
            raise ZabbixAPIException(
                f"Failed to unlink and clear templates: {e}"
            ) from e

    def create_user(
        self,
        username: str,
        password: str,
        first_name: str | None = None,
        last_name: str | None = None,
        role: UserRole | None = None,
        autologin: bool | None = None,
        autologout: str | int | None = None,
        usergroups: List[Usergroup] | None = None,
        media: List[UserMedia] | None = None,
    ) -> str:
        # TODO: handle invalid password
        # TODO: handle invalid type
        params = {compat.user_name(self.version): username, "passwd": password}  # type: ParamsType

        if first_name:
            params["name"] = first_name
        if last_name:
            params["surname"] = last_name

        if role:
            params[compat.role_id(self.version)] = role.as_api_value()

        if usergroups:
            params["usrgrps"] = [{"usrgrpid": ug.usrgrpid} for ug in usergroups]

        if autologin is not None:
            params["autologin"] = int(autologin)

        if autologout is not None:
            params["autologout"] = str(autologout)

        if media:
            params[compat.user_medias(self.version)] = [
                m.model_dump(mode="json") for m in media
            ]

        resp = self.user.create(**params)
        if not resp or not resp.get("userids"):
            raise ZabbixAPIException(f"Creating user {username!r} returned no user ID.")
        return resp["userids"][0]

    def get_role(self, name_or_id: str) -> Role:
        """Fetches a role given its ID or name."""
        roles = self.get_roles(name_or_id)
        if not roles:
            raise ZabbixNotFoundError(f"Role {name_or_id!r} not found")
        return roles[0]

    def get_roles(self, name_or_id: str | None = None) -> List[Role]:
        params = {"output": "extend"}  # type: ParamsType
        if name_or_id is not None:
            if name_or_id.isdigit():
                params["roleids"] = name_or_id
            else:
                params["filter"] = {"name": name_or_id}
        roles = self.role.get(**params)
        return [Role(**role) for role in roles]

    def get_user(self, username: str) -> User:
        """Fetches a user given its username."""
        users = self.get_users(username)
        if not users:
            raise ZabbixNotFoundError(f"User with username {username!r} not found")
        return users[0]

    def get_users(
        self,
        username: str | None = None,
        role: UserRole | None = None,
        search: bool = False,
    ) -> List[User]:
        params = {"output": "extend"}  # type: ParamsType
        filter_params = {}  # type: ParamsType
        if search:
            params["searchWildcardsEnabled"] = True
        if username is not None:
            if search:
                params["search"] = {compat.user_name(self.version): username}
            else:
                filter_params[compat.user_name(self.version)] = username
        if role:
            filter_params[compat.role_id(self.version)] = role.as_api_value()

        if filter_params:
            params["filter"] = filter_params

        users = self.user.get(**params)
        return [User(**user) for user in users]

    def delete_user(self, username: str) -> str:
        """Deletes a user given its username.

        Returns ID of deleted user."""
        user = self.get_user(username)
        try:
            resp = self.user.delete(user.userid)
        except ZabbixAPIException as e:
            raise ZabbixAPIException(f"Failed to delete user {username!r}") from e
        if not resp or not resp.get("userids"):
            raise ZabbixNotFoundError(
                f"No user ID returned when deleting user {username!r}"
            )
        return resp["userids"][0]

    def get_mediatype(self, name: str) -> MediaType:
        mts = self.get_mediatypes(name=name)
        if not mts:
            raise ZabbixNotFoundError(f"Media type {name!r} not found")
        return mts[0]

    def get_mediatypes(
        self, name: str | None = None, search: bool = False
    ) -> List[MediaType]:
        params = {"output": "extend"}  # type: ParamsType
        filter_params = {}  # type: ParamsType
        if search:
            params["searchWildcardsEnabled"] = True
        if name is not None:
            param = compat.mediatype_name(self.version)
            if search:
                params["search"] = {param: name}
            else:
                filter_params[param] = name
        if filter_params:
            params["filter"] = filter_params
        resp = self.mediatype.get(**params)
        return [MediaType(**mt) for mt in resp]

    ## Maintenance
    def get_maintenances(
        self,
        maintenance_ids: Optional[List[str]] = None,
        hostgroups: Optional[List[HostGroup]] = None,
        hosts: Optional[List[Host]] = None,
    ) -> List[Maintenance]:
        params = {
            "output": "extend",
            "selectHosts": "extend",
            compat.param_host_get_groups(self.version): "extend",
        }  # type: ParamsType
        if maintenance_ids:
            params["maintenanceids"] = maintenance_ids
        if hostgroups:
            params["groupids"] = [hg.groupid for hg in hostgroups]
        if hosts:
            params["hostids"] = [h.hostid for h in hosts]
        resp = self.maintenance.get(**params)
        return [Maintenance(**mt) for mt in resp]

    # def _construct_params(
    #     self,
    #     hostname_or_id: Optional[str] = None,
    #     macro_name: Optional[str] = None,
    #     search: bool = False,
    #     sort_field: Optional[str] = None,
    #     sort_order: Optional[SortOrder] = None,
    #     select_groups: bool = False,
    #     select_templates: bool = False,
    #     select_inventory: bool = False,
    #     select_macros: bool = False,
    #     **filter_kwargs,
    # ) -> ParamsType:
    #     pass

    def __getattr__(self, attr: str):
        """Dynamically create an object class (ie: host)"""
        return ZabbixAPIObjectClass(attr, self)


class ZabbixAPIObjectClass:
    def __init__(self, name: str, parent: ZabbixAPI):
        self.name = name
        self.parent = parent

    def __getattr__(self, attr: str) -> Any:
        """Dynamically create a method (ie: get)"""

        def fn(*args, **kwargs):
            if args and kwargs:
                raise TypeError("Found both args and kwargs")

            return self.parent.do_request(f"{self.name}.{attr}", args or kwargs)[
                "result"
            ]

        return fn

    def get(self, *args, **kwargs):
        """Provides per-endpoint overrides for the 'get' method"""
        if self.name == "proxy":
            # The proxy.get method changed from "host" to "name" in Zabbix 7.0
            # https://www.zabbix.com/documentation/6.0/en/manual/api/reference/proxy/get
            # https://www.zabbix.com/documentation/7.0/en/manual/api/reference/proxy/get
            output_kwargs = kwargs.get("output", None)
            params = ["name", "host"]
            if isinstance(output_kwargs, list) and any(
                p in output_kwargs for p in params
            ):
                for param in params:
                    try:
                        output_kwargs.remove(param)
                    except ValueError:
                        pass
                output_kwargs.append(compat.proxy_name(self.parent.version))
                kwargs["output"] = output_kwargs
        return self.__getattr__("get")(*args, **kwargs)
