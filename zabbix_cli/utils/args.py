from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
from typing import TYPE_CHECKING

import typer

from zabbix_cli.exceptions import ZabbixCLIError

if TYPE_CHECKING:
    from zabbix_cli.pyzabbix.types import Host
    from zabbix_cli.pyzabbix.types import HostGroup
    from zabbix_cli.app import StatefulApp


def is_set(ctx: typer.Context, option: str) -> bool:
    """Check if option is set in context."""
    from click.core import ParameterSource

    src = ctx.get_parameter_source(option)
    if not src:
        logging.warning(f"Parameter {option} not found in context.")
        return False
    return src != ParameterSource.DEFAULT
    # return option in ctx.params and ctx.params[option]


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
) -> list[HostGroup]:
    from zabbix_cli.output.prompts import str_prompt
    from zabbix_cli.output.console import exit_err

    if not hgroup_names_or_ids:
        hgroup_names_or_ids = str_prompt("Host group(s)")

    hg_args = [h.strip() for h in hgroup_names_or_ids.split(",")]
    if not hg_args:
        exit_err("At least one host group name/ID is required.")

    hostgroups = app.state.client.get_hostgroups(
        *hg_args, search=True, select_hosts=select_hosts
    )
    if not hostgroups:
        exit_err(f"No host groups found matching {hgroup_names_or_ids}")
    if strict and len(hostgroups) != len(hg_args):
        exit_err(f"Found {len(hostgroups)} host groups, expected {len(hostgroups)}")
    return hostgroups


def parse_hostnames_arg(
    app: StatefulApp,
    hostnames_or_ids: Optional[str],
    strict: bool = False,
) -> list[Host]:
    from zabbix_cli.output.prompts import str_prompt
    from zabbix_cli.output.console import exit_err

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
