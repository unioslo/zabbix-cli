# Local plugins

A local plugin is a Python module containing user-defined code that the application can load on startup. When the appliation reads the configuration file, it will attempt to import any plugins defined in the `plugins` section.

A local plugin consists of two parts:

1. [Python module](#python-module)
2. [Config file entry](#configuration)

## Python module

A plugin module can in theory contain anything, but typically we want to import `zabbix_cli.app.app` to access the application state, define new commands, modify existing commands, etc. The following is a simple example of a plugin module:

```Python
# /path/to/my_plugin.py
from __future__ import annotations

from typing import Optional

import typer
from zabbix_cli.app import app
from zabbix_cli.render import render_result


def __configure__(config: PluginConfig) -> None:
    # This function is called after the application has finished its own configuration
    pass


# Header for the rich help panel shown in the --help output
CATEGORY = "My custom commands"

# Define a new command
@app.command(name="my_command", rich_help_panel=CATEGORY)
def my_command(
    ctx: typer.Context,
    arg1: str = typer.Argument(help="Some positional argument"),
    opt1: Optional[str] = typer.Option(None, "--opt1", "-O", help="Some named option"),
) -> None:
    """Short description of the command."""
    # We can use the Zabbix API client
    host = app.state.client.get_host(arg1)

    # We can use the same rendering machinery as the built-in commands
    render_result(host)
```

### Post-import configuration

The module can define a function called `__configure__` that will be called after the application has finished its own configuration. This function can be used to perform any necessary setup or configuration that the plugin requires. The function takes a single `PluginConfig` argument.

```python
from zabbix_cli.app import app
import logging

logger = logging.getLogger(__name__)

def __configure__(config: PluginConfig) -> None:
    logger.info(f"Running post-import configuration for {config.module}")

    # We can access anything we need from the application state as long as the plugin module imports `zabbix_cli.app.app`

    # Set custom HTTP headers
    app.state.client.session.headers["X-Plugin-Header"] = "Some value"

    # Ensure that a certain configuration key is set
    app.state.config.api.legacy_json_format = False
```

The sky is the limit when it comes to what you can do in the `__configure__` function. However, be aware that modifying certain config options will not have any effect. This is especially true for the `api` section of the config file, since the applicaiton has already configured the API client by the time the plugin is loaded.

## Configuration

Each plugin requires its own configuration entry in the config file.

### Required options

#### `module`

The plugin must also be configured in the config file. Each plugin should be defined as a subsection of the `plugins` section in the config file.

```toml
[plugins.my_plugin]
module = "path.to.my_plugin"
# OR
# module = "/path/to/my_plugin.py"
```

The `module` key can be a module path or a a file path. If using a file path, it is highly recommended to use an absolute path.

### Optional options

#### `enabled`

Plugins can be selectively disabled by setting the `enabled` option to `false`.

```toml
[plugins.my_plugin]
enabled = false
```

#### `optional`

The `optional` option can be used to mark a plugin as optional, meaning the application will not raise an error if the plugin module cannot be imported.

```toml
[plugins.my_plugin]
optional = true
```

### Extra options

The plugin configuration can contain any number of extra options that the plugin module can access. These options can be accessed through the `PluginConfig` object that is passed to the `__configure__` function.

```toml
[plugins.my_plugin]
module = "path.to.my_plugin"
extra_option_str = "foo"
extra_option_int = 42
extra_option_list = ["a", "b", "c"]
```

These options are not type-checked by default. However, when fetching these values, one can pass in a type hint to assert that the value is of the correct type. The `PluginConfig` class provides the method `get()` for fetching values from the config. The method takes the key of the option as the first argument, and an optional default value as the second argument. The method also takes an optional type hint as the third argument `type`.

```python
from zabbix_cli.app import app

def __configure__(config: PluginConfig) -> None:
    # Access extra options
    opt1 = config.get("extra_option_str")

    # Validate the type of the option
    # Also lets type checkers know the type of the variable
    opt1 = config.get("extra_option_str", type=str)

    # Types are optional
    opt2 = config.get("extra_option_int")
    # reveal_type(opt2) # reveals Any because no type hint
    # Types from the TOML file are preserved
    assert isinstance(opt2, int)

    # We can validate more complex types too
    opt4 = config.get("extra_option_list", type=list[str])

    # We can also provide a default value
    opt4 = config.get("non_existent_option", "default")
    assert opt4 == "default"

    # Type hints are supported here too
    opt5 = config.get("non_existent_option", "default", type=str)
    # reveal_type(opt5) # reveals str
    assert opt5 is None

    # Use our config options:
    app.state.client.session.headers["X-Plugin-Header"] = config.get("extra_option_str", type=str)
```

!!! tip
    Providing a type for the `get()` method will also give you better auto completion and type checking in your editor.

### Accessing plugin configuration from commands

Inside commands, the plugin's configuration can be accessed through the `app.get_plugin_config()` method.

The name of the plugin, as denoted by its `[plugins]` key, is passed as the argument to the method. If no configuration can be found, a `zabbix_cli.exceptions.PluginError` exception will be raised.

Given the following configuration:

```toml
[plugins.my_plugin]
```

We can access its configuration like this:

```python
from zabbix_cli.app import app


@app.command()
def my_command() -> None:
    config = app.get_plugin_config("my_plugin")
```

!!! note
    Should no config be available, an empty `PluginConfig` is returned. This is to facilitate external plugins that do not _require_ a configuration to be defined.
