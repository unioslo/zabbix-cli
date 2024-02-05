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
from pathlib import Path
from typing import Optional

import typer
from click_repl import repl as start_repl
from prompt_toolkit.history import FileHistory
from rich.console import Group
from rich.panel import Panel

from zabbix_cli.__about__ import __version__
from zabbix_cli._v2_compat import run_command_from_option
from zabbix_cli.app import app
from zabbix_cli.auth import configure_auth
from zabbix_cli.bulk import run_bulk
from zabbix_cli.commands import bootstrap_commands
from zabbix_cli.config import Config
from zabbix_cli.config import create_config_file
from zabbix_cli.config import get_config
from zabbix_cli.config import OutputFormat
from zabbix_cli.exceptions import handle_exception
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.history import History
from zabbix_cli.logs import configure_logging
from zabbix_cli.logs import LogContext
from zabbix_cli.output.console import console
from zabbix_cli.output.console import error
from zabbix_cli.output.console import info
from zabbix_cli.output.formatting.path import path_link
from zabbix_cli.output.style.color import green
from zabbix_cli.state import get_state

logger = logging.getLogger("zabbix-cli")

bootstrap_commands()

history = History()


def try_load_config(config_file: Optional[Path]) -> None:
    """Attempts to load the config given a config file path.
    Assigns the loaded config to the global state.

    Parameters
    ----------
    config_file : Optional[Path]
        The path to the config file.
    create : bool, optional
        Whether to create a new config file if one is not found, by default True
    """
    # Don't load the config if it's already loaded (e.g. in REPL)
    state = get_state()
    if not state.is_config_loaded:
        try:
            conf = get_config(config_file)
        except FileNotFoundError:
            if not config_file:  # non-existant config file passed in is fatal
                raise ZabbixCLIError(f"Config file {config_file} not found.")

            info("Config file not found. Creating new config file.")
            config_path = create_config_file(config_file)
            info(f"Created config file: {path_link(config_path)}")
            conf = get_config(config_file)
            # TODO: run some sort of wizard so we can specify url, username and password
        except Exception as e:
            error(f"Unable to load config: {str(e)}", exc_info=True)
            return
        state.config = conf


def configure_state(config: Config) -> None:
    state = get_state()
    state.configure(config)


def run_repl(ctx: typer.Context) -> None:
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
        # TODO: find a better way to print a message ONCE at the start of the REPL
        if not state.repl:
            print_intro()
            state.repl = True
        state.revert_config_overrides()

    # TODO: add history file support
    prompt_kwargs = {"pre_run": pre_run}
    if state.config.app.history:
        prompt_kwargs["history"] = prompt_kwargs["history"] = FileHistory(
            str(state.config.app.history_file)
        )
    start_repl(ctx, prompt_kwargs=prompt_kwargs)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Define an alternative configuration file.",
    ),
    zabbix_command: str = typer.Option(
        "",
        "--command",
        "-C",
        help="Zabbix-CLI command to execute when running in command-line mode.",
    ),
    input_file: Optional[Path] = typer.Option(
        None,
        "--input-file",
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
) -> None:
    history.add(ctx)

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
    configure_auth(conf)  # NOTE: move into State.configure?
    configure_state(conf)

    # NOTE: LogContext is kept from <3.0.0. Do we still need it?
    with LogContext(logger, user=conf.app.username):
        # TODO: look at order of evaluation here. What takes precedence?
        # Should passing both --input-file and --command be an error? probably
        if zabbix_command:
            run_command_from_option(ctx, zabbix_command)
            return
        elif input_file:
            state
            run_bulk(ctx, input_file)
        elif ctx.invoked_subcommand is not None:
            return  # modern alternative to `-C` option to run a single command
        else:
            # If no command is passed in, we enter the REPL
            run_repl(ctx)


def main() -> None:
    """Main entry point for the CLI."""
    try:
        app()
    except Exception as e:
        handle_exception(e)
    else:
        print("\nDone, thank you for using Zabbix-CLI")
    finally:
        state = get_state()
        state.logout()
        logger.debug("Zabbix-CLI stopped.")


if __name__ == "__main__":
    main()
