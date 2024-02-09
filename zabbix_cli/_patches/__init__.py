from __future__ import annotations

from zabbix_cli._patches import typer


def patch_all() -> None:
    """Apply all patches to all modules."""
    typer.patch()
    # NOTE: we patch click_repl only when we actually launch the REPL
    # See: zabbix_cli.main.start_repl
