"""Commands that interact with the application itself."""
from __future__ import annotations

from typing import List
from typing import Literal
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union

import typer

from zabbix_cli.app import app
from zabbix_cli.app import Example
from zabbix_cli.models import AggregateResult
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


class LinkTemplateHostResult(TableRenderable):
    templates: List[str]
    hosts: List[str]
    action: str

    @classmethod
    def from_results(
        cls,
        templates: List[Template],
        hosts: List[Host],
        action: Literal["Link", "Unlink", "Unlink and clear"],
    ) -> LinkTemplateHostResult:
        return cls(
            hosts=[h.host for h in hosts],
            templates=[t.host for t in templates],
            action=action,
        )

    # def __cols_rows__(self) -> ColsRowsType:
    #     cols = ["Template", "Hosts"]
    #     hostnames = ", ".join([h.host for h in self.hosts])
    #     rows = [[template.host, hostnames] for template in self.templates]  # type: RowsType
    #     return cols, rows


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

    tg_args = parse_list_arg(tgroup_names_or_ids)
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

    template_args = parse_list_arg(template_names_or_ids)
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
    render_result(LinkTemplateHostResult.from_results(templates, hosts, "Link"))
    success(f"Linked {len(templates)} templates to {len(hosts)} hosts.")


class LinkTemplateResult(TableRenderable):
    source: List[str]
    destination: List[str]
    action: str

    @classmethod
    def from_results(
        cls,
        source: List[Template],
        destination: List[Template],
        action: Literal["Link", "Unlink", "Unlink and clear"],
    ) -> LinkTemplateResult:
        return cls(
            source=[t.host for t in source],
            destination=[t.host for t in destination],
            action=action,
        )


@app.command(
    "link_template_to_template",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Link one template to one template",
            "link_template_to_template 'Apache by HTTP' foo_template",
        ),
        Example(
            "Link many templates to many templates",
            "link_template_to_template 'Apache by HTTP,HAProxy by Zabbix agent' foo_template,bar_template",
        ),
        Example(
            "Link all templates starting with 'Apache' to a template",
            "link_template_to_template 'Apache*' foo_template",
        ),
        Example(
            "Link all templates containing 'HTTP' to a subset of templates",
            "link_template_to_template '*HTTP*' 'Webserver-*'",
        ),
    ],
)
def link_template_to_template(
    ctx: typer.Context,
    source: Optional[str] = ARG_TEMPLATE_NAMES_OR_IDS,
    dest: Optional[str] = ARG_TEMPLATE_NAMES_OR_IDS,
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail if any templates aren't found. Should not be used in conjunction with wildcards.",
    ),
    dryrun: bool = typer.Option(
        False,
        "--dryrun",
        help="Do not actually link templates, just show what would be done.",
    ),
) -> None:
    """Link template(s) to templates(s).

    [b]NOTE:[/] Destination templates are the ones that are ultimately modified. Source templates remain unchanged.
    """
    source_templates = _handle_template_arg(source, strict)
    dest_templates = _handle_template_arg(dest, strict)
    if dryrun:
        info(
            f"Would link {len(source_templates)} templates to {len(dest_templates)} templates:"
        )
    else:
        with app.state.console.status("Linking templates..."):
            app.state.client.link_templates(source_templates, dest_templates)
    render_result(
        LinkTemplateResult.from_results(source_templates, dest_templates, "Link")
    )
    if not dryrun:
        success(
            f"Linked {len(source_templates)} templates to {len(dest_templates)} templates."
        )


