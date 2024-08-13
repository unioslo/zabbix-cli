"""Commands that interact with the application itself."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Optional

import typer

from zabbix_cli.app import app
from zabbix_cli.dirs import CONFIG_DIR
from zabbix_cli.dirs import DATA_DIR
from zabbix_cli.dirs import EXPORT_DIR
from zabbix_cli.dirs import LOGS_DIR
from zabbix_cli.dirs import SITE_CONFIG_DIR
from zabbix_cli.exceptions import ConfigExistsError
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.output.console import info
from zabbix_cli.output.console import print_path
from zabbix_cli.output.console import print_toml
from zabbix_cli.output.console import success
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.output.render import render_result
from zabbix_cli.utils.utils import open_directory

if TYPE_CHECKING:
    from zabbix_cli.config.model import Config


HELP_PANEL = "CLI"


@app.command(
    "show_zabbixcli_config", rich_help_panel=HELP_PANEL, hidden=True, deprecated=True
)
@app.command("show_config", rich_help_panel=HELP_PANEL)
def show_config(ctx: typer.Context) -> None:
    """Show the current application configuration."""
    config = app.state.config
    print_toml(config.as_toml())
    if config.config_path:
        info(f"Config file: {config.config_path}")


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
        is_flag=True,
        help="LINUX: Try to open desite no detected window manager.",
    ),
    path: bool = typer.Option(
        False,
        "--path",
        is_flag=True,
        help="Show path instead of opening directory.",
    ),
    open_command: Optional[str] = typer.Option(
        None,
        "--command",
        help="Specify command to use to use for opening.",
    ),
) -> None:
    """Opens an app directory in the system's file manager.

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
        success(f"Opened {directory}")


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


@app.command(name="login", rich_help_panel=HELP_PANEL)
def login(
    ctx: typer.Context,
    username: str = typer.Option(
        None, "--username", "-u", help="Username to log in with."
    ),
    password: str = typer.Option(
        None, "--password", "-p", help="Password to log in with."
    ),
    token: str = typer.Option(None, "--token", "-t", help="API token to log in with."),
) -> None:
    """Reauthenticate with the Zabbix API.

    Creates a new auth token file if enabled in the config.
    """
    from pydantic import SecretStr

    if not app.state.repl:
        raise ZabbixCLIError("This command is only available in the REPL.")

    config = app.state.config

    # Prompt for password if username is specified
    if username and not password:
        password = str_prompt(
            "Password",
            password=True,
            empty_ok=False,
        )

    if username:
        config.api.username = username
        config.api.password = SecretStr(password)
        config.api.auth_token = None  # Clear token if it exists
    elif token:
        config.api.auth_token = SecretStr(token)
        config.api.password = SecretStr("")

    # End current session if it's active
    app.state.logout()
    app.state.login()
    success(f"Logged in to {config.api.url} as {config.api.username}.")


@app.command("show_history", rich_help_panel=HELP_PANEL)
def show_history(
    ctx: typer.Context,
    limit: int = typer.Option(
        10, "--limit", "-N", help="Limit to last N commands. 0 to disable.", min=0
    ),
    # TODO: Add --session option to limit to current session
    # In order to add that, we need to store the history len at the start of the session
) -> None:
    """Show the command history."""
    # Load the entire history, then limit afterwards
    from zabbix_cli.commands.results.cli import HistoryResult

    history = list(app.state.history.get_strings())
    history = history[-limit:]
    render_result(HistoryResult(commands=history))


@app.command("sample_config", rich_help_panel=HELP_PANEL)
def sample_config(ctx: typer.Context) -> None:
    """Print a sample configuration file."""
    # Load the entire history, then limit afterwards
    from zabbix_cli.config.model import Config

    conf = Config.sample_config()
    print_toml(conf.as_toml())


@app.command("init", rich_help_panel=HELP_PANEL)
def init(
    ctx: typer.Context,
    config_file: Optional[Path] = typer.Option(
        None, "--config-file", "-c", help="Location of the config file."
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Overwrite existing config"
    ),
) -> None:
    """Create and initialize config file."""
    from zabbix_cli.config.utils import init_config

    try:
        init_config(config_file=config_file, overwrite=overwrite)
    except ConfigExistsError as e:
        raise ZabbixCLIError(f"{e}. Use [option]--overwrite[/] to overwrite it") from e
