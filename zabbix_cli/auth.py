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
from collections.abc import Generator
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final
from typing import NamedTuple
from typing import Optional
from typing import Union

from pydantic import BaseModel
from pydantic import PrivateAttr
from pydantic import RootModel
from rich.console import ScreenContext
from strenum import StrEnum

from zabbix_cli._v2_compat import AUTH_FILE as AUTH_FILE_LEGACY
from zabbix_cli._v2_compat import AUTH_TOKEN_FILE as AUTH_TOKEN_FILE_LEGACY
from zabbix_cli.config.constants import AUTH_FILE
from zabbix_cli.config.constants import AUTH_TOKEN_FILE
from zabbix_cli.config.constants import ConfigEnvVars
from zabbix_cli.exceptions import AuthError
from zabbix_cli.exceptions import AuthTokenFileError
from zabbix_cli.exceptions import SessionFileError
from zabbix_cli.exceptions import SessionFileNotFoundError
from zabbix_cli.exceptions import SessionFilePermissionsError
from zabbix_cli.exceptions import ZabbixAPIException
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.logs import add_user
from zabbix_cli.output.console import err_console
from zabbix_cli.output.console import error
from zabbix_cli.output.console import warning
from zabbix_cli.output.prompts import str_prompt
from zabbix_cli.pyzabbix.client import ZabbixAPI

if TYPE_CHECKING:
    from zabbix_cli.config.model import Config


logger = logging.getLogger(__name__)


SECURE_PERMISSIONS: Final[int] = 0o600
SECURE_PERMISSIONS_STR = format(SECURE_PERMISSIONS, "o")


class SessionInfo(BaseModel):
    """Information about a session for a specific user."""

    username: str
    session_id: str


class SessionList(RootModel[list[SessionInfo]]):
    """List of sessions for a specific Zabbix API URL."""

    root: list[SessionInfo] = []

    def __len__(self) -> int:
        return len(self.root)

    def set_session(self, username: str, session_id: str) -> None:
        """Add or modify a session for a given user."""
        for session in self.root:
            if session.username == username:
                session.session_id = session_id
                return
        # Did not find existing session, add new one
        self.root.append(SessionInfo(username=username, session_id=session_id))

    def get_session(self, username: str) -> Optional[SessionInfo]:
        for session in self.root:
            if session.username == username:
                return session
        return None


class SessionFile(RootModel[dict[str, SessionList]]):
    """Contents of a session file.

    Root model that wraps a dict of URLs to `SessionList` objects.
    """

    root: dict[str, SessionList] = {}
    _path: Optional[Path] = PrivateAttr(default=None)

    def get_sessions(self, url: str) -> SessionList:
        """Get session list for a URL.

        Note:
            Returns a new empty `SessionList` if URL has no sessions.

            The returned `SessionList` should never be mutated directly.
            Always use `set_user_session` to modify a user's session for
            a given URL.
        """
        return self.root.get(url, None) or SessionList()  # lazily create default

    def set_sessions(self, url: str, sessions: SessionList) -> None:
        """Set session list for a URL."""
        self.root[url] = sessions

    def get_user_session(self, url: str, username: str) -> Optional[SessionInfo]:
        """Get a session given a URL and username."""
        return self.get_sessions(url).get_session(username)

    def set_user_session(self, url: str, username: str, session_id: str) -> None:
        """Add or update a user's session for a given URL."""
        session = self.get_sessions(url)
        session.set_session(username, session_id)
        self.set_sessions(url, session)

    @classmethod
    def load(cls, file: Path, allow_insecure: bool = False) -> SessionFile:
        """Load the contents of a session file."""
        if not file.exists():
            raise SessionFileNotFoundError("Session file does not exist: %s", file)

        if not file_has_secure_permissions(file) and not allow_insecure:
            raise SessionFilePermissionsError(
                f"Session file {file} must have {SECURE_PERMISSIONS_STR} permissions. Refusing to load."
            )
        try:
            contents = file.read_text()
            cl = cls.model_validate_json(contents)
            cl._path = file
            return cl
        except Exception as e:
            raise SessionFileError(f"Unable to load session file {file}: {e}") from e

    def save(self, path: Optional[Path] = None, allow_insecure: bool = False) -> None:
        path = path or self._path
        if not path:
            raise SessionFileError("Cannot save session file without a path.")

        try:
            logger.debug("Saving session file %s", path)
            path.write_text(self.model_dump_json(indent=2))
            if not allow_insecure and not file_has_secure_permissions(path):
                set_file_secure_permissions(path)
            logger.info("Saved session file %s", path)
        except Exception as e:
            raise SessionFileError(
                f"Unable to save session file {self._path}: {e}"
            ) from e