@app.command(
    "unlink_template_from_template",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Unlink one template from one template",
            "unlink_template_from_template 'Apache by HTTP' foo_template",
        ),
        Example(
            "Unlink many templates from many templates",
            "unlink_template_from_template 'Apache by HTTP,HAProxy by Zabbix agent' foo_template,bar_template",
        ),
        Example(
            "Unlink all templates starting with 'Apache' from a template",
            "unlink_template_from_template 'Apache*' foo_template",
        ),
        Example(
            "Unlink all templates containing 'HTTP' from a subset of templates",
            "unlink_template_from_template '*HTTP*' 'Webserver-*'",
        ),
        Example(
            "Unlink a template without clearing items and triggers",
            "unlink_template_from_template --no-clear foo_template bar_template",
        ),
    ],
)
def unlink_template_from_template(
    ctx: typer.Context,
    source: Optional[str] = ARG_TEMPLATE_NAMES_OR_IDS,
    dest: Optional[str] = ARG_TEMPLATE_NAMES_OR_IDS,
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail if any templates aren't found. Should not be used in conjunction with wildcards.",
    ),
    clear: bool = typer.Option(
        True,
        "--clear/--no-clear",
        help="Unlink and clear templates.",
    ),
    dryrun: bool = typer.Option(
        False,
        "--dryrun",
        help="Preview changes.",
    ),
) -> None:
    """Unlink template(s) from templates(s).

    Unlinks and clears by default. Use `--no-clear` to unlink without clearing.
    [b]NOTE:[/] Destination templates are the ones that are ultimately modified. Source templates remain unchanged.
    """
    source_templates = _handle_template_arg(source, strict)
    dest_templates = _handle_template_arg(dest, strict)
    action = "Unlink and clear" if clear else "Unlink"
    if dryrun:
        info(
            f"Would {action.lower()} {len(source_templates)} templates from {len(dest_templates)} templates:"
        )
    else:
        with app.state.console.status("Unlinking templates..."):
            app.state.client.unlink_templates(
                source_templates, dest_templates, clear=clear
            )
    render_result(
        LinkTemplateResult.from_results(
            source_templates,
            dest_templates,
            action,  # type: ignore # mypy unable to infer literal type
        )
    )
    if not dryrun:
        action_success = "Unlinked and cleared" if clear else "Unlinked"
        success(
            f"{action_success} {len(source_templates)} templates from {len(dest_templates)} templates."
        )


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
        LinkTemplateHostResult.from_results(templates, hosts, "Unlink and clear")
    )
    success(f"Unlinked and cleared {len(templates)} templates from {len(hosts)} hosts.")


class TemplateGroupResult(TableRenderable):
    templates: List[str]
    groups: List[str]

    @classmethod
    def from_results(
        cls,
        templates: List[Template],
        groups: Union[List[TemplateGroup], List[HostGroup]],
    ) -> TemplateGroupResult:
        return cls(
            templates=[t.host for t in templates],
            groups=[h.name for h in groups],
        )


# Changed in V3: Changed name to reflect introduction of template groups in >=6.2
@app.command("add_template_to_group", rich_help_panel=HELP_PANEL)
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
    """Add template(s) to group(s).

    [bold]NOTE:[/] Group arguments are interpreted as template groups in >= 6.2,
    otherwise as host groups.
    """
    groups: Union[List[HostGroup], List[TemplateGroup]]
    if app.state.client.version.release >= (6, 2, 0):
        groups = _handle_templategroup_args(group_names_or_ids, strict)
    else:
        groups = _handle_hostgroups_args(group_names_or_ids, strict)

    templates = _handle_template_arg(template_names_or_ids, strict)

    with app.state.console.status("Adding templates..."):
        app.state.client.link_templates_to_groups(templates, groups)
    render_result(TemplateGroupResult.from_results(templates, groups))
    success(f"Added {len(templates)} templates to {len(groups)} groups.")


# Changed in V3: Changed name to reflect introduction of template groups in >=6.2
@app.command("remove_template_from_group", rich_help_panel=HELP_PANEL)
@app.command(
    # old name for backwards compatibility
    "unlink_template_from_hostgroup",
    hidden=True,
    rich_help_panel=HELP_PANEL,
)
def remove_template_from_group(
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
    """Remove templates from groups."""
    groups: Union[List[HostGroup], List[TemplateGroup]]
    if app.state.client.version.release >= (6, 2, 0):
        groups = _handle_templategroup_args(group_names_or_ids, strict)
    else:
        groups = _handle_hostgroups_args(group_names_or_ids, strict)

    templates = _handle_template_arg(template_names_or_ids, strict)

    with app.state.console.status("Removing templates from groups..."):
        # LEGACY: This used to also pass the templateids to templateids_clear,
        # which would unlink and clear all the templates from each other
        # This was a mistake, and has been removed in V3.
        # Users should use `unlink_templates_from_templates` for that.
        app.state.client.remove_templates_from_groups(
            templates,
            groups,
        )
    render_result(TemplateGroupResult.from_results(templates, groups))
    success(f"Removed {len(templates)} templates from {len(groups)} groups.")


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
