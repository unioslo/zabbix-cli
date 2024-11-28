from __future__ import annotations

from zabbix_cli._patches import typer as typ


def patch_all() -> None:
    """Apply all patches to all modules."""
    typ.patch()
