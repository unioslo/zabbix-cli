from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING
from typing import List
from typing import Union

import typer

from zabbix_cli.app import Example
from zabbix_cli.app import app
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.console import success
from zabbix_cli.output.formatting.grammar import pluralize as p
from zabbix_cli.output.render import render_result
from zabbix_cli.utils.args import parse_list_arg

if TYPE_CHECKING:
    from zabbix_cli.pyzabbix.types import Host
    from zabbix_cli.pyzabbix.types import HostGroup
    from zabbix_cli.pyzabbix.types import Template
    from zabbix_cli.pyzabbix.types import TemplateGroup


HELP_PANEL = "Template"


# FIXME: use parse_hostgroup_args from utils.args
def _handle_hostnames_args(
    hostnames_or_ids: str,
    strict: bool = False,
) -> List[Host]:
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
    hgroup_names_or_ids: str,
    strict: bool = False,
    select_templates: bool = False,
) -> List[HostGroup]:
    hg_args = [h.strip() for h in hgroup_names_or_ids.split(",")]
    if not hg_args:
        exit_err("At least one host group name/ID is required.")

    hostgroups = app.state.client.get_hostgroups(
        *hg_args, search=True, select_templates=select_templates
    )
    if not hostgroups:
        exit_err(f"No host groups found matching {hgroup_names_or_ids}")
    if strict and len(hostgroups) != len(hg_args):
        exit_err(f"Found {len(hostgroups)} host groups, expected {len(hostgroups)}")
    return hostgroups


def _handle_templategroup_args(
    tgroup_names_or_ids: str,
    strict: bool = False,
    select_templates: bool = False,
) -> List[TemplateGroup]:
    tg_args = parse_list_arg(tgroup_names_or_ids)
    if not tg_args:
        exit_err("At least one template group name/ID is required.")

    templategroups = app.state.client.get_templategroups(
        *tg_args, search=True, select_templates=select_templates
    )
    if not templategroups:
        exit_err(f"No template groups found matching {tgroup_names_or_ids}")
    if strict and len(templategroups) != len(tg_args):
        exit_err(
            f"Found {len(templategroups)} template groups, expected {len(templategroups)}"
        )
    return templategroups


def _handle_template_arg(
    template_names_or_ids: str,
    strict: bool = False,
    select_hosts: bool = False,
) -> List[Template]:
    template_args = parse_list_arg(template_names_or_ids)
    if not template_args:
        exit_err("At least one template name/ID is required.")

    templates = app.state.client.get_templates(
        *template_args, select_hosts=select_hosts
    )
    if not templates:
        exit_err(f"No templates found matching {template_names_or_ids}")
    if strict and len(templates) != len(template_args):
        exit_err(f"Found {len(templates)} templates, expected {len(template_args)}")

    return templates


ARG_TEMPLATE_NAMES_OR_IDS = typer.Argument(
    help="Template names or IDs. Comma-separated. Supports wildcards.",
    show_default=False,
)
ARG_HOSTNAMES_OR_IDS = typer.Argument(
    help="Hostnames or IDs. Comma-separated. Supports wildcards.",
    show_default=False,
)
ARG_GROUP_NAMES_OR_IDS = typer.Argument(
    help="Host/template group names or IDs. Comma-separated. Supports wildcards.",
    show_default=False,
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
    template_names_or_ids: str = ARG_TEMPLATE_NAMES_OR_IDS,
    hostnames_or_ids: str = ARG_HOSTNAMES_OR_IDS,
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail if any hosts or templates aren't found. Should not be used in conjunction with wildcards.",
    ),
    dryrun: bool = typer.Option(
        False,
        "--dryrun",
        help="Preview changes.",
    ),
) -> None:
    """Link templates to hosts."""
    from zabbix_cli.commands.results.template import LinkTemplateToHostResult
    from zabbix_cli.models import AggregateResult

    templates = _handle_template_arg(template_names_or_ids, strict, select_hosts=True)
    hosts = _handle_hostnames_args(hostnames_or_ids, strict)
    if not dryrun:
        with app.state.console.status("Linking templates..."):
            app.state.client.link_templates_to_hosts(templates, hosts)

    result: List[LinkTemplateToHostResult] = []
    for host in hosts:
        r = LinkTemplateToHostResult.from_result(templates, host, "Link")
        if not r.templates:
            continue
        result.append(r)

    total_templates = len(set(chain.from_iterable((r.templates) for r in result)))
    total_hosts = len(result)

    render_result(AggregateResult(result=result))
    base_msg = f"{p('template', total_templates)} to {p('host', total_hosts)}"
    if dryrun:
        info(f"Would link {base_msg}.")
    else:
        success(f"Linked {base_msg}.")