class CredentialsType(StrEnum):
    """Login credentials type."""

    PASSWORD = "username and password"
    AUTH_TOKEN = "auth token"
    SESSION = "session"


class CredentialsSource(StrEnum):
    """Source of login credentials."""

    ENV = "env"
    FILE = "file"
    PROMPT = "prompt"
    CONFIG = "config"
    LOGIN_COMMAND = "login command"


class Credentials(NamedTuple):
    """Credentials for logging in to the Zabbix API."""

    source: Optional[CredentialsSource] = None
    username: Optional[str] = None
    password: Optional[str] = None
    auth_token: Optional[str] = None
    session_id: Optional[str] = None

    def __str__(self) -> str:
        if self.type and self.source:
            return f"{self.type} from {self.source}"
        return "no credentials"

    @property
    def type(self) -> Optional[CredentialsType]:
        if self.auth_token:
            return CredentialsType.AUTH_TOKEN
        if self.username and self.password:
            return CredentialsType.PASSWORD
        if self.session_id:
            return CredentialsType.SESSION
        return None

    def is_valid(self) -> bool:
        """Check if credentials are valid (non-empty)."""
        return self.type is not None


class LoginInfo(NamedTuple):
    credentials: Credentials
    token: str
    """Token or Session ID returned from the Zabbix API."""


