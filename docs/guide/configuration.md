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

A more convoluted way of creating a default config file in the default location would be:

```
zabbix-cli sample_config > "$(zabbix-cli open --path config)/zabbix-cli.toml"
```

The created config looks like this:

```toml
{% include "data/sample_config.toml" %}
```

## Options

<!-- TODO: Automatically generate this from pydantic models using field name, aliases and field descriptions.

To do this, we need to add Field() for every field in the model, and also ensure they have description= set. Possibly also add examples.
 -->

=== "`api`"

    The `api` section configures the application's Zabbix API connection.

    ```toml
    [api]
    url = "https://zabbix.example.com"
    username = "Admin"
    password = ""
    auth_token = ""
    verify_ssl = true
    ```

    #### `url`

    URL of the Zabbix API host. Should not include the `/api_jsonrpc.php` path.

    Type: `str`

    ```toml
    [api]
    url = "https://zabbix.example.com"
    ```

    ----

    #### `username`

    Username for Zabbix API authentication. Can be used  in combination with `password`, or to provide a default username for the login prompt.

    Type: `str`

    Default: `Admin`

    ```toml
    [api]
    username = "Admin"
    ```

    ----

    #### `password`

    Password to use in combination with a username.

    Type: `str`

    ```toml
    [api]
    password = "password123"
    ```


    ----

    #### `auth_token`

    Session token or API token to use for authentication. Takes precedence over `username` and `password` if set.

    Type: `str`

    ```toml
    [api]
    auth_token = "API_TOKEN_123"
    ```

    ----

    #### `verify_ssl`

    Whether to verify SSL certificates.

    Type: `bool`

    Default: `true`

    ```toml
    [api]
    verify_ssl = true
    ```

