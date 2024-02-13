"""Commands that interact with the application itself."""
from __future__ import annotations

from typing import List
from typing import Literal
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union

import typer
from pydantic import Field
from pydantic import model_serializer

from zabbix_cli.app import app
from zabbix_cli.app import Example
from zabbix_cli.models import AggregateResult
from zabbix_cli.models import ColsRowsType
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.console import success
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import HostGroup
from zabbix_cli.pyzabbix.types import Template
from zabbix_cli.pyzabbix.types import TemplateGroup
from zabbix_cli.utils.args import parse_list_arg


if TYPE_CHECKING:
    from zabbix_cli.models import ColsType  # noqa: F401
    from zabbix_cli.models import RowsType  # noqa: F401


HELP_PANEL = "Template"


# TODO: we do share these models between different commands, but they are impacting
# the startup time of the application. Can we inline them in the commands?
class LinkTemplateResult(TableRenderable):
    """Result type for `(un)link_template_{to,from}_host` command."""

    templates: List[Template] = []
    hosts: List[Host] = []
    groups: Union[List[HostGroup], List[TemplateGroup]] = Field(default_factory=list)
    action: Literal["link", "unlink", "unlink_clear"]

    @model_serializer
    def ser_model(self) -> dict:
        # V2 has no JSON output for this beyond message and status code
        # so we are free to invent our own for new and legacy formats
        return {
            # Custom format here instead of dumping all fields of each object
            "action": self.action,
            "templates": [
                {
                    "name": template.name,
                    "templateid": template.templateid,
                }
                for template in self.templates
            ],
            "hosts": [
                {"host": host.host, "hostid": host.hostid} for host in self.hosts
            ],
            "groups": [
                {"name": group.name, "groupid": group.groupid} for group in self.groups
            ],
        }


class LinkTemplateHostResult(LinkTemplateResult):
    def __cols_rows__(self) -> ColsRowsType:
        cols = ["Template", "Hosts"]
        hostnames = ", ".join([h.host for h in self.hosts])
        rows = [[template.host, hostnames] for template in self.templates]  # type: RowsType
        return cols, rows


class LinkTemplateGroupResult(LinkTemplateResult):
    def __cols_rows__(self) -> ColsRowsType:
        cols = ["Groups", "Templates"]
        rows = []  # type: RowsType
        tmp_names = "\n".join([t.host for t in self.templates])
        for group in self.groups:
            rows.append([group.name, tmp_names])
        return cols, rows


def _handle_hostnames_args(
    hostnames_or_ids: str | None,
    strict: bool = False,
) -> list[Host]:
    if not hostnames_or_ids:
        hostnames_or_ids = str_prompt("Host(s)")

    host_args = [h.strip() for h in hostnames_or_ids.split(",")]
    if not host_args:
        exit_err("At least one host name/ID is required.")

    hosts = app.state.client.get_hosts(*host_args, search=True)
    if not hosts:
        exit_err(f"No hosts found matching {hostnames_or_ids}")
    if strict and len(hosts) != len(host_args):
        exit_err(f"Found {len(hosts)} hosts, expected {len(host_args)}")
    return hosts


def _handle_hostgroups_args(
    hgroup_names_or_ids: str | None,
    strict: bool = False,
) -> list[HostGroup]:
    if not hgroup_names_or_ids:
        hgroup_names_or_ids = str_prompt("Host group(s)")

    hg_args = [h.strip() for h in hgroup_names_or_ids.split(",")]
    if not hg_args:
        exit_err("At least one host group name/ID is required.")

    hostgroups = app.state.client.get_hostgroups(*hg_args, search=True)
    if not hostgroups:
        exit_err(f"No host groups found matching {hgroup_names_or_ids}")
    if strict and len(hostgroups) != len(hg_args):
        exit_err(f"Found {len(hostgroups)} host groups, expected {len(hostgroups)}")
    return hostgroups


