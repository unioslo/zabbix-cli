from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import typer
from pydantic import computed_field
from pydantic import Field
from pydantic import field_serializer

from zabbix_cli.app import app
from zabbix_cli.models import AggregateResult
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.types import Template


HELP_PANEL = "Template Group"


class TemplateGroupResult(TableRenderable):
    """Result type for templategroup."""

    groupid: str = Field(..., json_schema_extra={"header": "Group ID"})
    name: str
    templates: List[Template] = []
    show_templates: bool = Field(True, exclude=True)

    @computed_field()
    @property
    def template_count(self) -> int:
        return len(self.templates)

    @field_serializer("templates")
    def templates_serializer(self, value: List[Template]) -> List[Dict[str, Any]]:
        if self.show_templates:
            return [t.model_dump(mode="json") for t in value]
        return []

    def __rows__(self) -> list[list[str]]:
        tpls = self.templates if self.show_templates else []
        return [
            [
                self.groupid,
                self.name,
                "\n".join(str(t.host) for t in sorted(tpls, key=lambda t: t.host)),
                str(self.template_count),
            ]
        ]


@app.command("show_templategroup", rich_help_panel=HELP_PANEL)
def show_templategroup(
    ctx: typer.Context,
    templategroup: Optional[str] = typer.Argument(
        None, help="Name of the group to show. Wildcards supported."
    ),
    templates: bool = typer.Option(
        True,
        "--templates/--no-templates",
        help="Show/hide templates associated with the group.",
    ),
) -> None:
    """Show details for all template groups."""
    if not templategroup:
        templategroup = str_prompt("Template group")
    tg = app.state.client.get_templategroup(
        templategroup, search=True, select_templates=templates
    )
    render_result(TemplateGroupResult(**tg.model_dump()))


@app.command("show_templategroups", rich_help_panel=HELP_PANEL)
def show_templategroups(
    ctx: typer.Context,
    templates: bool = typer.Option(
        True,
        "--templates/--no-templates",
        help="Show/hide templates associated with each group.",
    ),
) -> None:
    """Show details for all template groups."""
    try:
        templategroups = app.state.client.get_templategroups(select_templates=True)
    except Exception as e:
        exit_err(f"Failed to get all template groups: {e}")

    # Sort by name before rendering
    templategroups = sorted(templategroups, key=lambda tg: tg.name)

    render_result(
        AggregateResult(
            result=[
                TemplateGroupResult(**tg.model_dump(), show_templates=templates)
                for tg in templategroups
            ]
        )
    )
