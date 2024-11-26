"""Commands for managing media."""

from __future__ import annotations

import typer

from zabbix_cli.app import app
from zabbix_cli.output.render import render_result

HELP_PANEL = "Media"


@app.command("show_media_types", rich_help_panel=HELP_PANEL)
def show_media_types(ctx: typer.Context) -> None:
    """Show all available media types."""
    from zabbix_cli.models import AggregateResult

    media_types = app.state.client.get_mediatypes()

    render_result(AggregateResult(result=media_types))
