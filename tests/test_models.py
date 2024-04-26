from __future__ import annotations

from typing import List

import pytest
from pydantic import Field

from zabbix_cli.models import MetaKey
from zabbix_cli.models import TableRenderable


@pytest.mark.parametrize(
    "header, expect",
    [
        pytest.param(None, "Foo", id="None is default"),
        pytest.param("", "Foo", id="Empty string is default"),
        ("Foo Header", "Foo Header"),
    ],
)
def test_table_renderable_metakey_header(header: str, expect: str) -> None:
    class TestTableRenderable(TableRenderable):
        foo: str = Field(..., json_schema_extra={MetaKey.HEADER: header})

    t = TestTableRenderable(foo="bar")
    assert t.__cols__() == [expect]
    assert t.__rows__() == [["bar"]]
    assert t.__cols_rows__() == ([expect], [["bar"]])


@pytest.mark.parametrize(
    "content, join_char, expect",
    [
        (["a", "b", "c"], ",", ["a,b,c"]),
        (["a", "b", "c"], "|", ["a|b|c"]),
        (["a", "b", "c"], " ", ["a b c"]),
        (["a", "b", "c"], "", ["abc"]),
        # Test empty list
        ([], ",", [""]),
        ([], "|", [""]),
        ([], " ", [""]),
        ([], "", [""]),
    ],
)
def test_table_renderable_metakey_join_char(
    content: List[str], join_char: str, expect: str
) -> None:
    class TestTableRenderable(TableRenderable):
        foo: List[str] = Field(..., json_schema_extra={MetaKey.JOIN_CHAR: join_char})

    t = TestTableRenderable(foo=content)
    assert t.__rows__() == [expect]


def test_all_metakeys() -> None:
    class TestTableRenderable(TableRenderable):
        foo: List[str] = Field(
            ...,
            json_schema_extra={MetaKey.JOIN_CHAR: "|", MetaKey.HEADER: "Foo Header"},
        )

    t = TestTableRenderable(foo=["foo", "bar"])
    assert t.__cols__() == ["Foo Header"]
    assert t.__rows__() == [["foo|bar"]]
    assert t.__cols_rows__() == (["Foo Header"], [["foo|bar"]])
