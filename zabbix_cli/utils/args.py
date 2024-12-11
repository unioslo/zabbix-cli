"""Utilities for parsing and validating command-line arguments."""

# NOTE: Should be moved to `commands.common` and merged with the existing `commands.common.args` module.

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Optional

import typer

from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import print_help

if TYPE_CHECKING:
    from zabbix_cli.app import StatefulApp
    from zabbix_cli.pyzabbix.types import Host
    from zabbix_cli.pyzabbix.types import HostGroup
    from zabbix_cli.pyzabbix.types import Template
    from zabbix_cli.pyzabbix.types import TemplateGroup


def is_set(ctx: typer.Context, option: str) -> bool:
    """Check if option is set in context."""
    from click.core import ParameterSource

    src = ctx.get_parameter_source(option)
    if not src:
        logging.warning(f"Parameter {option} not found in context.")
        return False

    # HACK: A typer callback that sets an empty list as a default value
    # for a field with a None default and `Optiona[List[str]]` type
    # will cause the parameter to be set to a non-default value,
    # and thus be considered "set" by Click. That is wrong.
    # This is only relevant because of `zabbix_cli._v2_compat.ARGS_POSITIONAL`.
    # It might be better to check for that specific case instead of this
    # general check, which might catch other cases that are not bugs (?)
    if ctx.params.get(option) == [] and option == "args":
        return False

    return src != ParameterSource.DEFAULT


def parse_int_arg(arg: str) -> int:
    """Convert string to int."""
    try:
        return int(arg.strip())
    except ValueError as e:
        raise ZabbixCLIError(f"Invalid integer value: {arg}") from e


def parse_list_arg(arg: Optional[str], keep_empty: bool = False) -> list[str]:
    """Convert comma-separated string to list."""
    try:
        args = arg.strip().split(",") if arg else []
        if not keep_empty:
            args = [a for a in args if a]
        return args
    except ValueError as e:
        raise ZabbixCLIError(f"Invalid comma-separated string value: {arg}") from e


def parse_int_list_arg(arg: str) -> list[int]:
    """Convert comma-separated string of ints to list of ints."""
    args = parse_list_arg(
        arg,
        keep_empty=False,  # Important that we never try to parse empty strings as ints
    )
    try:
        return list(map(parse_int_arg, args))
    except ValueError as e:
        raise ZabbixCLIError(f"Invalid comma-separated string value: {arg}") from e


def parse_hostgroups_arg(
    app: StatefulApp,
    hgroup_names_or_ids: Optional[str],
    strict: bool = False,
    select_hosts: bool = False,
    select_templates: bool = False,
) -> list[HostGroup]:
    from zabbix_cli.output.console import exit_err
    from zabbix_cli.output.prompts import str_prompt

    if not hgroup_names_or_ids:
        hgroup_names_or_ids = str_prompt("Host group(s)")

    hg_args = [h.strip() for h in hgroup_names_or_ids.split(",")]
    if not hg_args:
        exit_err("At least one host group name/ID is required.")

    hostgroups = app.state.client.get_hostgroups(
        *hg_args,
        search=True,
        select_hosts=select_hosts,
        select_templates=select_templates,
    )
    if not hostgroups:
        exit_err(f"No host groups found matching {hgroup_names_or_ids}")
    if strict and len(hostgroups) != len(hg_args):
        exit_err(f"Found {len(hostgroups)} host groups, expected {len(hostgroups)}")
    return hostgroups


def parse_hosts_arg(
    app: StatefulApp,
    hostnames_or_ids: Optional[str],
    strict: bool = False,
) -> list[Host]:
    from zabbix_cli.output.console import exit_err
    from zabbix_cli.output.prompts import str_prompt

    if not hostnames_or_ids:
        hostnames_or_ids = str_prompt("Host(s)")

    host_args = parse_list_arg(hostnames_or_ids)
    if not host_args:
        exit_err("At least one host name/ID is required.")

    hosts = app.state.client.get_hosts(*host_args, search=True)
    if not hosts:
        exit_err(f"No hosts found matching {hostnames_or_ids}")
    if strict and len(hosts) != len(host_args):
        exit_err(f"Found {len(hosts)} hosts, expected {len(host_args)}")
    return hosts


def parse_templates_arg(
    app: StatefulApp,
    template_names_or_ids: Optional[str],
    strict: bool = False,
    select_hosts: bool = False,
) -> list[Template]:
    from zabbix_cli.output.console import exit_err

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


def parse_templategroups_arg(
    app: StatefulApp,
    tgroup_names_or_ids: str,
    strict: bool = False,
    select_templates: bool = False,
) -> list[TemplateGroup]:
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


TRUE_CHOICES = ["true", "yes", "1", "on"]
FALSE_CHOICES = ["false", "no", "0", "off"]


def parse_bool_arg(arg: str) -> bool:
    """Convert string to bool."""
    arg = arg.strip().lower()
    if arg in TRUE_CHOICES:
        return True
    elif arg in FALSE_CHOICES:
        return False
    else:
        raise ZabbixCLIError(f"Invalid boolean value: {arg}")


def parse_path_arg(arg: str, must_exist: bool = False) -> Path:
    """Convert string to Path."""
    try:
        p = Path(arg)
    except ValueError as e:
        raise ZabbixCLIError(f"Invalid path value: {arg}") from e
    else:
        if must_exist and not p.exists():
            raise ZabbixCLIError(f"Path does not exist: {arg}")
        return p


### API / arg utilities ###


def get_hostgroup_hosts(
    app: StatefulApp, hostgroups: list[HostGroup] | str
) -> list[Host]:
    """Get all hosts from a list of host groups.

    Args:
        app: The application instance.
        hostgroups: List of host groups or a comma-separated string of host group names."""
    if isinstance(hostgroups, str):
        hostgroup_names = parse_list_arg(hostgroups)
        hostgroups = app.state.client.get_hostgroups(
            *hostgroup_names, select_hosts=True, search=True
        )
    # Get all hosts from all host groups
    # Some hosts can be in multiple host groups - ensure no dupes
    hosts: list[Host] = []
    seen: set[str] = set()
    for hg in hostgroups:
        for host in hg.hosts:
            if host.host not in seen:
                hosts.append(host)
                seen.add(host.host)
    return hosts


def check_at_least_one_option_set(ctx: typer.Context) -> None:
    """Check that at least one option is set in the context.

    Useful for commands used to update resources, where all options
    are optional, but at least one is required to make a change."""
    optional_params: set[str] = set()
    for param in ctx.command.params:
        if param.required:
            continue
        if not param.name:
            logging.warning("Unnamed parameter in command %s", ctx.command.name)
            continue
        optional_params.add(param.name)
    if not any(is_set(ctx, param) for param in optional_params):
        print_help(ctx)
        exit_err("At least one option is required.")
