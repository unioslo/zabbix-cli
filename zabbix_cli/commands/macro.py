"""Commands to view and manage macros."""

from __future__ import annotations

from typing import Optional

import typer

from zabbix_cli.app import Example
from zabbix_cli.app import app
from zabbix_cli.commands.common.args import get_limit_option
from zabbix_cli.config.constants import OutputFormat
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.exceptions import ZabbixNotFoundError
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.render import render_result

HELP_PANEL_USER = "Macro (User)"
HELP_PANEL_GLOBAL = "Macro (Global)"


def fmt_macro_name(macro: str) -> str:
    """Format macro name for use in a query."""
    macro = macro.strip()
    if not macro:
        # TODO: More specific exception class
        raise ZabbixCLIError("Macro name cannot be empty.")
    if not macro.isupper():
        macro = macro.upper()
    if not macro.startswith("{"):
        macro = "{" + macro
    if not macro.endswith("}"):
        macro = macro + "}"
    if not macro[1] == "$":  # NOTE: refactor could break this
        macro = "{$" + macro[1:]
    if macro == "{$}":
        raise ZabbixCLIError(f"Invalid macro name {macro!r}")
    return macro


@app.command("define_global_macro", rich_help_panel=HELP_PANEL_GLOBAL)
def define_global_macro(
    ctx: typer.Context,
    name: str = typer.Argument(help="Name of the macro", show_default=False),
    value: str = typer.Argument(help="Value of the macro", show_default=False),
) -> None:
    """Create a global macro."""
    from zabbix_cli.commands.results.macro import GlobalMacroResult
    from zabbix_cli.models import Result

    name = fmt_macro_name(name)

    try:
        macro = app.state.client.get_global_macro(macro_name=name)
    except ZabbixNotFoundError:
        pass
    else:
        exit_err(f"Macro {name!r} already exists with value {macro.value!r}")

    macro_id = app.state.client.create_global_macro(macro=name, value=value)
    render_result(
        Result(
            message=f"Created macro {name!r} with ID {macro_id}.",
            result=GlobalMacroResult(macro=name, globalmacroid=macro_id, value=value),
        ),
    )


@app.command("show_global_macros", rich_help_panel=HELP_PANEL_GLOBAL)
def show_global_macros(ctx: typer.Context) -> None:
    """Show all global macros."""
    from zabbix_cli.commands.results.macro import GlobalMacroResult
    from zabbix_cli.models import AggregateResult

    macros = app.state.client.get_global_macros()
    render_result(
        AggregateResult(
            result=[
                GlobalMacroResult(
                    macro=m.macro, globalmacroid=m.globalmacroid, value=m.value
                )
                for m in macros
            ]
        )
    )


@app.command(
    name="define_host_usermacro",
    rich_help_panel=HELP_PANEL_USER,
    examples=[
        Example(
            "Create a macro named {$SNMP_COMMUNITY} for a host",
            "define_host_usermacro foo.example.com '{$SNMP_COMMUNITY}' public",
        ),
        Example(
            "Create a macro named {$SITE_URL} for a host (automatic name conversion)",
            "define_host_usermacro foo.example.com site_url https://example.com",
        ),
    ],
)
def define_host_usermacro(
    # NOTE: should this use old style args?
    hostname: str = typer.Argument(
        help="Host to define macro for.", show_default=False
    ),
    macro_name: str = typer.Argument(
        help=(
            "Name of macro. "
            "Names will be converted to the Zabbix format, "
            "i.e. [value]site_url[/] becomes [value]{$SITE_URL}[/]."
        ),
        show_default=False,
    ),
    macro_value: str = typer.Argument(
        help="Default value of macro.", show_default=False
    ),
) -> None:
    """Create or update a host usermacro."""
    from zabbix_cli.models import Result

    host = app.state.client.get_host(hostname)
    macro_name = fmt_macro_name(macro_name)

    # Determine if we should create or update macro
    try:
        macro = app.state.client.get_macro(host=host, macro_name=macro_name)
    except ZabbixNotFoundError:
        macro_id = app.state.client.create_macro(
            host=host, macro=macro_name, value=macro_value
        )
        action = "Created"
    else:
        macro_id = app.state.client.update_macro(
            macroid=macro.hostmacroid, value=macro_value
        )
        action = "Updated"

    render_result(
        Result(
            message=f"{action} macro {macro_name!r} with ID {macro_id} for host {hostname!r}."
        )
    )


