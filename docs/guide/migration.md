# Migration Guide

Zabbix CLI 3.0 introduces a whole range of new features and improvements, as well as deprecating some old ones. This guide is intended to help you migrate from Zabbix CLI 2.x to 3.0.

Notable changes include:

**Config**

- [**New configuration file format**](#config-file)
- [**New default configuration file location.**](#new-default-configuration-file-location)
- [**New configuration options**](#new-configuration-options)
- [**Renamed configuration options**](#renamed-configuration-options)

**Exports**

- [**New export formats**](#new-export-formats)
      - `yaml`
      - `php`
- [**New default export filenames**](#new-default-export-filenames)
      - Exported files are no longer prefixed with `zabbix_export_`
      - Exported files no longer include a timestamp in the filename by default. Newer exports overwrite older ones automatically.

**Commands**

- [**Command invocation syntax**](#command-invocation-syntax)
      - Using `zabbix-cli -C 'command args ...'` is no longer required.
      - Commands can be invoked directly with `zabbix-cli command args ...`
- [**Command syntax**](#command-syntax)
      - Commands use positional arguments to a lesser degree than in 2.x. Named options are now preferred.
      - Legacy positional arguments are deprecated and will generate a warning when used.
      - Most prompts have been removed and replaced with named options due to the increase in scope of the commands.

**Output**

- [**JSON output format**](#json-output-format)
      - The JSON output format has changed. The old format can be enabled with the `app.legacy_json_format` option in the new TOML configuration file format.
      - When using a legacy `.conf` configuration file, the old JSON format is assumed.

## Config file

Multiple changes have been made to the application's configuration file, in terms of format, location and option names.

### New configuration file format

The configuration file is now in [TOML](https://toml.io/en/) format. The old `.conf` format is deprecated but can still be loaded. Old configs generate a warning when used. See [configuration](./configuration.md) for more information on the new format.

An old configuration file can be migrated using the `migrate_config` command:

```bash
zabbix-cli migrate_config
```

The command uses the currently loaded configuration file to generate a new TOML configuration file. The new file is saved in the default TOML configuration file location.

Custom source and destination files can be specified with the `--source` and `--destination` options, respectively:

```bash
zabbix-cli migrate_config --source /path/to/old/config.conf --destination /path/to/new/config.toml
```

### New default configuration file location

The location of the configuration file is now determined by [platformdirs](https://pypi.org/project/platformdirs/). See [Configuration](./configuration.md) for a brief summary of the new default location.

To open the default configuration file directory, use the command:

```bash
zabbix-cli open config
```

### New configuration options

New configuration options have been introduced to the configuration file:

| Option | Description | Default |
| --- | --- | --- |
| `app.default_format` | Default output format in the CLI | `table` |
| `app.legacy_json_format` | Enable [legacy json format](#json-output-format) | `false` |

### Renamed configuration options

Several configuration options have been renamed to better reflect their purpose.

The following table lists the old config section names and their new counterparts:

| Old Config Section | New Config Section |
| --- | --- |
| `zabbix_api` | `api` |
| `zabbix_config` | `app` |

The following table lists the old option names and their new counterparts:

| Old Config Section | Old Option Name | New Config Section | New Option Name |
| --- | --- | --- | --- |
| `zabbix_config` | `zabbix_api_url` | `api` | `url` |
| `zabbix_config` | `cert_verify` | `api` | `verify_ssl` |
| `zabbix_config` | `system_id` | `api` | `username` |
| `zabbix_config` | `default_directory_exports` | `app` | `export_directory` |
| `zabbix_config` | `default_export_format` | `app` | `export_format` |
| `zabbix_config` | `include_timestamp_export_filename` | `app` | `export_timestamps` |
| `logging` | `logging` | `logging` | `enabled` |

For backwards compatibility, all the old option names are still supported, but will be removed in a future version.

See [Sample configuration file](./configuration.md#sample-configuration-file) to see an example of the new configuration file format.

## Exports

### New export formats

Zabbix CLI 3.0 introduces two new export formats: `yaml` and `php`. The availability of these formats depends on the Zabbix version you are using.

Furthermore, the formats are no longer case-sensitive. For example, `YAML` and `yaml` are now equivalent.

### New default export filenames*

Exported files are no longer prefixed with `zabbix_export_`. This behavior can be re-enabled with the `--legacy-filenames` option.

Exported files no longer include a timestamp in the filename by default. Newer exports overwrite older ones automatically. Timestamps can be re-anbled by setting the `app.export_timestamps` option in the configuration file.

## Commands

### Command invocation syntax

In Zabbix CLI 2.x, invoking single commands without entering the REPL required the `-C` option followed by the command and its arguments as a single string:

```bash
zabbix-cli -C 'show_hostgroup "Linux servers"'
```

In Zabbix CLI 3.0, the `-C` option is no longer required. Commands can be invoked directly:

```bash
zabbix-cli show_hostgroup "Linux servers"
```

### Command syntax

In Zabbix CLI 3.0, the majority of positional arguments are replaced with named options. Each command required a specific number of positional arguments that _had_ to be specified. For example, the `export_configuration` command in Zabbix CLI 2.x required the following syntax, even when we wanted to export all hosts:

```bash
zabbix-cli -C 'export_configuration /tmp/zabbix_export.conf hosts #all#'
```

In Zabbix CLI 3.0, the same command would look like this:

```bash
zabbix-cli export_configuration --directory /tmp/exports --type hosts
```

We don't have to pass in a special name argument to indicate that we want to export all hosts. Instead, we can simply omit the `--name` option.

## Output

### JSON output format

In Zabbix CLI 2.x, the output format of commands generally took the form of a JSON mapping with numeric string keys for each result. For example:

```json
{
  "0": {
    "hostid": "10609",
    "host": "foo.example.com",
    "groups": [],
    // ...
  }
}
```

In the new default JSON format introduced in Zabbix CLI 3.0, the output is always a JSON mapping with the keys `message`, `errors`, `return_code` and `result`. For example:

```json
{
  "message": "",
  "errors": [],
  "return_code": "Done",
  "result": {
    "hostid": "10609",
    "host": "foo.example.com",
    "groups": [],
    // ...
  }
}
```

Which means when a command fails to execute or returns an error, the shape of the JSON output will be consistent with the successful output, making it significantly easier to parse:

```json
{
  "message": "Host 'foobar.example.com' not found. Check your search pattern and filters.",
  "errors": [
    "Host 'foobar.example.com' not found. Check your search pattern and filters."
  ],
  "return_code": "Error",
  "result": null
}
```

In case of a chain of errors, the application makes an attempt to populate the `errors` array with all the errors encountered during the execution of the command.