@app.command(
    "unlink_template_from_host",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Unlink a template from a host",
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
            "Unlink templates starting with 'Apache' from hosts starting with 'Web'",
            "unlink_template_from_host 'Apache*' 'Web-*'",
        ),
        Example(
            "Unlink template from host without clearing items and triggers",
            "unlink_template_from_host --no-clear 'Apache by HTTP' foo.example.com",
        ),
    ],
)
def unlink_template_from_host(
    ctx: typer.Context,
    template_names_or_ids: str = ARG_TEMPLATE_NAMES_OR_IDS,
    hostnames_or_ids: str = ARG_HOSTNAMES_OR_IDS,
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail if any hosts or templates aren't found. Should not be used in conjunction with wildcards.",
    ),
    dryrun: bool = typer.Option(
        False,
        "--dryrun",
        help="Preview changes.",
    ),
    clear: bool = typer.Option(
        True, "--clear/--no-clear", help="Unlink and clear templates."
    ),
) -> None:
    """Unlink templates from hosts.

    Unlinks and clears by default. Use `--no-clear` to unlink without clearing.
    """
    from zabbix_cli.commands.results.template import UnlinkTemplateFromHostResult
    from zabbix_cli.models import AggregateResult

    templates = _handle_template_arg(template_names_or_ids, strict, select_hosts=True)
    hosts = _handle_hostnames_args(hostnames_or_ids, strict)

    action = "Unlink and clear" if clear else "Unlink"
    if not dryrun:
        with app.state.console.status("Unlinking templates..."):
            app.state.client.unlink_templates_from_hosts(templates, hosts)

    # Only show hosts with matching templates to unlink
    result: List[UnlinkTemplateFromHostResult] = []
    for host in hosts:
        r = UnlinkTemplateFromHostResult.from_result(templates, host, action)
        if not r.templates:
            continue
        result.append(r)

    total_templates = len(set(chain.from_iterable((r.templates) for r in result)))
    total_hosts = len(result)

    render_result(AggregateResult(result=result))
    base_msg = f"{p('template', total_templates)} from {p('host', total_hosts)}"
    if dryrun:
        info(f"Would {action.lower()} {base_msg}.")
    else:
        action_success = "Unlinked and cleared" if clear else "Unlinked"
        success(f"{action_success} {base_msg}.")


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
    source: str = ARG_TEMPLATE_NAMES_OR_IDS,
    dest: str = ARG_TEMPLATE_NAMES_OR_IDS,
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
    """Link templates to templates.

    [b]NOTE:[/] Destination templates are the ones that are ultimately modified. Source templates remain unchanged.
    """
    from zabbix_cli.commands.results.template import LinkTemplateResult

    # TODO: add existing link checking just like in `link_template_to_host` & `unlink_template_from_host`
    # so we only print the ones that are actually linked
    source_templates = _handle_template_arg(source, strict)
    dest_templates = _handle_template_arg(dest, strict)

    if not dryrun:
        with app.state.console.status("Linking templates..."):
            app.state.client.link_templates(source_templates, dest_templates)
    render_result(
        LinkTemplateResult.from_result(source_templates, dest_templates, "Link")
    )
    base_msg = f"{p('template', len(source_templates))} to {p('template', len(dest_templates))}"
    if dryrun:
        info(f"Would link {base_msg}.")
    else:
        success(f"Linked {base_msg}.")


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
            "unlink_template_from_template '*HTTP*' 'Web-*'",
        ),
        Example(
            "Unlink a template without clearing items and triggers",
            "unlink_template_from_template --no-clear foo_template bar_template",
        ),
    ],
)
def unlink_template_from_template(
    ctx: typer.Context,
    source: str = ARG_TEMPLATE_NAMES_OR_IDS,
    dest: str = ARG_TEMPLATE_NAMES_OR_IDS,
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
    """Unlink templates from templates.

    Unlinks and clears by default. Use `--no-clear` to unlink without clearing.
    [b]NOTE:[/] Destination templates are the ones that are ultimately modified. Source templates remain unchanged.
    """
    from zabbix_cli.commands.results.template import LinkTemplateResult

    source_templates = _handle_template_arg(source, strict)
    dest_templates = _handle_template_arg(dest, strict)
    if not dryrun:
        with app.state.console.status("Unlinking templates..."):
            app.state.client.unlink_templates(
                source_templates, dest_templates, clear=clear
            )
    action = "Unlink and clear" if clear else "Unlink"
    render_result(
        LinkTemplateResult.from_result(
            source_templates,
            dest_templates,
            action,
        )
    )
    base_msg = f"{p('template', len(source_templates))} from {p('template', len(dest_templates))}"
    if dryrun:
        info(f"Would {action.lower()} {base_msg}.")
    else:
        action_success = "Unlinked and cleared" if clear else "Unlinked"
        success(f"{action_success} {base_msg}.")


# Changed in V3: Changed name to reflect introduction of template groups in >=6.2
@app.command("add_template_to_group", rich_help_panel=HELP_PANEL)
@app.command(
    # old name for backwards compatibility
    "link_template_to_hostgroup",
    hidden=True,
    deprecated=True,
    rich_help_panel=HELP_PANEL,
    help="DEPRECATED: Use add_template_to_group instead.",
)
def add_template_to_group(
    ctx: typer.Context,
    template_names_or_ids: str = ARG_TEMPLATE_NAMES_OR_IDS,
    group_names_or_ids: str = ARG_GROUP_NAMES_OR_IDS,
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail if any host groups or templates aren't found. Should not be used in conjunction with wildcards.",
    ),
) -> None:
    """Add templates to groups.

    [bold]NOTE:[/] Group arguments are interpreted as template groups in >= 6.2,
    otherwise as host groups.
    """
    from zabbix_cli.commands.results.template import TemplateGroupResult

    groups: Union[List[HostGroup], List[TemplateGroup]]
    if app.state.client.version.release >= (6, 2, 0):
        groups = _handle_templategroup_args(group_names_or_ids, strict)
    else:
        groups = _handle_hostgroups_args(group_names_or_ids, strict)

    templates = _handle_template_arg(template_names_or_ids, strict)

    with app.state.console.status("Adding templates..."):
        app.state.client.link_templates_to_groups(templates, groups)
    render_result(TemplateGroupResult.from_result(templates, groups))
    success(f"Added {len(templates)} templates to {len(groups)} groups.")


