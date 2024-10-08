from __future__ import annotations

import pytest
from zabbix_cli.commands.macro import fmt_macro_name
from zabbix_cli.exceptions import ZabbixCLIError

MARK_FAIL = pytest.mark.xfail(raises=ZabbixCLIError, strict=True)


@pytest.mark.parametrize(
    "name, expected",
    [
        pytest.param("my_macro", "{$MY_MACRO}"),
        pytest.param("MY_MACRO", "{$MY_MACRO}"),
        pytest.param("mY_maCrO", "{$MY_MACRO}"),
        pytest.param("foo123", "{$FOO123}"),
        pytest.param(" ", "", marks=MARK_FAIL),
        pytest.param("", "", marks=MARK_FAIL),
        pytest.param("{$}", "", marks=MARK_FAIL),
    ],
)
def test_fmt_macro_name(name: str, expected: str) -> None:
    assert fmt_macro_name(name) == expected
