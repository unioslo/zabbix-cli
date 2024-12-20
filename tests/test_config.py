from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import Optional
from typing import Union

import pytest
import tomli
from inline_snapshot import snapshot
from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator
from typing_extensions import Self
from zabbix_cli.config.constants import OutputFormat
from zabbix_cli.config.constants import SecretMode
from zabbix_cli.config.model import APIConfig
from zabbix_cli.config.model import AppConfig
from zabbix_cli.config.model import Config
from zabbix_cli.config.model import PluginConfig
from zabbix_cli.config.model import PluginsConfig
from zabbix_cli.config.utils import DeprecatedField
from zabbix_cli.config.utils import get_deprecated_fields_set
from zabbix_cli.config.utils import update_deprecated_fields
from zabbix_cli.exceptions import ConfigOptionNotFound
from zabbix_cli.exceptions import PluginConfigTypeError


def test_config_default() -> None:
    """Assert that the config can be instantiated with no arguments."""
    assert Config()


def test_sample_config() -> None:
    """Assert that the sample config can be instantiated."""
    assert Config.sample_config()


@pytest.mark.parametrize(
    "bespoke",
    [True, False],
)
def test_load_config_file_legacy(legacy_config_path: Path, bespoke: bool) -> None:
    if bespoke:
        conf = Config.from_conf_file(legacy_config_path)
    else:
        conf = Config.from_file(legacy_config_path)
    assert conf
    # Should be loaded from the file we specified
    assert conf.config_path == legacy_config_path
    # Should be marked as legacy
    assert conf.app.is_legacy is True
    # Should use legacy JSON format automatically
    assert conf.app.legacy_json_format is True


def remove_path_options(config_path: Path, tmp_path: Path) -> None:
    """Remove all path options from a TOML config file.

    Some config options require a directory or file to exist, which is not always
    possible or desirable in a test environment."""
    contents = config_path.read_text()
    new_contents = "\n".join(
        line for line in contents.splitlines() if "/path/to" not in line
    )
    config_path.write_text(new_contents)


def replace_paths(config_path: Path, tmp_path: Path) -> None:
    """Replace all /path/to paths in a file with temporary directories."""
    contents = config_path.read_text()
    new_contents = contents.replace("/path/to", str(tmp_path))
    tmp_path.mkdir(exist_ok=True)
    config_path.write_text(new_contents)


@pytest.mark.parametrize(
    "bespoke",
    [True, False],
)
@pytest.mark.parametrize(
    "with_paths",
    [True, False],
)
def test_load_config_file(
    config_path: Path, tmp_path: Path, bespoke: bool, with_paths: bool
) -> None:
    """Test loading a TOML configuration file."""
    # Test with and without custom file paths
    if with_paths:
        replace_paths(config_path, tmp_path)
    else:
        remove_path_options(config_path, tmp_path)

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
    assert config.get("extra4", type=list[int]) == [1, 2, 3]
    assert config.get("extra4", type=list[int]) == [1, 2, 3]

    # Dict type
    assert config.get("extra5", type=dict) == {"foo": [1, 2, 3]}
    assert config.get("extra5", type=dict[str, list[int]]) == {"foo": [1, 2, 3]}
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


@pytest.mark.parametrize(
    "context, expect",
    [
        ({"secrets": SecretMode.HIDE}, SecretMode.HIDE),
        ({"secrets": SecretMode.MASK}, SecretMode.MASK),
        ({"secrets": SecretMode.PLAIN}, SecretMode.PLAIN),
        ({"secrets": "hide"}, SecretMode.HIDE),
        ({"secrets": "mask"}, SecretMode.MASK),
        ({"secrets": "plain"}, SecretMode.PLAIN),
        ({}, SecretMode.MASK),
        (None, SecretMode.MASK),
        (lambda: {}, SecretMode.MASK),  # type: ignore
        ({"secrets": True}, SecretMode.PLAIN),
        ({"secrets": False}, SecretMode.MASK),
    ],
)
def test_secret_mode_from_context(context: Any, expect: SecretMode) -> None:
    assert SecretMode.from_context(context) == expect


def test_secret_mode_default() -> None:
    assert SecretMode._DEFAULT is SecretMode.MASK  # type: ignore


def _get_config_with_secrets() -> Config:
    return Config(
        api=APIConfig(
            username="Admin",
            password="password",
            auth_token="token123",
        )
    )