class Authenticator:
    """Encapsulates logic for authenticating with the Zabbix API
    using various methods, as well as storing and loading auth tokens.


    Exposes methods for logging in with specific credentials, as well as
    a method for logging in with any valid credentials.

    Bootstraps application state with login and API info on successful login.
    """

    config: Config

    def __init__(self, config: Config) -> None:
        self.config = config
        # Ensure we have a Zabbix API URL before instantiating client
        self.config.api.url = self.get_zabbix_url()
        self.client = ZabbixAPI.from_config(self.config)

    @cached_property
    def screen(self) -> ScreenContext:
        return err_console.screen()

    def login_with_any(self) -> tuple[ZabbixAPI, LoginInfo]:
        """Log in to the Zabbix API using any valid method.

        Returns the Zabbix API client object.

        If multiple methods are available, they are tried in the following order:

        1. API token in environment variables
        2. API token in config file
        3. Session ID in session file (if `use_session_file=true`)
        4. Username and password in environment variables
        5. Username and password in config file
        6. Username and password in auth file
        7. Session ID in legacy auth token file (if `use_session_file=true`)
        8. Username and password from prompt
        """

        for credentials in self._iter_all_credentials():
            if not credentials.is_valid():
                logger.debug("No valid credentials found with %s", credentials)
                continue
            info = self.login_with_credentials(credentials)
            if info:
                return self.client, info
        raise AuthError(
            f"No authentication method succeeded for {self.config.api.url}. Check the logs for more information."
        )

    def _iter_all_credentials(
        self, prompt_password: bool = True
    ) -> Generator[Credentials, None, None]:
        """Generator that yields credentials from all possible sources.

        Only yields non-empty credentials, but does not check if they are valid.

        Finally yields a prompt for username and password if `prompt_password` is True.
        """
        for func in [
            self._get_auth_token_env,
            self._get_auth_token_config,
            self._get_session_file,
            self._get_username_password_env,
            self._get_username_password_config,
            self._get_username_password_auth_file,
            self._get_auth_token_file_legacy,
        ]:
            try:
                creds = func()
                if creds:
                    yield creds
            except Exception as e:
                logger.error("Error getting credentials from %s: %s", func, e)
                continue

        if prompt_password:
            yield self._get_username_password_prompt()

    @classmethod
    def login_with_prompt(cls, config: Config) -> tuple[ZabbixAPI, LoginInfo]:
        """Log in to the Zabbix API using username and password from a prompt."""
        auth = cls(config)
        creds = auth._get_username_password_prompt()
        info = auth.login_with_credentials(creds)
        creds._replace(source=CredentialsSource.LOGIN_COMMAND)
        if not info:
            raise AuthError("Failed to log in with username and password.")
        return auth.client, info

    @classmethod
    def login_with_username_password(
        cls, config: Config, username: str, password: str
    ) -> tuple[ZabbixAPI, LoginInfo]:
        """Log in to the Zabbix API using username and password from a prompt."""
        auth = cls(config)
        creds = Credentials(
            username=username,
            password=password,
            source=CredentialsSource.LOGIN_COMMAND,
        )
        info = auth.login_with_credentials(creds)
        if not info:
            raise AuthError("Failed to log in with username and password.")
        return auth.client, info

    @classmethod
    def login_with_token(
        cls, config: Config, token: str
    ) -> tuple[ZabbixAPI, LoginInfo]:
        """Log in to the Zabbix API using username and password from a prompt."""
        auth = cls(config)
        creds = Credentials(
            auth_token=token,
            source=CredentialsSource.LOGIN_COMMAND,
        )
        info = auth.login_with_credentials(creds)
        if not info:
            raise AuthError("Failed to log in with auth token.")
        return auth.client, info

    def login_with_credentials(self, credentials: Credentials) -> LoginInfo | None:
        """Log in to the Zabbix API using the provided credentials.

        Cannot fail; logs errors and returns None if unsuccessful.

        Args:
            credentials (Credentials): Credentials to use for logging in.

        Returns:
            LoginInfo | None: Login information if successful, None if not.
        """
        try:
            logger.debug(
                "Attempting to log in with %s from %s",
                credentials.type,
                credentials.source,
            )
            return self._do_login_with_credentials(credentials)
        except ZabbixAPIException as e:
            logger.warning("Failed to log in with %s: %s", credentials, e)
            return
        except Exception as e:
            logger.error("Unexpected error logging in with %s: %s", credentials, e)
            return

    def _do_login_with_credentials(self, credentials: Credentials) -> LoginInfo:
        """Login to Zabbix API, and update application state if successful."""
        token = self.client.login(
            user=credentials.username,
            password=credentials.password,
            auth_token=credentials.auth_token,
            session_id=credentials.session_id,
        )
        info = LoginInfo(credentials, token)

        if info.credentials.type == CredentialsType.AUTH_TOKEN:
            logger.info("Logged in using auth token from %s", info.credentials.source)
        elif info.credentials.type == CredentialsType.SESSION:
            logger.info("Logged in using session ID from %s", info.credentials.source)
        else:
            logger.info(
                "Logged in as %s using username and password from %s",
                info.credentials.username,
                info.credentials.source,
            )

        self._update_application_with_login_info(info)
        return info

    def _update_application_with_login_info(self, info: LoginInfo) -> None:
        """Update the application state with the login information.

        Includes the following:
        - Write session file if configured
        - Add username to log records context
        - Update config with credentials
        - Set Zabbix API version on the TableRenderable base class
        """
        from zabbix_cli.models import TableRenderable

        # Write session file
        if info.credentials.username and self.config.app.use_session_file:
            sessionfile = self.load_session_file()
            if not sessionfile:
                logger.debug("No session file found, creating new one.")
                sessionfile = SessionFile()

            sessionfile.set_user_session(
                url=self.config.api.url,
                username=info.credentials.username,
                session_id=info.token,
            )
            try:
                sessionfile.save(
                    self.config.app.session_file,
                    allow_insecure=self.config.app.allow_insecure_auth_file,
                )
            except SessionFileError as e:
                logger.error("Unable to save session file: %s", e)

        # Log context
        if info.credentials.username:
            add_user(info.credentials.username)
        else:
            logger.debug("No username detected, adding <TOKEN> to logs")
            add_user("<TOKEN>")

        # Update config with the new credentials
        self._update_config(info.credentials)

        # Set the Zabbix API version on the TableRenderable base class
        TableRenderable.zabbix_version = self.client.version

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

    def get_zabbix_url(self, prompt: bool = True) -> str:
        """Get the URL of the Zabbix server from env, config, then finally prompt for it.."""
        for source in [self._get_zabbix_url_env, self._get_zabbix_url_config]:
            url = source()
            if url:
                return url
        if prompt:
            with self.screen:
                return self._get_zabbix_url_prompt()
        raise AuthError("No Zabbix URL found in environment or config.")

    def _get_zabbix_url_env(self) -> str:
        """Get the URL of the Zabbix server from the environment."""
        return os.environ.get(ConfigEnvVars.URL, "")

    def _get_zabbix_url_config(self) -> str:
        """Get the URL of the Zabbix server from the config file."""
        return self.config.api.url

    def _get_zabbix_url_prompt(self) -> str:
        """Prompt for the URL of the Zabbix server."""
        return str_prompt("Zabbix URL (without /api_jsonrpc.php)", empty_ok=False)

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
        """Get auth token from the config file."""
        return Credentials(
            auth_token=self.config.api.auth_token.get_secret_value(),
            source=CredentialsSource.CONFIG,
        )

    def _get_session_file(self) -> Optional[Credentials]:
        """Get session ID from a file."""
        if not self.config.app.use_session_file:
            logger.debug("Not configured to use auth token file.")
            return

        sessionfile = self.load_session_file()
        if not sessionfile:
            return
        logger.info("Found session file %s", sessionfile._path)  # pyright: ignore[reportPrivateUsage]

        session = sessionfile.get_user_session(
            self.config.api.url, self.config.api.username
        )
        if session:
            return Credentials(
                username=session.username,
                session_id=session.session_id,
                source=CredentialsSource.FILE,
            )

    def _get_auth_token_file_legacy(self) -> Optional[Credentials]:
        """Get auth token (session ID) from a legacy auth token file.

        From Zabbix-CLI 3.5.0 onwards, we use a new session file."""
        if not self.config.app.use_session_file:
            logger.debug("Not configured to use auth token file.")
            return

        path, contents = self.load_auth_token_file()
        username, auth_token = _parse_auth_file_contents(contents)

        # Found token, but does not match configured username
        if auth_token and username and username != self.config.api.username:
            warning(
                f"Ignoring existing auth token in auth file {path}: "
                f"Username {username!r} in file does not match username {self.config.api.username!r} in configuration file."
            )
            return

        # NOTE: Originally, this was named auth token file, but it does in fact
        # contain a Session ID, not an API token.
        # So we return it under the `session_id` key.
        return Credentials(
            username=username, session_id=auth_token, source=CredentialsSource.FILE
        )

    def load_session_file(self) -> Optional[SessionFile]:
        """Load a session file from configured path."""
        try:
            return SessionFile.load(self.config.app.session_file)
        except SessionFileError as e:
            logger.error("Unable to load session file: %s", e)
            return None
        except Exception as e:
            logger.error("Unexpected error loading session file: %s", e)
            return None

    def load_auth_token_file(self) -> Union[tuple[Path, str], tuple[None, None]]:
        """Attempts to load an auth token file."""
        paths = get_auth_token_file_paths(self.config)
        for path in paths:
            contents = self._do_load_auth_file(path)
            if contents:
                return path, contents
        logger.info(
            f"No auth token file found. Searched in {', '.join(str(p) for p in paths)}"
        )
        return None, None

    def load_auth_file(self) -> tuple[Optional[Path], Optional[str]]:
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
    client, _ = auth.login_with_any()
    return client


