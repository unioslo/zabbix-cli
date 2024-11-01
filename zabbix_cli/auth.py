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
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Tuple
from typing import Union

from rich.console import ScreenContext
from strenum import StrEnum

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
from zabbix_cli.output.console import warning
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.pyzabbix.client import ZabbixAPI

if TYPE_CHECKING:
    from zabbix_cli.config.model import Config


logger = logging.getLogger(__name__)


# Auth file location


SECURE_PERMISSIONS: Final[int] = 0o600
SECURE_PERMISSIONS_STR = format(SECURE_PERMISSIONS, "o")


class LoginCredentialType(StrEnum):
    """Types of valid login credentials."""

    PASSWORD = "username and password"
    AUTH_TOKEN = "auth token"


class CredentialsSource(StrEnum):
    """Source of login credentials."""

    ENV = "env"
    FILE = "file"
    PROMPT = "prompt"
    CONFIG = "config"


class LoginInfo(NamedTuple):
    credentials: Credentials
    token: str


class Credentials(NamedTuple):
    """Credentials for logging in to the Zabbix API."""

    source: Optional[CredentialsSource] = None
    username: Optional[str] = None
    password: Optional[str] = None
    auth_token: Optional[str] = None

    @property
    def type(self) -> Optional[LoginCredentialType]:
        if self.auth_token:
            return LoginCredentialType.AUTH_TOKEN
        if self.username and self.password:
            return LoginCredentialType.PASSWORD
        return None

    def is_valid(self) -> bool:
        """Check if credentials are valid (non-empty)."""
        return self.type is not None


