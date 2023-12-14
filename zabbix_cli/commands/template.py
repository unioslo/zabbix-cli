"""Commands that interact with the application itself."""
from __future__ import annotations

from typing import Optional
from typing import TYPE_CHECKING

import typer

from zabbix_cli.app import app
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.prompts import str_prompt


if TYPE_CHECKING:
    from zabbix_cli.models import ColsType  # noqa: F401
    from zabbix_cli.models import RowsType  # noqa: F401


HELP_PANEL = "Template"


@app.command("link_template_to_host", rich_help_panel=HELP_PANEL)
def link_template_to_host(
    ctx: typer.Context,
    templates: Optional[str] = typer.Argument(
        None, help="Template names or IDs. Separate values with commas."
    ),
    hostnames: Optional[str] = typer.Argument(
        None, help="Hostnames or IDs. Separate values with commas."
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail if any hosts or templates aren't found. Should not be used with wildcard names.",
    ),
) -> None:
    """Link template(s) to host(s)"""
    if not templates:
        templates = str_prompt("Template(s)")
    if not hostnames:
        hostnames = str_prompt("Host(s)")

    tpls = [t.strip() for t in templates.split(",")]
    if not tpls:
        exit_err("At least one template name/ID is required.")

    hnames = [h.strip() for h in hostnames.split(",")]
    if not hnames:
        exit_err("At least one host name/ID is required.")

    hosts = app.state.client.get_hosts(*hnames)  # search=False?
    templates = app.state.client.get_templates(*tpls)
    if strict:
        if not hosts:
            exit_err(f"No hosts found matching {hnames}")
        elif len(hosts) != len(hnames):
            exit_err(f"Found {len(hosts)} hosts, expected {len(hnames)}")
        elif not templates:
            exit_err(f"No templates found matching {tpls}")
    app.state.client.link_templates_to_hosts(templates, hosts)


@app.command("unlink_template_from_host", rich_help_panel=HELP_PANEL)
def unlink_template_from_host(ctx: typer.Context) -> None:
    pass


@app.command("show_template", rich_help_panel=HELP_PANEL)
def show_template(ctx: typer.Context) -> None:
    pass


@app.command("show_templates", rich_help_panel=HELP_PANEL)
def show_templates(ctx: typer.Context) -> None:
    pass
