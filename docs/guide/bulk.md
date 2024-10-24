# Bulk Operations

Zabbix-CLI supports performing bulk operations with the `--file` option:

```bash
zabbix-cli --file /path/to/commands.txt
```

The `--file` option takes in a file containing commands to run in bulk. Each line in the file should be a separate command. Comments are added by prepending a `#` to the line.

```bash
# /path/to/commands.txt
# This is a comment
show_hostgroup "Linux servers"
create_host foobarbaz.example.com --hostgroup "Linux servers,Applications" --proxy .+ --status on --no-default-hostgroup --description "Added in bulk mode"
show_host foobarbaz.example.com
create_hostgroup "My new group"
add_host_to_hostgroup foobarbaz.example.com "My new group"
remove_host_from_hostgroup foobarbaz.example.com "My new group"
remove_hostgroup "My new group"
remove_host foobarbaz.example.com
```

*Example of a bulk operation file that adds a host and a host group, then removes them.*

## Errors

By default, all errors are fatal. If a command fails, the bulk operation is aborted. This behavior can be changed with the `app.bulk_mode` setting in the configuration file:

```toml
[app]
bulk_mode = "strict" # strict|continue|skip
```

- `strict`: The operation will stop at the first encountered error.
- `continue`: The operation will continue on errors and report them afterwards.
- `skip`: Same as continue, but invalid lines in the bulk file are also skipped. Errors are completely ignored.
