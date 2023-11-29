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
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Zabbix-CLI.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import annotations

import getpass
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from click_repl import repl as start_repl

from zabbix_cli.__about__ import __version__
from zabbix_cli.auth import configure_auth
from zabbix_cli.bulk import load_command_file
from zabbix_cli.cli import zabbixcli
from zabbix_cli.commands import app
from zabbix_cli.config import Config
from zabbix_cli.config import create_config_file
from zabbix_cli.config import get_config
from zabbix_cli.config import OutputFormat
from zabbix_cli.exceptions import handle_exception
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.logs import configure_logging
from zabbix_cli.logs import LogContext
from zabbix_cli.output.console import error
from zabbix_cli.output.console import info
from zabbix_cli.output.formatting.path import path_link
from zabbix_cli.state import get_state

logger = logging.getLogger("zabbix-cli")


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

    intro = f"""
#############################################################
Welcome to the Zabbix command-line interface (v{__version__})
Connected to server {state.config.api.url} (v{state.client.version})
#############################################################
Type --help for a list of commands, :h for a list of REPL commands, :q to exit.
"""

    # TODO: find a better way to print a message ONCE at the start of the REPL
    def print_intro() -> None:
        state = get_state()
        if not state.repl:
            print(intro)
            state.repl = True

    # TODO: add history file support
    prompt_kwargs = {"pre_run": print_intro}
    try:
        start_repl(ctx, prompt_kwargs=prompt_kwargs)
    finally:
        state.logout()


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
    ),
) -> None:
    logger.debug("Zabbix-CLI started.")
    state = get_state()
    if state.is_config_loaded:
        conf = state.config
    else:
        conf = get_config(config_file)

    # Overrides for config options can be (re-)applied here
    if output_format is not None:
        conf.app.output_format = output_format

    # If we are already inside the REPL, we don't need re-run configuration
    if state.repl:
        return

    configure_logging(conf.logging)
    configure_auth(conf)  # NOTE: move into State.configure?
    configure_state(conf)

    if zabbix_command:
        # run command here
        pass
    elif input_file:
        commands = load_command_file(input_file)  # noqa
    else:
        raise SystemExit(run_repl(ctx))

    try:
        #
        # If logging is activated, start logging to the file defined
        # with log_file in the config file.
        #'

        #
        # Non-interactive authentication procedure
        #
        # If the file .zabbix_cli_auth exists at $HOME, use the
        # information in this file to authenticate into Zabbix API
        #
        # Format:
        # <Zabbix username>::<password>
        #
        # Use .zabbix-cli_auth_token if it exists and .zabbix_cli_auth
        # does not exist.
        #
        # Format:
        # <Zabbix username>::<API-token>
        #

        auth_token = ""
        username = ""
        password = ""
        zabbix_auth_file = ""
        zabbix_auth_token_file = ""

        if os.getenv("HOME") is not None:
            zabbix_auth_file = os.getenv("HOME") + "/.zabbix-cli_auth"
            zabbix_auth_token_file = os.getenv("HOME") + "/.zabbix-cli_auth_token"

        else:
            print(
                "\n[ERROR]: The $HOME environment variable is not defined. Zabbix-CLI cannot read ~/.zabbix-cli_auth or ~/.zabbix-cli_auth_token"
            )

            logger.error(
                "The $HOME environment variable is not defined. Zabbix-CLI cannot read ~/.zabbix-cli_auth or ~/.zabbix-cli_auth_token"
            )

            sys.exit(1)

        env_username = os.getenv("ZABBIX_USERNAME")
        env_password = os.getenv("ZABBIX_PASSWORD")

        if env_username is not None and env_password is not None:
            username = env_username
            password = env_password

            logger.info(
                "Environment variables ZABBIX_USERNAME and ZABBIX_PASSWORD exist. Using these variables to get authentication information"
            )

        elif os.path.isfile(zabbix_auth_file):
            try:
                # TODO: This should be done when writing the file.
                #       If permissions are wrong here, we should refuse using
                #       it, ssh style.
                os.chmod(zabbix_auth_file, 0o400)

                with open(zabbix_auth_file) as f:
                    for line in f:
                        (username, password) = line.split("::")

                password = password.replace("\n", "")
                logger.info(
                    "File %s exists. Using this file to get authentication information",
                    zabbix_auth_file,
                )

            except Exception as e:
                print("\n[ERROR]:" + str(e) + "\n")

                logger.error("Problems using file %s - %s", zabbix_auth_file, e)

        elif os.path.isfile(zabbix_auth_token_file):
            try:
                # TODO: This should be done when writing the file.
                #       If permissions are wrong here, we should refuse using
                #       it, ssh style.
                os.chmod(zabbix_auth_token_file, 0o600)

                with open(zabbix_auth_token_file) as f:
                    for line in f:
                        (username, auth_token) = line.split("::")

                logger.info(
                    "File %s exists. Using this file to get authentication token information",
                    zabbix_auth_token_file,
                )

            except Exception as e:
                print("\n[ERROR]:" + str(e) + "\n")

                logger.error("Problems using file %s - %s", zabbix_auth_token_file, e)

        #
        # Interactive authentication procedure
        #

        else:
            default_user = getpass.getuser()

            print("-------------------------")
            print("Zabbix-CLI authentication")
            print("-------------------------")

            try:
                username = input("# Username[" + default_user + "]: ")
                password = getpass.getpass("# Password: ")

            except Exception:
                print("\n[Aborted]\n")
                sys.exit(0)

            if username == "":
                username = default_user

        #
        # Check that username and password have some values if the
        # API-auth-token is empty ($HOME/.zabbix-cli_auth_token does
        # not exist)
        #

        if auth_token == "":
            if username == "" or password == "":
                print("\n[ERROR]: Username or password is empty\n")
                logger.error("Username or password is empty")

                sys.exit(1)

        with LogContext(logger, user=username):
            #
            # Zabbix-CLI in interactive modus
            #

            if zabbix_command == "" and input_file is None:
                logger.debug("Zabbix-CLI running in interactive modus")

                os.system("clear")

                cli = zabbixcli(conf, username, password, auth_token)

                cli.cmdloop()

            #
            # Zabbix-CLI in bulk execution modus.
            #
            # This mode is activated when we run zabbix-cli with the
            # parameter -f to define a file with zabbix-cli commands.
            #

            elif zabbix_command == "" and input_file is not None:
                cli = zabbixcli(conf, username, password, auth_token)

                # Normalized absolutized version of the pathname if
                # files does not include an absolute path

                if os.path.isabs(input_file) is False:
                    input_file = os.path.abspath(input_file)

                if os.path.exists(input_file):
                    logger.info(
                        "File [%s] exists. Bulk execution of commands defined in this file.",
                        input_file,
                    )

                    print(
                        "[OK] File ["
                        + input_file
                        + "] exists. Bulk execution of commands defined in this file started."
                    )

                    #
                    # Register that this is a bulk execution via -f
                    # parameter. This will activate some performance
                    # improvements to boost bulk execution.
                    #

                    cli.bulk_execution = True

                    # Register CSV output format

                    if output_format == "csv":
                        cli.output_format = "csv"

                    # Register JSON output format

                    elif output_format == "json":
                        cli.output_format = "json"

                    # Register Table output format

                    else:
                        cli.output_format = "table"

                    #
                    # Processing zabbix commands in file.
                    #
                    # Empty lines or comment lines (started with #) will
                    # not be considered.

                    try:
                        with open(input_file) as f:
                            for input_line in f:
                                if (
                                    input_line.find("#", 0) == -1
                                    and input_line.strip() != ""
                                ):
                                    zabbix_cli_command = input_line.strip()
                                    cli.onecmd(zabbix_cli_command)

                                    logger.info(
                                        "Zabbix-cli command [%s] executed via input file",
                                        zabbix_cli_command,
                                    )

                    except Exception as e:
                        logger.error(
                            "Problems using input file [%s] - %s", input_file, e
                        )

                        print(
                            "[ERROR] Problems using input file ["
                            + input_file
                            + "] - "
                            + str(e)
                        )
                        sys.exit(1)

                else:
                    logger.info(
                        "Input file [%s] does not exist. Bulk execution of commands aborted.",
                        input_file,
                    )

                    print(
                        "[ERROR] Input file ["
                        + input_file
                        + "] does not exist. Bulk execution of commands aborted"
                    )

            #
            # Zabbix-CLI in non-interactive modus(command line)
            #

            elif zabbix_command != "":
                logger.debug("Zabbix-CLI running in non-interactive modus")

                # CSV format output

                if output_format == "csv":
                    cli = zabbixcli(conf, username, password, auth_token)
                    cli.output_format = "csv"
                    cli.non_interactive = True

                    cli.onecmd(zabbix_command)

                # JSON format output

                elif output_format == "json":
                    cli = zabbixcli(conf, username, password, auth_token)
                    cli.output_format = "json"
                    cli.non_interactive = True

                    cli.onecmd(zabbix_command)

                # Table format output

                else:
                    cli = zabbixcli(conf, username, password, auth_token)
                    cli.output_format = "table"
                    cli.non_interactive = True

                    cli.onecmd(zabbix_command)

            else:
                raise NotImplementedError

            logger.debug("**** Zabbix-CLI stopped. ****")

        sys.exit(0)

    except KeyboardInterrupt:
        print()
        print("\nDone, thank you for using Zabbix-CLI")

        logger.debug("**** Zabbix-CLI stopped. ****")

        sys.exit(0)

    except Exception as e:
        print("\n[ERROR]:" + str(e) + "\n")
        raise


def main() -> None:
    """Main entry point for the CLI."""
    try:
        app()
    except Exception as e:
        handle_exception(e)
    finally:
        state = get_state()
        state.logout()


if __name__ == "__main__":
    main()
