#!/usr/bin/env python
#
# Authors:
# rafael@e-mc2.net / https://e-mc2.net/
#
# Copyright (c) 2014-2024 USIT-University of Oslo
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
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Zabbix-CLI.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Optional

import typer

from zabbix_cli.__about__ import __version__
from zabbix_cli.app import app
from zabbix_cli.config.constants import OutputFormat
from zabbix_cli.config.utils import get_config
from zabbix_cli.logs import configure_logging
from zabbix_cli.logs import logger
from zabbix_cli.state import get_state

if TYPE_CHECKING:
    from typing import Any


def run_repl(ctx: typer.Context) -> None:
    from rich.console import Group
    from rich.panel import Panel

    from zabbix_cli.output.console import console
    from zabbix_cli.output.style import green
    from zabbix_cli.repl.repl import repl as start_repl
    from zabbix_cli.state import get_state

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

    prompt_kwargs: dict[str, Any] = {"pre_run": pre_run, "history": state.history}
    start_repl(ctx, app, prompt_kwargs=prompt_kwargs)


def version_callback(value: bool):
    if value:
        print(f"zabbix-cli version {__version__}")
        raise typer.Exit()


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
        "--format",
        "--output-format",  # DEPRECATED: V2 name for compatibility
        "-o",
        help="Define the output format when running in command-line mode.",
        case_sensitive=False,
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        help="Show the version of Zabbix-CLI and exit.",
        is_eager=True,
        callback=version_callback,
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

    state = get_state()
    if not should_skip_configuration(ctx) and not state.is_config_loaded:
        state.config = get_config(config_file, init=True)

    # Config overrides are always applied
    if output_format is not None:
        state.config.app.output.format = output_format

    if state.repl or state.bulk:
        return  # In REPL or bulk mode already; no need to re-configure.

    logger.debug("Zabbix-CLI started.")

    if should_skip_login(ctx):
        return

    state.login()
    # Configure plugins _after_ login
    # This allows plugins to use the Zabbix API client + more
    # in their __configure__ functions.
    app.configure_plugins(state.config)

    # TODO: look at order of evaluation here. What takes precedence?
    # Should passing both --input-file and --command be an error? probably!
    if zabbix_command:
        from zabbix_cli._v2_compat import run_command_from_option

        run_command_from_option(ctx, zabbix_command)
        return
    elif input_file:
        from zabbix_cli.bulk import run_bulk

        run_bulk(ctx, input_file, state.config.app.bulk_mode)
    elif ctx.invoked_subcommand is not None:
        return  # modern alternative to `-C` option to run a single command
    else:
        # If no command is passed in, we enter the REPL
        run_repl(ctx)


# TODO: Add a decorator for skipping or some sort of parameter to the existing
#       StatefulApp.command method that marks a command as not requiring
#       a configuration file to be loaded.


def should_skip_configuration(ctx: typer.Context) -> bool:
    """Check if the command should skip all configuration of the app."""
    return ctx.invoked_subcommand in [
        "update",
        "open",
        "sample_config",
        "show_dirs",
        "init",
    ]


def should_skip_login(ctx: typer.Context) -> bool:
    """Check if the command should skip logging in to the Zabbix API."""
    if should_skip_configuration(ctx):
        return True
    return ctx.invoked_subcommand in ["migrate_config"]


def _parse_config_arg() -> Optional[Path]:
    """Get a custom config file path from the command line arguments.

    Modifies sys.argv in place to remove the --config/-c option and its
    argument in order to load the config before instantiating the Typer app.

    This hack enables us to read plugins from the configuration file
    and load them _before_ we call `app()`. This lets commands defined
    in plugins to be used in single-command mode as well as showing up
    when the user types `--help`. Otherwise, the plugin commands would
    not be registered to the active Click command group that drives the CLI.
    """
    opts = ["--config", "-c"]
    for opt in opts:
        if opt in sys.argv:
            index = sys.argv.index(opt)
            break
    else:
        return None

    # If we have the option, we need an argument
    if not len(sys.argv) > index + 1 or not (conf := sys.argv[index + 1].strip()):
        from zabbix_cli.output.console import exit_err

        exit_err("No value provided for --config/-c argument.")
    return Path(conf)


def main() -> int:
    """Main entry point for the CLI."""
    state = get_state()

    try:
        # Load config before launching the app in order to:
        # - configure logging
        # - configure console output
        # - load local plugins (defined in the config)
        configure_logging()
        conf = _parse_config_arg()
        config = get_config(conf, init=False)
        state.config = config
        app.load_plugins(state.config)
        app()
    except Exception as e:
        from zabbix_cli.exceptions import handle_exception

        handle_exception(e)
    finally:
        state.logout_on_exit()
        logger.debug("Zabbix-CLI stopped.")
    return 0


if __name__ == "__main__":
    main()