def logout(client: ZabbixAPI, config: Config) -> None:
    """Log out of the current Zabbix API session."""
    client.logout()
    if config.app.use_session_file:
        clear_auth_token_file(config)


def _parse_auth_file_contents(
    contents: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
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


def get_auth_file_paths(config: Optional[Config] = None) -> list[Path]:
    """Get all possible auth token file paths."""
    paths = [
        AUTH_FILE,
        AUTH_FILE_LEGACY,
    ]
    if config and config.app.auth_file not in paths:  # config has custom path
        paths.insert(0, config.app.auth_file)
    return paths


def get_auth_token_file_paths(config: Optional[Config] = None) -> list[Path]:
    """Get all possible auth token file paths."""
    paths = [
        AUTH_TOKEN_FILE,
        AUTH_TOKEN_FILE_LEGACY,
    ]
    if config and config.app.auth_token_file not in paths:  # config has custom path
        paths.insert(0, config.app.auth_token_file)
    return paths


def write_auth_token_file(
    username: str,
    auth_token: str,
    file: Path = AUTH_TOKEN_FILE,
    allow_insecure: bool = False,
) -> Path:
    """Write a username/auth token pair to the auth token file."""
    if not username or not auth_token:
        logger.error(
            "Cannot write auth token file without both a username (%s) and token (%s).",
            username,
            auth_token,
        )
        return file

    try:
        file.write_text(f"{username}::{auth_token}")
        logger.info(f"Wrote auth token file {file}")
    except OSError as e:
        raise AuthTokenFileError(f"Unable to write auth token file {file}: {e}") from e

    # Ensure file has secure permissions if configured
    if not allow_insecure and not file_has_secure_permissions(file):
        try:
            file.chmod(SECURE_PERMISSIONS)
        except OSError as e:
            raise AuthTokenFileError(
                f"Unable to set secure permissions ({SECURE_PERMISSIONS_STR}) on {file} when saving auth token. "
                "Change permissions manually or delete the file."
            ) from e

    return file


def clear_auth_token_file(config: Optional[Config] = None) -> None:
    """Clear the contents of the auth token file.

    Attempts to clear both the new and the old auth token file locations.
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


def set_file_secure_permissions(file: Path) -> None:
    """Set the permissions of a file to secure permissions."""
    try:
        file.chmod(SECURE_PERMISSIONS)
    except OSError as e:
        raise ZabbixCLIError(
            f"Unable to set secure permissions ({SECURE_PERMISSIONS_STR}) on {file}. Change permissions manually or delete the file."
        ) from e


def get_file_permissions(file: Path) -> int:
    """Get the 3 digit octal permissions of a file."""
    return file.stat().st_mode & 0o777
