# Local plugins

!!! important
    This page assumes you have read the [Writing plugins](./guide.md) page to understand the basics of writing plugins.

A local plugin is a Python module that is loaded by the application on startup. It _must_ be manually configured in the configuration file for the application to find it.

## Directory structure

Given your plugin is structured like this:

```plaintext
/path/to/
└── my_plugin/
    ├── __init__.py
    └── plugin.py
```

You can add the following to your configuration file:

```toml
[plugins.my_plugin]
module = "/path/to/my_plugin/plugin.py"
# or
# module = "my_plugin.plugin"
```

An absolute path to the plugin file is preferred, but a Python module path can also be used. The differences are outlined below.

### File path

It is recommended to use an absolute path to the plugin file. This ensures that the application can find the plugin regardless of the current working directory. The path should point to the plugin file itself, not the directory containing it.

### Module path

One can also use a Python module path to the plugin file. This is useful if the plugin is part of a larger Python package. The path must be available in the Python path (`$PYTHONPATH`) for the application to find it. The import path can point to the plugin file itself or the directory containing it as long as ``__init__.py` is present and imports the plugin file.
