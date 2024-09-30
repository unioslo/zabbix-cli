# Configuration

The application is configured with a TOML file. The default location is platform-dependent.

{% include ".includes/config-locations.md" %}

## Create a configuration file

Before using the application, a configuration file must be created. This can be done with the `zabbix-cli-init` command:

```
zabbix-cli-init
```

The application will print the location of the created config file:

```
! Configuration file created: /Users/pederhan/Library/Application Support/zabbix-cli/zabbix-cli.toml
```

To bootstrap the config with a URL and username, use the options `--url` and `--user`:

```
zabbix-cli-init --url https://zabbix.example.com --user Admin
```

## Open configuration directory

The default configuration directory can be opened in the system's file manager with the `open` command:

```bash
zabbix-cli open config
```

To print the path instead of opening it, use the `--path` option:

```bash
zabbix-cli open config --path
```

## Show configuration file contents

The contents of the current configuration file can be displayed with `show_config`:

```bash
zabbix-cli show_config
```

### Create a sample config

A sample configuration file can be printed to the terminal with the `sample_config` command. This can be redirected to a file to create a configuration file in an arbitrary location:

```
zabbix-cli sample_config > /path/to/config.toml
```

A more convoluted way of creating a default config file in the default location would be:

```
zabbix-cli sample_config > "$(zabbix-cli open --path config)/zabbix-cli.toml"
```

## Sample configuration file

```toml
{% include "data/sample_config.toml" %}
```

## Configuration options

<!-- TODO: Automatically generate this from pydantic models using field name, aliases and field help.

           To do this, we need to add Field() for every field in the model, and also ensure they have help= set. Possibly also add examples.
 -->

Required fields are marked with a `*`.

----

### `api`

The `api` section contains the configuration for the Zabbix API.

----

#### `url` \*

URL of the Zabbix API host. Should not include the `/api_jsonrpc.php` path.

Type: `str`

----

#### `username`

Username for the Zabbix API.

Type: `str`

Default: `Admin`

----

#### `verify_ssl`

Whether to verify SSL certificates.

Type: `bool`

Default: `true`

----

### `app`

The `app` section contains the configuration for the application, such as default values for certain commands, output and exports.

----

#### `default_hostgroups`

Default host groups to assign to hosts created with `create_host`. Hosts are always added to these groups unless `--no-default-hostgroup` is provided.

Type: `List[str]`

Default: `["All-hosts"]`

----

#### `default_admin_usergroups`

Default user groups to give read/write permissions to groups created with `create_hostgroup` and `create_templategroup` when `--rw-groups` option is not provided.

Type: `List[str]`

Default: `[]`

----

#### `default_create_user_usergroups`

Default user groups to add users created with `create_user` to when `--usergroups` is not provided.

Type: `List[str]`

Default: `[]`

----

#### `default_notification_users_usergroups`

Default user groups to add notification users created with `create_notification_user` to when `--usergroups` is not provided.

Type: `List[str]`

Default: `["All-notification-users"]`

----

#### `export_directory`

Directory for exports.

Type: `str`

Default: `"<DATA_DIR>/zabbix-cli/exports"`

----

#### `export_format`

Format for exports.

Type: `str`

Default: `"json"`

----

#### `export_timestamps`

Whether to include timestamps in export filenames.

Type: `bool`

Default: `false`

----

#### `use_colors`

Whether to use colors in the output.

Type: `bool`

Default: `true`

----

#### `use_auth_token_file`

Whether to use an auth token file.

Type: `bool`

Default: `true`

----

#### `use_paging`

Whether to use paging in the output.

Type: `bool`

Default: `false`

----

#### `output_format`

Format for the output.

Type: `str`

Default: `"table"`

----

#### `history`

Whether to keep a history of commands.

Type: `bool`

Default: `true`

----

#### `history_file`

File for storing the history of commands.

Type: `str`

Default: `"<DATA_DIR>/zabbix-cli/history"`

----

#### `allow_insecure_auth_file`

Whether to allow insecure auth files.

Type: `bool`

Default: `true`

----

#### `legacy_json_format`

Whether to use the legacy JSON format (pre-Zabbix CLI 3.0), where the output is a JSON mapping with numeric string keys for each result. See the [migration guide](./migration.md) for more information.

Type: `bool`

Default: `false`

### `logging`

The `logging` section contains the configuration for logging.

----

#### `enabled`

Whether logging is enabled.

Type: `bool`

Default: `true`

----

#### `log_level`

Level for logging.

Type: `str`

Default: `"ERROR"`

----

#### `log_file`

File for storing logs.

Type: `str`

Default: `"<LOG_DIR>/zabbix-cli.log"`
