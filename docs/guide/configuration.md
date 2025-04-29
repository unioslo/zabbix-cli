# Configuration

!!! note "Configuration file directory"
    The application uses the [platformdirs](https://pypi.org/project/platformdirs/) package to determine the configuration directory.

The application is configured with a TOML file. The file is created on startup if it doesn't exist.

The configuration file is searched for in the following locations:

{% include ".includes/config-locations.md" %}

<!-- TODO: Gather the different paths in CI, then combine them to construct the config-locations.md file -->

## Create a config

The configuration file is automatically created when the application is started for the first time.

The config file can also manually be created with the `init` command:

```bash
zabbix-cli init
```

The application will print the location of the created configuration file.

To bootstrap the config with a URL and username, use the options `--url` and `--user`:

```bash
zabbix-cli init --url https://zabbix.example.com --user Admin
```

To overwrite an existing configuration file, use the `--overwrite` option:

```
zabbix-cli init --overwrite
```

## Config directory

The default configuration directory can be opened in the system's file manager with the `open` command:

```bash
zabbix-cli open config
```

To print the path instead of opening it, use the `--path` option:

```bash
zabbix-cli open config --path
```

## Show config

The contents of the current configuration file can be displayed with `show_config`:

```bash
zabbix-cli show_config
```

## Sample config

A sample configuration file can be printed to the terminal with the `sample_config` command. This can be redirected to a file to create a configuration file in an arbitrary location:

```
zabbix-cli sample_config > /path/to/config.toml
```

The created config looks like this (with actual paths instead of placeholders)

```toml
{% include "data/sample_config.toml" %}
```

## Options

{% macro render_option(option) %}
{% if option.is_model %}

### `{{ option.name }}`

{{ option.description }}

{% for field in option.fields %}
{{ render_option(field) }}
{% endfor %}

{% else %}

#### `{{ option.name }}`

{{ option.description }}

Type: `{{ option.type }}`

{% if option.default %}
Default: `{{ option.default }}`
{% endif %}

{% if option.choices_str %}
Choices: `{{ option.choices_str }}`
{% endif %}

{% if option.required %}
Required: `true`
{% endif %}

{% if option.parents_str and option.example %}
**Example:**

```toml
{{ option.example }}
```

{% endif %}

----

{% endif %}
{% endmacro %}
{% for option in config_options.fields %}
{{ render_option(option) }}
{% endfor %}
