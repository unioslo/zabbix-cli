from __future__ import annotations

from itertools import chain
from typing import Optional

import typer

from zabbix_cli.app import Example
from zabbix_cli.app import app
from zabbix_cli.commands.common.args import ARG_HOSTNAMES_OR_IDS
from zabbix_cli.commands.common.args import ARG_TEMPLATE_NAMES_OR_IDS
from zabbix_cli.output.console import info
from zabbix_cli.output.console import success
from zabbix_cli.output.formatting.grammar import pluralize as p
from zabbix_cli.output.render import render_result
from zabbix_cli.utils.args import parse_hosts_arg
from zabbix_cli.utils.args import parse_list_arg
from zabbix_cli.utils.args import parse_templates_arg

HELP_PANEL = "Template"


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

    templates = parse_templates_arg(
        app, template_names_or_ids, strict, select_hosts=True
    )
    hosts = parse_hosts_arg(app, hostnames_or_ids, strict)
    if not dryrun:
        with app.state.console.status("Linking templates..."):
            app.state.client.link_templates_to_hosts(templates, hosts)

    result: list[LinkTemplateToHostResult] = []
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
    source_templates = parse_templates_arg(app, source, strict=strict)
    dest_templates = parse_templates_arg(app, dest, strict=strict)

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
    templates: Optional[str] = typer.Argument(
        None,
        help="Template name(s) or ID(s). Comma-separated. Supports wildcards.",
        show_default=False,
    ),
) -> None:
    """Show all templates.

    Shows all templates by default. The template name can be a pattern containing wildcards.
    Names and IDs cannot be mixed.
    """
    from zabbix_cli.models import AggregateResult

    template_names_or_ids = parse_list_arg(templates)
    tpls = app.state.client.get_templates(
        *template_names_or_ids,
        select_hosts=True,
        select_templates=True,
        select_parent_templates=True,
    )
    render_result(AggregateResult(result=tpls))


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

    templates = parse_templates_arg(
        app, template_names_or_ids, strict, select_hosts=True
    )
    hosts = parse_hosts_arg(app, hostnames_or_ids, strict)

    action = "Unlink and clear" if clear else "Unlink"
    if not dryrun:
        with app.state.console.status("Unlinking templates..."):
            app.state.client.unlink_templates_from_hosts(templates, hosts)

    # Only show hosts with matching templates to unlink
    result: list[UnlinkTemplateFromHostResult] = []
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

    source_templates = parse_templates_arg(app, source, strict)
    dest_templates = parse_templates_arg(app, dest, strict)
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