def test_config_dump_to_file_masked(tmp_path: Path) -> None:
    conf_file = tmp_path / "zabbix-cli.toml"
    conf = _get_config_with_secrets()
    conf.dump_to_file(conf_file, secrets=SecretMode.MASK)

    toml_str = conf_file.read_text()
    config_dict = tomli.loads(toml_str)
    assert config_dict["api"]["password"] == snapshot("**********")
    assert config_dict["api"]["auth_token"] == snapshot("**********")


def test_deprecated_field_warnings(caplog: pytest.LogCaptureFixture) -> None:
    """Test that deprecated fields are logged."""
    Config(
        app=AppConfig(
            output_format=OutputFormat.JSON,
            use_colors=True,
            use_paging=True,
            system_id="System-User",
        )
    )
    assert caplog.record_tuples == snapshot(
        [
            (
                "zabbix_cli",
                30,
                "Config option [configopt]output_format[/] is deprecated. Use [configopt]app.output.format[/] instead.",
            ),
            (
                "zabbix_cli",
                30,
                "Config option [configopt]system_id[/] is deprecated. Use [configopt]api.username[/] instead.",
            ),
            (
                "zabbix_cli",
                30,
                "Config option [configopt]use_colors[/] is deprecated. Use [configopt]app.output.color[/] instead.",
            ),
            (
                "zabbix_cli",
                30,
                "Config option [configopt]use_paging[/] is deprecated. Use [configopt]app.output.paging[/] instead.",
            ),
            (
                "zabbix_cli",
                30,
                """\
Your configuration file contains deprecated options.
  To update your config file with the new options, run:
  [command]zabbix-cli update_config[/]
  For more information, see the documentation.\
""",
            ),
        ]
    )


def test_get_deprecated_fields_set() -> None:
    config = Config(
        app=AppConfig(
            output_format=OutputFormat.JSON,
            use_colors=True,
            use_paging=True,
            system_id="System-User",
        )
    )
    # Sort because order of `BaseModel.model_fields_set` is not guaranteed
    assert sorted(get_deprecated_fields_set(config)) == snapshot(
        [
            DeprecatedField(
                field_name="app.output_format",
                value=OutputFormat.JSON,
                replacement="app.output.format",
            ),
            DeprecatedField(
                field_name="app.system_id",
                value="System-User",
                replacement="api.username",
            ),
            DeprecatedField(
                field_name="app.use_colors", value=True, replacement="app.output.color"
            ),
            DeprecatedField(
                field_name="app.use_paging", value=True, replacement="app.output.paging"
            ),
        ]
    )


def test_get_deprecated_fields_deep_nesting() -> None:
    """Test that deprecated fields are found in nested models."""

    class Baz(BaseModel):
        qux: str = ""

    class Bar(BaseModel):
        baz: Baz = Field(default_factory=Baz)
        qux_deprecated: str = Field(
            default="",
            deprecated=True,
            json_schema_extra={"replacement": "bar.baz.qux"},
        )

    class Foo(BaseModel):
        bar: Bar = Field(default_factory=Bar)

        # Copied from zabbix_cli.config.model.Config
        # TODO: to test this better, we could declare a new BaseModel
        # subclass intended for top-level models which automatically implement
        # this validator. That way we can be sure the validator behavior
        # in the test is consistent with the behavior in the actual code.
        @model_validator(mode="after")
        def _set_deprecated_fields_in_new_location(self) -> Self:
            """Set deprecated fields in their new location."""
            update_deprecated_fields(self)
            return self

    foo = Foo(bar=Bar(qux_deprecated="test123"))

    # Deprecated field should be found
    assert sorted(get_deprecated_fields_set(foo)) == snapshot(
        [
            DeprecatedField(
                field_name="bar.qux_deprecated",
                value="test123",
                replacement="bar.baz.qux",
            )
        ]
    )

    # Deprecated field should be automatically assigned to the new field
    assert foo.model_dump() == snapshot(
        {"bar": {"baz": {"qux": "test123"}, "qux_deprecated": "test123"}}
    )


def test_deprecated_fields_updated() -> None:
    """Test that deprecated fields are assigned to the new fields if specified."""
    conf = Config(
        app=AppConfig(
            # Set fields to non-default values for comparison
            output_format=OutputFormat.JSON,
            use_colors=False,
            use_paging=True,
            system_id="System-User",
        )
    )
    assert sorted(conf.app.model_fields_set) == snapshot(
        ["output_format", "system_id", "use_colors", "use_paging"]
    )
    assert sorted(conf.app.output.model_fields_set) == snapshot(
        ["color", "format", "paging"]
    )
    assert conf.app.output.format == OutputFormat.JSON
    assert conf.app.output.color is False
    assert conf.app.output.paging is True
    assert conf.api.username == "System-User"


