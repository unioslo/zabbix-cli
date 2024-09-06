# Usage

## Interactive mode

Invoking `zabbix-cli` without any arguments will start the application in an interactive shell. This is the default mode of operation, and is the most user-friendly way to use the application.

```bash
zabbix-cli
```

Within the interactive shell, commands can be entered and executed. Command and argument hints, tab autocompletion and history are supported out of the box.

```
% zabbix-cli
╭────────────────────────────────────────────────────────────╮
│ Welcome to the Zabbix command-line interface (v3.0.0)      │
│ Connected to server http://localhost:8082 (v7.0.0)         │
╰────────────────────────────────────────────────────────────╯
Type --help to list commands, :h for REPL help, :q to exit.
>
```

## Single command mode

Commands can also be invoked directly from the command line. This is useful for scripting and automation, as well for just running one-off commands.

```bash
zabbix-cli show_hostgroup "Linux servers"
```

## Bulk mode

Zabbix CLI also supports running commands sourced from a file with the `--file` option. This is useful for running a series of commands in bulk.

The file should contain one command per line, with arguments separated by spaces. Comments can be added with `#`.

```
$ cat /path/to/commands.txt
# This is a comment
show_hostgroup "Linux servers"
create_host --host "foo.example.com" --hostgroup "Linux servers,Applications" --proxy .+ --status on --no-default-hostgroup --description "Added in bulk mode"
create_hostgroup "My new group"
add_host_to_hostgroup foo.example.com "My new group"
```

```
$ zabbix-cli --file /path/to/commands.txt
╭────┬───────────────┬───────┬───────╮
│ ID │ Name          │ Flag  │ Hosts │
├────┼───────────────┼───────┼───────┤
│ 2  │ Linux servers │ Plain │       │
╰────┴───────────────┴───────┴───────╯
✓ Created host 'foobarbaz.example.com' (10634)
✓ Created host group My new group (31).
╭──────────────┬───────────────────────╮
│ Hostgroup    │ Hosts                 │
├──────────────┼───────────────────────┤
│ My new group │ foobarbaz.example.com │
╰──────────────┴───────────────────────╯
✓ Added 1 host to 1 host group.
```
