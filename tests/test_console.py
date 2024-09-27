from __future__ import annotations

import logging
from typing import Any
from typing import Dict

import pytest
from inline_snapshot import snapshot
from zabbix_cli.config.constants import OutputFormat
from zabbix_cli.exceptions import ZabbixAPIException
from zabbix_cli.exceptions import ZabbixAPIRequestError
from zabbix_cli.output.console import RESERVED_EXTRA_KEYS
from zabbix_cli.output.console import debug
from zabbix_cli.output.console import debug_kv
from zabbix_cli.output.console import error
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import get_extra_dict
from zabbix_cli.output.console import info
from zabbix_cli.output.console import success
from zabbix_cli.output.console import warning
from zabbix_cli.pyzabbix.types import ZabbixAPIError
from zabbix_cli.pyzabbix.types import ZabbixAPIResponse
from zabbix_cli.state import State


@pytest.mark.parametrize(
    "inp,expect",
    [
        # No extras
        ({}, {}),
        # 1 extra
        ({"name": "foo"}, {"name_": "foo"}),
        # 2 extras
        ({"name": "foo", "level": "DEBUG"}, {"name_": "foo", "level_": "DEBUG"}),
        # 3 extras (2 reserved)
        (
            {"name": "foo", "level": "DEBUG", "key": "value"},
            {"name_": "foo", "level_": "DEBUG", "key": "value"},
        ),
    ],
)
def test_get_extra_dict(inp: Dict[str, Any], expect: Dict[str, Any]) -> None:
    extra = get_extra_dict(**inp)
    assert extra == expect


def test_get_extra_dict_reserved_keys() -> None:
    """Test that all reserved keys are renamed."""
    d: Dict[str, Any] = {}
    for key in RESERVED_EXTRA_KEYS:
        d[key] = key
    extra = get_extra_dict(**d)
    assert extra == snapshot(
        {
            "name_": "name",
            "level_": "level",
            "pathname_": "pathname",
            "lineno_": "lineno",
            "msg_": "msg",
            "args_": "args",
            "exc_info_": "exc_info",
            "func_": "func",
            "sinfo_": "sinfo",
        }
    )


def test_debug_kv(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    debug_kv("some", "error")
    captured = capsys.readouterr()
    assert captured.err == snapshot("some                : error\n")
    assert caplog.record_tuples == snapshot(
        [("zabbix_cli", 10, "some                : error")]
    )
    assert caplog.records[0].funcName == snapshot("test_debug_kv")


def test_debug(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    debug("Some error")
    captured = capsys.readouterr()
    assert captured.err == snapshot("Some error\n")
    assert caplog.record_tuples == snapshot([("zabbix_cli", 10, "Some error")])
    assert caplog.records[0].funcName == snapshot("test_debug")


def test_info(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    info("Some error")
    captured = capsys.readouterr()
    assert captured.err == snapshot("! Some error\n")
    assert caplog.record_tuples == snapshot([("zabbix_cli", 20, "Some error")])
    assert caplog.records[0].funcName == snapshot("test_info")


def test_success(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    success("Some error")
    captured = capsys.readouterr()
    assert captured.err == snapshot("✓ Some error\n")
    assert caplog.record_tuples == snapshot([("zabbix_cli", 20, "Some error")])
    assert caplog.records[0].funcName == snapshot("test_success")


def test_warning(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    warning("Some error")
    captured = capsys.readouterr()
    assert captured.err == snapshot("⚠ Some error\n")
    assert caplog.record_tuples == snapshot([("zabbix_cli", 30, "Some error")])
    assert caplog.records[0].funcName == snapshot("test_warning")


def test_error(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    error("Some error")
    captured = capsys.readouterr()
    assert captured.err == snapshot("✗ ERROR: Some error\n")
    assert caplog.record_tuples == snapshot([("zabbix_cli", 40, "Some error")])
    assert caplog.records[0].funcName == snapshot("test_error")


def test_exit_err_table(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture, state: State
) -> None:
    assert state.is_config_loaded is True
    state.config.app.output_format = OutputFormat.TABLE
    caplog.set_level(logging.INFO)
    with pytest.raises(SystemExit):
        exit_err("Some error")
    captured = capsys.readouterr()
    assert captured.err == snapshot("✗ ERROR: Some error\n")
    assert captured.out == snapshot("")


def test_exit_err_json(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture, state: State
) -> None:
    state.config.app.output_format = OutputFormat.JSON
    with pytest.raises(SystemExit):
        exit_err("Some error")
    captured = capsys.readouterr()
    assert captured.err == snapshot("✗ ERROR: Some error\n")
    assert captured.out == snapshot(
        """\
{
  "message": "Some error",
  "errors": [],
  "return_code": "Error",
  "result": null
}
"""
    )
    assert caplog.record_tuples == snapshot([("zabbix_cli", 40, "Some error")])


def test_exit_err_json_with_errors(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture, state: State
) -> None:
    outer_exc = TypeError("Outer exception")
    outer_exc.__cause__ = ValueError("Inner exception")

    state.config.app.output_format = OutputFormat.JSON
    with pytest.raises(SystemExit):
        exit_err("Some error", exception=outer_exc)
    captured = capsys.readouterr()
    assert captured.err == snapshot("✗ ERROR: Some error\n")
    assert captured.out == snapshot(
        """\
{
  "message": "Some error",
  "errors": [
    "Outer exception",
    "Inner exception"
  ],
  "return_code": "Error",
  "result": null
}
"""
    )
    assert caplog.record_tuples == snapshot([("zabbix_cli", 40, "Some error")])


def test_exit_err_json_with_zabbix_api_request_error(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture, state: State
) -> None:
    api_resp = ZabbixAPIResponse(
        jsonrpc="2.0",
        result=None,
        id=1,
        error=ZabbixAPIError(
            code=-123, message="API response error", data='{"foo": 42}'
        ),
    )
    outer_exc = ZabbixAPIException("Outer exception")
    outer_exc.__cause__ = ZabbixAPIRequestError(
        "Inner exception", api_response=api_resp
    )

    state.config.app.output_format = OutputFormat.JSON
    with pytest.raises(SystemExit):
        exit_err("Some error", exception=outer_exc)
    captured = capsys.readouterr()
    assert captured.err == snapshot("✗ ERROR: Some error\n")
    assert captured.out == snapshot(
        """\
{
  "message": "Some error",
  "errors": [
    "Outer exception",
    "Inner exception",
    "(-123) API response error {\\"foo\\": 42}"
  ],
  "return_code": "Error",
  "result": null
}
"""
    )
    assert caplog.record_tuples == snapshot([("zabbix_cli", 40, "Some error")])
