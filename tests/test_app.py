from __future__ import annotations

import pytest
from zabbix_cli.app.app import StatefulApp
from zabbix_cli.config.model import PluginConfig
from zabbix_cli.state import State


def test_get_plugin_config(app: StatefulApp, state: State) -> None:
    """Test that we can get a plugin's configuration."""
    # Add a plugin configuration
    state.config.plugins.root = {
        "my_commands": PluginConfig(
            module="path.to.my_commands",
        ),
        "my_commands2": PluginConfig(
            module="path/to/my_commands2.py",
        ),
        # Match name of this module
        "test_app": PluginConfig(
            module="tests.test_app",
        ),
    }

    # With name
    config = app.get_plugin_config("my_commands")
    assert config
    assert config.module == "path.to.my_commands"

    # Auto-detect module name
    config = app.get_plugin_config()
    assert config
    assert config.module == "tests.test_app"

    # Missing (name)
    with pytest.raises(KeyError):
        config = app.get_plugin_config("missing")

    # Missing (auto-detect)
    state.config.plugins.root.pop("test_app")
    with pytest.raises(KeyError):
        config = app.get_plugin_config()