def _handle_templategroup_args(
    tgroup_names_or_ids: str | None,
    strict: bool = False,
) -> list[TemplateGroup]:
    if not tgroup_names_or_ids:
        tgroup_names_or_ids = str_prompt("Template group(s)")

    tg_args = [h.strip() for h in tgroup_names_or_ids.split(",")]
    if not tg_args:
        exit_err("At least one template group name/ID is required.")

    templategroups = app.state.client.get_templategroups(*tg_args, search=True)
    if not templategroups:
        exit_err(f"No template groups found matching {tgroup_names_or_ids}")
    if strict and len(templategroups) != len(tg_args):
        exit_err(
            f"Found {len(templategroups)} template groups, expected {len(templategroups)}"
        )
    return templategroups


def _handle_template_arg(
    template_names_or_ids: str | None, strict: bool = False
) -> list[Template]:
    if not template_names_or_ids:
        template_names_or_ids = str_prompt("Template(s)")

    template_args = [t.strip() for t in template_names_or_ids.split(",")]
    if not template_args:
        exit_err("At least one template name/ID is required.")

    templates = app.state.client.get_templates(*template_args)
    if not templates:
        exit_err(f"No templates found matching {template_names_or_ids}")
    if strict and len(templates) != len(template_args):
        exit_err(f"Found {len(templates)} templates, expected {len(template_args)}")
    return templates


ARG_TEMPLATE_NAMES_OR_IDS = typer.Argument(
    None, help="Template names or IDs. Separate values with commas."
)
ARG_HOSTNAMES_OR_IDS = typer.Argument(
    None, help="Hostnames or IDs. Separate values with commas."
)
ARG_GROUP_NAMES_OR_IDS = typer.Argument(
    None, help="Host/template group names or IDs. Separate values with commas."
)


@app.command(
    "link_template_to_host",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Link one template to one host",
            "link_template_to_host 'Apache by HTTP' foo.example.com",
        ),
        Example(
            "Link many templates to many hosts",
            "link_template_to_host 'Apache by HTTP,HAProxy by Zabbix agent' foo.example.com,bar.example.com",
        ),
        Example(
            "Link one template to all hosts",
            "link_template_to_host 'Apache by HTTP' '*'",
        ),
        Example(
            "Link many templates to all hosts",
            "link_template_to_host 'Apache by HTTP,HAProxy by Zabbix agent' '*'",
        ),
        Example(
            "Link all templates to all hosts [red](use with caution!)[/red]",
            "link_template_to_host '*' '*'",
        ),
    ],
)
def link_template_to_host(
    ctx: typer.Context,
    template_names_or_ids: Optional[str] = ARG_TEMPLATE_NAMES_OR_IDS,
    hostnames_or_ids: Optional[str] = ARG_HOSTNAMES_OR_IDS,
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail if any hosts or templates aren't found. Should not be used in conjunction with wildcards.",
    ),
) -> None:
    """Link template(s) to host(s)."""
    templates = _handle_template_arg(template_names_or_ids, strict)
    hosts = _handle_hostnames_args(hostnames_or_ids, strict)
    with app.state.console.status("Linking templates..."):
        app.state.client.link_templates_to_hosts(templates, hosts)
    render_result(
        LinkTemplateHostResult(
            templates=templates,
            hosts=hosts,
            action="link",
        )
    )
    success(f"Linked {len(templates)} templates to {len(hosts)} hosts.")


