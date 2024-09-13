""" "Module for authenticating with the Zabbix API as well as
loading/storing authentication information.

Manages the following:
- Loading and saving auth token files (file containing API session token)
- Loading and saving auth files (file containing username and password)
- Loading username and password from environment variables
- Prompting for username and password
- Logging in to the Zabbix API using one of the above methods
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final
from typing import List
from typing import NamedTuple
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
from zabbix_cli.logs import add_user
from zabbix_cli.output.console import err_console
from zabbix_cli.output.console import error
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.console import warning
from zabbix_cli.output.prompts import str_prompt

if TYPE_CHECKING:
    from zabbix_cli.config.model import Config
    from zabbix_cli.pyzabbix.client import ZabbixAPI


logger = logging.getLogger(__name__)


# Auth file location


SECURE_PERMISSIONS: Final[int] = 0o600
SECURE_PERMISSIONS_STR = format(SECURE_PERMISSIONS, "o")


class Credentials(NamedTuple):
    username: Optional[str] = None
    password: Optional[str] = None
    auth_token: Optional[str] = None

    def is_valid(self) -> bool:
        """Check if credentials are valid (non-empty)."""
        if self.username and self.password:
            return True
        if self.auth_token:
            return True
        return False


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
        2. API token in environment variables
        3. API token in file (if `use_auth_token_file=true`)
        4. Username and password in config file
        5. Username and password in auth file
        6. Username and password in environment variables
        7. Username and password from prompt
        """
        for func in [
            self._get_auth_token_config,
            self._get_auth_token_env,
            self._get_auth_token_file,
            self._get_username_password_config,
            self._get_username_password_auth_file,
            self._get_username_password_env,
            self._get_username_password_prompt,
        ]:
            try:
                credentials = func()
                if not credentials.is_valid():
                    logger.debug("No credentials found with %s", func.__name__)
                    continue
                logger.debug(
                    "Attempting to log in with credentials from %s", func.__name__
                )
                token = self.do_login(credentials)
                logger.info("Logged in with %s", func.__name__)
                self.update_config(credentials)
                return token
            except ZabbixAPIException as e:
                logger.warning("Failed to log in with %s: %s", func.__name__, e)
                continue
            except Exception as e:
                logger.error(
                    "Unexpected error logging in with %s: %s", func.__name__, e
                )
                continue
        else:
            raise AuthError(
                f"No authentication method succeeded for {self.config.api.url}. Check the logs for more information."
            )

    def do_login(self, credentials: Credentials) -> str:
        """Log in to the Zabbix API using the provided credentials."""
        return self.client.login(
            user=credentials.username,
            password=credentials.password,
            auth_token=credentials.auth_token,
        )

    def update_config(self, credentials: Credentials) -> None:
        """Update the config with the provided credentials."""
        from pydantic import SecretStr

        if credentials.username:
            self.config.api.username = credentials.username
        if credentials.password:
            self.config.api.password = SecretStr(credentials.password)
        if credentials.auth_token:
            self.config.api.auth_token = SecretStr(credentials.auth_token)

    def _get_username_password_env(self) -> Credentials:
        """Get username and password from environment variables."""
        return Credentials(
            username=os.environ.get(ConfigEnvVars.USERNAME),
            password=os.environ.get(ConfigEnvVars.PASSWORD),
        )

    def _get_auth_token_env(self) -> Credentials:
        """Get auth token from environment variables."""
        return Credentials(auth_token=os.environ.get(ConfigEnvVars.API_TOKEN))

    def _get_username_password_auth_file(
        self,
    ) -> Credentials:
        """Get username and password from environment variables."""
        contents = self.load_auth_file()
        username, password = _parse_auth_file_contents(contents)
        return Credentials(username=username, password=password)

    def _get_username_password_config(
        self,
    ) -> Credentials:
        """Get username and password from config file."""
        return Credentials(
            username=self.config.api.username,
            password=self.config.api.password.get_secret_value(),
        )

    def _get_username_password_prompt(
        self,
    ) -> Credentials:
        """Get username and password from prompt."""
        username, password = prompt_username_password(username=self.config.api.username)
        return Credentials(username=username, password=password)

    def _get_auth_token_config(self) -> Credentials:
        return Credentials(auth_token=self.config.api.auth_token.get_secret_value())

    def _get_auth_token_file(self) -> Credentials:
        if not self.config.app.use_auth_token_file:
            logger.debug("Not configured to use auth token file.")
            return Credentials()

        contents = self.load_auth_token_file()
        username, auth_token = _parse_auth_file_contents(contents)

        # Found token, but does not match configured username
        if auth_token and username and username != self.config.api.username:
            warning(
                "Ignoring existing auth token. "
                f"Username {username!r} does not match configured username {self.config.api.username!r}."
            )
            auth_token = None

        return Credentials(auth_token=auth_token)

    def load_auth_token_file(self) -> Optional[str]:
        paths = get_auth_token_file_paths(self.config)
        for path in paths:
            contents = self._do_load_auth_file(path)
            if contents:
                return contents
        logger.info(
            f"No auth token file found. Searched in {', '.join(str(p) for p in paths)}"
        )

    def load_auth_file(self) -> Optional[str]:
        """Attempts to load an auth file."""
        paths = get_auth_file_paths(self.config)
        for path in paths:
            contents = self._do_load_auth_file(path)
            if contents:
                return contents
        logger.info(
            f"No auth file found. Searched in {', '.join(str(p) for p in paths)}"
        )

    def _do_load_auth_file(self, file: Path) -> Optional[str]:
        """Attempts to read the contents of an auth (token) file.
        Returns None if the file does not exist or is not secure.
        """
        if not file.exists():
            return None
        if (
            not self.config.app.allow_insecure_auth_file
            and not file_has_secure_permissions(file)
        ):
            error(
                f"Auth file {file} must have {SECURE_PERMISSIONS_STR} permissions, has {oct(get_file_permissions(file))}. Refusing to load."
            )
            return None
        return file.read_text().strip()


