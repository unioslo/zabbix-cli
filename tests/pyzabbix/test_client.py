from __future__ import annotations

from typing import Any
from typing import Literal

import pytest
from inline_snapshot import snapshot
from packaging.version import Version
from pytest_httpserver import HTTPServer
from zabbix_cli.exceptions import ZabbixAPILoginError
from zabbix_cli.exceptions import ZabbixAPILogoutError
from zabbix_cli.pyzabbix.client import ZabbixAPI
from zabbix_cli.pyzabbix.client import add_param
from zabbix_cli.pyzabbix.client import append_param

from tests.utils import add_zabbix_endpoint
from tests.utils import add_zabbix_version_endpoint


@pytest.mark.parametrize(
    "inp, key, value, expect",
    [
        pytest.param(
            {"hostids": 1},
            "hostids",
            2,
            {"hostids": [1, 2]},
            id="non-list (int)",
        ),
        pytest.param(
            {"hostids": [1]},
            "hostids",
            2,
            {"hostids": [1, 2]},
            id="list (int)",
        ),
        pytest.param(
            {"hostids": "1"},
            "hostids",
            "2",
            {"hostids": ["1", "2"]},
            id="non-list (str)",
        ),
        pytest.param(
            {"hostids": ["1"]},
            "hostids",
            "2",
            {"hostids": ["1", "2"]},
            id="list (str)",
        ),
        pytest.param(
            {"lists": [[1, 2, 3]]},
            "lists",
            [4, 5, 6],
            {"lists": [[1, 2, 3], [4, 5, 6]]},
            id="list of lists",
        ),
    ],
)
def test_append_param(inp: Any, key: str, value: Any, expect: dict[str, Any]) -> None:
    result = append_param(inp, key, value)
    assert result == expect
    # Check in-place modification
    assert result is inp


@pytest.mark.parametrize(
    "inp, subkey, value, expect",
    [
        (
            {"output": "extend"},
            "hostids",
            2,
            {"output": "extend", "search": {"hostids": 2}},
        ),
    ],
)
def test_add_param(inp: Any, subkey: str, value: Any, expect: dict[str, Any]) -> None:
    result = add_param(inp, "search", subkey, value)
    assert result == expect
    # Check in-place modification


def test_login_fails(zabbix_client_mock_version: ZabbixAPI) -> None:
    client = zabbix_client_mock_version
    client.set_url("http://some-url-that-will-fail.gg")
    assert client.url == snapshot("http://some-url-that-will-fail.gg/api_jsonrpc.php")

    with pytest.raises(ZabbixAPILoginError) as exc_info:
        client.login(user="username", password="password")

    assert exc_info.exconly() == snapshot(
        "zabbix_cli.exceptions.ZabbixAPILoginError: Failed to log in to Zabbix: Failed to send request to http://some-url-that-will-fail.gg/api_jsonrpc.php (user.login) with params {'username': 'username', 'password': 'password'}"
    )
    assert str(exc_info.value) == snapshot(
        "Failed to log in to Zabbix: Failed to send request to http://some-url-that-will-fail.gg/api_jsonrpc.php (user.login) with params {'username': 'username', 'password': 'password'}"
    )


def test_logout_fails(zabbix_client_mock_version: ZabbixAPI) -> None:
    """Test that we get the correct exception type when login fails
    due to a connection error."""
    client = zabbix_client_mock_version
    client.set_url("http://some-url-that-will-fail.gg")
    assert client.url == snapshot("http://some-url-that-will-fail.gg/api_jsonrpc.php")

    client.auth = "authtoken123456789"

    with pytest.raises(ZabbixAPILogoutError) as exc_info:
        client.logout()

    assert exc_info.exconly() == snapshot(
        "zabbix_cli.exceptions.ZabbixAPILogoutError: Failed to log out of Zabbix: Failed to send request to http://some-url-that-will-fail.gg/api_jsonrpc.php (user.logout) with params {}"
    )


