from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest
from packaging.version import Version
from pydantic import SecretStr
from zabbix_cli import auth
from zabbix_cli._v2_compat import AUTH_FILE as AUTH_FILE_LEGACY
from zabbix_cli._v2_compat import AUTH_TOKEN_FILE as AUTH_TOKEN_FILE_LEGACY
from zabbix_cli.auth import Authenticator
from zabbix_cli.auth import Credentials
from zabbix_cli.auth import CredentialsSource
from zabbix_cli.auth import CredentialsType
from zabbix_cli.auth import get_auth_file_paths
from zabbix_cli.auth import get_auth_token_file_paths
from zabbix_cli.config.constants import AUTH_FILE
from zabbix_cli.config.constants import AUTH_TOKEN_FILE
from zabbix_cli.config.model import Config
from zabbix_cli.models import TableRenderable
from zabbix_cli.pyzabbix.client import ZabbixAPI


def test_get_auth_file_paths_defafult(config: Config) -> None:
    """Test the default auth file paths."""
    # Path from config is not present (same as default AUTH_FILE)
    assert get_auth_file_paths(config) == [
        AUTH_FILE,
        AUTH_FILE_LEGACY,
    ]


def test_get_auth_file_paths_override(tmp_path: Path, config: Config) -> None:
    """Test overriding the default auth file path in the config."""
    auth_file = tmp_path / "auth"
    config.app.auth_file = auth_file
    # Path from config is first (highest priority)
    assert get_auth_file_paths(config) == [
        auth_file,
        AUTH_FILE,
        AUTH_FILE_LEGACY,
    ]


def test_get_auth_token_file_paths_defafult(config: Config) -> None:
    """Test the default auth token file paths."""
    # Path from config is not present (same as default AUTH_TOKEN_FILE)
    assert get_auth_token_file_paths(config) == [
        AUTH_TOKEN_FILE,
        AUTH_TOKEN_FILE_LEGACY,
    ]


def test_get_auth_token_file_paths_override(tmp_path: Path, config: Config) -> None:
    """Override the default auth token file path in the config."""
    auth_file = tmp_path / "auth_token"
    config.app.auth_token_file = auth_file
    # Path from config is first (highest priority)
    assert get_auth_token_file_paths(config) == [
        auth_file,
        AUTH_TOKEN_FILE,
        AUTH_TOKEN_FILE_LEGACY,
    ]


@pytest.fixture(name="auth_token_file")
def _auth_token_file(tmp_path: Path) -> Path:
    return tmp_path / ".zabbix-cli_auth_token"


@pytest.fixture(name="auth_file")
def _auth_file(tmp_path: Path) -> Path:
    return tmp_path / ".zabbix-cli_auth"


