from __future__ import annotations

from typing import Any
from typing import Dict

import pytest
from inline_snapshot import snapshot
from packaging.version import Version
from zabbix_cli.exceptions import ZabbixAPILoginError
from zabbix_cli.exceptions import ZabbixAPILogoutError
from zabbix_cli.pyzabbix.client import ZabbixAPI
from zabbix_cli.pyzabbix.client import add_param
from zabbix_cli.pyzabbix.client import append_param


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
def test_append_param(inp: Any, key: str, value: Any, expect: Dict[str, Any]) -> None:
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
def test_add_param(inp: Any, subkey: str, value: Any, expect: Dict[str, Any]) -> None:
    result = add_param(inp, "search", subkey, value)
    assert result == expect
    # Check in-place modification


def test_login_fails(zabbix_client: ZabbixAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    zabbix_client.set_url("http://some-url-that-will-fail.gg")
    assert zabbix_client.url == snapshot(
        "http://some-url-that-will-fail.gg/api_jsonrpc.php"
    )

    # Patch the version check
    monkeypatch.setattr(zabbix_client, "api_version", lambda: Version("7.0.0"))

    with pytest.raises(ZabbixAPILoginError) as exc_info:
        zabbix_client.login(user="username", password="password")

    assert exc_info.exconly() == snapshot(
        "zabbix_cli.exceptions.ZabbixAPILoginError: Failed to log in to Zabbix: Failed to send request to http://some-url-that-will-fail.gg/api_jsonrpc.php (user.login) with params {'username': 'username', 'password': 'password'}"
    )
    assert str(exc_info.value) == snapshot(
        "Failed to log in to Zabbix: Failed to send request to http://some-url-that-will-fail.gg/api_jsonrpc.php (user.login) with params {'username': 'username', 'password': 'password'}"
    )


def test_logout_fails(zabbix_client: ZabbixAPI) -> None:
    """Test that we get the correct exception type when login fails
    due to a connection error."""
    zabbix_client.set_url("http://some-url-that-will-fail.gg")
    assert zabbix_client.url == snapshot(
        "http://some-url-that-will-fail.gg/api_jsonrpc.php"
    )

    zabbix_client.auth = "authtoken123456789"

    with pytest.raises(ZabbixAPILogoutError) as exc_info:
        zabbix_client.logout()

    assert exc_info.exconly() == snapshot(
        "zabbix_cli.exceptions.ZabbixAPILogoutError: Failed to log out of Zabbix: Failed to send request to http://some-url-that-will-fail.gg/api_jsonrpc.php (user.logout) with params {}"
    )
