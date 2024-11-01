# Logging

The application supports logging to a file or directly to the terminal. By default, file logging is enabled and set to the `ERROR` level.

## Enable/disable logging

Logging is enabled by default. To disable logging, set the `enabled` option to `false` in the configuration file:

```toml
[logging]
enabled = true
```

## Levels

The application only logs messages with a level equal to or higher than the configured level. By default, the level is set to `ERROR`. The available levels are:

- `DEBUG`
- `INFO`
- `WARNING`
- `ERROR`
- `CRITICAL`

The level can be set in the configuration file:

```toml
[logging]
level = "DEBUG"
```

## Log file

The default location of the log file is a file named `zabbix-cli.log` in the application's logs directory.

The log file location can be changed in the configuration file:

```toml
[logging]
log_file = "/path/to/zabbix-cli.log"
```

The default logs directory can be opened with the command:

```bash
zabbix-cli open logs
```

## Log to terminal

!!! warning "Verbose output"
    Logging to the terminal can produce a lot of output, especially when the log level is set to `DEBUG`. Furthermore, some of the output messages may be shown twice, as they are printed once by the application and once by the logging library.

If the `log_file` option is set to an empty string or an invalid file path, the application will log to the terminal instead of a file.

```toml
[logging]
log_file = ""
```
