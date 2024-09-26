from __future__ import annotations

from inline_snapshot import snapshot
from pytest import LogCaptureFixture
from zabbix_cli.app.app import StatefulApp
from zabbix_cli.config.model import PluginConfig
from zabbix_cli.state import State


def test_get_plugin_config(
    app: StatefulApp, state: State, caplog: LogCaptureFixture
) -> None:
    """Test that we can get a plugin's configuration."""
    # Add a plugin configuration
    state.config.plugins.root = {
        # From module specification
        "my_commands": PluginConfig(
            module="path.to.my_commands",
        ),
        # From path
        "my_commands2": PluginConfig(
            module="path/to/my_commands2.py",
        ),
        # From package with entrypoint
        "my_commands3": PluginConfig(),
    }

    # With name
    config = app.get_plugin_config("my_commands")
    assert config.module == "path.to.my_commands"

    # Missing config returns empty config
    config = app.get_plugin_config("missing")
    assert config.module == ""
    assert caplog.records[-1].message == snapshot(
        "Plugin 'missing' not found in configuration"
    )
