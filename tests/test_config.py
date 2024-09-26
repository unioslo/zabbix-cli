from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

import pytest
from inline_snapshot import snapshot
from pydantic import ValidationError
from zabbix_cli.config.model import Config
from zabbix_cli.config.model import PluginConfig
from zabbix_cli.config.model import PluginsConfig
from zabbix_cli.exceptions import ConfigOptionNotFound
from zabbix_cli.exceptions import PluginConfigTypeError


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


def test_plugins_config_get() -> None:
    """Test that we can get a plugin configuration."""
    config = PluginsConfig(
        root={
            "test1": PluginConfig(
                enabled=True,
                module="zabbix_cli.plugins.test1",
            ),
            "test2": PluginConfig(
                enabled=True,
                module="zabbix_cli.plugins.test2",
            ),
        }
    )
    assert config.get("test1")
    assert config.get("test2")
    assert not config.get("test3")


def test_plugin_config_get() -> None:
    config = PluginConfig(module="test")
    assert config.get("module") == "test"

    # With type validation
    assert config.get("module", type=str) == "test"

    # Missing option
    with pytest.raises(ConfigOptionNotFound):
        assert config.get("missing") is None

    # Default value
    assert config.get("missing", "default") == "default"

    # Default value with type validation
    assert config.get("missing", "default", type=str) == "default"

    # Extra values
    config = PluginConfig(
        module="test",
        extra1="foo",
        extra2=2,
        extra3=True,
        extra4=[1, 2, 3],
    )
    assert config.get("extra1") == "foo"
    assert config.get("extra2") == 2
    assert config.get("extra3") is True
    assert config.get("extra4") == [1, 2, 3]

    # With type validation
    assert config.get("extra1", type=str) == "foo"
    assert config.get("extra2", type=int) == 2
    assert config.get("extra3", type=bool) is True
    assert config.get("extra4", type=list) == [1, 2, 3]

    # Type validation with coercion
    assert config.get("extra3", type=int) == 1
    assert config.get("extra4", type=tuple) == (1, 2, 3)
    # Cannot coerce int to str by default in Pydantic
    with pytest.raises(PluginConfigTypeError):
        assert config.get("extra2", type=str) == "2"


def test_config_get_with_annotations() -> None:
    """Test PluginConfig.get with more complex annotations"""
    config = PluginConfig(
        module="test",
        extra1="foo",
        extra2=2,
        extra3=True,
        extra4=[1, 2, 3],
        extra5={"foo": [1, 2, 3]},
    )

    assert config.get("extra1", type=Optional[str]) == "foo"
    assert config.get("extra1", 123, type=Optional[str]) == "foo"
    assert config.get("extra1", type=Union[str, int])

    # Invalid default type
    with pytest.raises(PluginConfigTypeError):
        config.get("wrong", 123, type=Optional[str])
    assert config.get("wrong", "123", type=Optional[str]) == "123"

    # List type
    assert config.get("extra4", type=list) == [1, 2, 3]
    assert config.get("extra4", type=List[int]) == [1, 2, 3]
    if sys.version_info >= (3, 9):
        assert config.get("extra4", type=list[int]) == [1, 2, 3]

    # Dict type
    assert config.get("extra5", type=dict) == {"foo": [1, 2, 3]}
    assert config.get("extra5", type=Dict[str, List[int]]) == {"foo": [1, 2, 3]}
    if sys.version_info >= (3, 9):
        assert config.get("extra5", type=dict[str, list[int]]) == {"foo": [1, 2, 3]}


def test_plugin_config_set() -> None:
    config = PluginConfig()

    # Existing model field
    config.set("module", "new")
    assert config.module == "new"

    # New attribute/field
    config.set("extra", "new")
    assert config.extra == "new"

    # Any type goes
    obj = object()
    config.set("object", obj)
    assert config.object is obj

    # Instantiated with extra values
    config = PluginConfig(
        module="test",
        extra1="extra1",
        extra2=2,
        extra3=True,
    )

    # Override existing values
    config.set("extra1", "new")
    config.set("extra2", 3)
    config.set("extra3", False)

    assert config.extra1 == "new"
    assert config.extra2 == 3
    assert config.extra3 is False

    assert config.model_dump() == snapshot(
        {
            "module": "test",
            "enabled": True,
            "optional": False,
            "extra1": "new",
            "extra2": 3,
            "extra3": False,
        }
    )