@pytest.mark.parametrize(
    "sources, expect_type, expect_source",
    [
        pytest.param(
            [
                (CredentialsType.AUTH_TOKEN, CredentialsSource.CONFIG),
                (CredentialsType.AUTH_TOKEN, CredentialsSource.ENV),
                (CredentialsType.AUTH_TOKEN, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.CONFIG),
                (CredentialsType.PASSWORD, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.ENV),
                (CredentialsType.PASSWORD, CredentialsSource.PROMPT),
            ],
            CredentialsType.AUTH_TOKEN,
            CredentialsSource.CONFIG,
            id="expect_auth_token_config",
        ),
        pytest.param(
            [
                (CredentialsType.AUTH_TOKEN, CredentialsSource.ENV),
                (CredentialsType.AUTH_TOKEN, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.CONFIG),
                (CredentialsType.PASSWORD, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.ENV),
                (CredentialsType.PASSWORD, CredentialsSource.PROMPT),
            ],
            CredentialsType.AUTH_TOKEN,
            CredentialsSource.ENV,
            id="expect_auth_token_env",
        ),
        pytest.param(
            [
                (CredentialsType.AUTH_TOKEN, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.CONFIG),
                (CredentialsType.PASSWORD, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.ENV),
                (CredentialsType.PASSWORD, CredentialsSource.PROMPT),
            ],
            CredentialsType.AUTH_TOKEN,
            CredentialsSource.FILE,
            id="expect_auth_token_file",
        ),
        pytest.param(
            [
                (CredentialsType.PASSWORD, CredentialsSource.CONFIG),
                (CredentialsType.PASSWORD, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.ENV),
                (CredentialsType.PASSWORD, CredentialsSource.PROMPT),
            ],
            CredentialsType.PASSWORD,
            CredentialsSource.CONFIG,
            id="expect_password_config",
        ),
        pytest.param(
            [
                (CredentialsType.PASSWORD, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.ENV),
                (CredentialsType.PASSWORD, CredentialsSource.PROMPT),
            ],
            CredentialsType.PASSWORD,
            CredentialsSource.FILE,
            id="expect_password_file",
        ),
        pytest.param(
            [
                (CredentialsType.PASSWORD, CredentialsSource.ENV),
                (CredentialsType.PASSWORD, CredentialsSource.PROMPT),
            ],
            CredentialsType.PASSWORD,
            CredentialsSource.ENV,
            id="expect_password_env",
        ),
        pytest.param(
            [
                (CredentialsType.PASSWORD, CredentialsSource.PROMPT),
            ],
            CredentialsType.PASSWORD,
            CredentialsSource.PROMPT,
            id="expect_password_prompt",
        ),
    ],
)
def test_authenticator_login_with_any(
    monkeypatch: pytest.MonkeyPatch,
    auth_token_file: Path,
    auth_file: Path,
    config: Config,
    sources: list[tuple[CredentialsType, CredentialsSource]],
    expect_source: CredentialsSource,
    expect_type: CredentialsType,
) -> None:
    """Test the authenticator login with a variety of credential sources."""
    # TODO: test with other variations of sources and types
    authenticator = Authenticator(config)

    MOCK_USER = "Admin"
    MOCK_PASSWORD = "zabbix"
    MOCK_TOKEN = "abc1234567890"

    # Mock certain methods that are difficult to test

    # REASON: Makes HTTP calls to the Zabbix API
    def mock_login(self: ZabbixAPI, *args, **kwargs):
        self.auth = MOCK_TOKEN
        return self.auth

    monkeypatch.setattr(auth.ZabbixAPI, "login", mock_login)

    # REASON: Makes HTTP calls to the Zabbix API
    monkeypatch.setattr(auth.ZabbixAPI, "version", Version("1.2.3"))

    # REASON: Prompts for input (could be tested with a fake input stream)
    def mock_get_username_password_prompt() -> Credentials:
        return Credentials(
            username=MOCK_USER,
            password=MOCK_PASSWORD,
            source=CredentialsSource.PROMPT,
        )

    monkeypatch.setattr(
        authenticator,
        "_get_username_password_prompt",
        mock_get_username_password_prompt,
    )

    # REASON: Falls back on default auth token file path (which might exist)
    def mock_get_auth_token_file_paths(config: Optional[Config] = None) -> list[Path]:
        return [auth_token_file]

    monkeypatch.setattr(
        auth, "get_auth_token_file_paths", mock_get_auth_token_file_paths
    )

    # REASON: Falls back on default auth file path (which might exist)
    def mock_get_auth_file_paths(config: Optional[Config] = None) -> list[Path]:
        return [auth_file]

    monkeypatch.setattr(auth, "get_auth_file_paths", mock_get_auth_file_paths)

    # Set the credentials in the various sources
    for ctype, csource in sources:
        if csource == CredentialsSource.CONFIG:
            if ctype == CredentialsType.AUTH_TOKEN:
                config.api.auth_token = SecretStr(MOCK_TOKEN)
            elif ctype == CredentialsType.PASSWORD:
                config.api.username = MOCK_USER
                config.api.password = SecretStr(MOCK_PASSWORD)
        elif csource == CredentialsSource.ENV:
            if ctype == CredentialsType.AUTH_TOKEN:
                monkeypatch.setenv("ZABBIX_API_TOKEN", MOCK_TOKEN)
            elif ctype == CredentialsType.PASSWORD:
                monkeypatch.setenv("ZABBIX_USERNAME", MOCK_USER)
                monkeypatch.setenv("ZABBIX_PASSWORD", MOCK_PASSWORD)
        elif csource == CredentialsSource.FILE:
            if ctype == CredentialsType.AUTH_TOKEN:
                auth_token_file.write_text(f"{MOCK_USER}::{MOCK_TOKEN}")
                config.app.auth_token_file = auth_token_file
                config.app.use_auth_token_file = True
                config.app.allow_insecure_auth_file = True
            elif ctype == CredentialsType.PASSWORD:
                auth_file.write_text(f"{MOCK_USER}::{MOCK_PASSWORD}")
                config.app.auth_file = auth_file

    client, info = authenticator.login_with_any()
    assert info.credentials.source == expect_source
    assert info.credentials.type == expect_type
    assert info.token == MOCK_TOKEN

    # Ensure the login method modified the base renderable's zabbix version attribute
    assert TableRenderable.zabbix_version == Version("1.2.3")
