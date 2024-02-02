from __future__ import annotations

from zabbix_cli._patches import click_repl
from zabbix_cli._patches import typer


def patch_all() -> None:
    """Apply all patches to all modules."""
    typer.patch()
    click_repl.patch()