@pytest.mark.parametrize(
    "inp, expect",
    [
        pytest.param(
            "http://localhost",
            "http://localhost/api_jsonrpc.php",
            id="localhost-no-slash",
        ),
        pytest.param(
            "http://localhost/",
            "http://localhost/api_jsonrpc.php",
            id="localhost-with-slash",
        ),
        pytest.param(
            "http://localhost/api_jsonrpc.php",
            "http://localhost/api_jsonrpc.php",
            id="localhost-full-url",
        ),
        pytest.param(
            "http://localhost/api_jsonrpc.php/",
            "http://localhost/api_jsonrpc.php",
            id="localhost-full-url-with-slash",
        ),
        pytest.param(
            "http://example.com",
            "http://example.com/api_jsonrpc.php",
            id="tld-no-slash",
        ),
        pytest.param(
            "http://example.com/",
            "http://example.com/api_jsonrpc.php",
            id="tld-with-slash",
        ),
        pytest.param(
            "http://example.com/api_jsonrpc.php",
            "http://example.com/api_jsonrpc.php",
            id="tld-full-url",
        ),
        pytest.param(
            "http://example.com/api_jsonrpc.php/",
            "http://example.com/api_jsonrpc.php",
            id="tld-full-url-with-slash",
        ),
    ],
)
def test_client_server_url(inp: str, expect: str) -> None:
    zabbix_client = ZabbixAPI(server=inp)
    assert zabbix_client.url == expect


AuthMethod = Literal["header", "body"]


@pytest.mark.parametrize(
    "version,expect_method",
    [
        pytest.param(Version("5.0.0"), "body", id="5.0.0"),
        pytest.param(Version("5.2.0"), "body", id="5.2.0"),
        pytest.param(Version("6.0.0"), "body", id="6.0.0"),
        pytest.param(Version("6.2.0"), "body", id="6.2.0"),
        pytest.param(Version("6.4.0"), "header", id="6.4.0"),
        pytest.param(Version("7.0.0"), "header", id="7.0.0"),
        pytest.param(Version("7.2.0"), "header", id="7.2.0"),
    ],
)
def test_client_auth_method(
    zabbix_client: ZabbixAPI,
    httpserver: HTTPServer,
    version: Version,
    expect_method: AuthMethod,
) -> None:
    """Test that the correct auth method (body/header) is used based on the Zabbix server version."""
    # Add endpoint for version check
    zabbix_client.set_url(httpserver.url_for("/api_jsonrpc.php"))

    # Set a mock token we can use for testing
    zabbix_client.auth = "token123"

    # Add endpoint that returns the parametrized version
    add_zabbix_version_endpoint(httpserver, str(version), id=0)

    assert zabbix_client.version == version

    headers: dict[str, str] = {}
    auth = None
    # We expect auth token to be in header on >= 6.4.0
    if expect_method == "header":
        headers["Authorization"] = f"Bearer {zabbix_client.auth}"
    else:
        auth = zabbix_client.auth

    add_zabbix_endpoint(
        httpserver,
        method="test.method.do_stuff",
        params={},
        response="authtoken123456789",
        headers=headers,
        auth=auth,
    )

    # Will fail if the auth method is not set correctly
    resp = zabbix_client.do_request("test.method.do_stuff")
    assert resp.result == "authtoken123456789"

    httpserver.check_assertions()
    httpserver.check_handler_errors()


AuthType = Literal["token", "sessionid"]


@pytest.mark.parametrize(
    "auth_type,auth",
    [
        pytest.param("token", "authtoken123456789", id="token"),
        pytest.param("token", "", id="token (empty string)"),
        pytest.param("sessionid", "sessionid123456789", id="sessionid"),
        pytest.param("sessionid", "", id="sessionid (empty string)"),
    ],
)
def test_client_logout(httpserver: HTTPServer, auth_type: AuthType, auth: str) -> None:
    add_zabbix_version_endpoint(httpserver, "7.0.0")

    # We only expect a logout request if we are using a sessionid and have an auth token
    if auth_type == "sessionid" and auth:
        add_zabbix_endpoint(httpserver, "user.logout", {}, True)
    zabbix_client = ZabbixAPI(server=httpserver.url_for("/api_jsonrpc.php"))
    zabbix_client.auth = auth
    if auth_type == "token":
        zabbix_client.use_api_token = True
    zabbix_client.logout()

    httpserver.check_assertions()
    httpserver.check_handler_errors()
