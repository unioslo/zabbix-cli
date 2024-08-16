# Run the config module with python -m zabbix_cli.config
from __future__ import annotations

if __name__ == "__main__":
    import typer

    from zabbix_cli.config.run import main

    typer.run(main)
