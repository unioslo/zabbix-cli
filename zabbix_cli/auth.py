""""Module for loading/storing Zabbix API authentication info.

Manages the following:
- Loading and saving auth token files (file containing API session token)
- Loading and saving auth files (file containing username and password)
- Loading username and password from environment variables
- Prompting for username and password
- Updating the Config object with the authentication information
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable
from typing import Final
from typing import Optional
from typing import Tuple

from pydantic import SecretStr

from zabbix_cli._v2_compat import AUTH_FILE as AUTH_FILE_LEGACY
from zabbix_cli._v2_compat import AUTH_TOKEN_FILE as AUTH_TOKEN_FILE_LEGACY
from zabbix_cli.config import Config
from zabbix_cli.config import ENV_ZABBIX_PASSWORD
from zabbix_cli.config import ENV_ZABBIX_USERNAME
from zabbix_cli.dirs import DATA_DIR
from zabbix_cli.exceptions import AuthTokenFileError
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.output.console import error
from zabbix_cli.output.console import warning
from zabbix_cli.output.prompts import str_prompt

logger = logging.getLogger(__name__)

AuthFunc = Callable[[Config], Tuple[Optional[str], Optional[str]]]
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
        config.app.auth_token = SecretStr(auth_token)


def configure_auth_username_password(config: Config) -> None:
    """Gets a Zabbix username and password with the following priority:

    1. Environment variables
    2. Auth file
    3. Prompt for it
    """
    funcs = [_get_username_password_env, _get_username_password_auth_file]  # type: list[AuthFunc]
    for func in funcs:
        username, password = func(config)
        if username and password:
            break
    else:
        # Found no auth methods, prompt for it
        username, password = _prompt_username_password(config)
    config.app.username = username
    config.app.password = SecretStr(password)


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
        except OSError as e:
            raise AuthTokenFileError(f"Unable to create auth token file {file}.") from e
    elif not file_has_secure_permissions(file):
        try:
            file.chmod(SECURE_PERMISSIONS)
        except OSError as e:
            raise AuthTokenFileError(
                f"Unable to set secure permissions ({SECURE_PERMISSIONS_STR}) on {file} when saving auth token. "
                "Change permissions manually or delete the file."
            ) from e
    file.write_text(contents)
    logger.debug(f"Wrote auth token file {file}")
    return file


def clear_auth_token_file() -> None:
    """Clear the contents of the auth token file.
    Attempts to clear both the new and the old auth token file locations.
    """
    for file in (AUTH_TOKEN_FILE, AUTH_TOKEN_FILE_LEGACY):
        try:
            _do_clear_auth_token_file(file)
        except OSError as e:
            # Only happens if file exists and we fail to write to it.
            error(f"Unable to clear auth token file {file}: {e}")


def _do_clear_auth_token_file(file: Path) -> None:
    if file.exists():
        file.write_text("")
        logger.debug(f"Cleared auth token file contents {file}")
    else:
        logger.debug(f"Auth token file {file} does not exist. Skipping...")


def _prompt_username_password(config: Config) -> Tuple[str, str]:
    """Prompt for username and password."""
    username = str_prompt("Username", default=config.app.username)
    password = str_prompt("Password", password=True)
    return username, password


def _get_username_password_env(config: Config) -> Tuple[Optional[str], Optional[str]]:
    """Get username and password from environment variables."""
    username = os.environ.get(ENV_ZABBIX_USERNAME)
    password = os.environ.get(ENV_ZABBIX_PASSWORD)
    return username, password


# TODO: refactor. Support other auth file locations(?)
def _get_username_password_auth_file(
    config: Config
) -> Tuple[Optional[str], Optional[str]]:
    """Get username and password from environment variables."""
    contents = load_auth_file(config)
    return _parse_auth_file_contents(contents)


def _parse_auth_file_contents(
    contents: Optional[str]
) -> Tuple[Optional[str], Optional[str]]:
    if contents:
        lines = contents.splitlines()
        if lines:
            line = lines[0].strip()
            username, _, secret = line.partition("::")
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
    if not allow_insecure and not file_has_secure_permissions(file):
        error(
            f"Auth file {file} must have {SECURE_PERMISSIONS_STR} permissions, has {oct(get_file_permissions(file))}. Refusing to load."
        )
        return None
    return file.read_text().strip()


def file_has_secure_permissions(file: Path) -> bool:
    """Check if a file has secure permissions."""
    return get_file_permissions(file) == SECURE_PERMISSIONS


def get_file_permissions(file: Path) -> int:
    """Get the 3 digit octal permissions of a file."""
    return file.stat().st_mode & 0o777