# Changed in V3: Changed name to reflect introduction of template groups in >=6.2
@app.command(
    "remove_template_from_group",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Remove one template from one group",
            "remove_template_from_group 'Apache by HTTP' foo_group",
        ),
        Example(
            "Remove many templates from many groups",
            "remove_template_from_group 'Apache by HTTP,HAProxy by Zabbix agent' foo_group,bar_group",
        ),
        Example(
            "Remove all templates starting with 'Apache' from a group",
            "remove_template_from_group 'Apache*' foo_group",
        ),
        Example(
            "Remove all templates containing 'HTTP' from all groups",
            "remove_template_from_group '*HTTP*' '*'",
        ),
    ],
)
@app.command(
    # old name for backwards compatibility
    "unlink_template_from_hostgroup",
    hidden=True,
    deprecated=True,
    rich_help_panel=HELP_PANEL,
    help="Use `remove_template_from_group` instead.",
)
def remove_template_from_group(
    ctx: typer.Context,
    template_names_or_ids: str = ARG_TEMPLATE_NAMES_OR_IDS,
    group_names_or_ids: str = ARG_GROUP_NAMES_OR_IDS,
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail if any host groups or templates aren't found. Should not be used in conjunction with wildcards.",
    ),
    dryrun: bool = typer.Option(
        False,
        "--dryrun",
        help="Preview changes.",
    ),
    # TODO: add toggle for NOT clearing when unlinking?
) -> None:
    """Remove templates from groups."""
    from zabbix_cli.commands.results.template import RemoveTemplateFromGroupResult
    from zabbix_cli.models import AggregateResult

    groups: Union[List[HostGroup], List[TemplateGroup]]
    if app.state.client.version.release >= (6, 2, 0):
        groups = _handle_templategroup_args(
            group_names_or_ids, strict=strict, select_templates=True
        )
    else:
        groups = _handle_hostgroups_args(
            group_names_or_ids, strict=strict, select_templates=True
        )

    templates = _handle_template_arg(template_names_or_ids, strict=strict)

    if not dryrun:
        with app.state.console.status("Removing templates from groups..."):
            # LEGACY: This used to also pass the templateids to templateids_clear,
            # which would unlink and clear all the templates from each other
            # This was a mistake, and has been removed in V3.
            # Users should use `unlink_templates_from_templates` for that.
            app.state.client.remove_templates_from_groups(
                templates,
                groups,
            )
    result: List[RemoveTemplateFromGroupResult] = []
    for group in groups:
        r = RemoveTemplateFromGroupResult.from_result(templates, group)
        if not r.templates:
            continue
        result.append(r)

    total_templates = len(set(chain.from_iterable((r.templates) for r in result)))
    total_groups = len(result)

    render_result(AggregateResult(result=result, empty_ok=True))
    base_msg = f"{p('template', total_templates)} from {p('group', total_groups)}"
    if dryrun:
        info(f"Would remove {base_msg}.")
    else:
        success(f"Removed {base_msg}.")


