from __future__ import annotations

from ._app import app


@app.command("add_host_to_hostgroup")
def add_host_to_hostgroup() -> None:
    pass


@app.command("create_hostgroup")
def create_hostgroup() -> None:
    pass


@app.command("remove_host_from_hostgroup")
def remove_host_from_hostgroup() -> None:
    pass


@app.command("show_hostgroup")
def show_hostgroup() -> None:
    pass


@app.command("show_hostgroup_permissions")
def show_hostgroup_permissions() -> None:
    pass


@app.command("show_hostgroups")
def show_hostgroups() -> None:
    pass
