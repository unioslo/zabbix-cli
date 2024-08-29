from __future__ import annotations

import logging
from typing import Any
from typing import Dict

import pytest
from inline_snapshot import snapshot
from zabbix_cli.output.console import RESERVED_EXTRA_KEYS
from zabbix_cli.output.console import debug
from zabbix_cli.output.console import debug_kv
from zabbix_cli.output.console import error
from zabbix_cli.output.console import get_extra_dict
from zabbix_cli.output.console import info
from zabbix_cli.output.console import success
from zabbix_cli.output.console import warning


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
    debug_kv("hello", "world")
    captured = capsys.readouterr()
    assert captured.err == snapshot(
        """\
hello               : world
"""
    )
    assert caplog.record_tuples == snapshot(
        [("zabbix_cli", 10, "hello               : world")]
    )


def test_debug(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    debug("Hello, world!")
    captured = capsys.readouterr()
    assert captured.err == snapshot(
        """\
Hello, world!
"""
    )
    assert caplog.record_tuples == snapshot([("zabbix_cli", 10, "Hello, world!")])


def test_info(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    info("Hello, world!")
    captured = capsys.readouterr()
    assert captured.err == snapshot(
        """\
! Hello, world!
"""
    )
    assert caplog.record_tuples == snapshot([("zabbix_cli", 20, "Hello, world!")])


def test_success(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    success("Hello, world!")
    captured = capsys.readouterr()
    assert captured.err == snapshot(
        """\
✓ Hello, world!
"""
    )
    assert caplog.record_tuples == snapshot([("zabbix_cli", 20, "Hello, world!")])


def test_warning(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    warning("Hello, world!")
    captured = capsys.readouterr()
    assert captured.err == snapshot(
        """\
⚠ Hello, world!
"""
    )
    assert caplog.record_tuples == snapshot([("zabbix_cli", 30, "Hello, world!")])


def test_error(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    error("Hello, world!")
    captured = capsys.readouterr()
    assert captured.err == snapshot(
        """\
✗ ERROR: Hello, world!
"""
    )
    assert caplog.record_tuples == snapshot([("zabbix_cli", 40, "Hello, world!")])
