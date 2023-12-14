"""Commands that interact with the application itself."""
from __future__ import annotations

from typing import List
from typing import Optional
from typing import TYPE_CHECKING

import typer
from pydantic import model_serializer

from zabbix_cli.app import app
from zabbix_cli.models import ColsRowsType
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import Template


if TYPE_CHECKING:
    from zabbix_cli.models import ColsType  # noqa: F401
    from zabbix_cli.models import RowsType  # noqa: F401


HELP_PANEL = "Template"


class LinkTemplateResult(TableRenderable):
    """Result type for `link_template_to_host` command."""

    templates: List[Template] = []
    hosts: List[Host] = []

    @model_serializer
    def ser_model(self) -> dict:
        # V2 has no JSON output for this beyond message and status code
        # so we are free to invent our own for new and legacy formats
        return {
            # Custom format here instead of dumping all fields of each object
            "templates": [
                {
                    "host": template.host,
                    "name": template.name,
                    "templateid": template.templateid,
                }
                for template in self.templates
            ],
            "hosts": [
                {"host": host.host, "hostid": host.hostid} for host in self.hosts
            ],
        }

    def _table_cols_rows(self) -> ColsRowsType:
        cols = ["Template", "Hosts"]
        rows = []
        hostnames = ", ".join([h.host for h in self.hosts])
        for template in self.templates:
            rows.append([template.name_or_host, hostnames])
        return cols, rows


@app.command("link_template_to_host", rich_help_panel=HELP_PANEL)
def link_template_to_host(
    ctx: typer.Context,
    template_names_or_ids: Optional[str] = typer.Argument(
        None, help="Template names or IDs. Separate values with commas."
    ),
    hostnames_or_ids: Optional[str] = typer.Argument(
        None, help="Hostnames or IDs. Separate values with commas."
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail if any hosts or templates aren't found. Should not be used with wildcard names.",
    ),
) -> None:
    """Link template(s) to host(s).


    [bold underline]Examples[/]

    To link one template to all hosts: `link_template_to_host <template> '*'`

    """
    # NOTE: Type safety necessitates a lot of similarly named variables:
    # template_names_or_ids, template_args, templates
    # hostnames_or_ids, host_args, hosts
    if not template_names_or_ids:
        template_names_or_ids = str_prompt("Template(s)")
    if not hostnames_or_ids:
        hostnames_or_ids = str_prompt("Host(s)")

    template_args = [t.strip() for t in template_names_or_ids.split(",")]
    if not template_args:
        exit_err("At least one template name/ID is required.")

    host_args = [h.strip() for h in hostnames_or_ids.split(",")]
    if not host_args:
        exit_err("At least one host name/ID is required.")

    hosts = app.state.client.get_hosts(*host_args)  # search=False?
    templates = app.state.client.get_templates(*template_args)
    if strict:
        if not hosts:
            exit_err(f"No hosts found matching {hostnames_or_ids}")
        elif len(hosts) != len(host_args):
            exit_err(f"Found {len(hosts)} hosts, expected {len(host_args)}")
        elif not templates:
            exit_err(f"No templates found matching {template_names_or_ids}")
        elif len(templates) != len(template_args):
            exit_err(f"Found {len(templates)} templates, expected {len(template_args)}")
    app.state.client.link_templates_to_hosts(templates, hosts)
    info(f"Linked {len(templates)} templates to {len(hosts)} hosts.")
    render_result(
        LinkTemplateResult(
            templates=templates,
            hosts=hosts,
        )
    )


@app.command("unlink_template_from_host", rich_help_panel=HELP_PANEL)
def unlink_template_from_host(ctx: typer.Context) -> None:
    pass


@app.command("show_template", rich_help_panel=HELP_PANEL)
def show_template(ctx: typer.Context) -> None:
    pass


@app.command("show_templates", rich_help_panel=HELP_PANEL)
def show_templates(ctx: typer.Context) -> None:
    pass
