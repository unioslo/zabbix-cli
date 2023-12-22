"""Commands to view and manage macros."""
from __future__ import annotations

from typing import Any
from typing import Dict
from typing import Optional
from typing import TYPE_CHECKING

import typer
from pydantic import Field
from pydantic import model_serializer

from zabbix_cli.app import app
from zabbix_cli.config import OutputFormat
from zabbix_cli.exceptions import ZabbixNotFoundError
from zabbix_cli.models import AggregateResult
from zabbix_cli.models import Result
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.types import Macro
from zabbix_cli.utils.commands import ARG_HOSTNAME_OR_ID


if TYPE_CHECKING:
    from zabbix_cli.models import ColsType  # noqa: F401
    from zabbix_cli.models import ColsRowsType
    from zabbix_cli.models import RowsType  # noqa: F401

# # `zabbix-cli host macro <cmd>`
# macro_cmd = StatefulApp(
#     name="macro",
#     help="Host macro commands.",
# )
# app.add_subcommand(macro_cmd)

HELP_PANEL = "Macro"


def fmt_macro_name(macro: str) -> str:
    """Format macro name for use in a query."""
    if not macro.isupper():
        macro = macro.upper()
    if not macro.startswith("{"):
        macro = "{" + macro
    if not macro.endswith("}"):
        macro = macro + "}"
    if not macro[1] == "$":
        macro = "{$" + macro[1:]
    return macro


@app.command(name="define_host_usermacro", rich_help_panel=HELP_PANEL)
def define_host_usermacro(
    # NOTE: should this use old style args?
    hostname: Optional[str] = typer.Argument(None, help="Host to define macro for."),
    macro_name: Optional[str] = typer.Argument(
        None,
        help=(
            "Name of macro. "
            "Names will be converted to the Zabbix format, "
            "i.e. `site_url` becomes {$SITE_URL}."
        ),
    ),
    macro_value: Optional[str] = typer.Argument(None, help="Default value of macro."),
) -> None:
    """Create or update a host usermacro."""
    if not hostname:
        hostname = str_prompt("Hostname")
    if not macro_name:
        macro_name = str_prompt("Macro name")
    if not macro_value:
        macro_value = str_prompt("Macro value")

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


class ShowHostUserMacrosResult(TableRenderable):
    hostmacroid: str = Field(validation_alias="MacroID")
    macro: str
    value: Optional[str] = None
    type: str
    description: Optional[str] = None
    hostid: str = Field(validation_alias="HostID")
    automatic: Optional[int]


# @macro_cmd.command(name="list", rich_help_panel=HELP_PANEL)
@app.command(name="show_host_usermacros", rich_help_panel=HELP_PANEL, hidden=False)
def show_host_usermacros(hostname_or_id: str = ARG_HOSTNAME_OR_ID) -> None:
    """Shows all macros defined for a host."""
    if not hostname_or_id:
        hostname_or_id = str_prompt("Hostname or ID")
    # By getting the macros via the host, we also ensure the host exists.
    host = app.state.client.get_host(hostname_or_id, select_macros=True)

    render_result(
        AggregateResult(
            result=[
                ShowHostUserMacrosResult(
                    hostmacroid=macro.hostmacroid,
                    macro=macro.macro,
                    value=macro.value,
                    type=macro.type,
                    description=macro.description,
                    hostid=macro.hostid,
                    automatic=macro.automatic,
                )
                # Sort macros by name when rendering
                for macro in sorted(host.macros, key=lambda m: m.macro)
            ]
        )
    )


class MacroHostListV2(TableRenderable):
    macro: Macro

    def __cols_rows__(self) -> ColsRowsType:
        rows = [
            [self.macro.macro, str(self.macro.value), host.hostid, host.host]
            for host in self.macro.hosts
        ]
        return ["Macro", "Value", "HostID", "Host"], rows

    @model_serializer()
    def model_ser(self) -> Dict[str, Any]:
        if not self.macro.hosts:
            return {}  # match V2 output
        return {
            "macro": self.macro.macro,
            "value": self.macro.value,
            "hostid": self.macro.hosts[0].hostid,
            "host": self.macro.hosts[0].host,
        }


class MacroHostListV3(TableRenderable):
    macro: Macro

    def __cols_rows__(self) -> ColsRowsType:
        rows = [
            [host.hostid, host.host, self.macro.macro, str(self.macro.value)]
            for host in self.macro.hosts
        ]
        return ["Host ID", "Host", "Macro", "Value"], rows


# TODO: find out what we actually want this command to do.
# Each user macro belongs to one host, so we can't really list all hosts
# with a single macro...
# @macro_cmd.command(name="find", rich_help_panel=HELP_PANEL)
@app.command(name="show_usermacro_host_list", rich_help_panel=HELP_PANEL, hidden=False)
def show_usermacro_host_list(
    usermacro: Optional[str] = typer.Argument(
        None,
        help=(
            "Name of macro to find hosts with. "
            "Application will automatically format macro names, e.g. `site_url` becomes `{$SITE_URL}`."
        ),
    ),
) -> None:
    """Find all hosts with a user macro of the given name.

    Renders a list of the complete macro object and its hosts in JSON mode."""
    if not usermacro:
        usermacro = str_prompt("Macro name")
    usermacro = fmt_macro_name(usermacro)
    macros = app.state.client.get_macros(macro_name=usermacro, select_hosts=True)

    # This is a place where we need to differentiate between legacy and
    # new JSON modes instead of sharing a single model and
    # letting the render function figure it out.
    # The V2 command only renders a single host, but the whole point of this
    # command is to list _all_ hosts with the given macro, so we want to render
    # the macro and a list of EVERY host with that macro.
    if (
        app.state.config.app.output_format == OutputFormat.JSON
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


class GlobalMacroResult(TableRenderable):
    """Result of `define_global_macro` command."""

    globalmacroid: str
    macro: str
    value: Optional[str] = None  # for usermacro.get calls


# TODO: find out how to log full command invocations (especially in REPL, where we cant use sys.argv)
@app.command("define_global_macro", rich_help_panel=HELP_PANEL)
def define_global_macro(
    ctx: typer.Context,
    name: Optional[str] = typer.Argument(None, help="Name of the macro"),
    value: Optional[str] = typer.Argument(None, help="Value of the macro"),
) -> None:
    if not name:
        name = str_prompt("Macro name")
    if not value:
        value = str_prompt("Macro value")
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


@app.command("show_global_macros", rich_help_panel=HELP_PANEL)
def show_global_macros(ctx: typer.Context) -> None:
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


class ShowUsermacroTemplateListResult(TableRenderable):
    macro: str
    value: Optional[str] = None
    templateid: str
    template: str

    def __cols__(self) -> list[str]:
        return ["Macro", "Value", "Template ID", "Template"]


@app.command("show_usermacro_template_list", rich_help_panel=HELP_PANEL)
def show_usermacro_template_list(
    ctx: typer.Context,
    macro_name: Optional[str] = typer.Argument(
        None, help="Name of the macro to find templates with. Automatically formatted."
    ),
) -> None:
    """Find all templates with a user macro of the given name."""
    if not macro_name:
        macro_name = str_prompt("Macro name")
    macro_name = fmt_macro_name(macro_name)
    macro = app.state.client.get_macro(macro_name=macro_name, select_templates=True)
    render_result(
        AggregateResult(
            result=[
                ShowUsermacroTemplateListResult(
                    macro=macro.macro,
                    value=macro.value,
                    templateid=template.templateid,
                    template=template.host,
                )
                for template in macro.templates
            ]
        )
    )
