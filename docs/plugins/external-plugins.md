# External plugins

!!! important
    This page assumes you have read the [Writing plugins](./guide.md) page to understand the basics of writing plugins.

External plugins are plugins that are packaged as Python packages and can be installed with Pip. Using [`pyproject.toml` entry points](https://packaging.python.org/en/latest/specifications/entry-points/), the application can automatically discover and load these plugins.

A complete example of an external plugin can be found here: <https://github.com/pederhan/zabbix-cli-plugin-entrypoint>

## Packaging your plugin

Assuming you have written a plugin module as outlined in[Writing plugins](./guide.md), you can package it as a Python package that defines an entry point for Zabbix-CLI to discover. Similar to local plugins, the entry point is a Python file or module that contains the plugin's functionality, except for external plugins, the entry point is defined in the `pyproject.toml` file - _not_ the configuration file.

### Directory structure

The plugin package should have the following directory structure:

```plaintext
.
├── my_plugin/
│   ├── __init__.py
│   └── plugin.py
└── pyproject.toml
```

Alternatively, if using the src layout:

```plaintext
.
├── src/
│   └── my_plugin/
│       ├── __init__.py
│       └── plugin.py
└── pyproject.toml
```

### pyproject.toml

The package must contain a `pyproject.toml` file that instructs your package manager how to build and install the package. The following is a good starting point for a project using `hatchling` as the build backend:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "my_plugin"
authors = [
    {name = "Firstname Lastname", email = "mail@example.com"},
]
version = "0.1.0"
description = "My first Zabbix CLI plugin"
readme = "README.md"
requires-python = ">=3.8"
license = "MIT"
dependencies = [
    "zabbix-cli@git+https://github.com/unioslo/zabbix-cli.git",
]

[tool.hatch.metadata]
allow-direct-references = true

[project.entry-points.'zabbix-cli.plugins']
my_plugin = "my_plugin.plugin"
```

#### Alternative build backends

If you prefer setuptools, you can omit the `[tool.hatch.metadata]` section and replace the `[build-system]` section with the following:

```toml
[build-system]
requires = ["setuptools", "setuptools-scm"]
build-backend = "setuptools.build_meta"
```

### Configuring the plugin

Much like local plugins, external plugins define their configuration in the application's configuration file, except for external plugins the configuration is entirely optional.

The name of the plugin in the configuration file must match the name of the entry point defined in the `pyproject.toml` file. Given that we used the entry point `my_plugin`, its configuration should look like this:

```toml
[plugins.my_plugin]
# module must be omitted for external plugins
enabled = true
extra_option_1 = "Some value"
extra_option_2 = 42
```

Unlike local plugins, external plugins do not _require_ a configuration entry to be loaded. The application is able to automatically detect the plugin and load it using its metadata.
However, the option is there if you want to provide users with additional configuration options for your plugin. This configuration section can also be used to disable a plugin without having to uninstall it by setting `enabled = false`.

!!! note
    If rewriting a local plugin as an external one, remember to remove the `module` key from the plugin's configuration.

## Installing the plugin

How to install the plugins depends on how Zabbix-CLI is installed. The plugin must be installed in the same Python environment as Zabbix-CLI, which is different with each installation method.

### uv

`uv` can install plugins using the same `uv tool install` command, but with the `--with` flag:

```bash
uv tool install git+https://github.com/unioslo/zabbix-cli.git@master --with my_plugin
```

### pipx

`pipx` Zabbix-CLI installations require the plugin to be injected into the environment:

```bash
pipx install git+https://github.com/unioslo/zabbix-cli.git@master
pipx inject zabbix-cli my_plugin
```

### pip

If Zabbix-CLI is installed with `pip`, the plugin can be installed as a regular Python package:

```bash
pip install my_plugin
```