=== "`app`"

    The `app` section configures general application settings, such as defaults for Zabbix host and group creation, export configuration, and more.


    ```toml
    [app]
    default_hostgroups = [
        "All-hosts",
    ]
    default_admin_usergroups = []
    default_create_user_usergroups = []
    default_notification_users_usergroups = [
        "All-notification-users",
    ]
    export_directory = "/path/to/exports"
    export_format = "json"
    export_timestamps = true
    use_auth_token_file = true
    auth_token_file = "/path/to/auth_token_file"
    auth_file = "/path/to/auth_token_file"
    history = true
    history_file = "/path/to/history_file.history"
    bulk_mode = "strict"
    allow_insecure_auth_file = true
    legacy_json_format = false
    ```

    ----

    #### `default_hostgroups`

    Default host groups to assign to hosts created with `create_host`. Hosts are always added to these groups unless `--no-default-hostgroup` is provided.

    Type: `List[str]`

    Default: `["All-hosts"]`


    ```toml
    [app]
    default_hostgroups = ["All-hosts"]
    ```

    ----

    #### `default_admin_usergroups`

    Default user groups to give read/write permissions to groups created with `create_hostgroup` and `create_templategroup` when `--rw-groups` option is not provided.

    Type: `List[str]`

    Default: `[]`

    ```toml
    [app]
    default_admin_usergroups = ["All-admins"]
    ```

    ----

    #### `default_create_user_usergroups`

    Default user groups to add users created with `create_user` to when `--usergroups` is not provided.

    Type: `List[str]`

    Default: `[]`


    ```toml
    [app]
    default_create_user_usergroups = ["All-users"]
    ```

    ----

    #### `default_notification_users_usergroups`

    Default user groups to add notification users created with `create_notification_user` to when `--usergroups` is not provided.

    Type: `List[str]`

    Default: `["All-notification-users"]`

    ```toml
    [app]
    default_create_user_usergroups = ["All-notification-users"]
    ```

    ----

    #### `export_directory`

    Directory for exports.

    Type: `str`

    Default: `"<DATA_DIR>/zabbix-cli/exports"`

    ```toml
    [app]
    default_create_user_usergroups = "/path/to/exports"
    ```


    ----

    #### `export_format`

    Format for exports.

    Type: `str`

    Default: `"json"`

    ```toml
    [app]
    export_format = "json"
    ```


    ----

    #### `export_timestamps`

    Whether to include timestamps in export filenames.

    Type: `bool`

    Default: `false`

    ```toml
    [app]
    export_timestamps = false
    ```

    ----

    #### `use_auth_token_file`

    Whether to use an auth token file to save session token once authenticated. Allows for reusing the token in subsequent sessions.

    Type: `bool`

    Default: `true`

    ```toml
    [app]
    use_auth_token_file = true
    ```

    ----

    #### `auth_token_file`

    Paht to the auth token file.

    Type: `str`

    Default: `"<DATA_DIR>/zabbix-cli/.zabbix-cli_auth_token"`

    ```toml
    [app]
    auth_token_file = "/path/to/auth_token_file"
    ```

    ----

    #### `auth_file`

    Paht to a file containing username and password in the format `username:password`. Alternative to specifying `username` and `password` in the configuration file.

    Type: `str`

    Default: `"<DATA_DIR>/zabbix-cli/.zabbix-cli_auth"`

    ```toml
    [app]
    auth_token = "/path/to/auth_file"
    ```

    ----

    #### `history`

    Whether to keep a history of commands.

    Type: `bool`

    Default: `true`

    ```toml
    [app]
    history = true
    ```

    ----

    #### `history_file`

    File for storing the history of commands.

    Type: `str`

    Default: `"<DATA_DIR>/zabbix-cli/history"`


    ```toml
    [app]
    history_file = "/path/to/history_file.history"
    ```

    ----

    #### `bulk_mode`

    Strictness of error handling in bulk operations. If `strict`, the operation will stop at the first error. If `continue`, the operation will continue after errors and report them afterwards. If `skip`, the operation will skip invalid lines in bulk file, as well as ignore all errors when executing the operation.

    Type: `str`

    Choices: `"strict"`, `"continue"`, `"skip"`

    Default: `"strict"`

    ```toml
    [app]
    bulk_mode = "strict"
    ```

    ----

    #### `allow_insecure_auth_file`

    Whether to allow insecure auth files.

    Type: `bool`

    Default: `true`

    ```toml
    [app]
    allow_insecure_auth_file = false
    ```

    ----

    #### `legacy_json_format`

    Whether to use the legacy JSON format (pre-Zabbix CLI 3.0), where the output is a JSON mapping with numeric string keys for each result. See the [migration guide](./migration.md) for more information.

    Type: `bool`

    Default: `false`

    ```toml
    [app]
    legacy_json_format = false
    ```

=== "`app.output`"

    The `app.output` section configures the output format of the application.

    ```toml
    [app.output]
    format = "table"
    color = true
    paging = false
    theme = "default"
    ```

    ----

    #### `format`

    Format of the application output.

    Type: `str`

    Default: `"table"`

    Choices: `"table"`, `"json"`

    ```toml
    [app.output]
    format = "table"
    ```

    ----

    #### `color`

    Whether to use color in the terminal output.

    Type: `bool`

    Default: `true`

    ```toml
    [app.output]
    color = true
    ```

    ----

    #### `paging`

    Whether to use paging in the output.

    Type: `bool`

    Default: `false`

    ```toml
    [app.output]
    paging = false
    ```

=== "`logging`"

    The `logging` section configures logging.


    ```toml
    [logging]
    enabled = true
    log_level = "INFO"
    log_file = "/path/to/zabbix-cli.log"
    ```

    ----

    #### `enabled`

    Whether logging is enabled.

    Type: `bool`

    Default: `true`

    ```toml
    [logging]
    enabled = true
    ```

    ----

    #### `log_level`

    Level for logging.

    Type: `str`

    Default: `"ERROR"`

    Choices: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`

    ```toml
    [logging]
    log_level = "ERROR"
    ```

    ----

    #### `log_file`

    File for storing logs. Can be omitted to log to stderr (**warning:** NOISY).

    Type: `Optional[str]`

    Default: `"<LOG_DIR>/zabbix-cli.log"`

    ```toml
    [logging]
    log_file = "/path/to/zabbix-cli.log"
    ```
