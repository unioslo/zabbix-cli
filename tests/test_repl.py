from __future__ import annotations

from inline_snapshot import snapshot
from zabbix_cli.repl.repl import _help_internal  # pyright: ignore[reportPrivateUsage]


def test_help_internal() -> None:
    assert _help_internal() == snapshot(
        """\
REPL help:

  External Commands:
    prefix external commands with "!"

  Internal Commands:
    prefix internal commands with ":"
    :exit, :q, :quit  exits the repl
    :?, :h, :help     displays general help information
"""
    )
