from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from zabbix_cli.config.model import Config


def test_config_default() -> None:
    """Assert that the config by default only requires a URL."""
    with pytest.raises(ValidationError) as excinfo:
        Config()
    assert "1 validation error" in str(excinfo.value)
    assert "url" in str(excinfo.value)


def test_sample_config() -> None:
    """Assert that the sample config can be instantiated."""
    assert Config.sample_config()


@pytest.mark.parametrize(
    "bespoke",
    [True, False],
)
def test_load_config_file_legacy(data_dir: Path, bespoke: bool) -> None:
    config_path = data_dir / "zabbix-cli.conf"
    if bespoke:
        conf = Config.from_conf_file(config_path)
    else:
        conf = Config.from_file(config_path)
    assert conf
    # Should be loaded from the file we specified
    assert conf.config_path == config_path
    # Should be marked as legacy
    assert conf.app.is_legacy is True
    # Should use legacy JSON format automatically
    assert conf.app.legacy_json_format is True


def remove_path_options(path: Path, tmp_path: Path) -> Path:
    """Remove all path options from a TOML config file.

    Some config options require a directory or file to exist, which is not always
    possible or desirable in a test environment."""
    contents = path.read_text()
    new_contents = "\n".join(
        line for line in contents.splitlines() if "/path/to" not in line
    )
    new_file = tmp_path / path.name
    new_file.write_text(new_contents)
    return new_file


def replace_paths(path: Path, tmp_path: Path) -> Path:
    """Replace all /path/to paths with directory created by tmp_path."""
    contents = path.read_text()
    new_contents = contents.replace("/path/to", str(tmp_path))
    tmp_path.mkdir(exist_ok=True)
    new_file = tmp_path / path.name
    new_file.write_text(new_contents)
    return new_file


@pytest.mark.parametrize(
    "bespoke",
    [True, False],
)
@pytest.mark.parametrize(
    "with_paths",
    [True, False],
)
def test_load_config_file(
    data_dir: Path, tmp_path: Path, bespoke: bool, with_paths: bool
) -> None:
    """Test loading a TOML configuration file."""
    config_path = data_dir / "zabbix-cli.toml"

    # Test with and without custom file paths
    if with_paths:
        config_path = replace_paths(config_path, tmp_path)
    else:
        config_path = remove_path_options(config_path, tmp_path)

    # Use bespoke method for loading the given format
    if bespoke:
        conf = Config.from_toml_file(config_path)
    else:
        conf = Config.from_file(config_path)

    assert conf
    # Should be loaded from the file we specified
    assert conf.config_path == config_path
    assert conf.app.is_legacy is False
    assert conf.app.legacy_json_format is False
