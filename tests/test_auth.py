from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Optional
from unittest.mock import patch

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
from zabbix_cli.auth import SessionFile
from zabbix_cli.auth import SessionInfo
from zabbix_cli.auth import SessionList
from zabbix_cli.auth import get_auth_file_paths
from zabbix_cli.auth import get_auth_token_file_paths
from zabbix_cli.config.constants import AUTH_FILE
from zabbix_cli.config.constants import AUTH_TOKEN_FILE
from zabbix_cli.config.model import Config
from zabbix_cli.exceptions import SessionFileError
from zabbix_cli.exceptions import SessionFileNotFoundError
from zabbix_cli.exceptions import SessionFilePermissionsError
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


@pytest.fixture(name="session_file")
def _session_file(tmp_path: Path) -> Path:
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
                (CredentialsType.SESSION, CredentialsSource.FILE),
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
                (CredentialsType.SESSION, CredentialsSource.FILE),
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
                (CredentialsType.SESSION, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.CONFIG),
                (CredentialsType.PASSWORD, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.ENV),
                (CredentialsType.AUTH_TOKEN, CredentialsSource.FILE),
                (CredentialsType.PASSWORD, CredentialsSource.PROMPT),
            ],
            CredentialsType.SESSION,
            CredentialsSource.FILE,
            id="expect_session_file",
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
            CredentialsType.SESSION,
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
    session_file: Path,
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
    config.app.session_file = session_file

    authenticator = Authenticator(config)

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
            if ctype == CredentialsType.SESSION:
                sidfile = SessionFile()
                sidfile.set_user_session(MOCK_URL, MOCK_USER, MOCK_TOKEN)
                sidfile.save(session_file)
                config.app.use_session_file = True
                config.app.allow_insecure_auth_file = True
            elif ctype == CredentialsType.AUTH_TOKEN:
                auth_token_file.write_text(f"{MOCK_USER}::{MOCK_TOKEN}")
                config.app.use_session_file = True
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


@pytest.fixture
def sample_session_file(tmp_path: Path) -> Path:
    """Create a sample session file for testing."""
    file_path = tmp_path / "sessions.json"
    file_path.write_text(
        '{"https://zabbix.example.com": [{"username": "admin", "session_id": "abc123"}]}'
    )
    return file_path


def test_sessionid_list_set_session() -> None:
    """Test setting sessions in SessionList."""
    session_list = SessionList()

    def check_session(username: str, session_id: str, expected_count: int):
        session = session_list.get_session(username)
        assert session is not None
        assert session.username == username
        assert session.session_id == session_id
        assert len(session_list) == expected_count

    assert len(session_list) == 0

    # Add new session
    session_list.set_session("user1", "abcd1234")
    check_session("user1", "abcd1234", 1)

    # Update the session
    session_list.set_session("user1", "xyz7890")
    check_session("user1", "xyz7890", 1)

    # Add another new session
    session_list.set_session("user2", "1234abcd")
    check_session("user2", "1234abcd", 2)


@pytest.mark.parametrize(
    "initial_sessions,username,expected",
    [
        ([], "user1", None),  # Empty list
        ([{"username": "user1", "session_id": "abc"}], "user1", "abc"),  # Existing user
        (
            [{"username": "user1", "session_id": "abc"}],
            "user2",
            None,
        ),  # Non-existent user
    ],
)
def test_sessionid_list_get_session(
    initial_sessions: list[dict[str, str]], username: str, expected: Optional[str]
):
    """Test retrieving sessions from SessionList."""
    session_list = SessionList(root=[SessionInfo(**s) for s in initial_sessions])
    result = session_list.get_session(username)

    if expected is None:
        assert result is None
    else:
        assert result is not None
        assert result.session_id == expected


@pytest.mark.parametrize(
    "url,username,expected_session",
    [
        ("https://zabbix1.com", "user1", None),  # Non-existent URL
        ("https://zabbix2.com", "user2", "xyz789"),  # Existing URL and user
    ],
)
def test_sessionid_file_get_user_session(
    url: str, username: str, expected_session: Optional[str]
):
    """Test retrieving user sessions from SessionFile."""
    session_file = SessionFile(
        root={
            "https://zabbix2.com": SessionList(
                root=[SessionInfo(username="user2", session_id="xyz789")]
            )
        }
    )

    result = session_file.get_user_session(url, username)
    if expected_session is None:
        assert result is None
    else:
        assert result is not None
        assert result.session_id == expected_session


@pytest.mark.parametrize(
    "url,username,session_id,expected_urls",
    [
        ("https://new.com", "user1", "session1", ["https://new.com"]),  # New URL
        (
            "https://existing.com",
            "user2",
            "session2",
            ["https://existing.com"],
        ),  # Existing URL
    ],
)
def test_sessionid_file_set_user_session(
    url: str, username: str, session_id: str, expected_urls: list[str]
):
    """Test setting user sessions in SessionFile."""
    session_file = SessionFile()
    session_file.set_user_session(url, username, session_id)

    assert set(session_file.root.keys()) == set(expected_urls)
    session = session_file.get_user_session(url, username)
    assert session is not None
    assert session.session_id == session_id


@pytest.mark.parametrize(
    "file_exists,secure_permissions,allow_insecure,should_raise",
    [
        (True, True, False, False),  # Normal case
        (False, True, False, True),  # File doesn't exist
        (True, False, False, True),  # Insecure permissions
        (True, False, True, False),  # Insecure permissions but allowed
    ],
)
def test_sessionid_file_load(
    tmp_path: Path,
    file_exists: bool,
    secure_permissions: bool,
    allow_insecure: bool,
    should_raise: bool,
):
    """Test loading SessionFile with various conditions."""
    file_path = tmp_path / "test_sessions.json"
    if file_exists:
        file_path.write_text('{"https://zabbix.example.com": []}')

    with patch("zabbix_cli.auth.file_has_secure_permissions") as mock_secure:
        mock_secure.return_value = secure_permissions

        if should_raise:
            with pytest.raises((SessionFileNotFoundError, SessionFilePermissionsError)):
                SessionFile.load(file_path, allow_insecure=allow_insecure)
        else:
            result = SessionFile.load(file_path, allow_insecure=allow_insecure)
            assert isinstance(result, SessionFile)
            assert result._path == file_path


@pytest.mark.parametrize(
    "has_path,allow_insecure,secure_permissions,should_raise",
    [
        (True, False, True, False),  # Normal case
        (False, False, True, True),  # No path specified
        (True, False, False, False),  # Insecure permissions, will be fixed
        (True, True, False, False),  # Insecure permissions allowed
    ],
)
def test_sessionid_file_save(
    tmp_path: Path,
    has_path: bool,
    allow_insecure: bool,
    secure_permissions: bool,
    should_raise: bool,
):
    """Test saving SessionFile with various conditions."""
    file_path = tmp_path / "test_sessions.json" if has_path else None
    session_file = SessionFile()
    if has_path:
        session_file._path = file_path

    with (
        patch("zabbix_cli.auth.file_has_secure_permissions") as mock_secure,
        patch("zabbix_cli.auth.set_file_secure_permissions") as mock_set_secure,
    ):
        mock_secure.return_value = secure_permissions

        if should_raise:
            with pytest.raises(SessionFileError) as exc_info:
                session_file.save(path=file_path, allow_insecure=allow_insecure)
            assert str(exc_info.value) == snapshot(
                "Cannot save session file without a path."
            )
        else:
            session_file.save(path=file_path, allow_insecure=allow_insecure)
            assert file_path and file_path.exists()
            if not secure_permissions and not allow_insecure:
                mock_set_secure.assert_called_once_with(file_path)
