from __future__ import annotations

from inline_snapshot import snapshot
from zabbix_cli.bulk import BulkRunnerMode
from zabbix_cli.commands.cli_configwizard import get_enum_attr_docs
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