@app.command(name="show_host_usermacros", rich_help_panel=HELP_PANEL_USER, hidden=False)
def show_host_usermacros(
    hostname_or_id: str = typer.Argument(
        help="Hostname or ID to show macros for",
        show_default=False,
    ),
) -> None:
    """Show all macros defined for a host."""
    from zabbix_cli.commands.results.macro import ShowHostUserMacrosResult
    from zabbix_cli.models import AggregateResult

    # By getting the macros via the host, we also ensure the host exists.
    host = app.state.client.get_host(hostname_or_id, select_macros=True)

    render_result(
        AggregateResult(
            result=[
                ShowHostUserMacrosResult.from_result(macro)
                # Sort macros by name when rendering
                for macro in sorted(host.macros, key=lambda m: m.macro)
            ]
        )
    )


@app.command(
    name="show_usermacro_host_list", rich_help_panel=HELP_PANEL_USER, hidden=False
)
def show_usermacro_host_list(
    usermacro: str = typer.Argument(
        help=(
            "Name of macro to find hosts with. "
            "Macro names are automatically formatted, e.g. [value]site_url[/] becomes [value]{$SITE_URL}[/]."
        ),
        show_default=False,
    ),
    limit: Optional[int] = get_limit_option(),
) -> None:
    """Find all hosts with a user macro of the given name.

    Renders a list of the complete macro object and its hosts in JSON mode.
    """
    from zabbix_cli.commands.results.macro import MacroHostListV2
    from zabbix_cli.commands.results.macro import MacroHostListV3
    from zabbix_cli.models import AggregateResult

    usermacro = fmt_macro_name(usermacro)
    macros = app.state.client.get_macros(
        macro_name=usermacro, select_hosts=True, limit=limit
    )
    macros = [macro for macro in macros if macro.hosts]

    # This is a place where we need to differentiate between legacy and
    # new JSON modes instead of sharing a single model and
    # letting the render function figure it out.
    # The V2 command only renders a single host, but the whole point of this
    # command is to list _all_ hosts with the given macro, so we want to render
    # the macro and a list of EVERY host with that macro.
    if (
        app.state.config.app.output.format == OutputFormat.JSON
        and app.state.config.app.legacy_json_format
    ):
        render_result(
            AggregateResult(result=[MacroHostListV2(macro=macro) for macro in macros])
        )
    else:
        if not macros:
            exit_err(f"Macro {usermacro!r} not found.")
        render_result(
            AggregateResult(result=[MacroHostListV3(macro=macro) for macro in macros])
        )


@app.command(
    "show_usermacro_template_list",
    rich_help_panel=HELP_PANEL_USER,
    examples=[
        Example(
            "Show all templates with a user macro named {$SNMP_COMMUNITY}",
            "show_usermacro_template_list SNMP_COMMUNITY",
        )
    ],
)
def show_usermacro_template_list(
    ctx: typer.Context,
    macro_name: str = typer.Argument(
        help="Name of the macro to find templates with. Automatically formatted.",
        show_default=False,
    ),
    limit: Optional[int] = get_limit_option(),
) -> None:
    """Find all templates with a user macro of the given name."""
    import itertools

    from zabbix_cli.commands.results.macro import ShowUsermacroTemplateListResult
    from zabbix_cli.models import AggregateResult

    macro_name = fmt_macro_name(macro_name)
    macros = app.state.client.get_macros(
        macro_name=macro_name, select_templates=True, limit=limit
    )
    macros = [macro for macro in macros if macro.templates]

    results = itertools.chain.from_iterable(
        [
            [
                ShowUsermacroTemplateListResult(
                    macro=macro.macro,
                    value=macro.value,
                    templateid=template.templateid,
                    template=template.host,
                )
                for template in macro.templates
            ]
            for macro in macros
        ]
    )

    render_result(
        AggregateResult(
            result=list(results),
        )
    )
