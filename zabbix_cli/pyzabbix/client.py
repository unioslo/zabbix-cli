#
# The code in this file is based on the pyzabbix library:
# https://github.com/lukecyca/pyzabbix
#
# Numerous changes have been made to the original code to make it more
# type-safe and to better fit the use-cases of the zabbix-cli project.
#
# We have modified the login method to be able to send an auth-token so
# we do not have to login again as long as the auth-token used is still
# active.
#
# We have also modified the output when an error happens to not show
# the username + password information.
#
from __future__ import annotations

import logging
from collections.abc import MutableMapping
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Literal
from typing import Optional
from typing import Union
from typing import cast

import httpx
from packaging.version import InvalidVersion
from packaging.version import Version
from pydantic import ValidationError

from zabbix_cli.__about__ import APP_NAME
from zabbix_cli.__about__ import __version__
from zabbix_cli.exceptions import ZabbixAPICallError
from zabbix_cli.exceptions import ZabbixAPIException
from zabbix_cli.exceptions import ZabbixAPILoginError
from zabbix_cli.exceptions import ZabbixAPILogoutError
from zabbix_cli.exceptions import ZabbixAPINotAuthorizedError
from zabbix_cli.exceptions import ZabbixAPIRequestError
from zabbix_cli.exceptions import ZabbixAPIResponseParsingError
from zabbix_cli.exceptions import ZabbixAPISessionExpired
from zabbix_cli.exceptions import ZabbixAPITokenExpiredError
from zabbix_cli.exceptions import ZabbixNotFoundError
from zabbix_cli.pyzabbix import compat
from zabbix_cli.pyzabbix.enums import ActiveInterface
from zabbix_cli.pyzabbix.enums import DataCollectionMode
from zabbix_cli.pyzabbix.enums import ExportFormat
from zabbix_cli.pyzabbix.enums import GUIAccess
from zabbix_cli.pyzabbix.enums import InventoryMode
from zabbix_cli.pyzabbix.enums import MaintenanceStatus
from zabbix_cli.pyzabbix.enums import MonitoredBy
from zabbix_cli.pyzabbix.enums import MonitoringStatus
from zabbix_cli.pyzabbix.enums import TriggerPriority
from zabbix_cli.pyzabbix.enums import UsergroupPermission
from zabbix_cli.pyzabbix.enums import UserRole
from zabbix_cli.pyzabbix.types import CreateHostInterfaceDetails
from zabbix_cli.pyzabbix.types import Event
from zabbix_cli.pyzabbix.types import GlobalMacro
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import HostGroup
from zabbix_cli.pyzabbix.types import HostInterface
from zabbix_cli.pyzabbix.types import Image
from zabbix_cli.pyzabbix.types import ImportRules
from zabbix_cli.pyzabbix.types import InterfaceType
from zabbix_cli.pyzabbix.types import Item
from zabbix_cli.pyzabbix.types import Json
from zabbix_cli.pyzabbix.types import Macro
from zabbix_cli.pyzabbix.types import Maintenance
from zabbix_cli.pyzabbix.types import Map
from zabbix_cli.pyzabbix.types import MediaType
from zabbix_cli.pyzabbix.types import ParamsType
from zabbix_cli.pyzabbix.types import Proxy
from zabbix_cli.pyzabbix.types import ProxyGroup
from zabbix_cli.pyzabbix.types import Role
from zabbix_cli.pyzabbix.types import Template
from zabbix_cli.pyzabbix.types import TemplateGroup
from zabbix_cli.pyzabbix.types import Trigger
from zabbix_cli.pyzabbix.types import UpdateHostInterfaceDetails
from zabbix_cli.pyzabbix.types import User
from zabbix_cli.pyzabbix.types import Usergroup
from zabbix_cli.pyzabbix.types import UserMedia
from zabbix_cli.pyzabbix.types import ZabbixAPIResponse
from zabbix_cli.pyzabbix.types import ZabbixRight
from zabbix_cli.utils.utils import get_acknowledge_action_value

if TYPE_CHECKING:
    from httpx._types import TimeoutTypes
    from typing_extensions import TypedDict

    from zabbix_cli.config.model import Config
    from zabbix_cli.pyzabbix.types import ModifyGroupParams
    from zabbix_cli.pyzabbix.types import ModifyHostParams
    from zabbix_cli.pyzabbix.types import ModifyTemplateParams
    from zabbix_cli.pyzabbix.types import SortOrder

    class HTTPXClientKwargs(TypedDict, total=False):
        timeout: TimeoutTypes


logger = logging.getLogger(__name__)

RPC_ENDPOINT = "/api_jsonrpc.php"


