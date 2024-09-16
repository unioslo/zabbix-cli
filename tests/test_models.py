from __future__ import annotations

import logging
from typing import List

import pytest
from inline_snapshot import snapshot
from pydantic import BaseModel
from pydantic import Field
from pytest import LogCaptureFixture
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


def test_rows_with_unknown_base_model(caplog: LogCaptureFixture) -> None:
    """Test that we log when we try to render a BaseModel
    instance that does not inherit from TableRenderable."""

    class FooModel(BaseModel):
        foo: str
        bar: int
        baz: float
        qux: List[str]

    class TestTableRenderable(TableRenderable):
        foo: FooModel

    t = TestTableRenderable(foo=FooModel(foo="foo", bar=1, baz=1.0, qux=["a", "b"]))

    caplog.set_level(logging.WARNING)

    # Non-TableRenderable models are rendered as JSON
    assert t.__rows__() == snapshot(
        [
            [
                """\
{
  "foo": "foo",
  "bar": 1,
  "baz": 1.0,
  "qux": [
    "a",
    "b"
  ]
}\
"""
            ]
        ]
    )

    # Check that we logged info on what happened and how we got there
    assert caplog.record_tuples == snapshot(
        [("zabbix_cli", 30, "Cannot render FooModel as a table.")]
    )
    record = caplog.records[0]
    assert record.funcName == "__rows__"
    assert record.stack_info is not None
    assert "test_rows_with_unknown_base_model" in record.stack_info
