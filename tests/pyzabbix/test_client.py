from __future__ import annotations

from typing import Any
from typing import Dict

import pytest
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
