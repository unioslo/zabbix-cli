#!/usr/bin/env python
#
# Authors:
# rafael@e-mc2.net / https://e-mc2.net/
#
# Copyright (c) 2014-2017 USIT-University of Oslo
#
# This file is part of Zabbix-cli
# https://github.com/unioslo/zabbix-cli
#
# Zabbix-CLI is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Zabbix-CLI is distributed in the hope that it will be useful,
# but WITHOUT ANY W
# ARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Zabbix-CLI.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Dict
from typing import Optional

import typer

from zabbix_cli.__about__ import __version__
from zabbix_cli.app import app
from zabbix_cli.config.constants import OutputFormat
from zabbix_cli.config.utils import get_config

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger("zabbix-cli")


def run_repl(ctx: typer.Context) -> None:
    from rich.console import Group
    from rich.panel import Panel

    # Patch click-repl THEN import it
    # Apply patches here to avoid impacting startup time of the CLI
    from zabbix_cli._patches.click_repl import patch
    from zabbix_cli.output.console import console
    from zabbix_cli.output.style import green
    from zabbix_cli.state import get_state

    patch()
    from click_repl import (  # pyright: ignore[reportUnknownVariableType, reportMissingTypeStubs]
        repl as start_repl,  # pyright: ignore[reportUnknownVariableType, reportMissingTypeStubs]
    )

    state = get_state()

    def print_intro() -> None:
        info_text = (
            f"[bold]Welcome to the Zabbix command-line interface (v{__version__})[/]\n"
            f"[bold]Connected to server {state.config.api.url} (v{state.client.version})[/]"
        )
        info_panel = Panel(
            green(info_text),
            expand=False,
            padding=(0, 1),
        )
        help_text = "Type --help to list commands, :h for REPL help, :q to exit."
        intro = Group(info_panel, help_text)
        console.print(intro)

    def pre_run() -> None:
        if not state.repl:
            print_intro()
            state.repl = True
        state.revert_config_overrides()

    prompt_kwargs: Dict[str, Any] = {"pre_run": pre_run, "history": state.history}
    start_repl(ctx, prompt_kwargs=prompt_kwargs)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Alternate configuration file to use.",
    ),
    input_file: Optional[Path] = typer.Option(
        None,
        "--file",
        "--input-file",  # DEPRECATED: V2 name for compatibility
        "-f",
        help="File with Zabbix-CLI commands to be executed in bulk mode.",
    ),
    output_format: Optional[OutputFormat] = typer.Option(
        None,
        "--output-format",
        "-o",
        help="Define the output format when running in command-line mode.",
        case_sensitive=False,
    ),
    # Deprecated option, kept for compatibility with V2
    zabbix_command: Optional[str] = typer.Option(
        None,
        "--command",
        "-C",
        help="Zabbix-CLI command to execute when running in command-line mode.",
        hidden=True,
    ),
) -> None:
    # Don't run callback if --help is passed in
    # https://github.com/tiangolo/typer/issues/55
    if "--help" in sys.argv:
        return

    from zabbix_cli.logs import LogContext
    from zabbix_cli.logs import configure_logging
    from zabbix_cli.state import get_state

    if should_skip_configuration(ctx):
        return

    state = get_state()
    if state.is_config_loaded:
        conf = state.config
    else:
        conf = get_config(config_file)

    # Config overrides are always applied
    if output_format is not None:
        conf.app.output_format = output_format

    if state.repl:
        return  # In REPL already; no need to re-configure.

    logger.debug("Zabbix-CLI started.")

    configure_logging(conf.logging)
    state.configure(conf)

    # NOTE: LogContext is kept from V2. Do we still need it?
    with LogContext(logger, user=conf.api.username):
        # TODO: look at order of evaluation here. What takes precedence?
        # Should passing both --input-file and --command be an error? probably
        if zabbix_command:
            from zabbix_cli._v2_compat import run_command_from_option

            run_command_from_option(ctx, zabbix_command)
            return
        elif input_file:
            from zabbix_cli.bulk import run_bulk

            run_bulk(ctx, input_file)
        elif ctx.invoked_subcommand is not None:
            return  # modern alternative to `-C` option to run a single command
        else:
            # If no command is passed in, we enter the REPL
            run_repl(ctx)


# TODO: Add a decorator for skipping or some sort of parameter to the existing
#       StatefulApp.command method that marks a command as not requiring
#       an existing configuration file.
SKIPPABLE_COMMANDS = ["open", "sample_config"]


def should_skip_configuration(ctx: typer.Context) -> bool:
    """Check if the command should skip loading the configuration file."""
    return ctx.invoked_subcommand in SKIPPABLE_COMMANDS


def main() -> int:
    """Main entry point for the CLI."""
    try:
        app()
    except Exception as e:
        from zabbix_cli.exceptions import handle_exception

        handle_exception(e)
    else:
        print("\nDone, thank you for using Zabbix-CLI")
    finally:
        from zabbix_cli.state import get_state

        state = get_state()
        state.logout_on_exit()
        logger.debug("Zabbix-CLI stopped.")
    return 0


if __name__ == "__main__":
    main()
