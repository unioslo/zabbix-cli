from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Optional

import pytest
from inline_snapshot import snapshot
from packaging.version import Version
from pydantic import SecretStr
from pytest_httpserver import HTTPServer
from zabbix_cli import auth
from zabbix_cli._v2_compat import AUTH_FILE as AUTH_FILE_LEGACY
from zabbix_cli._v2_compat import AUTH_TOKEN_FILE as AUTH_TOKEN_FILE_LEGACY
from zabbix_cli.auth import Authenticator
from zabbix_cli.auth import Credentials
from zabbix_cli.auth import CredentialsSource
from zabbix_cli.auth import CredentialsType
from zabbix_cli.auth import SessionIDFile
from zabbix_cli.auth import get_auth_file_paths
from zabbix_cli.auth import get_auth_token_file_paths
from zabbix_cli.config.constants import AUTH_FILE
from zabbix_cli.config.constants import AUTH_TOKEN_FILE
from zabbix_cli.config.model import Config
from zabbix_cli.pyzabbix.client import ZabbixAPI

from tests.utils import add_zabbix_endpoint
from tests.utils import add_zabbix_version_endpoint

if TYPE_CHECKING:
    from zabbix_cli.models import TableRenderable


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


@pytest.fixture
def table_renderable_mock(monkeypatch) -> type[TableRenderable]:
    """Replace TableRenderable class in zabbix_cli.models with mock class
    so that tests can mutate it without affecting other tests."""
    from zabbix_cli.models import TableRenderable

    class MockTableRenderable(TableRenderable):
        pass

    # Set a default version that is different from the real class
    # so that we can tell if the mock class was used
    MockTableRenderable.zabbix_version = Version("0.0.1")

    # Use monkeypatch to temporarily replace the real class with the mock class
    monkeypatch.setattr("zabbix_cli.models.TableRenderable", MockTableRenderable)

    return MockTableRenderable


def yield_then_delete_file(file: Path) -> None:
    try:
        yield file
    finally:
        if file.exists():
            file.unlink()


@pytest.fixture(name="session_id_file")
def _session_id_file(tmp_path: Path) -> Path:
    yield from yield_then_delete_file(tmp_path / ".zabbix-cli_session_id.json")


@pytest.fixture(name="auth_token_file")
def _auth_token_file(tmp_path: Path) -> Path:
    yield from yield_then_delete_file(tmp_path / ".zabbix-cli_auth_token")


@pytest.fixture(name="auth_file")
def _auth_file(tmp_path: Path) -> Path:
    yield from yield_then_delete_file(tmp_path / ".zabbix-cli_auth")


