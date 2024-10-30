from __future__ import annotations

from pathlib import Path

from zabbix_cli._v2_compat import AUTH_FILE as AUTH_FILE_LEGACY
from zabbix_cli._v2_compat import AUTH_TOKEN_FILE as AUTH_TOKEN_FILE_LEGACY
from zabbix_cli.auth import get_auth_file_paths
from zabbix_cli.auth import get_auth_token_file_paths
from zabbix_cli.config.constants import AUTH_FILE
from zabbix_cli.config.constants import AUTH_TOKEN_FILE
from zabbix_cli.config.model import Config


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