@app.command(
    "unlink_template_from_host",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Unlink one template from one host",
            "unlink_template_from_host 'Apache by HTTP' foo.example.com",
        ),
        Example(
            "Unlink many templates from many hosts",
            "unlink_template_from_host 'Apache by HTTP,HAProxy by Zabbix agent' foo.example.com,bar.example.com",
        ),
        Example(
            "Unlink one template from all hosts",
            "unlink_template_from_host 'Apache by HTTP' '*'",
        ),
        Example(
            "Unlink many templates from all hosts",
            "unlink_template_from_host 'Apache by HTTP,HAProxy by Zabbix agent' '*'",
        ),
        Example(
            "Unlink all templates from all hosts [red](use with caution!)[/red]",
            "unlink_template_from_host '*' '*'",
        ),
    ],
)
def unlink_template_from_host(
    ctx: typer.Context,
    template_names_or_ids: Optional[str] = ARG_TEMPLATE_NAMES_OR_IDS,
    hostnames_or_ids: Optional[str] = ARG_HOSTNAMES_OR_IDS,
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail if any hosts or templates aren't found. Should not be used in conjunction with wildcards.",
    ),
) -> None:
    """Unlinks and clears template(s) from host(s)."""
    templates = _handle_template_arg(template_names_or_ids, strict)
    hosts = _handle_hostnames_args(hostnames_or_ids, strict)
    with app.state.console.status("Unlinking templates..."):
        app.state.client.unlink_templates_from_hosts(templates, hosts)
    # TODO: find out which templates were actually unlinked
    # Right now we just assume all of them were.
    # host.massremove does not return anything useful in this regard...
    render_result(
        LinkTemplateHostResult(
            templates=templates,
            hosts=hosts,
            action="unlink_clear",
        )
    )
    success(f"Unlinked and cleared {len(templates)} templates from {len(hosts)} hosts.")


# Changed in V3: Changed name to reflect introduction of template groups in >=6.2
@app.command("link_template_to_group", rich_help_panel=HELP_PANEL)
@app.command(
    # old name for backwards compatibility
    "link_template_to_hostgroup",
    hidden=True,
    rich_help_panel=HELP_PANEL,
)
def link_template_to_group(
    ctx: typer.Context,
    template_names_or_ids: Optional[str] = ARG_TEMPLATE_NAMES_OR_IDS,
    group_names_or_ids: Optional[str] = ARG_GROUP_NAMES_OR_IDS,
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail if any host groups or templates aren't found. Should not be used in conjunction with wildcards.",
    ),
) -> None:
    """Link template(s) to group(s).

    [bold]NOTE:[/] Group arguments are interpreted as template groups in >= 6.2,
    otherwise as host groups.
    """
    groups: Union[List[HostGroup], List[TemplateGroup]]
    if app.state.client.version.release >= (6, 2, 0):
        groups = _handle_templategroup_args(group_names_or_ids, strict)
    else:
        groups = _handle_hostgroups_args(group_names_or_ids, strict)

    templates = _handle_template_arg(template_names_or_ids, strict)

    with app.state.console.status("Linking templates..."):
        app.state.client.link_templates_to_groups(templates, groups)
    render_result(
        LinkTemplateGroupResult(
            templates=templates,
            groups=groups,
            action="link",
        )
    )
    success(f"Linked {len(templates)} templates to {len(groups)} groups.")


# Changed in V3: Changed name to reflect introduction of template groups in >=6.2
@app.command("unlink_template_from_group", rich_help_panel=HELP_PANEL)
@app.command(
    # old name for backwards compatibility
    "unlink_template_from_hostgroup",
    hidden=True,
    rich_help_panel=HELP_PANEL,
)
def unlink_template_from_group(
    ctx: typer.Context,
    template_names_or_ids: Optional[str] = ARG_TEMPLATE_NAMES_OR_IDS,
    group_names_or_ids: Optional[str] = ARG_GROUP_NAMES_OR_IDS,
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail if any host groups or templates aren't found. Should not be used in conjunction with wildcards.",
    ),
    # TODO: add toggle for NOT clearing when unlinking?
) -> None:
    """Unlink and clear template(s) from host/template group(s)."""
    groups: Union[List[HostGroup], List[TemplateGroup]]
    if app.state.client.version.release >= (6, 2, 0):
        groups = _handle_templategroup_args(group_names_or_ids, strict)
    else:
        groups = _handle_hostgroups_args(group_names_or_ids, strict)

    templates = _handle_template_arg(template_names_or_ids, strict)

    with app.state.console.status("Unlinking templates..."):
        app.state.client.unlink_templates_from_groups(templates, groups)
    render_result(
        LinkTemplateGroupResult(
            templates=templates,
            groups=groups,
            action="unlink_clear",
        )
    )
    success(f"Unlinked and cleared {len(templates)} templates to {len(groups)} groups.")


