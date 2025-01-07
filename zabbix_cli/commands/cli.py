"""Commands that interact with the application itself."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Optional

import typer
from click import Command

from zabbix_cli.app import app
from zabbix_cli.commands.common.args import OPTION_LIMIT
from zabbix_cli.config.constants import SecretMode
from zabbix_cli.dirs import CONFIG_DIR
from zabbix_cli.dirs import DATA_DIR
from zabbix_cli.dirs import EXPORT_DIR
from zabbix_cli.dirs import LOGS_DIR
from zabbix_cli.dirs import SITE_CONFIG_DIR
from zabbix_cli.exceptions import ConfigExistsError
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.console import print_path
from zabbix_cli.output.console import print_toml
from zabbix_cli.output.console import success
from zabbix_cli.output.formatting.path import path_link
from zabbix_cli.output.render import render_result
from zabbix_cli.utils.fs import open_directory

if TYPE_CHECKING:
    from zabbix_cli.config.model import Config


HELP_PANEL = "CLI"


class DirectoryType(Enum):
    """Directory types."""

    CONFIG = "config"
    DATA = "data"
    LOGS = "logs"
    SITE_CONFIG = "siteconfig"
    EXPORTS = "exports"

    def as_path(self) -> Path:
        DIR_MAP = {
            DirectoryType.CONFIG: CONFIG_DIR,
            DirectoryType.DATA: DATA_DIR,
            DirectoryType.LOGS: LOGS_DIR,
            DirectoryType.SITE_CONFIG: SITE_CONFIG_DIR,
            DirectoryType.EXPORTS: EXPORT_DIR,
        }
        d = DIR_MAP.get(self)
        if d is None:
            raise ZabbixCLIError(f"No default path available for {self!r}.")
        return d


def get_directory(directory_type: DirectoryType, config: Optional[Config]) -> Path:
    if config:
        if directory_type == DirectoryType.CONFIG and config.config_path:
            return config.config_path.parent
        elif directory_type == DirectoryType.EXPORTS:
            return config.app.export_directory
    return directory_type.as_path()


@app.command("debug", hidden=True, rich_help_panel=HELP_PANEL)
def debug_cmd(
    ctx: typer.Context,
    with_auth: bool = typer.Option(
        False, "--auth", help="Include auth token in the result."
    ),
) -> None:
    """Print debug info."""
    from zabbix_cli.commands.results.cli import DebugInfo

    render_result(DebugInfo.from_debug_data(app.state, with_auth=with_auth))


@app.command("help", rich_help_panel=HELP_PANEL)
def help(
    ctx: typer.Context,
    command: Optional[Command] = typer.Argument(None, help="Command name"),
) -> None:
    """Show help for a commmand"""
    # TODO: patch get_help() to make it return a string instead of magically
    # printing to stdout, which we have no control over.
    if not command:
        ctx.find_root().get_help()
        return

    # HACK: Set the info name to the resolved command name, otherwise
    # when we call get_help, it will use the name of the help command
    # instead of the resolved command name.
    # Maybe we can use make_context for this?
    ctx.info_name = command.name
    command.get_help(ctx)


@app.command("init", rich_help_panel=HELP_PANEL)
def init(
    ctx: typer.Context,
    config_file: Optional[Path] = typer.Option(
        None, "--config-file", "-c", help="Location of the config file."
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Overwrite existing config"
    ),
    url: Optional[str] = typer.Option(
        None, "--url", "-u", help="Zabbix API URL to use."
    ),
) -> None:
    """Create and initialize config file."""
    from zabbix_cli.config.utils import init_config

    try:
        init_config(config_file=config_file, overwrite=overwrite, url=url)
    except ConfigExistsError as e:
        raise ZabbixCLIError(f"{e}. Use [option]--overwrite[/] to overwrite it") from e


@app.command(name="login", rich_help_panel=HELP_PANEL)
def login(
    ctx: typer.Context,
    username: Optional[str] = typer.Option(
        None,
        "--username",
        "-u",
        help="Username to log in with.",
        show_default=False,
    ),
    password: Optional[str] = typer.Option(
        None,
        "--password",
        "-p",
        help="Password to log in with.",
        show_default=False,
    ),
    token: Optional[str] = typer.Option(
        None,
        "--token",
        "-t",
        help="API token to log in with.",
        show_default=False,
    ),
) -> None:
    """Trigger a new login prompt in the REPL.

    Ends the current session before triggering a new login prompt.

    Triggers a login prompt if [option]--username[/] & [option]--password[/] or [option]--token[/]
    is not provided.


    Creates a new auth token file if enabled in the config.
    """
    from pydantic import SecretStr

    from zabbix_cli.auth import Authenticator

    if not app.state.repl:
        raise ZabbixCLIError("This command is only available in the REPL.")

    # Copy config to avoid invalid/incomplete state if login fails
    config = app.state.config.model_copy(deep=True)

    # Set auth info in the config to use as defaults in prompts
    config.api.username = username or ""
    config.api.auth_token = SecretStr(token or "")
    config.api.password = SecretStr(password or "")

    # Try to end current session
    # We might not have an active session, which means any attempt to
    # terminate it will result in an error. Catch and log it.
    try:
        app.state.logout()
    except ZabbixCLIError as e:
        app.logger.warning(f"Failed to terminate session in login command: {e}")

    if username and password:
        client, info = Authenticator.login_with_username_password(
            config, username, password
        )
        success(f"Logged in to {config.api.url} as {info.credentials.username}.")
    elif token:
        client, info = Authenticator.login_with_token(config, token=token)
        success(f"Logged in to {config.api.url} with token.")
    else:
        client, info = Authenticator.login_with_prompt(config)
        success(f"Logged in to {config.api.url} as {info.credentials.username}.")

    app.state.client = client
    app.state.config = config


@app.command("migrate_config", rich_help_panel=HELP_PANEL)
def migrate_config(
    ctx: typer.Context,
    source: Optional[Path] = typer.Option(
        None, "--source", "-s", help="Location of the config file to migrate."
    ),
    destination: Optional[Path] = typer.Option(
        None,
        "--destination",
        "-d",
        help="Path of the new config file to create. Uses the default config path if not specified.",
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Overwrite destination config file if it exists."
    ),
    legacy_json: bool = typer.Option(
        False,
        "--legacy-json-format",
        help="Use legacy JSON format mode in the new config file.",
    ),
) -> None:
    """Migrate a legacy .conf config to a new .toml config.

    The new config file will be created in the default location if no destination is specified.
    The new config enables the new JSON format by default.
    """
    from zabbix_cli.config.constants import DEFAULT_CONFIG_FILE
    from zabbix_cli.config.model import Config

    if source:
        conf = Config.from_file(source)
    else:
        if not app.state.is_config_loaded:
            # this should never happen!
            exit_err(
                "Application was unable to load a config. Use [option]--source[/] to specify one."
            )
        conf = app.state.config

    if not conf.app.is_legacy:
        exit_err(
            "Unable to detect legacy config file. Use [option]--source[/] to specify one."
        )

    if not destination:
        destination = DEFAULT_CONFIG_FILE
    if not destination.suffix == ".toml":
        destination = destination.with_suffix(".toml")

    if destination.exists() and not overwrite:
        exit_err(
            f"File {destination} already exists. Use [option]--overwrite[/] to overwrite it."
        )

    # Set the legacy JSON format flag in the new file
    # By default, we move users over to the new format.
    conf.app.legacy_json_format = legacy_json

    conf.dump_to_file(destination)
    success(f"Config migrated to {destination}")


@app.command("open", rich_help_panel=HELP_PANEL)
def open_config_dir(
    ctx: typer.Context,
    directory_type: DirectoryType = typer.Argument(
        help="The type of directory to open.",
        case_sensitive=False,
        show_default=False,
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="LINUX: Try to open with [option]--command[/] even if no window manager is detected.",
    ),
    path: bool = typer.Option(
        False,
        "--path",
        help="Show path instead of opening directory.",
    ),
    open_command: Optional[str] = typer.Option(
        None,
        "--command",
        help="Specify command to use to use for opening.",
    ),
) -> None:
    """Open an app directory in the system's file manager.

    Use --force to attempt to open when no DISPLAY env var is set.
    """
    # Try to load the config, but don't fail if it's not available
    try:
        config = app.state.config
    except ZabbixCLIError:
        config = None

    directory = get_directory(directory_type, config)
    if path:
        print_path(directory)
    else:
        open_directory(directory, command=open_command, force=force)


@app.command("sample_config", rich_help_panel=HELP_PANEL)
def sample_config(ctx: typer.Context) -> None:
    """Print a sample configuration file."""
    # Load the entire history, then limit afterwards
    from zabbix_cli.config.model import Config

    conf = Config.sample_config()
    print_toml(conf.as_toml())


@app.command(
    "show_zabbixcli_config", rich_help_panel=HELP_PANEL, hidden=True, deprecated=True
)
@app.command("show_config", rich_help_panel=HELP_PANEL)
def show_config(
    ctx: typer.Context,
    secrets: SecretMode = typer.Option(
        SecretMode.MASK, "--secrets", help="Display mode for secrets."
    ),
) -> None:
    """Show the current application configuration."""
    config = app.state.config
    print_toml(config.as_toml(secrets=secrets))
    if config.config_path:
        info(f"Config file: {config.config_path.absolute()}")


@app.command("show_dirs", rich_help_panel=HELP_PANEL)
def show_directories(ctx: typer.Context) -> None:
    """Show the default directories used by the application."""
    from zabbix_cli.commands.results.cli import DirectoriesResult

    result = DirectoriesResult.from_directory_types(list(DirectoryType))
    render_result(result)


@app.command("show_history", rich_help_panel=HELP_PANEL)
def show_history(
    ctx: typer.Context,
    limit: int = OPTION_LIMIT,
    # TODO: Add --session option to limit to current session
    # In order to add that, we need to store the history len at the start of the session
) -> None:
    """Show the command history."""
    # Load the entire history, then limit afterwards
    from zabbix_cli.commands.results.cli import HistoryResult

    history = list(app.state.history.get_strings())
    history = history[-limit:]
    render_result(HistoryResult(commands=history))


@app.command("update_config", rich_help_panel=HELP_PANEL)
def update_config(
    ctx: typer.Context,
    config_file: Optional[Path] = typer.Option(
        None, "--config-file", "-c", help="Location of the config file to update."
    ),
    secrets: SecretMode = typer.Option(
        SecretMode.PLAIN, "--secrets", help="Visibility mode for secrets."
    ),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt."),
) -> None:
    """Update the config file with the current application state.

    Adds missing fields and updates deprecated fields to their new values."""
    from zabbix_cli.output.prompts import bool_prompt

    config_file = config_file or app.state.config.config_path
    if not config_file:
        exit_err("No config file specified and no config loaded.")
    if not force:
        if not bool_prompt("Update config file?", default=False):
            exit_err("Update cancelled.")

    config = app.state.config
    config.dump_to_file(config_file, secrets=secrets)
    success(f"Config saved to {path_link(config_file)}")


@app.command("update", rich_help_panel=HELP_PANEL, hidden=True)
def update_application(ctx: typer.Context) -> None:
    """Update the application to the latest version.

    Primarily intended for use with PyInstaller builds, but can also be
    used for updating other installations (except Homebrew)."""
    from zabbix_cli.__about__ import __version__
    from zabbix_cli.update import update

    info = update()
    if info and info.version:
        success(f"Application updated from {__version__} to {info.version}")
    else:
        success("Application updated.")