@pytest.mark.parametrize(
    "sources, expect_type, expect_source",
    [
        pytest.param(
            [
                (CredentialsType.AUTH_TOKEN, CredentialsSource.ENV),
                (CredentialsType.AUTH_TOKEN, CredentialsSource.CONFIG),
                (CredentialsType.SESSION_ID, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.CONFIG),
                (CredentialsType.PASSWORD, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.ENV),
                (CredentialsType.AUTH_TOKEN, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.PROMPT),
            ],
            CredentialsType.AUTH_TOKEN,
            CredentialsSource.ENV,
            id="expect_auth_token_env",
        ),
        pytest.param(
            [
                (CredentialsType.AUTH_TOKEN, CredentialsSource.CONFIG),
                (CredentialsType.SESSION_ID, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.CONFIG),
                (CredentialsType.PASSWORD, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.ENV),
                (CredentialsType.AUTH_TOKEN, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.PROMPT),
            ],
            CredentialsType.AUTH_TOKEN,
            CredentialsSource.CONFIG,
            id="expect_auth_token_config",
        ),
        pytest.param(
            [
                (CredentialsType.SESSION_ID, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.CONFIG),
                (CredentialsType.PASSWORD, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.ENV),
                (CredentialsType.AUTH_TOKEN, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.PROMPT),
            ],
            CredentialsType.SESSION_ID,
            CredentialsSource.FILE,
            id="expect_session_id_file",
        ),
        pytest.param(
            [
                (CredentialsType.PASSWORD, CredentialsSource.ENV),
                (CredentialsType.PASSWORD, CredentialsSource.CONFIG),
                (CredentialsType.PASSWORD, CredentialsSource.FILE),
                (CredentialsType.AUTH_TOKEN, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.PROMPT),
            ],
            CredentialsType.PASSWORD,
            CredentialsSource.ENV,
            id="expect_password_env",
        ),
        pytest.param(
            [
                (CredentialsType.PASSWORD, CredentialsSource.CONFIG),
                (CredentialsType.PASSWORD, CredentialsSource.FILE),
                (CredentialsType.AUTH_TOKEN, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.PROMPT),
            ],
            CredentialsType.PASSWORD,
            CredentialsSource.CONFIG,
            id="expect_password_config",
        ),
        pytest.param(
            [
                (CredentialsType.PASSWORD, CredentialsSource.FILE),
                (CredentialsType.AUTH_TOKEN, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.PROMPT),
            ],
            CredentialsType.PASSWORD,
            CredentialsSource.FILE,
            id="expect_password_file",
        ),
        pytest.param(
            [
                (CredentialsType.AUTH_TOKEN, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.PROMPT),
            ],
            CredentialsType.SESSION_ID,
            CredentialsSource.FILE,
            id="expect_legacy_auth_token_file",
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
    httpserver: HTTPServer,
    table_renderable_mock: type[TableRenderable],
    auth_token_file: Path,
    auth_file: Path,
    session_id_file: Path,
    config: Config,
    sources: list[tuple[CredentialsType, CredentialsSource]],
    expect_source: CredentialsSource,
    expect_type: CredentialsType,
) -> None:
    """Test that automatic selection of authentication source works given
    multiple valid authentication sources.


    Mocks ZabbixAPI methods to avoid reliace on a Zabbix server.
    """
    # TODO: test with a mix of valid and invalid sources, as well as
    #  with no valid sources.
    MOCK_USER = "Admin"
    MOCK_PASSWORD = "zabbix"
    MOCK_TOKEN = "abc1234567890"
    # Mock token used in legacy auth token file (to differentiate from new location)
    MOCK_URL = httpserver.url_for("/")

    config.api.url = MOCK_URL
    config.app.auth_token_file = auth_token_file
    config.app.session_id_file = session_id_file

    authenticator = Authenticator(config)

    # Mock endpoints for API calls:

    # Endpoint for ZabbixAPI.version
    # Add a version different from the default so we can tell if the mock was used
    # But also is recent enough that we use auth headers (>= 6.4.0)
    add_zabbix_version_endpoint(httpserver, "6.4.0", id=0)

    # Endpoint for ZabbixAPI.login()
    add_zabbix_endpoint(
        httpserver,
        method="user.login",
        params={},  # matching NYI
        response=MOCK_TOKEN,
        id=1,
    )

    # Replace certain difficult to test methods with mocks
    # States reasons for mocking each method

    # REASON: Implementation detail, not relevant to this test.
    # This method is called by the login method as of 3.4.2, but
    # it is an implementation detail and not relevant to this test
    # (it calls host.get with a limit of 1)
    def mock_ensure_authenticated(self: ZabbixAPI) -> None:
        return

    monkeypatch.setattr(
        auth.ZabbixAPI, "ensure_authenticated", mock_ensure_authenticated
    )

    # REASON: Prompts for input (could also be tested with a fake input stream)
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

    # REASON: Falls back on default auth token file path (which might exist on test user's system)
    # We want to ensure that the function only finds the test file we created
    def mock_get_auth_token_file_paths(config: Optional[Config] = None) -> list[Path]:
        return [auth_token_file]

    monkeypatch.setattr(
        auth, "get_auth_token_file_paths", mock_get_auth_token_file_paths
    )

    # REASON: Same as above
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
            if ctype == CredentialsType.SESSION_ID:
                sidfile = SessionIDFile()
                sidfile.set_user_session(MOCK_URL, MOCK_USER, MOCK_TOKEN)
                sidfile.save(session_id_file)
                config.app.use_session_id_file = True
                config.app.allow_insecure_auth_file = True
            elif ctype == CredentialsType.AUTH_TOKEN:
                auth_token_file.write_text(f"{MOCK_USER}::{MOCK_TOKEN}")
                config.app.use_session_id_file = True
                config.app.allow_insecure_auth_file = True
            elif ctype == CredentialsType.PASSWORD:
                auth_file.write_text(f"{MOCK_USER}::{MOCK_PASSWORD}")
                config.app.auth_file = auth_file

    _, info = authenticator.login_with_any()

    # Provide more verbose assertion messages in case of failures
    # We want to know both source AND type when it fails.
    def fmt_assert_msg(
        expect_type: CredentialsType, expect_source: CredentialsSource
    ) -> str:
        return (
            f"Expected {expect_type} from {expect_source}, got {info.credentials.type} "
            f"from {info.credentials.source}"
        )

    assert info.credentials.type == expect_type, fmt_assert_msg(
        expect_type, expect_source
    )
    assert info.credentials.source == expect_source, fmt_assert_msg(
        expect_type, expect_source
    )

    assert info.token == MOCK_TOKEN

    # Ensure the login method modified the base renderable's zabbix version attribute
    # with the one we got from the mocked API response

    # Check the mocked version we replace the real class with
    assert table_renderable_mock.zabbix_version == Version("6.4.0")

    # Try to import the real class and check that our mock changes were applied
    from zabbix_cli.models import TableRenderable

    assert TableRenderable.zabbix_version == Version("6.4.0")

    # Check HTTP server errors
    httpserver.check_assertions()
    httpserver.check_handler_errors()


def test_table_renderable_mock_reverted() -> None:
    """Attempt to ensure that the TableRenderable has been unchanged after
     running tests that mutate it.

    If those tests have used the mock class correctly, this test should pass.

    TODO: Ensure this test is run _after_ the tests that mutate the class.
    """
    from zabbix_cli.models import TableRenderable

    # Ensure the mock changes were reverted
    assert TableRenderable.zabbix_version != Version("1.2.3")
    assert TableRenderable.zabbix_version.release == snapshot((7, 0, 0))