@app.command("show_template", rich_help_panel=HELP_PANEL)
def show_template(
    ctx: typer.Context,
    template_name: Optional[str] = typer.Argument(
        None, help="Template name or ID. Names support wildcards."
    ),
) -> None:
    """Show a template."""
    if not template_name:
        template_name = str_prompt("Template")
    template = app.state.client.get_template(
        template_name,
        select_hosts=True,
        select_templates=True,
        select_parent_templates=True,
    )
    render_result(template)


@app.command("show_templates", rich_help_panel=HELP_PANEL)
def show_templates(
    ctx: typer.Context,
    templates: str = typer.Argument(
        "*",
        help="Template name(s) or ID(s). Comma-separated.",
    ),
) -> None:
    """Show one or more templates.

    Shows all templates by default. The template name can be a pattern containing wildcards.
    Names and IDs cannot be mixed."""
    args = parse_list_arg(templates)
    tmpls = app.state.client.get_templates(
        *args,
        select_hosts=True,
        select_templates=True,
        select_parent_templates=True,
    )
    render_result(AggregateResult(result=tmpls))


@app.command("show_items", rich_help_panel=HELP_PANEL)
def show_items(
    ctx: typer.Context,
    template_name: Optional[str] = typer.Argument(
        None, help="Template name or ID. Names support wildcards."
    ),
) -> None:
    """Show items that belong to a template."""
    if not template_name:
        template_name = str_prompt("Template")
    template = app.state.client.get_template(template_name)
    items = app.state.client.get_items(templates=[template])
    render_result(AggregateResult(result=items))


class ExtendTemplateGroupResult(TableRenderable):
    source: str
    destination: List[str]
    templates: List[str]

    @classmethod
    def from_result(
        cls,
        src_group: Union[HostGroup, TemplateGroup],
        dest_group: Union[List[HostGroup], List[TemplateGroup]],
        templates: List[Template],
    ) -> ExtendTemplateGroupResult:
        return cls(
            source=src_group.name,
            destination=[grp.name for grp in dest_group],
            templates=[t.host for t in templates],
        )


@app.command("extend_templategroup", rich_help_panel=HELP_PANEL)
def show_triggers(
    ctx: typer.Context,
    src_group: str = typer.Argument(..., help="Group to get templates from."),
    dest_group: str = typer.Argument(
        ..., help="Group(s) to add templates to. Comma-separated. Wildcards supported."
    ),
    dryrun: bool = typer.Option(
        False,
        "--dryrun",
        help="Show groups and templates without copying.",
    ),
) -> None:
    """Add all templates from a group to other group(s).

    Interprets the source group as a template group in >= 6.2, otherwise as a host group."""
    dest_arg = parse_list_arg(dest_group)

    src: Union[HostGroup, TemplateGroup]
    dest: Union[List[HostGroup], List[TemplateGroup]]
    if app.state.client.version.release > (6, 2, 0):
        src = app.state.client.get_templategroup(src_group, select_templates=True)
        dest = app.state.client.get_templategroups(
            *dest_arg, select_templates=True, search=True
        )
    else:
        src = app.state.client.get_hostgroup(src_group, select_templates=True)
        dest = app.state.client.get_hostgroups(
            *dest_arg, select_templates=True, search=True
        )

    if not src.templates:
        exit_err(f"No templates found in {src_group!r}")
    if not dest:
        exit_err(f"No groups found matching {dest_group!r}")

    if not dryrun:
        app.state.client.add_templates_to_groups(src.templates, dest)
        success(
            f"Copied {len(src.templates)} templates from {src.name} to {len(dest)} groups."
        )
    else:
        info("Would copy the following templates:")
    render_result(ExtendTemplateGroupResult.from_result(src, dest, src.templates))