def get_deprecated_fields(model: Union[type[BaseModel], BaseModel]) -> list[str]:
    """Get a set of names of deprecated fields in a model and its submodels."""
    fields: list[str] = []
    for field_name, field in model.model_fields.items():
        if field.deprecated:
            fields.append(field_name)
        if not field.annotation:
            continue
        try:
            if issubclass(field.annotation, BaseModel):
                submodel_fields = get_deprecated_fields(field.annotation)
                fields.extend(
                    f"{field_name}.{subfield}" for subfield in submodel_fields
                )
        except TypeError:
            pass
    return fields


def test_get_deprecated_fields() -> None:
    """Ensure we are aware of all deprecated fields in the Config model"""
    assert get_deprecated_fields(Config) == snapshot(
        ["app.output_format", "app.use_colors", "app.use_paging", "app.system_id"]
    )


def test_load_deprecated_config(tmp_path: Path) -> None:
    conf = tmp_path / "zabbix-cli.toml"
    conf.write_text(
        f"""
[api]
url = "http://localhost:8080"

# No username option specified (assigned from app.system_id)

password = ""
auth_token = ""
verify_ssl = true

[app]
default_hostgroups = ["All-hosts"]
default_admin_usergroups = []
default_create_user_usergroups = []
default_notification_users_usergroups = ["All-notification-users"]
export_directory = "{tmp_path}/exports"
export_format = "json"
export_timestamps = false
use_session_id_file = true
auth_token_file = "{tmp_path}/.zabbix-cli_auth_token"
auth_file = "{tmp_path}/.zabbix-cli_auth"
history = true
history_file = "{tmp_path}/history"
bulk_mode = "strict"

# Deprecated options (moved)
use_colors = false
use_paging = true
output_format = "json"
system_id = "System-User"

# Deprecated options (slated for removal)
allow_insecure_auth_file = true
legacy_json_format = false

# No [app.output] section specified (assigned from deprecated app options)

[logging]
enabled = true
log_level = "DEBUG"
log_file = "{tmp_path}/zabbix-cli.log"

[plugins]
"""
    )
    # Check that we can actually load the config
    config = Config.from_file(conf)

    # Check that the deprecated fields are assigned to the new fields
    assert config.app.output.color is False
    assert config.app.output.paging is True
    assert config.app.output.format == OutputFormat.JSON
    assert config.api.username == "System-User"


def test_load_deprecated_config_with_new_and_old_options(tmp_path: Path) -> None:
    """Test loading a config file where both new and deprecated options are present.

    The deprecated options should _not_ be assigned to the new options, as the new options
    are already set"""
    conf = tmp_path / "zabbix-cli.toml"
    conf.write_text(
        """
[api]
username = "Admin"

[app]
use_colors = false
use_paging = true
output_format = "json"
system_id = "System-User"

[app.output]
color = true
format = "table"
paging = false
"""
    )
    config = Config.from_file(conf)

    # New fields should NOT be overwritten by deprecated fields
    assert config.api.username == "Admin"
    assert config.app.output.color is True
    assert config.app.output.paging is False
    assert config.app.output.format == OutputFormat.TABLE


def test_load_deprecated_config_legacy(legacy_config_path: Path) -> None:
    """Test loading a legacy .conf config file with deprecated options."""
    config_str = legacy_config_path.read_text()
    assert "system_id=Test" in config_str
    assert "use_colors=ON" in config_str
    assert "use_paging=OFF" in config_str

    # Manipulate config to set default boolean values to opposite
    config_str = config_str.replace("use_colors=ON", "use_colors=OFF")
    config_str = config_str.replace("use_paging=OFF", "use_paging=ON")
    legacy_config_path.write_text(config_str)

    config = Config.from_conf_file(legacy_config_path)

    # Check that the deprecated fields are assigned to the new fields
    assert config.api.username == "Test"
    assert config.app.output.color is False
    assert config.app.output.paging is True

    # Check that the assigned fields are counted as set
    assert "username" in config.api.model_fields_set
    assert "color" in config.app.output.model_fields_set
    assert "paging" in config.app.output.model_fields_set
    assert "format" not in config.app.output.model_fields_set

    # Check that the deprecated fields are also set
    assert "system_id" in config.app.model_fields_set
    assert "use_colors" in config.app.model_fields_set
    assert "use_paging" in config.app.model_fields_set
    assert "output_format" not in config.app.model_fields_set
