# External plugins

!!! important
    This page assumes you have read the [local plugins](./local-plugins.md) page to understand the basics of writing plugins.

External plugins are plugins that are packaged as Python packages and can be installed with Pip. Using [`pyproject.toml` entry points](https://packaging.python.org/en/latest/specifications/entry-points/), the application can automatically discover and load these plugins.

## Packaging your plugin

Assuming you have written a plugin module as outlined on the [local plugins](./local-plugins.md) page, you can package it as a Python package that defines an entry point for Zabbix-CLI to discover.

An example plugin can be found here: <https://github.com/pederhan/zabbix-cli-plugin-entrypoint>

### Directory structure

The plugin package should have the following directory structure:

```plaintext
.
├── your_plugin/
│   ├── __init__.py
│   └── plugin.py
└── pyproject.toml
```

Alternatively, if using the src layout:

```plaintext
.
├── src/
│   └── your_plugin/
│       ├── __init__.py
│       └── plugin.py
└── pyproject.toml
```

### pyproject.toml

The package must contain a `pyproject.toml` file that instructs your package manager how to build and install the package. This is a good starting point for a `pyproject.toml` file using `hatchling` as the build backend:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "your_plugin_name"
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
your_plugin_name = "your_plugin_name.plugin"
```

#### Alternative build backends

If you prefer setuptools, you can omit the `[tool.hatch.metadata]` section and replace the `[build-system]` section with the following:

```toml
[build-system]
requires = ["setuptools", "setuptools-scm"]
build-backend = "setuptools.build_meta"
```

### Configuring the plugin

Much like local plugins, external plugins define their configuration in the application's configuration file. The name of the plugin in the configuration file must match the name of the entry point defined in the `pyproject.toml` file. Given that we used the entry point `your_plugin_name`, the configuration should look like this:

```toml
[plugins.your_plugin_name]
# module can be omitted for external plugins
enabled = true
extra_option_1 = "Some value"
extra_option_2 = 42
```

Unlike local plugins, external plugins do not _require_ a configuration entry to be loaded. The application is able to automatically detect the plugin and load it using its metadata. However, should you want to disable an external plugin without having to uninstall it, you can set the `enabled` option to `false` in the configuration file.

!!! note
    If rewriting a local plugin as an external one, remember to remove the `module` key from the configuration file.
