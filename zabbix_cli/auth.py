from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable
from typing import Final
from typing import Optional
from typing import Tuple

from zabbix_cli._v2_compat import AUTH_FILE as AUTH_FILE_LEGACY
from zabbix_cli._v2_compat import AUTH_TOKEN_FILE as AUTH_TOKEN_FILE_LEGACY
from zabbix_cli.config import Config
from zabbix_cli.config import ENV_ZABBIX_PASSWORD
from zabbix_cli.config import ENV_ZABBIX_USERNAME
from zabbix_cli.dirs import DATA_DIR
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.output.console import error
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import warning
from zabbix_cli.output.prompts import str_prompt

logger = logging.getLogger(__name__)

AuthFunc = Callable[[Config], Optional[Tuple[str, str]]]
"""Function that returns a username/password tuple or None if not available."""

# Auth file location
AUTH_FILE = DATA_DIR / ".zabbix-cli_auth"
AUTH_TOKEN_FILE = DATA_DIR / ".zabbix-cli_auth_token"

SECURE_PERMISSIONS: Final[int] = 0o600
SECURE_PERMISSIONS_STR = format(SECURE_PERMISSIONS, "o")


def configure_auth(config: Config) -> None:
    """Configure Zabbix API authentication.

    The different authentication functions modify the Config object in-place.
    """
    # Use token file if enabled
    if config.app.use_auth_token_file:
        configure_auth_token(config)
    # Always fall back on username/password if token cannot be loaded or is disabled
    if not config.app.auth_token:
        configure_auth_username_password(config)

    # Sanity checks to ensure our auth functions set the required info
    # This should never happen.
    if not (config.app.username and config.app.password) and not config.app.auth_token:
        raise ZabbixCLIError(
            "No authentication method configured. Cannot continue. Please check your configuration file."
        )


def configure_auth_token(config: Config) -> None:
    contents = load_auth_token_file(config)
    username, auth_token = _parse_auth_file_contents(contents)
    # If we have a mismatch between username in config and auth token, we
    # can't use the auth token. We don't clear it here, but it will never be
    # loaded by us as long as the usernames don't match.
    # When we prompt for username and password and store the new auth token,
    # the old auth token will be overwritten.
    if username and username != config.app.username:
        warning(
            "Ignoring existing auth token. "
            f"Username {username!r} does not match configured username {config.app.username!r}."
        )
        return
    if auth_token:  # technically not needed, but might as well
        config.app.auth_token = auth_token


def configure_auth_username_password(config: Config) -> Tuple[str, str]:
    """Gets a Zabbix username and password with the following priority:

    1. Environment variables
    2. Auth file
    3. Prompt for it
    """
    funcs = [_get_username_password_env, _get_username_password_auth_file]  # type: list[AuthFunc]
    for func in funcs:
        username, password = func(config)
        if username and password:
            return username, password
    # Found no auth methods, prompt for it
    username, password = _prompt_username_password(config)
    config.app.username = username
    config.app.password = password


def load_auth_token_file(config: Config) -> Optional[str]:
    files = (AUTH_TOKEN_FILE, AUTH_TOKEN_FILE_LEGACY)
    for file in files:
        contents = _do_load_auth_file(file, config.app.allow_insecure_authfile)
        if contents:
            return contents
    logging.debug(
        f"No auth token file found. Searched in {', '.join(str(f) for f in files)}"
    )
    return None


def write_auth_token_file(
    username: str, auth_token: str, file: Path = AUTH_TOKEN_FILE
) -> Path:
    """Write a username/auth token pair to the auth token file."""
    contents = f"{username}::{auth_token}"
    if not file.exists():
        try:
            file.touch(mode=SECURE_PERMISSIONS)
        except OSError:
            exit_err(f"Unable to create auth token file {file}.")
    elif not file_has_secure_permissions(file):
        try:
            file.chmod(SECURE_PERMISSIONS)
        except OSError:
            exit_err(
                f"Unable to set secure permissions ({SECURE_PERMISSIONS_STR}) on {file} when saving auth token. "
                "Change permissions manually or delete the file."
            )
    file.write_text(contents)
    logger.debug(f"Wrote auth token file {file}")
    return file


def _prompt_username_password(config: Config) -> Tuple[str, str]:
    """Prompt for username and password."""
    username = str_prompt("Username", default=config.app.username)
    password = str_prompt("Password", password=True)
    return username, password


def _get_username_password_env(config: Config) -> Optional[Tuple[str, str]]:
    """Get username and password from environment variables."""
    username = os.environ.get(ENV_ZABBIX_USERNAME)
    password = os.environ.get(ENV_ZABBIX_PASSWORD)
    return username, password


# TODO: refactor. Support other auth file locations(?)
def _get_username_password_auth_file(config: Config) -> Optional[Tuple[str, str]]:
    """Get username and password from environment variables."""
    contents = load_auth_file(config)
    return _parse_auth_file_contents(contents)


def _parse_auth_file_contents(contents: str) -> Tuple[Optional[str], Optional[str]]:
    if contents:
        lines = contents.splitlines()
        if lines:
            line = lines[0].strip()
            username, sep, secret = line.partition("::")
            return username, secret
    return None, None


def load_auth_file(config: Config) -> Optional[str]:
    # TODO: refactor. re-use code from load_auth_token_file
    files = (AUTH_FILE, AUTH_FILE_LEGACY)
    for file in files:
        contents = _do_load_auth_file(file, config.app.allow_insecure_authfile)
        if contents:
            return contents
    logging.debug(f"No auth file found. Searched in {', '.join(str(f) for f in files)}")
    return None


def _do_load_auth_file(file: Path, allow_insecure: bool) -> Optional[str]:
    """Attempts to read the contents of an auth file.
    Returns None if the file does not exist or is not secure.
    """
    if not file.exists():
        return None
    permissions = file.stat().st_mode & 0o777
    if not allow_insecure and permissions != 0o600:
        error(
            f"Auth file {file} must have 600 permissions, has {oct(permissions)}. Refusing to load."
        )
        return None
    return file.read_text().strip()


def file_has_secure_permissions(file: Path) -> bool:
    """Check if a file has secure permissions."""
    return file.stat().st_mode & 0o777 == SECURE_PERMISSIONS