def strip_none(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively strip None values from a dictionary."""
    new: dict[str, Any] = {}
    for key, value in data.items():
        if value is not None:
            if isinstance(value, dict):
                v = strip_none(value)  # pyright: ignore[reportUnknownArgumentType]
                if v:
                    new[key] = v
            elif isinstance(value, list):
                new[key] = [i for i in value if i is not None]  # pyright: ignore[reportUnknownVariableType]
            else:
                new[key] = value
    return new


def append_param(
    data: MutableMapping[str, Any], key: str, value: Json
) -> MutableMapping[str, Any]:
    """Append a JSON-serializable value to a list in a dictionary.

    If the key does not exist in the dictionary, it is created with a list
    containing the value. If the key already exists and the value is not a list,
    the value is converted to a list and appended to the existing list.
    """
    if key in data:
        if not isinstance(data[key], list):
            logger.debug("Converting param %s to list", key, stacklevel=2)
            data[key] = [data[key]]
    else:
        data[key] = []
    data[key].append(value)
    return data


def add_param(
    data: MutableMapping[str, Any], key: str, subkey: str, value: Json
) -> MutableMapping[str, Any]:
    """Add a JSON-serializable value to a nested dict in dict."""
    if key in data:
        if not isinstance(data[key], dict):
            logger.debug("Converting param %s to dict", key, stacklevel=2)
            data[key] = {key: data[key]}
    else:
        data[key] = {}
    data[key][subkey] = value
    return data


def parse_name_or_id_arg(
    params: ParamsType,
    names_or_ids: tuple[str, ...],
    name_param: str,
    id_param: str,
    search: bool = True,
    search_union: bool = True,
    search_params: Optional[ParamsType] = None,
) -> ParamsType:
    """Parse a tuple of names or IDs and add them to an existing params dict."""
    search_params = search_params or {}

    # If we have a wildcard, we can omit names or IDs entirely
    if "*" in names_or_ids:
        names_or_ids = tuple()

    if names_or_ids:
        for name_or_id in names_or_ids:
            name_or_id = name_or_id.strip()
            is_id = name_or_id.isnumeric()

            # ID searching uses a different top-level parameter,
            # while names require searching or filtering
            if is_id:
                append_param(params, id_param, name_or_id)
            else:
                # Names can be used as a filter or search parameter
                if search:
                    append_param(search_params, name_param, name_or_id)
                else:
                    params["filter"] = {name_param: name_or_id}
    if search_params:
        params["search"] = search_params
        params["searchWildcardsEnabled"] = True
        params["searchByAny"] = search_union
    return params


def add_common_params(
    params: ParamsType,
    sort_field: Optional[Union[str, list[str]]] = None,
    sort_order: Optional[SortOrder] = None,
    limit: Optional[int] = None,
) -> ParamsType:
    """Add common GET parameters to a params dict.

    Based on https://www.zabbix.com/documentation/7.0/en/manual/api/reference_commentary#common-get-method-parameters

    NOTE
    ----
    `parse_name_or_id_arg` handles the `search*` parameters
    """
    if sort_field:
        params["sortfield"] = sort_field
    if sort_order:
        params["sortorder"] = sort_order
    if limit:
        params["limit"] = limit
    return params


def get_returned_list(returned: Any, key: str, endpoint: str) -> list[str]:
    """Retrieve a list from a given key in a Zabbix API response."""
    if not isinstance(returned, dict):
        raise ZabbixAPIException(
            f"Expected endpoint {endpoint!r} to return a dict, got {type(returned)}"
        )
    response_list = returned.get(key, [])  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
    if not isinstance(response_list, list):
        raise ZabbixAPIException(
            f"{endpoint!r} response did not contain a list for key {key!r}"
        )
    return cast(list[str], response_list)


class ZabbixAPI:
    def __init__(
        self,
        server: str = "http://localhost/zabbix",
        timeout: Optional[int] = None,
        verify_ssl: bool = True,
    ) -> None:
        """Parameters:
        server: Base URI for zabbix web interface (omitting /api_jsonrpc.php)
        session: optional pre-configured requests.Session instance
        timeout: optional connect and read timeout in seconds.
        """
        self.timeout = timeout if timeout else None
        self.session = self._get_client(verify_ssl=verify_ssl, timeout=timeout)

        self.auth = ""
        self.use_api_token = False
        self.id = 0

        self.url = self._get_url(server)
        logger.info("JSON-RPC Server Endpoint: %s", self.url)

    def _get_url(self, server: str) -> str:
        """Format a URL for the Zabbix API."""
        server, _, _ = server.partition(RPC_ENDPOINT)
        return f"{server.rstrip('/')}{RPC_ENDPOINT}"

    def set_url(self, server: str) -> str:
        """Set a new URL for the client."""
        self.url = self._get_url(server)
        return self.url

    @classmethod
    def from_config(cls, config: Config) -> ZabbixAPI:
        """Create a ZabbixAPI instance from a Config object and logs in."""
        client = cls(
            server=config.api.url,
            timeout=config.api.timeout,
            verify_ssl=config.api.verify_ssl,
        )
        return client

    def _get_client(
        self, verify_ssl: bool, timeout: Union[float, int, None] = None
    ) -> httpx.Client:
        kwargs: HTTPXClientKwargs = {}
        if timeout is not None:
            kwargs["timeout"] = timeout
        client = httpx.Client(
            verify=verify_ssl,
            # Default headers for all requests
            headers={
                "Content-Type": "application/json-rpc",
                "User-Agent": f"python/{APP_NAME}/{__version__}",
                "Cache-Control": "no-cache",
            },
            **kwargs,
        )
        return client

    def disable_ssl_verification(self):
        """Disables SSL verification for HTTP requests.

        Replaces the current session with a new session.
        """
        self.session = self._get_client(verify_ssl=False, timeout=self.timeout)

    def login(
        self,
        user: Optional[str] = None,
        password: Optional[str] = None,
        auth_token: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Log in to the Zabbix API using a username/password, API token or session ID.

        At least one authentication method must be provided.

        Args:
            user (str, optional): Username. Defaults to None.
            password (str, optional): Password. Defaults to None.
            auth_token (str, optional): API token. Defaults to None.
            session_id (str, optional): Session ID. Defaults to None.


        """
        # By checking the version, we also check if the API is reachable
        try:
            version = self.version  # property
        except ZabbixAPIRequestError as e:
            raise ZabbixAPIException(
                f"Failed to connect to Zabbix API at {self.url}"
            ) from e

        logger.debug("Logging in to Zabbix %s API at %s", version, self.url)

        # Inform applicaiton of whether we're using an API token or not,
        # so we can handle user.logout, user.checkauthentication, etc. correctly.
        use_auth_token = False

        if auth_token:
            # TODO: revert this if token is invalid
            logger.debug("Using API token for authentication")
            auth = auth_token
            use_auth_token = True
        elif session_id:
            logger.debug("Using session ID for authentication")
            auth = session_id
        elif user and password:
            logger.debug("Using username and password for authentication")

            params: ParamsType = {
                compat.login_user_name(version): user,
                "password": password,
            }
            try:
                auth = self.user.login(**params)
            except ZabbixAPIRequestError as e:
                raise ZabbixAPILoginError("Failed to log in to Zabbix") from e
            except Exception as e:
                raise ZabbixAPILoginError(
                    "Unknown error when trying to log in to Zabbix"
                ) from e
            else:
                auth = str(auth) if auth else ""
        else:
            raise ZabbixAPILoginError(
                "No authentication method provided. Must provide user/password, API token or session ID"
            )

        self.auth = auth
        self.use_api_token = use_auth_token

        # Check if the auth token we obtained or specified is valid
        # XXX: should revert auth token to what it was before this method
        # was called if token is invalid.
        self.ensure_authenticated()
        return self.auth

    def ensure_authenticated(self) -> None:
        """Test an authenticated Zabbix API session."""
        try:
            self.host.get(output=["hostid"], limit=1)
        except Exception as e:
            # Leaking the token should be OK - it's invalid
            raise ZabbixAPICallError(f"Invalid session token: {self.auth}") from e

    def logout(self) -> None:
        if not self.auth:
            logger.debug("No auth token to log out with")
            return
        elif self.use_api_token:
            logger.debug("Logging out with API token")
            self.auth = ""
            return

        # Technically this API endpoint might return `false`, which
        # would signify that that the logout somehow failed, but it's
        # not documented in the API docs - only the inverse case `true` is.
        try:
            self.user.logout()
        except ZabbixAPITokenExpiredError:
            logger.debug(
                "Attempted to log out of Zabbix API with expired token: %s", self.auth
            )
        except ZabbixAPIRequestError as e:
            raise ZabbixAPILogoutError("Failed to log out of Zabbix") from e
        else:
            self.auth = ""

    def confimport(self, format: ExportFormat, source: str, rules: ImportRules) -> Any:
        """Alias for configuration.import because it clashes with
        Python's import reserved keyword
        """
        return self.do_request(
            method="configuration.import",
            params={
                "format": format,
                "source": source,
                "rules": rules.model_dump_api(),
            },
        ).result

    @cached_property
    def version(self) -> Version:
        """`api_version()` exposed as a cached property."""
        return self.api_version()

    def api_version(self) -> Version:
        """Get the version of the Zabbix API as a Version object."""
        try:
            return Version(self.apiinfo.version())
        except ZabbixAPIException as e:
            raise ZabbixAPIException("Failed to get Zabbix version from API") from e
        except InvalidVersion as e:
            raise ZabbixAPIException("Got invalid Zabbix version from API") from e

    def do_request(
        self, method: str, params: Optional[ParamsType] = None
    ) -> ZabbixAPIResponse:
        params = params or {}

        request_json = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self.id,
        }
        request_headers: dict[str, str] = {}

        # We don't have to pass the auth token if asking for the apiinfo.version
        # TODO: ensure we have auth token if method requires it
        if self.auth and method.lower() not in [
            "apiinfo.version",
            "user.login",
            "user.checkauthentication",
        ]:
            if self.version.release >= (6, 4, 0):
                request_headers["Authorization"] = f"Bearer {self.auth}"
            else:
                request_json["auth"] = self.auth

        logger.debug("Sending %s to %s", method, self.url)

        try:
            response = self.session.post(
                self.url, json=request_json, headers=request_headers
            )
        except Exception as e:
            raise ZabbixAPIRequestError(
                f"Failed to send request to {self.url} ({method}) with params {params}",
                params=params,
            ) from e

        logger.debug("Response Code: %s", str(response.status_code))

        # NOTE: Getting a 412 response code means the headers are not in the
        # list of allowed headers.
        # OR we didnt pass an auth token
        response.raise_for_status()

        if not len(response.text):
            raise ZabbixAPIRequestError("Received empty response", response=response)

        self.id += 1

        try:
            resp = ZabbixAPIResponse.model_validate_json(response.text)
        except ValidationError as e:
            raise ZabbixAPIResponseParsingError(
                "Zabbix API returned malformed response", response=response
            ) from e
        except ValueError as e:
            raise ZabbixAPIResponseParsingError(
                "Zabbix API returned invalid JSON", response=response
            ) from e

        self._check_response_errors(resp, response, params)

        return resp

    def _check_response_errors(
        self,
        resp: ZabbixAPIResponse,
        response: httpx.Response,
        params: ParamsType,
    ) -> None:
        # Nothing to handlde
        if not resp.error:
            return

        # some errors don't contain 'data': workaround for ZBX-9340
        if not resp.error.data:
            resp.error.data = "No data"

        msg = f"Error: {resp.error.message} {resp.error.data}"

        to_replace = [
            (self.auth, "<token>"),
            (params.get("token", ""), "<token>"),
            (params.get("password", ""), "<password>"),
        ]
        for replace in to_replace:
            if replace[0]:
                msg = msg.replace(str(replace), replace[1])

        # TODO: refactor this exc type narrowing to some sort of predicate/dict lookup
        msgc = msg.casefold()
        if "api token expired" in msgc:
            cls = ZabbixAPITokenExpiredError
            logger.debug(
                "API token '%s' has expired.",
                f"{self.auth[:8]}...",  # Redact most of the token
            )
        elif "re-login" in msgc:
            cls = ZabbixAPISessionExpired
        elif "not authorized" in msgc:
            cls = ZabbixAPINotAuthorizedError
        else:
            cls = ZabbixAPIRequestError
        raise cls(
            msg,
            api_response=resp,
            response=response,
        )

    def get_hostgroup(
        self,
        name_or_id: str,
        search: bool = False,
        select_hosts: bool = False,
        select_templates: bool = False,
        sort_order: Optional[SortOrder] = None,
        sort_field: Optional[str] = None,
    ) -> HostGroup:
        """Fetches a host group given its name or ID.

        Name or ID argument is interpeted as an ID if the argument is numeric.

        Uses filtering by default, but can be switched to searching by setting
        the `search` argument to True.

        Args:
            name_or_id (str): Name or ID of the host group.
            search (bool, optional): Search for host groups using the given pattern instead of filtering. Defaults to False.
            select_hosts (bool, optional): Fetch hosts in host groups. Defaults to False.
            select_templates (bool, optional): <6.2 ONLY: Fetch templates in host groups. Defaults to False.

        Raises:
            ZabbixNotFoundError: Group is not found.

        Returns:
            HostGroup: The host group object.
        """
        hostgroups = self.get_hostgroups(
            name_or_id,
            search=search,
            sort_order=sort_order,
            sort_field=sort_field,
            select_hosts=select_hosts,
            select_templates=select_templates,
        )
        if not hostgroups:
            raise ZabbixNotFoundError(f"Host group {name_or_id!r} not found")
        return hostgroups[0]

    def get_hostgroups(
        self,
        *names_or_ids: str,
        search: bool = False,
        search_union: bool = True,
        select_hosts: bool = False,
        select_templates: bool = False,
        sort_order: Optional[SortOrder] = None,
        sort_field: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[HostGroup]:
        """Fetches a list of host groups given its name or ID.

        Name or ID argument is interpeted as an ID if the argument is numeric.

        Uses filtering by default, but can be switched to searching by setting
        the `search` argument to True.

        Args:
            name_or_id (str): Name or ID of the host group.
            search (bool, optional): Search for host groups using the given pattern instead of filtering. Defaults to False.
            search_union (bool, optional): Union searching. Has no effect if `search` is False. Defaults to True.
            select_hosts (bool, optional): Fetch hosts in host groups. Defaults to False.
            select_templates (bool, optional): <6.2 ONLY: Fetch templates in host groups. Defaults to False.
            sort_order (SortOrder, optional): Sort order. Defaults to None.
            sort_field (str, optional): Sort field. Defaults to None.

        Raises:
            ZabbixNotFoundError: Group is not found.

        Returns:
            List[HostGroup]: List of host groups.
        """
        params: ParamsType = {"output": "extend"}
        params = parse_name_or_id_arg(
            params,
            names_or_ids,
            name_param="name",
            id_param="groupids",
            search=search,
            search_union=search_union,
        )

        if select_hosts:
            params["selectHosts"] = "extend"
        if self.version.release < (6, 2, 0) and select_templates:
            params["selectTemplates"] = "extend"
        add_common_params(
            params, sort_field=sort_field, sort_order=sort_order, limit=limit
        )

        resp: list[Any] = self.hostgroup.get(**params) or []
        return [HostGroup(**hostgroup) for hostgroup in resp]

    def create_hostgroup(self, name: str) -> str:
        """Creates a host group with the given name."""
        try:
            resp = self.hostgroup.create(name=name)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(f"Failed to create host group {name!r}") from e
        if not resp or not resp.get("groupids"):
            raise ZabbixAPICallError(
                "Host group creation returned no data. Unable to determine if group was created."
            )
        return str(resp["groupids"][0])

    def delete_hostgroup(self, hostgroup_id: str) -> None:
        """Deletes a host group given its ID."""
        try:
            self.hostgroup.delete(hostgroup_id)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to delete host group(s) with ID {hostgroup_id}"
            ) from e

    def add_hosts_to_hostgroups(
        self, hosts: list[Host], hostgroups: list[HostGroup]
    ) -> None:
        """Adds hosts to one or more host groups."""
        try:
            self.hostgroup.massadd(
                groups=[{"groupid": hg.groupid} for hg in hostgroups],
                hosts=[{"hostid": host.hostid} for host in hosts],
            )
        except ZabbixAPIException as e:
            hgs = ", ".join(hg.name for hg in hostgroups)
            raise ZabbixAPICallError(f"Failed to add hosts to {hgs}") from e

    def remove_hosts_from_hostgroups(
        self, hosts: list[Host], hostgroups: list[HostGroup]
    ) -> None:
        """Removes the given hosts from one or more host groups."""
        try:
            self.hostgroup.massremove(
                groupids=[hg.groupid for hg in hostgroups],
                hostids=[host.hostid for host in hosts],
            )
        except ZabbixAPIException as e:
            hgs = ", ".join(hg.name for hg in hostgroups)
            raise ZabbixAPICallError(f"Failed to remove hosts from {hgs}") from e

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
        search_union: bool = True,
        select_templates: bool = False,
        sort_field: Optional[str] = None,
        sort_order: Optional[SortOrder] = None,
    ) -> list[TemplateGroup]:
        """Fetches a list of template groups, optionally filtered by name(s).

        Name or ID argument is interpeted as an ID if the argument is numeric.

        Uses filtering by default, but can be switched to searching by setting
        the `search` argument to True.

        Args:
            name_or_id (str): Name or ID of the template group.
            search (bool, optional): Search for template groups using the given pattern instead of filtering. Defaults to False.
            search_union (bool, optional): Union searching. Has no effect if `search` is False. Defaults to True.
            select_templates (bool, optional): Fetch templates in each group. Defaults to False.
            sort_order (SortOrder, optional): Sort order. Defaults to None.
            sort_field (str, optional): Sort field. Defaults to None.

        Raises:
            ZabbixNotFoundError: Group is not found.

        Returns:
            List[TemplateGroup]: List of template groups.
        """
        # FIXME: ensure we use searching correctly here
        # TODO: refactor this along with other methods that take names or ids (or wildcards)
        params: ParamsType = {"output": "extend"}
        params = parse_name_or_id_arg(
            params,
            names_or_ids,
            name_param="name",
            id_param="groupids",
            search=search,
            search_union=search_union,
        )

        if select_templates:
            params["selectTemplates"] = "extend"
        add_common_params(params, sort_field=sort_field, sort_order=sort_order)

        try:
            resp: list[Any] = self.templategroup.get(**params) or []
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to fetch template groups") from e
        return [TemplateGroup(**tgroup) for tgroup in resp]

    def create_templategroup(self, name: str) -> str:
        """Creates a template group with the given name."""
        try:
            resp = self.templategroup.create(name=name)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(f"Failed to create template group {name!r}") from e
        if not resp or not resp.get("groupids"):
            raise ZabbixAPICallError(
                "Template group creation returned no data. Unable to determine if group was created."
            )
        return str(resp["groupids"][0])

    def delete_templategroup(self, templategroup_id: str) -> None:
        """Deletes a template group given its ID."""
        try:
            self.templategroup.delete(templategroup_id)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to delete template group(s) with ID {templategroup_id}"
            ) from e

    def get_host(
        self,
        name_or_id: str,
        select_groups: bool = False,
        select_templates: bool = False,
        select_interfaces: bool = False,
        select_inventory: bool = False,
        select_macros: bool = False,
        proxy_group: Optional[ProxyGroup] = None,
        proxy: Optional[Proxy] = None,
        maintenance: Optional[MaintenanceStatus] = None,
        monitored: Optional[MonitoringStatus] = None,
        active_interface: Optional[ActiveInterface] = None,
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
            select_interfaces=select_interfaces,
            select_macros=select_macros,
            proxy=proxy,
            proxy_group=proxy_group,
            sort_field=sort_field,
            sort_order=sort_order,
            search=search,
            maintenance=maintenance,
            monitored=monitored,
            active_interface=active_interface,
            limit=1,
        )
        if not hosts:
            raise ZabbixNotFoundError(
                f"Host {name_or_id!r} not found. Check your search pattern and filters."
            )
        return hosts[0]

    def get_hosts(
        self,
        *names_or_ids: str,
        select_groups: bool = False,
        select_templates: bool = False,
        select_inventory: bool = False,
        select_macros: bool = False,
        select_interfaces: bool = False,
        proxy: Optional[Proxy] = None,
        proxy_group: Optional[ProxyGroup] = None,
        hostgroups: Optional[list[HostGroup]] = None,
        # These params take special API values we don't want to evaluate
        # inside this method, so we delegate it to the enums.
        maintenance: Optional[MaintenanceStatus] = None,
        monitored: Optional[MonitoringStatus] = None,
        active_interface: Optional[ActiveInterface] = None,
        sort_field: Optional[str] = None,
        sort_order: Optional[Literal["ASC", "DESC"]] = None,
        search: bool = True,  # we generally always want to search when multiple hosts are requested
        limit: Optional[int] = None,
    ) -> list[Host]:
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
            active_interface (Optional[ActiveInterface], optional): Filter by active interface s. Defaults to None.
            sort_field (Optional[str], optional): Sort hosts by the given field. Defaults to None.
            sort_order (Optional[Literal[ASC, DESC]], optional): Sort order. Defaults to None.
            search (Optional[bool], optional): Force positional arguments to be treated as a search pattern. Defaults to True.

        Raises:
            ZabbixAPIException: _description_

        Returns:
            List[Host]: _description_
        """
        params: ParamsType = {"output": "extend"}

        params = parse_name_or_id_arg(
            params,
            names_or_ids,
            name_param="host",
            id_param="hostids",
            search=search,
        )

        # Filters are applied with a logical AND (narrows down)
        filter_params: ParamsType = {}

        if maintenance is not None:
            filter_params["maintenance_status"] = maintenance.as_api_value()
        if monitored is not None:
            filter_params["status"] = monitored.as_api_value()
        if active_interface is not None:
            if self.version.release >= (6, 4, 0):
                params["active_available"] = active_interface.as_api_value()
            else:
                filter_params["active"] = active_interface.as_api_value()

        if filter_params:  # Only add filter if we actually have filter params
            params["filter"] = filter_params

        if hostgroups:
            params["groupids"] = [group.groupid for group in hostgroups]
        if proxy:
            params["proxyids"] = proxy.proxyid
        if proxy_group:
            params["proxy_groupids"] = proxy_group.proxy_groupid
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
        if select_interfaces:
            params["selectInterfaces"] = "extend"
        add_common_params(
            params, sort_field=sort_field, sort_order=sort_order, limit=limit
        )

        resp: list[Any] = self.host.get(**params) or []
        # TODO add result to cache
        return [Host(**r) for r in resp]

    def get_host_count(self, params: Optional[ParamsType] = None) -> int:
        """Fetches the total number of hosts in the Zabbix server."""
        return self.count("host", params=params)

    def count(self, object_type: str, params: Optional[ParamsType] = None) -> int:
        """Count the number of objects of a given type."""
        params = params or {}
        params["countOutput"] = True
        try:
            resp = getattr(self, object_type).get(**params)
            return int(resp)
        except (ZabbixAPIException, TypeError, ValueError) as e:
            raise ZabbixAPICallError(f"Failed to fetch {object_type} count") from e

    def create_host(
        self,
        host: str,
        groups: list[HostGroup],
        proxy: Optional[Proxy] = None,
        status: MonitoringStatus = MonitoringStatus.ON,
        interfaces: Optional[list[HostInterface]] = None,
        inventory_mode: InventoryMode = InventoryMode.AUTOMATIC,
        inventory: Optional[dict[str, Any]] = None,
        description: Optional[str] = None,
    ) -> str:
        params: ParamsType = {
            "host": host,
            "status": status.as_api_value(),
            "inventory_mode": inventory_mode.as_api_value(),
        }

        # dedup group IDs
        groupids = list({group.groupid for group in groups})
        params["groups"] = [{"groupid": groupid} for groupid in groupids]

        if proxy:
            params[compat.host_proxyid(self.version)] = proxy.proxyid
            if self.version.release >= (7, 0, 0):
                params["monitored_by"] = MonitoredBy.PROXY.as_api_value()

        if interfaces:
            params["interfaces"] = [iface.model_dump_api() for iface in interfaces]

        if inventory:
            params["inventory"] = inventory

        if description:
            params["description"] = description

        try:
            resp = self.host.create(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(f"Failed to create host {host!r}") from e
        if not resp or not resp.get("hostids"):
            raise ZabbixAPICallError(
                "Host creation returned no data. Unable to determine if host was created."
            )
        return str(resp["hostids"][0])

    def update_host(
        self,
        host: Host,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Updates basic information about a host."""
        params: ParamsType = {
            "hostid": host.hostid,
        }
        if name:
            params["host"] = name
        if description:
            params["description"] = description
        try:
            self.host.update(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(f"Failed to update host {host.host!r}") from e

    def delete_host(self, host_id: str) -> None:
        """Deletes a host."""
        try:
            self.host.delete(host_id)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to delete host with ID {host_id!r}"
            ) from e

    def host_exists(self, name_or_id: str) -> bool:
        """Checks if a host exists given its name or ID."""
        try:
            self.get_host(name_or_id)
        except ZabbixNotFoundError:
            return False
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Unknown error when fetching host {name_or_id}"
            ) from e
        else:
            return True

    def hostgroup_exists(self, hostgroup_name: str) -> bool:
        try:
            self.get_hostgroup(hostgroup_name)
        except ZabbixNotFoundError:
            return False
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to fetch host group {hostgroup_name}"
            ) from e
        else:
            return True

    def get_hostinterface(
        self,
        interfaceid: Optional[str] = None,
    ) -> HostInterface:
        """Fetches a host interface given its ID"""
        interfaces = self.get_hostinterfaces(interfaceids=interfaceid)
        if not interfaces:
            raise ZabbixNotFoundError(f"Host interface with ID {interfaceid} not found")
        return interfaces[0]

    def get_hostinterfaces(
        self,
        hostids: Union[str, list[str], None] = None,
        interfaceids: Union[str, list[str], None] = None,
        itemids: Union[str, list[str], None] = None,
        triggerids: Union[str, list[str], None] = None,
        # Can expand with the rest of the parameters if needed
    ) -> list[HostInterface]:
        """Fetches a list of host interfaces, optionally filtered by host ID,
        interface ID, item ID or trigger ID.
        """
        params: ParamsType = {"output": "extend"}
        if hostids:
            params["hostids"] = hostids
        if interfaceids:
            params["interfaceids"] = interfaceids
        if itemids:
            params["itemids"] = itemids
        if triggerids:
            params["triggerids"] = triggerids
        try:
            resp = self.hostinterface.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to fetch host interfaces") from e
        return [HostInterface(**iface) for iface in resp]

    def create_host_interface(
        self,
        host: Host,
        main: bool,
        type: InterfaceType,
        use_ip: bool,
        port: str,
        ip: Optional[str] = None,
        dns: Optional[str] = None,
        details: Optional[CreateHostInterfaceDetails] = None,
    ) -> str:
        if not ip and not dns:
            raise ZabbixAPIException("Either IP or DNS must be provided")
        if use_ip and not ip:
            raise ZabbixAPIException("IP must be provided if using IP connection mode.")
        if not use_ip and not dns:
            raise ZabbixAPIException(
                "DNS must be provided if using DNS connection mode."
            )
        params: ParamsType = {
            "hostid": host.hostid,
            "main": int(main),
            "type": type.as_api_value(),
            "useip": int(use_ip),
            "port": str(port),
            "ip": ip or "",
            "dns": dns or "",
        }
        if type == InterfaceType.SNMP:
            if not details:
                raise ZabbixAPIException(
                    "SNMP details must be provided for SNMP interfaces."
                )
            params["details"] = details.model_dump_api()

        try:
            resp = self.hostinterface.create(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to create host interface for host {host.host!r}"
            ) from e
        if not resp or not resp.get("interfaceids"):
            raise ZabbixAPICallError(
                "Host interface creation returned no data. Unable to determine if interface was created."
            )
        return str(resp["interfaceids"][0])

    def update_host_interface(
        self,
        interface: HostInterface,
        main: Optional[bool] = None,
        type: Optional[InterfaceType] = None,
        use_ip: Optional[bool] = None,
        port: Optional[str] = None,
        ip: Optional[str] = None,
        dns: Optional[str] = None,
        details: Optional[UpdateHostInterfaceDetails] = None,
    ) -> None:
        params: ParamsType = {"interfaceid": interface.interfaceid}
        if main is not None:
            params["main"] = int(main)
        if type is not None:
            params["type"] = type.as_api_value()
        if use_ip is not None:
            params["useip"] = int(use_ip)
        if port is not None:
            params["port"] = str(port)
        if ip is not None:
            params["ip"] = ip
        if dns is not None:
            params["dns"] = dns
        if details is not None:
            params["details"] = details.model_dump_api()
        try:
            self.hostinterface.update(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to update host interface with ID {interface.interfaceid}"
            ) from e

    def delete_host_interface(self, interface_id: str) -> None:
        """Deletes a host interface."""
        try:
            self.hostinterface.delete(interface_id)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to delete host interface with ID {interface_id}"
            ) from e

    def get_usergroup(
        self,
        name_or_id: str,
        select_users: bool = False,
        select_rights: bool = False,
        search: bool = True,
    ) -> Usergroup:
        """Fetches a user group by name. Always fetches the full contents of the group."""
        groups = self.get_usergroups(
            name_or_id,
            select_users=select_users,
            select_rights=select_rights,
            search=search,
        )
        if not groups:
            raise ZabbixNotFoundError(f"User group {name_or_id!r} not found")
        return groups[0]

    def get_usergroups(
        self,
        *names_or_ids: str,
        # See get_usergroup for why these are set to True by default
        select_users: bool = True,
        select_rights: bool = True,
        search: bool = True,
        limit: Optional[int] = None,
    ) -> list[Usergroup]:
        """Fetches all user groups. Optionally includes users and rights."""
        params: ParamsType = {
            "output": "extend",
        }
        params = parse_name_or_id_arg(
            params,
            names_or_ids,
            name_param="name",
            id_param="usrgrpids",
            search=search,
        )

        # Rights were split into host and template group rights in 6.2.0
        if select_rights:
            if self.version.release >= (6, 2, 0):
                params["selectHostGroupRights"] = "extend"
                params["selectTemplateGroupRights"] = "extend"
            else:
                params["selectRights"] = "extend"
        if select_users:
            params["selectUsers"] = "extend"
        add_common_params(params, limit=limit)

        try:
            res = self.usergroup.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Unable to fetch user groups") from e
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
            raise ZabbixAPICallError(
                f"Failed to create user group {usergroup_name!r}"
            ) from e
        if not resp or not resp.get("usrgrpids"):
            raise ZabbixAPICallError(
                "User group creation returned no data. Unable to determine if group was created."
            )
        return str(resp["usrgrpids"][0])

    def add_usergroup_users(self, usergroup_name: str, users: list[User]) -> None:
        """Add users to a user group. Ignores users already in the group."""
        self._update_usergroup_users(usergroup_name, users, remove=False)

    def remove_usergroup_users(self, usergroup_name: str, users: list[User]) -> None:
        """Remove users from a user group. Ignores users not in the group."""
        self._update_usergroup_users(usergroup_name, users, remove=True)

    def _update_usergroup_users(
        self, usergroup_name: str, users: list[User], remove: bool = False
    ) -> None:
        """Add/remove users from user group.

        Takes in the name of a user group instead of a `UserGroup` object
        to ensure the user group is fetched with `select_users=True`.
        """
        usergroup = self.get_usergroup(usergroup_name, select_users=True)

        params: ParamsType = {"usrgrpid": usergroup.usrgrpid}

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
            params["userids"] = new_userids
        self.usergroup.update(usrgrpid=usergroup.usrgrpid, userids=new_userids)

    def update_usergroup_rights(
        self,
        usergroup_name: str,
        groups: list[str],
        permission: UsergroupPermission,
        hostgroup: bool,
    ) -> None:
        """Update usergroup rights for host or template groups."""
        usergroup = self.get_usergroup(usergroup_name, select_rights=True)

        params: ParamsType = {"usrgrpid": usergroup.usrgrpid}

        if hostgroup:
            hostgroups = [self.get_hostgroup(hg) for hg in groups]
            if self.version.release >= (6, 2, 0):
                hg_rights = usergroup.hostgroup_rights
            else:
                hg_rights = usergroup.rights
            new_rights = self._get_updated_rights(hg_rights, permission, hostgroups)
            params[compat.usergroup_hostgroup_rights(self.version)] = [
                r.model_dump_api() for r in new_rights
            ]
        else:
            if self.version.release < (6, 2, 0):
                raise ZabbixAPIException(
                    "Template group rights are only supported in Zabbix 6.2.0 and later"
                )
            templategroups = [self.get_templategroup(tg) for tg in groups]
            tg_rights = usergroup.templategroup_rights
            new_rights = self._get_updated_rights(tg_rights, permission, templategroups)
            params[compat.usergroup_templategroup_rights(self.version)] = [
                r.model_dump_api() for r in new_rights
            ]
        try:
            self.usergroup.update(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to update usergroup rights for {usergroup_name!r}"
            ) from e

    def _get_updated_rights(
        self,
        rights: list[ZabbixRight],
        permission: UsergroupPermission,
        groups: Union[list[HostGroup], list[TemplateGroup]],
    ) -> list[ZabbixRight]:
        new_rights: list[ZabbixRight] = []  # list of new rights to add
        rights = list(rights)  # copy rights (don't modify original)
        for group in groups:
            for right in rights:
                if right.id == group.groupid:
                    right.permission = permission.as_api_value()
                    break
            else:
                new_rights.append(
                    ZabbixRight(id=group.groupid, permission=permission.as_api_value())
                )
        rights.extend(new_rights)
        return rights

    def get_proxy(
        self, name_or_id: str, select_hosts: bool = False, search: bool = True
    ) -> Proxy:
        """Fetches a single proxy matching the given name."""
        proxies = self.get_proxies(name_or_id, select_hosts=select_hosts, search=search)
        if not proxies:
            raise ZabbixNotFoundError(f"Proxy {name_or_id!r} not found")
        return proxies[0]

    def get_proxies(
        self,
        *names_or_ids: str,
        select_hosts: bool = False,
        search: bool = True,
        **kwargs: Any,
    ) -> list[Proxy]:
        """Fetches all proxies.

        NOTE: IDs and names cannot be mixed
        """
        params: ParamsType = {"output": "extend"}
        params = parse_name_or_id_arg(
            params,
            names_or_ids,
            name_param=compat.proxy_name(self.version),
            id_param="proxyids",
            search=search,
            search_union=True,
        )

        if select_hosts:
            params["selectHosts"] = "extend"

        try:
            res = self.proxy.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Unknown error when fetching proxies") from e
        else:
            return [Proxy(**proxy) for proxy in res]

    def get_proxy_group(
        self,
        name_or_id: str,
        proxies: Optional[list[Proxy]] = None,
        select_proxies: bool = False,
    ) -> ProxyGroup:
        """Fetches a proxy group given its ID or name."""
        groups = self.get_proxy_groups(
            name_or_id,
            proxies=proxies,
            select_proxies=select_proxies,
        )
        if not groups:
            raise ZabbixNotFoundError(f"Proxy group {name_or_id!r} not found")
        return groups[0]

    def get_proxy_groups(
        self,
        *names_or_ids: str,
        proxies: Optional[list[Proxy]] = None,
        select_proxies: bool = False,
    ) -> list[ProxyGroup]:
        """Fetches a proxy group given its ID or name."""
        params: ParamsType = {"output": "extend"}
        params = parse_name_or_id_arg(
            params,
            names_or_ids,
            name_param="name",
            id_param="proxy_groupids",
            search=True,
            search_union=True,
        )
        if proxies:
            params["proxyids"] = [proxy.proxyid for proxy in proxies]
        if select_proxies:
            params["selectProxies"] = "extend"
        try:
            result = self.proxygroup.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to retrieve proxy groups") from e
        return [ProxyGroup(**group) for group in result]

    def add_proxy_to_group(
        self, proxy: Proxy, group: ProxyGroup, local_address: str, local_port: str
    ) -> None:
        """Adds proxy to a proxy group."""
        # NOTE: there is no endpoint for proxy groups to add to proxies
        # We must update each proxy individually to add them to the group
        try:
            self.proxy.update(
                proxyid=proxy.proxyid,
                proxy_groupid=group.proxy_groupid,
                local_address=local_address,
                local_port=local_port,
            )
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to add proxy {proxy} to group {group}"
            ) from e

    def remove_proxy_from_group(self, proxy: Proxy) -> None:
        """Remove a proxy from any group it's part of."""
        # NOTE: there is no endpoint for proxy groups to add to proxies
        # We must update each proxy individually to add them to the group
        try:
            self.proxy.update(
                proxyid=proxy.proxyid,
                proxy_groupid=0,
            )
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to remove proxy {proxy} from group with ID {proxy.proxy_groupid}."
            ) from e

    def add_host_to_proxygroup(self, host: Host, proxygroup: ProxyGroup) -> None:
        """Adds a host to a proxy group."""
        try:
            self.host.update(
                hostid=host.hostid,
                proxy_hostid=proxygroup.proxy_groupid,
                monitored_by=MonitoredBy.PROXY_GROUP.as_api_value(),
            )
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to add host {host} to proxy group {proxygroup}"
            ) from e

    def add_hosts_to_proxygroup(
        self, hosts: list[Host], proxygroup: ProxyGroup
    ) -> list[str]:
        try:
            updated = self.host.massupdate(
                hosts=[{"hostid": host.hostid} for host in hosts],
                proxy_groupid=proxygroup.proxy_groupid,
                monitored_by=MonitoredBy.PROXY_GROUP.as_api_value(),
            )
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to add hosts to proxy group {proxygroup}"
            ) from e

        return get_returned_list(updated, "hostids", "host.massupdate")

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

    def get_hosts_with_macro(self, macro: str) -> list[Host]:
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
        limit: Optional[int] = None,
    ) -> list[Macro]:
        params: ParamsType = {"output": "extend"}

        if host:
            params["hostids"] = host.hostid

        if macro_name:
            add_param(params, "search", "macro", macro_name)

        # Enable wildcard searching if we have one or more search terms
        if params.get("search"):
            params["searchWildcardsEnabled"] = True

        if select_hosts:
            params["selectHosts"] = "extend"

        if select_templates:
            params["selectTemplates"] = "extend"

        add_common_params(
            params, sort_field=sort_field, sort_order=sort_order, limit=limit
        )

        try:
            result = self.usermacro.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to retrieve macros") from e
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
    ) -> list[GlobalMacro]:
        params: ParamsType = {"output": "extend", "globalmacro": True}

        if macro_name:
            add_param(params, "search", "macro", macro_name)

        # Enable wildcard searching if we have one or more search terms
        if params.get("search"):
            params["searchWildcardsEnabled"] = True

        add_common_params(params, sort_field=sort_field, sort_order=sort_order)

        try:
            result = self.usermacro.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to retrieve global macros") from e

        return [GlobalMacro(**macro) for macro in result]

    def create_macro(self, host: Host, macro: str, value: str) -> str:
        """Creates a macro given a host ID, macro name and value."""
        try:
            resp = self.usermacro.create(hostid=host.hostid, macro=macro, value=value)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
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
            raise ZabbixAPICallError(f"Failed to create global macro {macro!r}.") from e
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
            raise ZabbixAPICallError(f"Failed to update macro with ID {macroid}") from e
        if not resp or not resp.get("hostmacroids"):
            raise ZabbixNotFoundError(
                f"No macro ID returned when updating macro with ID {macroid}"
            )
        return resp["hostmacroids"][0]

    def update_host_inventory(self, host: Host, inventory: dict[str, str]) -> str:
        """Updates a host inventory given a host and inventory."""
        try:
            resp = self.host.update(hostid=host.hostid, inventory=inventory)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to update host inventory for host {host.host!r} (ID {host.hostid})"
            ) from e
        if not resp or not resp.get("hostids"):
            raise ZabbixNotFoundError(
                f"No host ID returned when updating inventory for host {host.host!r} (ID {host.hostid})"
            )
        return resp["hostids"][0]

    def update_host_proxy(self, host: Host, proxy: Proxy) -> str:
        """Updates a host's proxy."""
        resp = self.update_hosts_proxy([host], proxy)
        return resp[0] if resp else ""

    def update_hosts_proxy(self, hosts: list[Host], proxy: Proxy) -> list[str]:
        """Updates a list of hosts' proxy."""
        params: ParamsType = {
            "hosts": [{"hostid": host.hostid} for host in hosts],
            compat.host_proxyid(self.version): proxy.proxyid,
        }
        if self.version.release >= (7, 0, 0):
            params["monitored_by"] = MonitoredBy.PROXY.as_api_value()
        try:
            resp = self.host.massupdate(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to update proxy for hosts {[str(host) for host in hosts]}"
            ) from e
        return get_returned_list(resp, "hostids", "host.massupdate")

    def clear_host_proxies(self, hosts: list[Host]) -> list[str]:
        """Clears a host's proxy."""
        params: ParamsType = {
            "hosts": [{"hostid": host.hostid} for host in hosts],
        }
        if self.version.release >= (7, 0, 0):
            params["monitored_by"] = MonitoredBy.SERVER.as_api_value()
        else:
            params[compat.host_proxyid(self.version)] = None
        try:
            resp = self.host.massupdate(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to clear host proxy for hosts") from e
        return get_returned_list(resp, "hostids", "host.massupdate")

    def update_host_status(self, host: Host, status: MonitoringStatus) -> str:
        """Updates a host status given a host ID and status."""
        try:
            resp = self.host.update(hostid=host.hostid, status=status.as_api_value())
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to update host status for host {host.host!r} (ID {host.hostid})"
            ) from e
        if not resp or not resp.get("hostids"):
            raise ZabbixNotFoundError(
                f"No host ID returned when updating status for host {host.host!r} (ID {host.hostid})"
            )
        return resp["hostids"][0]

    # NOTE: maybe passing in a list of hosts to this is overkill?
    # Just pass in a list of host IDs instead?
    def move_hosts_to_proxy(self, hosts: list[Host], proxy: Proxy) -> None:
        """Moves a list of hosts to a proxy."""
        params: ParamsType = {
            "hosts": [{"hostid": host.hostid} for host in hosts],
            compat.host_proxyid(self.version): proxy.proxyid,
        }
        if self.version.release >= (7, 0, 0):
            params["monitored_by"] = MonitoredBy.PROXY.as_api_value()
        try:
            self.host.massupdate(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
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
    ) -> list[Template]:
        """Fetches one or more templates given a name or ID."""
        params: ParamsType = {"output": "extend"}
        params = parse_name_or_id_arg(
            params,
            template_names_or_ids,
            name_param="host",
            id_param="templateids",
        )

        if select_hosts:
            params["selectHosts"] = "extend"
        if select_templates:
            params["selectTemplates"] = "extend"
        if select_parent_templates:
            params["selectParentTemplates"] = "extend"

        try:
            templates = self.template.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Unable to fetch templates") from e
        return [Template(**template) for template in templates]

    def add_templates_to_groups(
        self,
        templates: list[Template],
        groups: Union[list[HostGroup], list[TemplateGroup]],
    ) -> None:
        try:
            self.template.massadd(
                templates=[
                    {"templateid": template.templateid} for template in templates
                ],
                groups=[{"groupid": group.groupid} for group in groups],
            )
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to add templates to group(s)") from e

    def link_templates_to_hosts(
        self, templates: list[Template], hosts: list[Host]
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
        template_ids: ModifyTemplateParams = [
            {"templateid": template.templateid} for template in templates
        ]
        host_ids: ModifyHostParams = [{"hostid": host.hostid} for host in hosts]
        try:
            self.host.massadd(templates=template_ids, hosts=host_ids)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to link templates") from e

    def unlink_templates_from_hosts(
        self, templates: list[Template], hosts: list[Host], clear: bool = True
    ) -> None:
        """Unlinks and clears one or more templates from one or more hosts.

        Args:
            templates (List[Template]): A list of templates to unlink
            hosts (List[Host]): A list of hosts to unlink templates from
        """
        if not templates:
            raise ZabbixAPIException("At least one template is required")
        if not hosts:
            raise ZabbixAPIException("At least one host is required")

        params: ParamsType = {
            "hostids": [h.hostid for h in hosts],
        }
        tids = [t.templateid for t in templates]
        if clear:
            params["templateids_clear"] = tids
        else:
            params["templateids"] = tids

        try:
            self.host.massremove(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to unlink and clear templates") from e

    def link_templates(
        self, source: list[Template], destination: list[Template]
    ) -> None:
        """Links one or more templates to one or more templates

        Destination templates are the templates that ultimately inherit the
        items and triggers from the source templates.

        Args:
            source (List[Template]): A list of templates to link from
            destination (List[Template]): A list of templates to link to
        """
        if not source:
            raise ZabbixAPIException("At least one source template is required")
        if not destination:
            raise ZabbixAPIException("At least one destination template is required")
        # NOTE: source templates are passed to templates_link param
        templates: ModifyTemplateParams = [
            {"templateid": template.templateid} for template in destination
        ]
        templates_link: ModifyTemplateParams = [
            {"templateid": template.templateid} for template in source
        ]
        try:
            self.template.massadd(templates=templates, templates_link=templates_link)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to link templates") from e

    def unlink_templates(
        self, source: list[Template], destination: list[Template], clear: bool = True
    ) -> None:
        """Unlinks template(s) from template(s) and optionally clears them.

        Destination templates are the templates that ultimately inherit the
        items and triggers from the source templates.

        Args:
            source (List[Template]): A list of templates to unlink
            destination (List[Template]): A list of templates to unlink source templates from
            clear (bool): Whether to clear the source templates from the destination templates. Defaults to True.
        """
        if not source:
            raise ZabbixAPIException("At least one source template is required")
        if not destination:
            raise ZabbixAPIException("At least one destination template is required")
        params: ParamsType = {
            "templateids": [template.templateid for template in destination],
            "templateids_link": [template.templateid for template in source],
        }
        # NOTE: despite what the docs say, we need to pass both templateids_link and templateids_clear
        # in order to unlink and clear templates. Only passing in templateids_clear will just
        # unlink the templates but not clear them (????) Absurd behavior.
        # This is NOT the case for host.massremove, where `templateids_clear` is sufficient...
        if clear:
            params["templateids_clear"] = params["templateids_link"]
        try:
            self.template.massremove(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to unlink template(s)") from e

    def link_templates_to_groups(
        self,
        templates: list[Template],
        groups: Union[list[HostGroup], list[TemplateGroup]],
    ) -> None:
        """Links one or more templates to one or more host/template groups.

        Callers must ensure that the right type of group is passed in depending
        on the Zabbix version:
            * Host groups for Zabbix < 6.2
            * Template groups for Zabbix >= 6.2

        Args:
            templates (List[str]): A list of template names or IDs
            groups (Union[List[HostGroup], List[TemplateGroup]]): A list of host/template groups
        """
        if not templates:
            raise ZabbixAPIException("At least one template is required")
        if not groups:
            raise ZabbixAPIException("At least one group is required")
        template_ids: ModifyTemplateParams = [
            {"templateid": template.templateid} for template in templates
        ]
        group_ids: ModifyGroupParams = [{"groupid": group.groupid} for group in groups]
        try:
            self.template.massadd(templates=template_ids, groups=group_ids)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to link template(s)") from e

    def remove_templates_from_groups(
        self,
        templates: list[Template],
        groups: Union[list[HostGroup], list[TemplateGroup]],
    ) -> None:
        """Removes template(s) from host/template group(s).

        Callers must ensure that the right type of group is passed in depending
        on the Zabbix version:
            * Host groups for Zabbix < 6.2
            * Template groups for Zabbix >= 6.2

        Args:
            templates (List[str]): A list of template names or IDs
            groups (Union[List[HostGroup], List[TemplateGroup]]): A list of host/template groups
        """
        # NOTE: do we even want to enforce this?
        if not templates:
            raise ZabbixAPIException("At least one template is required")
        if not groups:
            raise ZabbixAPIException("At least one group is required")
        try:
            self.template.massremove(
                templateids=[template.templateid for template in templates],
                groupids=[group.groupid for group in groups],
            )
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to unlink template from groups") from e

    def get_items(
        self,
        *names: str,
        templates: Optional[list[Template]] = None,
        hosts: Optional[list[Template]] = None,  # NYI
        proxies: Optional[list[Proxy]] = None,  # NYI
        search: bool = True,
        monitored: bool = False,
        select_hosts: bool = False,
        limit: Optional[int] = None,
        # TODO: implement interfaces
        # TODO: implement graphs
        # TODO: implement triggers
    ) -> list[Item]:
        params: ParamsType = {"output": "extend"}
        params = parse_name_or_id_arg(
            params,
            names,
            name_param="name",
            id_param="itemids",
            search=search,
        )
        if templates:
            params: ParamsType = {
                "templateids": [template.templateid for template in templates]
            }
        if monitored:
            params["monitored"] = monitored  # false by default in API
        if select_hosts:
            params["selectHosts"] = "extend"
        add_common_params(params, limit=limit)
        try:
            items = self.item.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Unable to fetch items") from e
        return [Item(**item) for item in items]

    def create_user(
        self,
        username: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role: Optional[UserRole] = None,
        autologin: Optional[bool] = None,
        autologout: Union[str, int, None] = None,
        usergroups: Union[list[Usergroup], None] = None,
        media: Optional[list[UserMedia]] = None,
    ) -> str:
        # TODO: handle invalid password
        # TODO: handle invalid type
        params: ParamsType = {
            compat.user_name(self.version): username,
            "passwd": password,
        }

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
            raise ZabbixAPICallError(f"Creating user {username!r} returned no user ID.")
        return resp["userids"][0]

    def get_role(self, name_or_id: str) -> Role:
        """Fetches a role given its ID or name."""
        roles = self.get_roles(name_or_id)
        if not roles:
            raise ZabbixNotFoundError(f"Role {name_or_id!r} not found")
        return roles[0]

    def get_roles(self, name_or_id: Optional[str] = None) -> list[Role]:
        params: ParamsType = {"output": "extend"}
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
        *names_or_ids: str,
        role: Optional[UserRole] = None,
        search: bool = True,
        limit: Optional[int] = None,
        sort_field: Optional[str] = None,
        sort_order: Optional[SortOrder] = None,
    ) -> list[User]:
        params: ParamsType = {"output": "extend"}
        params = parse_name_or_id_arg(
            params,
            names_or_ids,
            name_param=compat.user_name(self.version),
            id_param="userids",
            search=search,
        )
        if role:
            add_param(
                params, "filter", compat.role_id(self.version), role.as_api_value()
            )

        add_common_params(params, sort_field, sort_order, limit=limit)

        users = self.user.get(**params)
        return [User(**user) for user in users]

    def delete_user(self, user: User) -> str:
        """Delete a user.

        Returns ID of deleted user.
        """
        try:
            resp = self.user.delete(user.userid)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to delete user {user.username!r} ({user.userid})"
            ) from e
        if not resp or not resp.get("userids"):
            raise ZabbixNotFoundError(
                f"No user ID returned when deleting user {user.username!r} ({user.userid})"
            )
        return resp["userids"][0]

    def update_user(
        self,
        user: User,
        current_password: Optional[str] = None,
        new_password: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role: Optional[UserRole] = None,
        autologin: Optional[bool] = None,
        autologout: Union[str, int, None] = None,
    ) -> str:
        """Update a user. Returns ID of updated user."""
        query: ParamsType = {"userid": user.userid}
        if current_password and new_password:
            query["current_passwd"] = current_password
            query["passwd"] = new_password
        if first_name:
            query["name"] = first_name
        if last_name:
            query["surname"] = last_name
        if role:
            query[compat.role_id(self.version)] = role.as_api_value()
        if autologin is not None:
            query["autologin"] = int(autologin)
        if autologout is not None:
            query["autologout"] = str(autologout)

        # Media and user groups are not supported in this method

        try:
            resp = self.user.update(**query)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to update user {user.username!r} ({user.userid})"
            ) from e
        if not resp or not resp.get("userids"):
            raise ZabbixNotFoundError(
                f"No user ID returned when updating user {user.username!r} ({user.userid})"
            )
        return resp["userids"][0]

    def get_mediatype(self, name_or_id: str) -> MediaType:
        mts = self.get_mediatypes(name_or_id)
        if not mts:
            raise ZabbixNotFoundError(f"Media type {name_or_id!r} not found")
        return mts[0]

    def get_mediatypes(
        self, *names_or_ids: str, search: bool = False
    ) -> list[MediaType]:
        params: ParamsType = {"output": "extend"}
        params = parse_name_or_id_arg(
            params,
            names_or_ids,
            name_param="name",
            id_param="mediatypeids",
            search=search,
        )
        resp = self.mediatype.get(**params)
        return [MediaType(**mt) for mt in resp]

    ## Maintenance
    def get_maintenance(self, maintenance_id: str) -> Maintenance:
        """Fetches a maintenance given its ID."""
        maintenances = self.get_maintenances(maintenance_ids=[maintenance_id])
        if not maintenances:
            raise ZabbixNotFoundError(f"Maintenance {maintenance_id!r} not found")
        return maintenances[0]

    def get_maintenances(
        self,
        maintenance_ids: Optional[list[str]] = None,
        hostgroups: Optional[list[HostGroup]] = None,
        hosts: Optional[list[Host]] = None,
        name: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[Maintenance]:
        params: ParamsType = {
            "output": "extend",
            "selectHosts": "extend",
            compat.param_host_get_groups(self.version): "extend",
            "selectTimeperiods": "extend",
        }
        filter_params: ParamsType = {}
        if maintenance_ids:
            params["maintenanceids"] = maintenance_ids
        if hostgroups:
            params["groupids"] = [hg.groupid for hg in hostgroups]
        if hosts:
            params["hostids"] = [h.hostid for h in hosts]
        if name:
            filter_params["name"] = name
        if filter_params:
            params["filter"] = filter_params
        params = add_common_params(params, limit=limit)
        resp = self.maintenance.get(**params)
        return [Maintenance(**mt) for mt in resp]

    def create_maintenance(
        self,
        name: str,
        active_since: datetime,
        active_till: datetime,
        description: Optional[str] = None,
        hosts: Optional[list[Host]] = None,
        hostgroups: Optional[list[HostGroup]] = None,
        data_collection: Optional[DataCollectionMode] = None,
    ) -> str:
        """Create a one-time maintenance definition."""
        if not hosts and not hostgroups:
            raise ZabbixAPIException("At least one host or hostgroup is required")
        params: ParamsType = {
            "name": name,
            "active_since": int(active_since.timestamp()),
            "active_till": int(active_till.timestamp()),
            "timeperiods": {
                "timeperiod_type": 0,
                "start_date": int(active_since.timestamp()),
                "period": int((active_till - active_since).total_seconds()),
            },
        }
        if description:
            params["description"] = description
        if hosts:
            if self.version.release >= (6, 0, 0):
                params["hosts"] = [{"hostid": h.hostid} for h in hosts]
            else:
                params["hostids"] = [h.hostid for h in hosts]
        if hostgroups:
            if self.version.release >= (6, 0, 0):
                params["groups"] = {"groupid": hg.groupid for hg in hostgroups}
            else:
                params["groupids"] = [hg.groupid for hg in hostgroups]
        if data_collection:
            params["maintenance_type"] = data_collection.as_api_value()
        resp = self.maintenance.create(**params)
        if not resp or not resp.get("maintenanceids"):
            raise ZabbixAPICallError(f"Creating maintenance {name!r} returned no ID.")
        return resp["maintenanceids"][0]

    def delete_maintenance(self, *maintenance_ids: str) -> list[str]:
        """Deletes one or more maintenances given their IDs

        Returns IDs of deleted maintenances.
        """
        try:
            resp = self.maintenance.delete(*maintenance_ids)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(
                f"Failed to delete maintenances {maintenance_ids}"
            ) from e
        if not resp or not resp.get("maintenanceids"):
            raise ZabbixNotFoundError(
                f"No maintenance IDs returned when deleting maintenance {maintenance_ids}"
            )
        return resp["maintenanceids"]

    def acknowledge_event(
        self,
        *event_ids: str,
        message: Optional[str] = None,
        acknowledge: bool = True,
        close: bool = False,
        change_severity: bool = False,
        unacknowledge: bool = False,
        suppress: bool = False,
        unsuppress: bool = False,
        change_to_cause: bool = False,
        change_to_symptom: bool = False,
    ) -> list[str]:
        # The action is an integer that is created based on
        # the combination of the parameters passed in.
        action = get_acknowledge_action_value(
            close=close,
            message=bool(message),
            acknowledge=acknowledge,
            change_severity=change_severity,
            unacknowledge=unacknowledge,
            suppress=suppress,
            unsuppress=unsuppress,
            change_to_cause=change_to_cause,
            change_to_symptom=change_to_symptom,
        )
        params: ParamsType = {"eventids": list(event_ids), "action": action}
        if message:
            params["message"] = message
        try:
            resp = self.event.acknowledge(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError(f"Failed to acknowledge events {event_ids}") from e
        if not resp or not resp.get("eventids"):
            raise ZabbixNotFoundError(
                f"No event IDs returned when acknowledging events {event_ids}"
            )
        # For some reason this API msethod returns a list of ints instead of strings
        # even though the API docs specify that it should be a list of strings.
        return [str(eventid) for eventid in resp["eventids"]]

    def get_event(
        self,
        # NOTE: Does this API make sense?
        # Should we just expose event_id instead, and then
        # use `get_events()` for everything else?
        event_id: Optional[str] = None,
        group_id: Optional[str] = None,
        host_id: Optional[str] = None,
        object_id: Optional[str] = None,
        sort_field: Optional[str] = None,
        sort_order: Optional[SortOrder] = None,
    ) -> Event:
        """Fetches an event given its ID."""
        events = self.get_events(
            event_ids=event_id,
            group_ids=group_id,
            host_ids=host_id,
            object_ids=object_id,
            sort_field=sort_field,
            sort_order=sort_order,
        )
        if not events:
            reasons: list[str] = []
            if event_id:
                reasons.append(f"event ID {event_id!r}")
            if group_id:
                reasons.append(f"group ID {group_id!r}")
            if host_id:
                reasons.append(f"host ID {host_id!r}")
            if object_id:
                reasons.append(f"object ID {object_id!r}")
            r = " and ".join(reasons)
            raise ZabbixNotFoundError(
                f"Event {'with' if reasons else ''} {r} not found".replace("  ", " ")
            )
        return events[0]

    def get_events(
        self,
        event_ids: Union[str, list[str], None] = None,
        # Why are we taking in strings here instead of objects?
        # Should we instead take in objects and then extract the IDs?
        group_ids: Union[str, list[str], None] = None,
        host_ids: Union[str, list[str], None] = None,
        object_ids: Union[str, list[str], None] = None,
        sort_field: Union[str, list[str], None] = None,
        sort_order: Optional[SortOrder] = None,
        limit: Optional[int] = None,
    ) -> list[Event]:
        params: ParamsType = {"output": "extend"}
        if event_ids:
            params["eventids"] = event_ids
        if group_ids:
            params["groupids"] = group_ids
        if host_ids:
            params["hostids"] = host_ids
        if object_ids:
            params["objectids"] = object_ids
        add_common_params(params, sort_field=sort_field, sort_order=sort_order)

        try:
            resp = self.event.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to fetch events") from e
        return [Event(**event) for event in resp]

    def get_triggers(
        self,
        trigger_ids: Union[str, list[str], None] = None,
        hostgroups: Optional[list[HostGroup]] = None,
        templates: Optional[list[Template]] = None,
        description: Optional[str] = None,
        priority: Optional[TriggerPriority] = None,
        unacknowledged: bool = False,
        skip_dependent: Optional[bool] = None,
        monitored: Optional[bool] = None,
        active: Optional[bool] = None,
        expand_description: Optional[bool] = None,
        filter: Optional[dict[str, Any]] = None,
        select_hosts: bool = False,
        sort_field: Optional[str] = "lastchange",
        sort_order: SortOrder = "DESC",
    ) -> list[Trigger]:
        params: ParamsType = {"output": "extend"}
        if description:
            params["search"] = {"description": description}
        if skip_dependent is not None:
            params["skipDependent"] = int(skip_dependent)
        if monitored is not None:
            params["monitored"] = int(monitored)
        if active is not None:
            params["active"] = int(active)
        if expand_description is not None:
            params["expandDescription"] = int(expand_description)
        if filter:
            params["filter"] = filter
        if trigger_ids:
            params["triggerids"] = trigger_ids
        if hostgroups:
            params["groupids"] = [hg.groupid for hg in hostgroups]
        if templates:
            params["templateids"] = [t.templateid for t in templates]
        if priority:
            # TODO: refactor and combine with filter argument
            # Since priority is a part of filter, we should either
            # delegate this to the filter argument or add every possible
            # filter argument to the method signature.
            if not params.get("filter"):
                params["filter"] = {}
            assert isinstance(params["filter"], dict)
            params["filter"]["priority"] = priority.as_api_value()
        if unacknowledged:
            params["withLastEventUnacknowledged"] = True
        if select_hosts:
            params["selectHosts"] = "extend"
        add_common_params(params, sort_field, sort_order)

        try:
            resp = self.trigger.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to fetch triggers") from e
        return [Trigger(**trigger) for trigger in resp]

    def get_images(self, *image_names: str, select_image: bool = True) -> list[Image]:
        """Fetches images, optionally filtered by name(s)."""
        params: ParamsType = {"output": "extend"}
        params = parse_name_or_id_arg(
            params, image_names, name_param="name", id_param="imageids"
        )

        if select_image:
            params["selectImage"] = True

        try:
            resp = self.image.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to fetch images") from e
        return [Image(**image) for image in resp]

    def get_maps(self, *map_names: str) -> list[Map]:
        """Fetches maps, optionally filtered by name(s)."""
        params: ParamsType = {"output": "extend"}
        params = parse_name_or_id_arg(
            params,
            map_names,
            name_param="name",
            id_param="sysmapids",
        )

        try:
            resp = self.map.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to fetch maps") from e
        return [Map(**m) for m in resp]

    def get_media_types(self, *names: str) -> list[MediaType]:
        """Fetches media types, optionally filtered by name(s)."""
        params: ParamsType = {"output": "extend"}
        params = parse_name_or_id_arg(
            params, names, name_param="name", id_param="mediatypeids"
        )

        try:
            resp = self.mediatype.get(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to fetch maps") from e
        return [MediaType(**m) for m in resp]

    def export_configuration(
        self,
        host_groups: Optional[list[HostGroup]] = None,
        template_groups: Optional[list[TemplateGroup]] = None,
        hosts: Optional[list[Host]] = None,
        images: Optional[list[Image]] = None,
        maps: Optional[list[Map]] = None,
        templates: Optional[list[Template]] = None,
        media_types: Optional[list[MediaType]] = None,
        format: ExportFormat = ExportFormat.JSON,
        pretty: bool = True,
    ) -> str:
        """Exports a configuration to a JSON or XML file."""
        params: ParamsType = {"format": str(format)}
        options: ParamsType = {}
        if host_groups:
            options["host_groups"] = [hg.groupid for hg in host_groups]
        if template_groups:
            options["template_groups"] = [tg.groupid for tg in template_groups]
        if hosts:
            options["hosts"] = [h.hostid for h in hosts]
        if images:
            options["images"] = [i.imageid for i in images]
        if maps:
            options["maps"] = [m.sysmapid for m in maps]
        if templates:
            options["templates"] = [t.templateid for t in templates]
        if media_types:
            options["mediaTypes"] = [mt.mediatypeid for mt in media_types]
        if pretty:
            if self.version.release >= (5, 4, 0):
                if format == ExportFormat.XML:
                    logger.warning("Pretty printing is not supported for XML")
                else:
                    params["prettyprint"] = True
            else:
                logger.warning(
                    "Pretty printing is not supported in Zabbix versions < 5.4.0"
                )
        if options:
            params["options"] = options

        try:
            resp = self.configuration.export(**params)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to export configuration") from e
        # TODO: validate response
        return str(resp)

    def import_configuration(
        self,
        to_import: Path,
        create_missing: bool = True,
        update_existing: bool = True,
        delete_missing: bool = False,
    ) -> None:
        """Imports a configuration from a file.

        The format to import is determined by the file extension.
        """
        try:
            conf = to_import.read_text()
            fmt = ExportFormat(to_import.suffix.strip("."))
            rules = ImportRules.get(
                create_missing=create_missing,
                update_existing=update_existing,
                delete_missing=delete_missing,
            )
            self.confimport(format=fmt, source=conf, rules=rules)
        except ZabbixAPIException as e:
            raise ZabbixAPICallError("Failed to import configuration") from e

    def __getattr__(self, attr: str) -> ZabbixAPIObjectClass:
        """Dynamically create an object class (ie: host)"""
        return ZabbixAPIObjectClass(attr, self)


class ZabbixAPIObjectClass:
    def __init__(self, name: str, parent: ZabbixAPI) -> None:
        self.name = name
        self.parent = parent

    def __getattr__(self, attr: str) -> Any:
        """Dynamically create a method (ie: get)"""

        def fn(*args: Any, **kwargs: Any) -> Any:
            if args and kwargs:
                raise TypeError("Found both args and kwargs")

            return self.parent.do_request(f"{self.name}.{attr}", args or kwargs).result  # type: ignore

        return fn

    def get(self, *args: Any, **kwargs: Any) -> Any:
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
                output_kwargs = cast(list[str], output_kwargs)
                for param in params:
                    try:
                        output_kwargs.remove(param)
                    except ValueError:
                        pass
                output_kwargs.append(compat.proxy_name(self.parent.version))
                kwargs["output"] = output_kwargs
        return self.__getattr__("get")(*args, **kwargs)