@app.command("show_template", rich_help_panel=HELP_PANEL)
def show_template(
    ctx: typer.Context,
    template_name: str = typer.Argument(
        help="Template name or ID. Names support wildcards.",
        show_default=False,
    ),
) -> None:
    """Show a template."""
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
        help="Template name(s) or ID(s). Comma-separated. Supports wildcards.",
    ),
) -> None:
    """Show one or more templates.

    Shows all templates by default. The template name can be a pattern containing wildcards.
    Names and IDs cannot be mixed.
    """
    from zabbix_cli.models import AggregateResult

    args = parse_list_arg(templates)
    tmpls = app.state.client.get_templates(
        *args,
        select_hosts=True,
        select_templates=True,
        select_parent_templates=True,
    )
    render_result(AggregateResult(result=tmpls))


@app.command(
    "show_items",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Show items for a template",
            "show_items 'Apache by HTTP'",
        ),
    ],
)
def show_items(
    ctx: typer.Context,
    template_name: str = typer.Argument(
        help="Template name or ID. Supports wildcards.",
        show_default=False,
    ),
) -> None:
    """Show a template's items."""
    from zabbix_cli.models import AggregateResult

    template = app.state.client.get_template(template_name)
    items = app.state.client.get_items(templates=[template])
    # NOTE: __title__ is ignored by Pydantic when used as a kwarg
    # when instantiating a model. We either need to subclass AggregateResult
    # or set it after instantiation.
    # Ideally, we would rename the field to `table_title` and make it an actual field
    # but that clashes with our existing `__<option>__` pattern for overriding
    res = AggregateResult(result=items)
    res.__title__ = template.host
    render_result(res)