class Authenticator:
    """Encapsulates logic for authenticating with the Zabbix API
    using various methods, as well as storing and loading auth tokens."""

    config: Config

    def __init__(self, config: Config) -> None:
        self.config = config

    @cached_property
    def screen(self) -> ScreenContext:
        return err_console.screen()

    def login(self) -> ZabbixAPI:
        """Log in to the Zabbix API using the configured credentials.

        Returns the Zabbix API client object.

        If multiple methods are available, they are tried in the following order:

        1. API token in config file
        2. API token in environment variables
        3. API token in file (if `use_auth_token_file=true`)
        4. Username and password in config file
        5. Username and password in auth file
        6. Username and password in environment variables
        7. Username and password from prompt
        """
        # Ensure we have a Zabbix API URL
        self.config.api.url = self.get_zabbix_url()
        client = ZabbixAPI.from_config(self.config)
        info = self._do_login(client)
        if self.config.app.use_auth_token_file:
            write_auth_token_file(self.config.api.username, info.token)

        if info.credentials.username:
            add_user(info.credentials.username)

        if info.credentials.type == LoginCredentialType.AUTH_TOKEN:
            logger.info("Logged in using auth token from %s", info.credentials.source)
        else:
            logger.info(
                "Logged in as %s using username and password from %s",
                info.credentials.username,
                info.credentials.source,
            )
        self._update_config(info.credentials)
        return client

    def _do_login(self, client: ZabbixAPI) -> LoginInfo:
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
                    logger.debug("No valid credentials found with %s", func.__name__)
                    continue
                logger.debug(
                    "Attempting to log in with %s from %s",
                    credentials.type,
                    credentials.source,
                )
                token = self.login_with_credentials(client, credentials)
                return LoginInfo(credentials, token)
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

    def login_with_credentials(
        self, client: ZabbixAPI, credentials: Credentials
    ) -> str:
        """Log in to the Zabbix API using the provided credentials."""
        return client.login(
            user=credentials.username,
            password=credentials.password,
            auth_token=credentials.auth_token,
        )

    def _update_config(self, credentials: Credentials) -> None:
        """Update the config with credentials from the successful login."""
        from pydantic import SecretStr

        if credentials.username:
            self.config.api.username = credentials.username

        # Only update secrets if they were already set in config and new ones are different.
        # we do not want to assign secrets to a config that does not already have them.
        # I.e. user logs in via file, prompt, env var, etc., which should not
        # assign those secrets to the config. ONLY prompt should assign secrets.
        # TODO: Better introspection of login method to determine if secrets should be updated.
        if (
            # we have a token in the config file
            (config_password := self.config.api.password.get_secret_value())
            and credentials.password
            and config_password != credentials.password
        ):
            self.config.api.password = SecretStr(credentials.password)

        if (
            # we have a token in the config file
            (config_token := self.config.api.auth_token.get_secret_value())
            and credentials.auth_token
            and config_token != credentials.auth_token
        ):
            self.config.api.auth_token = SecretStr(credentials.auth_token)

    def get_zabbix_url(self) -> str:
        """Get the URL of the Zabbix server from the config, or prompt for it."""
        if not self.config.api.url:
            with self.screen:
                return str_prompt("Zabbix URL (without /api_jsonrpc.php)")
        return self.config.api.url

    def _get_username_password_env(self) -> Credentials:
        """Get username and password from environment variables."""
        return Credentials(
            username=os.environ.get(ConfigEnvVars.USERNAME),
            password=os.environ.get(ConfigEnvVars.PASSWORD),
            source=CredentialsSource.ENV,
        )

    def _get_auth_token_env(self) -> Credentials:
        """Get auth token from environment variables."""
        return Credentials(
            auth_token=os.environ.get(ConfigEnvVars.API_TOKEN),
            source=CredentialsSource.ENV,
        )

    def _get_username_password_auth_file(
        self,
    ) -> Credentials:
        """Get username and password from environment variables."""
        path, contents = self.load_auth_file()
        if path:
            logger.debug("Loaded auth file %s", path)
        username, password = _parse_auth_file_contents(contents)
        return Credentials(
            username=username,
            password=password,
            source=CredentialsSource.FILE,
        )

    def _get_username_password_config(
        self,
    ) -> Credentials:
        """Get username and password from config file."""
        return Credentials(
            username=self.config.api.username,
            password=self.config.api.password.get_secret_value(),
            source=CredentialsSource.CONFIG,
        )

    def _get_username_password_prompt(
        self,
    ) -> Credentials:
        """Get username and password from a prompt in a separate screen."""
        with self.screen:
            username = str_prompt(
                "Username", default=self.config.api.username, empty_ok=False
            )
            password = str_prompt("Password", password=True, empty_ok=False)
            return Credentials(
                username=username, password=password, source=CredentialsSource.PROMPT
            )

    def _get_auth_token_config(self) -> Credentials:
        return Credentials(
            auth_token=self.config.api.auth_token.get_secret_value(),
            source=CredentialsSource.CONFIG,
        )

    def _get_auth_token_file(self) -> Credentials:
        if not self.config.app.use_auth_token_file:
            logger.debug("Not configured to use auth token file.")
            return Credentials()

        path, contents = self.load_auth_token_file()
        username, auth_token = _parse_auth_file_contents(contents)

        # Found token, but does not match configured username
        if auth_token and username and username != self.config.api.username:
            warning(
                f"Ignoring existing auth token in auth file {path}: "
                f"Username {username!r} in file does not match username {self.config.api.username!r} in configuration file."
            )
            auth_token = None

        return Credentials(
            username=username, auth_token=auth_token, source=CredentialsSource.FILE
        )

    def load_auth_token_file(self) -> Union[Tuple[Path, str], Tuple[None, None]]:
        paths = get_auth_token_file_paths(self.config)
        for path in paths:
            contents = self._do_load_auth_file(path)
            if contents:
                return path, contents
        logger.info(
            f"No auth token file found. Searched in {', '.join(str(p) for p in paths)}"
        )
        return None, None

    def load_auth_file(self) -> Tuple[Optional[Path], Optional[str]]:
        """Attempts to load an auth file."""
        paths = get_auth_file_paths(self.config)
        for path in paths:
            contents = self._do_load_auth_file(path)
            if contents:
                return path, contents
        logger.info(
            f"No auth file found. Searched in {', '.join(str(p) for p in paths)}"
        )
        return None, None

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


def login(config: Config) -> ZabbixAPI:
    """Log in to the Zabbix API using credentials from the config.

    Returns the Zabbix API client object.
    """
    auth = Authenticator(config)
    client = auth.login()
    return client


def logout(client: ZabbixAPI, config: Config) -> None:
    """Log out of the current Zabbix API session."""
    try:
        client.logout()
        if config.app.use_auth_token_file:
            clear_auth_token_file(config)
    except ZabbixAPIException as e:
        exit_err(f"Failed to log out of Zabbix API session: {e}")
    except AuthTokenFileError as e:
        exit_err(str(e))


def prompt_username_password(username: str) -> Tuple[str, str]:
    """Re-useable prompt for username and password."""
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
        paths.insert(0, config.app.auth_file)
    return paths


def get_auth_token_file_paths(config: Optional[Config] = None) -> List[Path]:
    """Get all possible auth token file paths."""
    paths = [
        AUTH_TOKEN_FILE,
        AUTH_TOKEN_FILE_LEGACY,
    ]
    if config and config.app.auth_token_file not in paths:  # config has custom path
        paths.insert(0, config.app.auth_token_file)
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