def login(client: ZabbixAPI, config: Config) -> None:
    with err_console.screen():
        info(f"Logging in to {config.api.url}")
        auth = Authenticator(client, config)
        token = auth.login()
        if config.app.use_auth_token_file:
            write_auth_token_file(
                config.api.username, token, config.app.auth_token_file
            )
        add_user(config.api.username)
        logger.info("Logged in as %s", config.api.username)


def logout(client: ZabbixAPI, config: Config) -> None:
    try:
        client.logout()
        if config.app.use_auth_token_file:
            clear_auth_token_file(config)
    except ZabbixAPIException as e:
        exit_err(f"Failed to log out of Zabbix API session: {e}")
    except AuthTokenFileError as e:
        exit_err(str(e))


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


def get_auth_file_paths(config: Optional[Config] = None) -> List[Path]:
    """Get all possible auth token file paths."""
    paths = [
        AUTH_FILE,
        AUTH_FILE_LEGACY,
    ]
    if config and config.app.auth_file not in paths:  # config has custom path
        paths.append(config.app.auth_file)
    return paths


def get_auth_token_file_paths(config: Optional[Config] = None) -> List[Path]:
    """Get all possible auth token file paths."""
    paths = [
        AUTH_TOKEN_FILE,
        AUTH_TOKEN_FILE_LEGACY,
    ]
    if config and config.app.auth_token_file not in paths:  # config has custom path
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
            raise AuthTokenFileError(
                f"Unable to create auth token file {file}. "
                "Change the location or disable auth token file in config."
            ) from e
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
            continue
        try:
            file.write_text("")
            logger.debug("Cleared auth token file contents '%s'", file)
        except OSError as e:
            raise AuthTokenFileError(
                f"Unable to clear auth token file {file}: {e}"
            ) from e


def file_has_secure_permissions(file: Path) -> bool:
    """Check if a file has secure permissions.

    Always returns True on Windows.
    """
    if sys.platform == "win32":
        return True
    return get_file_permissions(file) == SECURE_PERMISSIONS


def get_file_permissions(file: Path) -> int:
    """Get the 3 digit octal permissions of a file."""
    return file.stat().st_mode & 0o777
