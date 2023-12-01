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
from typing import Any
from typing import List
from typing import Optional

import requests
import urllib3
from packaging.version import Version

from zabbix_cli.cache import ZabbixCache
from zabbix_cli.exceptions import ZabbixAPIException
from zabbix_cli.exceptions import ZabbixNotFoundError
from zabbix_cli.pyzabbix import compat
from zabbix_cli.pyzabbix.types import Usergroup
from zabbix_cli.pyzabbix.types import ZabbixRight


class _NullHandler(logging.Handler):
    def emit(self, record):
        pass


logger = logging.getLogger(__name__)
logger.addHandler(_NullHandler())
logger.setLevel(logging.INFO)


class ZabbixAPI:
    def __init__(
        self,
        server: str = "http://localhost/zabbix",
        session: requests.Session = None,
        timeout: int = None,
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
        self._version = None

        # Cache
        self.cache = ZabbixCache(self)

    def disable_ssl_verification(self):
        """Disables SSL verification and suppresses urllib3 SSL warning."""
        self.session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def login(self, user: str = "", password: str = "", auth_token: str = "") -> str:
        """
        Convenience method for logging into the API and storing the resulting
        auth token as an instance variable.
        """
        # The username kwarg was called "user" in Zabbix 5.2 and earlier.
        # This sets the correct kwarg for the version of Zabbix we're using.
        user_kwarg = {compat.login_user_name(self.version): user}

        if not auth_token:
            self.auth = self.user.login(**user_kwarg, password=password)  # type: ignore
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

        logger.debug(
            "Sending: %s", json.dumps(request_json, indent=4, separators=(",", ": "))
        )

        response = self.session.post(
            self.url, data=json.dumps(request_json), timeout=self.timeout
        )

        logger.debug("Response Code: %s", str(response.status_code))

        # NOTE: Getting a 412 response code means the headers are not in the
        # list of allowed headers.
        response.raise_for_status()

        if not len(response.text):
            raise ZabbixAPIException("Received empty response")

        try:
            response_json = json.loads(response.text)
        except ValueError:
            raise ZabbixAPIException("Unable to parse json: %s" % response.text)
        logger.debug(
            "Response Body: %s",
            json.dumps(response_json, indent=4, separators=(",", ": ")),
        )

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

            if response_json["error"]["data"] == "Login name or password is incorrect.":
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
            raise ZabbixNotFoundError(f"Hostgroup with ID {hostgroup_id} not found")
        # TODO add result to cache
        return resp[0]["name"]

    def get_hostgroup_id(self, hostgroup_name: str) -> str:
        """Returns the ID of a host group given its name."""
        hostgroup_id = self.cache.get_hostgroup_id(hostgroup_name)
        if hostgroup_id:
            return hostgroup_id
        resp = self.hostgroup.get(filter={"name": hostgroup_name}, output=["name"])
        if not resp:
            raise ZabbixNotFoundError(
                f"Hostgroup with name {hostgroup_name!r} not found"
            )
        # TODO add result to cache
        return resp[0]["groupid"]

    def get_host_id(self, hostname: str) -> str:
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

    def get_usergroup(self, usergroup_name: str) -> Usergroup:
        """Fetches a user group by name. Always fetches the full contents of the group."""
        query = {
            "filter": {"name": usergroup_name},
            "output": "extend",
            "selectUsers": "extend",  # TODO: profile performance for large groups
        }
        # Rights were split into host and template group rights in 6.2.0
        if self.version.release >= (6, 2, 0):
            query["selectHostGroupRights"] = "extend"
            query["selectTemplateGroupRights"] = "extend"
        else:
            query["selectRights"] = "extend"

        try:
            res = self.usergroup.get(**query)
            if not res:
                raise ZabbixNotFoundError(
                    f"Usergroup with name {usergroup_name!r} not found"
                )
        except ZabbixNotFoundError:
            raise
        except ZabbixAPIException as e:
            raise ZabbixAPIException(
                f"Unknown error when fetching user group {usergroup_name}: {e}"
            )
        else:
            return Usergroup(**res[0])

    def update_usergroup(
        self,
        usergroup_name: str,
        rights: Optional[List[ZabbixRight]] = None,
        userids: Optional[List[ZabbixRight]] = None,
    ) -> Optional[list]:
        """
        Merge update a usergroup.

        Updating usergroups without replacing current state (i.e. merge update) is hard.
        This function simplifies the process.

        The rights and userids provided are merged into the usergroup.
        """
        usergroup = self.get_usergroup(usergroup_name)
        # usergroup = self.usergroup.get(
        #     filter={"usrgrpid": ug.usrgrpid},
        #     selectRights=["permission", "id"],
        #     selectUsers=["userid"],
        # )[0]

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
            current_userids = [user["userid"] for user in usergroup["users"]]  # type: list[str]
            # Make sure we only have unique ids
            new_userids = list(set(current_userids + userids))
            return self.usergroup.update(
                usrgrpid=usergroup.usrgrpid, userids=new_userids
            )

        return None

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
