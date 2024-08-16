pipx supports installing multiple versions of the same package by giving each installation a custom suffix. For example, if we have an existing installation of Zabbix CLI, and we wish to install a newer version of Zabbix CLI without shadowing or overwriting the existing installation, we can do so:

```bash
pipx install zabbix-cli>=3.0.0 --suffix @v3
```

This installs Zabbix CLI >= 3.0.0 with the suffix `@v3`, and we can run it with:

```bash
zabbix-cli@v3
```

and the existing installation can be run as usual:

```bash
zabbix-cli
```
