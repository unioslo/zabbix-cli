from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import TYPE_CHECKING

import typer
from pydantic import computed_field
from pydantic import Field
from pydantic import field_serializer

from zabbix_cli.app import app
from zabbix_cli.app import Example
from zabbix_cli.commands.template import HELP_PANEL  # combine with template commands
from zabbix_cli.models import AggregateResult
from zabbix_cli.models import Result
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import error
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.types import Template
from zabbix_cli.utils.args import parse_list_arg
from zabbix_cli.utils.args import UsergroupPermission


if TYPE_CHECKING:
    from zabbix_cli.models import RowsType


@app.command(
    "create_templategroup",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Create a template group with default user group permissions",
            "zabbix-cli create_templategroup 'My Template Group'",
        ),
        Example(
            "Create a template group with specific RO and RW groups",
            "zabbix-cli create_templategroup 'My Template Group' --ro-groups users --rw-groups admins",
        ),
        Example(
            "Create a template group with no user group permissions",
            "zabbix-cli create_templategroup 'My Template Group' --no-usergroup-permissions",
        ),
    ],
)
def create_templategroup(
    ctx: typer.Context,
    templategroup: str = typer.Argument(..., help="Name of the group."),
    rw_groups: Optional[str] = typer.Option(
        None,
        help="User group(s) to give read/write permissions. Comma-separated.",
    ),
    ro_groups: Optional[str] = typer.Option(
        None,
        help="User group(s) to give read-only permissions. Comma-separated.",
    ),
    no_usergroup_permissions: bool = typer.Option(
        False,
        "--no-usergroup-permissions",
        help="Do not assign user group permissions.",
    ),
) -> None:
    """Create a new template group.

    Assigns permissions for user groups defined in configuration file
    unless --no-usergroup-permissions is specified.

    The user groups can be overridden with the --rw-groups and --ro-groups.
    """
    groupid = app.state.client.create_templategroup(templategroup)

    app_config = app.state.config.app

    rw_grps = []  # type: list[str]
    ro_grps = []  # type: list[str]
    if not no_usergroup_permissions:
        rw_grps = parse_list_arg(rw_groups) or app_config.default_admin_usergroups
        ro_grps = parse_list_arg(ro_groups) or app_config.default_create_user_usergroups

    try:
        # Admin group(s) gets Read/Write
        for usergroup in rw_grps:
            app.state.client.update_usergroup_rights(
                usergroup,
                [templategroup],
                UsergroupPermission.READ_WRITE,
                hostgroup=False,
            )
            info(f"Assigned Read/Write permission for user group {usergroup!r}")
        # Default group(s) gets Read
        for usergroup in ro_grps:
            app.state.client.update_usergroup_rights(
                usergroup,
                [templategroup],
                UsergroupPermission.READ_ONLY,
                hostgroup=False,
            )
            info(f"Assigned Read-only permission for user group {usergroup!r}")

    except Exception as e:
        error(f"Failed to assign permissions to template group {templategroup!r}: {e}")
        info("Deleting template group...")
        app.state.client.delete_templategroup(groupid)

    render_result(
        Result(message=f"Created template group {templategroup} ({groupid}).")
    )


@app.command("delete_templategroup", rich_help_panel=HELP_PANEL)
def delete_templategroup(
    ctx: typer.Context,
    templategroup: str = typer.Argument(..., help="Name of the group to delete."),
) -> None:
    """Delete a template group."""
    app.state.client.delete_templategroup(templategroup)
    render_result(Result(message=f"Deleted template group {templategroup!r}."))


class ShowTemplateGroupResult(TableRenderable):
    """Result type for templategroup."""

    groupid: str = Field(..., json_schema_extra={"header": "Group ID"})
    name: str
    templates: List[Template] = []
    show_templates: bool = Field(True, exclude=True)

    @computed_field()  # type: ignore # mypy bug
    @property
    def template_count(self) -> int:
        return len(self.templates)

    @field_serializer("templates")
    def templates_serializer(self, value: List[Template]) -> List[Dict[str, Any]]:
        if self.show_templates:
            return [t.model_dump(mode="json") for t in value]
        return []

    def __rows__(self) -> RowsType:
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
    render_result(ShowTemplateGroupResult(**tg.model_dump()))


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
                ShowTemplateGroupResult(**tg.model_dump(), show_templates=templates)
                for tg in templategroups
            ]
        )
    )
