from __future__ import annotations

from typing import Any
from typing import Dict

import pytest
from pydantic import ValidationError
from zabbix_cli.pyzabbix.client import ParamsTypeSerializer
from zabbix_cli.pyzabbix.client import add_param
from zabbix_cli.pyzabbix.client import append_param
from zabbix_cli.pyzabbix.types import ParamsType


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


# TODO: write more extensive tests for params serialization and validation


def test_paramstype_serializer() -> None:
    params: ParamsType = {
        "output": "extend",
        "search": {"hostids": 2},
        "extra": None,
    }
    assert ParamsTypeSerializer.to_json_dict(params) == {
        "output": "extend",
        "search": {"hostids": 2},
        # None value stripped
    }


def test_paramstype_serializer_invalid() -> None:
    with pytest.raises(ValidationError):
        params: ParamsType = {
            "output": "extend",
            "search": {"hostids": object()},  # type: ignore
            "extra": None,
        }
        ParamsTypeSerializer.to_json_dict(params)
