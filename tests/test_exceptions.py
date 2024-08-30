from __future__ import annotations

from typing import Type

import pytest
from inline_snapshot import snapshot
from zabbix_cli.exceptions import ZabbixAPIException
from zabbix_cli.exceptions import ZabbixAPIRequestError
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.exceptions import get_cause_args
from zabbix_cli.pyzabbix.types import ZabbixAPIError
from zabbix_cli.pyzabbix.types import ZabbixAPIResponse


@pytest.mark.parametrize(
    "outer_t", [TypeError, ValueError, ZabbixCLIError, ZabbixAPIException]
)
def test_get_cause_args(outer_t: Type[Exception]) -> None:
    try:
        try:
            try:
                raise ZabbixAPIException("foo!")
            except ZabbixAPIException as e:
                raise TypeError("foo", "bar") from e
        except TypeError as e:
            raise outer_t("outer") from e
    except outer_t as e:
        args = get_cause_args(e)
        assert args == snapshot(["outer", "foo", "bar", "foo!"])


def test_get_cause_args_no_cause() -> None:
    e = ZabbixAPIException("foo!")
    args = get_cause_args(e)
    assert args == snapshot(["foo!"])


def test_get_cause_args_with_api_response() -> None:
    api_resp = ZabbixAPIResponse(
        jsonrpc="2.0",
        result=None,
        id=1,
        error=ZabbixAPIError(code=-123, message="Some error"),
    )
    e = ZabbixAPIRequestError("foo!", api_response=api_resp)
    args = get_cause_args(e)
    assert args == snapshot(["foo!", "(-123) Some error"])


def test_get_cause_args_with_api_response_with_data() -> None:
    """Get the cause args from an exception with an API response with data."""
    api_resp = ZabbixAPIResponse(
        jsonrpc="2.0",
        result=None,
        id=1,
        error=ZabbixAPIError(code=-123, message="Some error", data='{"foo": 42}'),
    )
    e = ZabbixAPIRequestError("foo!", api_response=api_resp)
    args = get_cause_args(e)
    assert args == snapshot(["foo!", '(-123) Some error {"foo": 42}'])
