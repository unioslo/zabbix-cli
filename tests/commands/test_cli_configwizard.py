from __future__ import annotations

from inline_snapshot import snapshot
from zabbix_cli.bulk import BulkRunnerMode
from zabbix_cli.commands.cli_configwizard import get_enum_attr_docs
from zabbix_cli.commands.cli_configwizard import is_enum_type
from zabbix_cli.config.constants import OutputFormat


def test_get_enum_attr_docs():
    """Test docstring retrieval for enum attributes."""
    assert get_enum_attr_docs(BulkRunnerMode) == snapshot(
        {
            BulkRunnerMode.STRICT: "Stop on first error.",
            BulkRunnerMode.CONTINUE: "Continue on errors, report at end.",
            BulkRunnerMode.SKIP: "Skip lines with errors. No reporting.",
        }
    )
    assert get_enum_attr_docs(OutputFormat) == snapshot(
        {
            OutputFormat.JSON: "JSON-serialized output.",
            OutputFormat.TABLE: "Rich terminal table output.",
        }
    )


def test_is_enum():
    """Test if an object is an enum type."""

    assert is_enum_type(BulkRunnerMode)
    assert is_enum_type(OutputFormat)
    assert not is_enum_type(str)
    assert not is_enum_type(int)
    assert not is_enum_type(list)
    assert not is_enum_type(dict)
    assert not is_enum_type(tuple)

    # Instances
    assert not is_enum_type(BulkRunnerMode.STRICT)
    assert not is_enum_type(OutputFormat.JSON)
    assert not is_enum_type("test")
    assert not is_enum_type(123)
    assert not is_enum_type(["test"])
    assert not is_enum_type({"test": "test"})
    assert not is_enum_type((1, 2, 3))
