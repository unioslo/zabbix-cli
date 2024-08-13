""" "Module for loading/storing Zabbix API authentication info.

Manages the following:
- Loading and saving auth token files (file containing API session token)
- Loading and saving auth files (file containing username and password)
- Loading username and password from environment variables
- Prompting for username and password
- Updating the Config object with the loaded authentication information
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Callable
from typing import Final
from typing import List
from typing import Optional
from typing import Tuple

from zabbix_cli._v2_compat import AUTH_FILE as AUTH_FILE_LEGACY
from zabbix_cli._v2_compat import AUTH_TOKEN_FILE as AUTH_TOKEN_FILE_LEGACY
from zabbix_cli.config.constants import AUTH_FILE
from zabbix_cli.config.constants import AUTH_TOKEN_FILE
from zabbix_cli.config.constants import ConfigEnvVars
from zabbix_cli.exceptions import AuthError
from zabbix_cli.exceptions import AuthTokenFileError
from zabbix_cli.exceptions import ZabbixAPIException
from zabbix_cli.output.console import error
from zabbix_cli.output.console import warning
from zabbix_cli.output.prompts import str_prompt

if TYPE_CHECKING:
    from zabbix_cli.config.model import Config
    from zabbix_cli.pyzabbix.client import ZabbixAPI

    UsernamePWMethod = Callable[[], Tuple[Optional[str], Optional[str]]]
    """Function that returns a username/password tuple or None if not available."""

    AuthMethod = Callable[[], str]

logger = logging.getLogger(__name__)


# Auth file location


SECURE_PERMISSIONS: Final[int] = 0o600
SECURE_PERMISSIONS_STR = format(SECURE_PERMISSIONS, "o")


class Authenticator:
    """Encapsulates logic for authenticating with the Zabbix API
    using various methods, as well as storing and loading auth tokens."""

    client: ZabbixAPI
    config: Config

    def __init__(self, client: ZabbixAPI, config: Config) -> None:
        self.client = client
        self.config = config

    def login(self) -> str:
        """Log in to the Zabbix API using the configured credentials.

        If multiple methods are available, they are tried in the following order:

        1. API token in config file
        2. API token in file (if `use_auth_token_file=true`)
        3. Username and password in config file
        4. Username and password in auth file
        5. Username and password in environment variables
        6. Username and password from prompt
        """
        # HACK: ensure that client auth token is cleared before entering login flow.
        # The client may have an auth token already!
        # We also can't rely on comparing new and old tokens, because if we use
        # an API auth token, we get the same token back.
        self.client.auth = ""
        for func in [
            self.login_with_auth_token_from_config,
            self.login_with_auth_token_file,
            self.login_with_username_password_auto,
        ]:
            try:
                auth_token = func()
                if auth_token:
                    logger.debug("Logged in with %s", func.__name__)
                    break
            except ZabbixAPIException as e:
                logger.warning("Failed to log in with %s: %s", func.__name__, e)
                continue
        else:
            raise AuthError("No authentication method succeeded.")
        return auth_token

    def login_with_username_password(
        self, username: Optional[str] = None, password: Optional[str] = None
    ) -> str:
        return self.client.login(user=username, password=password)

    def login_with_username_password_auto(self) -> Optional[str]:
        """Automatically get a username and password and log in"""
        username, password = self.get_username_password()
        if username and password:
            return self.login_with_username_password(username, password)

    def get_username_password(self) -> Tuple[Optional[str], Optional[str]]:
        """Gets a Zabbix username and password with the following priority:

        1. Config file
        2. Auth file
        3. Environment variables
        4. Prompt for it
        """
        funcs: List[UsernamePWMethod] = [
            self._get_username_password_from_config,
            self._get_username_password_auth_file,
            self._get_username_password_env,
            self._get_username_password_from_prompt,
        ]
        for func in funcs:
            username, password = func()
            if username and password:
                logger.debug(f"Got username and password from {func.__name__}")
                return username, password
        error("No username and password found.")
        return None, None

    def _get_username_password_env(self) -> Tuple[Optional[str], Optional[str]]:
        """Get username and password from environment variables."""
        username = os.environ.get(ConfigEnvVars.USERNAME)
        password = os.environ.get(ConfigEnvVars.PASSWORD)
        return username, password

    # TODO: refactor. Support other auth file locations(?)
    def _get_username_password_auth_file(
        self,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get username and password from environment variables."""
        contents = self.load_auth_file()
        return _parse_auth_file_contents(contents)

    def _get_username_password_from_config(
        self,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get username and password from config file."""
        return (self.config.api.username, self.config.api.password.get_secret_value())

    def _get_username_password_from_prompt(
        self,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get username and password from prompt."""
        return prompt_username_password(username=self.config.api.username)

    def login_with_auth_token_from_config(self) -> str:
        if self.config.api.auth_token:
            self.client.login(auth_token=self.config.api.auth_token.get_secret_value())
        return self.client.auth

    def login_with_auth_token_file(self) -> Optional[str]:
        if not self.config.app.use_auth_token_file:
            return None

        contents = self._load_auth_token_file()
        # FIXME: requires username to login with token here!
        # That is not actually the case in the API itself
        username, auth_token = _parse_auth_file_contents(contents)
        if not auth_token:
            return None
        if username and username == self.config.api.username:
            return self.client.login(auth_token=auth_token)
        # Found token, but does match configured username
        warning(
            "Ignoring existing auth token. "
            f"Username {username!r} does not match configured username {self.config.api.username!r}."
        )

    def _load_auth_token_file(self) -> Optional[str]:
        paths = get_auth_token_file_paths(self.config)
        for path in paths:
            contents = _do_load_auth_file(path, self.config.app.allow_insecure_authfile)
            if contents:
                return contents
        logger.error(
            f"No auth token file found. Searched in {', '.join(str(p) for p in paths)}"
        )

    def load_auth_file(self) -> Optional[str]:
        """Loads a"""
        paths = get_auth_file_paths(self.config)
        for path in paths:
            contents = self._load_auth_file(path)
            if contents:
                return contents
        logger.error(
            f"No auth file found. Searched in {', '.join(str(p) for p in paths)}"
        )

    def _load_auth_file(self, file: Path) -> Optional[str]:
        """Attempts to read the contents of an auth file.
        Returns None if the file does not exist or is not secure.
        """
        if not file.exists():
            return None
        if (
            not self.config.app.allow_insecure_authfile
            and not file_has_secure_permissions(file)
        ):
            error(
                f"Auth file {file} must have {SECURE_PERMISSIONS_STR} permissions, has {oct(get_file_permissions(file))}. Refusing to load."
            )
            return None
        return file.read_text().strip()


def login(client: ZabbixAPI, config: Config) -> None:
    auth = Authenticator(client, config)
    token = auth.login()
    if config.app.use_auth_token_file:
        write_auth_token_file(config.api.username, token, config.app.auth_token_file)


def prompt_username_password(username: str) -> Tuple[str, str]:
    """Prompt for username and password."""
    username = str_prompt("Username", default=username, empty_ok=False)
    password = str_prompt("Password", password=True, empty_ok=False)
    return username, password


def _parse_auth_file_contents(
    contents: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    """Parse the contents of an auth file.

    We store auth files in the format `username::secret`.
    """
    if contents:
        lines = contents.splitlines()
        if lines:
            line = lines[0].strip()
            username, _, secret = line.partition("::")
            return username, secret
    return None, None


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


def get_auth_file_paths(config: Optional[Config] = None) -> List[Path]:
    """Get all possible auth token file paths."""
    paths = [
        AUTH_FILE,
        AUTH_FILE_LEGACY,
    ]
    if config and config.app.auth_file not in paths:
        paths.append(config.app.auth_file)
    return paths


def get_auth_token_file_paths(config: Optional[Config] = None) -> List[Path]:
    """Get all possible auth token file paths."""
    paths = [
        AUTH_TOKEN_FILE,
        AUTH_TOKEN_FILE_LEGACY,
    ]
    if config and config.app.auth_token_file not in paths:
        paths.append(config.app.auth_token_file)
    return paths


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
    logger.info(f"Wrote auth token file {file}")
    return file


def clear_auth_token_file(config: Optional[Config] = None) -> None:
    """Clear the contents of the auth token file.
    Attempts to clear both the new and the old auth token file locations.

    Optionally also clears the loaded auth token from the config object.
    """
    for file in get_auth_token_file_paths(config):
        if not file.exists():
            logger.debug(f"Auth token file {file} does not exist. Skipping...")
            continue
        try:
            file.write_text("")
            logger.debug(f"Cleared auth token file contents {file}")
        except OSError as e:
            # Only happens if file exists and we fail to write to it.
            error(f"Unable to clear auth token file {file}: {e}")


def file_has_secure_permissions(file: Path) -> bool:
    """Check if a file has secure permissions."""
    return get_file_permissions(file) == SECURE_PERMISSIONS


def get_file_permissions(file: Path) -> int:
    """Get the 3 digit octal permissions of a file."""
    return file.stat().st_mode & 0o777
