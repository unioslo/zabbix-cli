from __future__ import annotations

from typing import TYPE_CHECKING
from typing import List
from typing import Optional
from typing import Union

import typer

from zabbix_cli.app import Example
from zabbix_cli.app import app
from zabbix_cli.commands.template import HELP_PANEL  # combine with template commands
from zabbix_cli.output.console import error
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.console import success
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.enums import UsergroupPermission
from zabbix_cli.utils.args import parse_list_arg

if TYPE_CHECKING:
    from zabbix_cli.pyzabbix.types import HostGroup
    from zabbix_cli.pyzabbix.types import TemplateGroup


@app.command(
    "create_templategroup",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Create a template group with default user group permissions",
            "create_templategroup 'My Template Group'",
        ),
        Example(
            "Create a template group with specific RO and RW groups",
            "create_templategroup 'My Template Group' --ro-groups users --rw-groups admins",
        ),
        Example(
            "Create a template group with no user group permissions",
            "create_templategroup 'My Template Group' --no-usergroup-permissions",
        ),
    ],
)
def create_templategroup(
    ctx: typer.Context,
    templategroup: str = typer.Argument(
        help="Name of the group.",
        show_default=False,
    ),
    rw_groups: Optional[str] = typer.Option(
        None,
        help="User group(s) to give read/write permissions. Comma-separated.",
    ),
    ro_groups: Optional[str] = typer.Option(
        None,
        help="User group(s) to give read-only permissions. Comma-separated.",
    ),
    no_usergroup_permissions: bool = typer.Option(
        False,
        "--no-usergroup-permissions",
        help="Do not assign user group permissions.",
    ),
) -> None:
    """Create a new template group.

    Assigns permissions for user groups defined in configuration file if no user groups are specified.

    --rw-groups uses the default admin user groups if not specified.
    --ro-groups uses the default create user groups if not specified.

    Use --no-usergroup-permissions to create a group without assigning user group permissions.

    NOTE: Calls [command]create_hostgroup[/] for Zabbix versions < 6.2.0.
    """
    from zabbix_cli.models import Result

    if app.state.client.version.release < (6, 2, 0):
        from zabbix_cli.commands.hostgroup import create_hostgroup

        create_hostgroup(
            hostgroup=templategroup,
            rw_groups=rw_groups,
            ro_groups=ro_groups,
            no_usergroup_permissions=no_usergroup_permissions,
        )
        return

    groupid = app.state.client.create_templategroup(templategroup)

    app_config = app.state.config.app

    rw_grps: List[str] = []
    ro_grps: List[str] = []
    if not no_usergroup_permissions:
        rw_grps = parse_list_arg(rw_groups) or app_config.default_admin_usergroups
        ro_grps = parse_list_arg(ro_groups) or app_config.default_create_user_usergroups

    try:
        # Admin group(s) gets Read/Write
        for usergroup in rw_grps:
            app.state.client.update_usergroup_rights(
                usergroup,
                [templategroup],
                UsergroupPermission.READ_WRITE,
                hostgroup=False,
            )
            info(f"Assigned Read/Write permission for user group {usergroup!r}")
        # Default group(s) gets Read
        for usergroup in ro_grps:
            app.state.client.update_usergroup_rights(
                usergroup,
                [templategroup],
                UsergroupPermission.READ_ONLY,
                hostgroup=False,
            )
            info(f"Assigned Read-only permission for user group {usergroup!r}")

    except Exception as e:
        error(f"Failed to assign permissions to template group {templategroup!r}: {e}")
        info("Deleting template group...")
        app.state.client.delete_templategroup(groupid)
        exit_err(f"Failed to create template group {templategroup!r}.")

    render_result(
        Result(message=f"Created template group {templategroup} ({groupid}).")
    )


@app.command("remove_templategroup", rich_help_panel=HELP_PANEL)
def remove_templategroup(
    ctx: typer.Context,
    templategroup: str = typer.Argument(
        help="Name of the group to delete.",
        show_default=False,
    ),
) -> None:
    """Delete a template group.

    NOTE: Calls [command]remove_hostgroup[/] for Zabbix <6.2.
    """
    from zabbix_cli.models import Result

    if app.state.client.version.release < (6, 2, 0):
        from zabbix_cli.commands.hostgroup import delete_hostgroup

        delete_hostgroup(hostgroup=templategroup)
        return

    app.state.client.delete_templategroup(templategroup)
    render_result(Result(message=f"Deleted template group {templategroup!r}."))


@app.command("show_templategroup", rich_help_panel=HELP_PANEL)
def show_templategroup(
    ctx: typer.Context,
    templategroup: str = typer.Argument(
        help="Name of the group to show. Supports wildcards.",
        show_default=False,
    ),
    templates: bool = typer.Option(
        True,
        "--templates/--no-templates",
        help="Show/hide templates associated with the group.",
    ),
) -> None:
    """Show details for a template group."""
    from zabbix_cli.commands.results.templategroup import ShowTemplateGroupResult

    tg: HostGroup | TemplateGroup
    if app.state.client.version.release < (6, 2, 0):
        tg = app.state.client.get_hostgroup(
            templategroup, search=True, select_templates=templates
        )
    else:
        tg = app.state.client.get_templategroup(
            templategroup, search=True, select_templates=templates
        )
    render_result(ShowTemplateGroupResult.from_result(tg, show_templates=templates))


@app.command(
    "show_templategroups",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Show all template groups",
            "show_templategroups",
        ),
        Example(
            "Show all template groups starting with 'Web-'",
            "show_templategroups 'Web-*'",
        ),
        Example(
            "Show template groups with 'web' in the name",
            "show_templategroups '*web*'",
        ),
    ],
)
def show_templategroups(
    ctx: typer.Context,
    name: Optional[str] = typer.Argument(
        None,
        help="Name of template group(s). Comma-separated. Supports wildcards.",
        show_default=False,
    ),
    templates: bool = typer.Option(
        True,
        "--templates/--no-templates",
        help="Show/hide templates associated with each group.",
    ),
) -> None:
    """Show template groups.

    Fetches all groups by default, but can be filtered by name.
    """
    from zabbix_cli.commands.results.templategroup import ShowTemplateGroupResult
    from zabbix_cli.models import AggregateResult

    names = parse_list_arg(name)

    groups: Union[List[HostGroup], List[TemplateGroup]]
    with app.status("Fetching template groups..."):
        if app.state.client.version.release < (6, 2, 0):
            groups = app.state.client.get_hostgroups(
                *names,
                search=True,
                select_templates=True,
                sort_field="name",
                sort_order="ASC",
            )
        else:
            groups = app.state.client.get_templategroups(
                *names,
                search=True,
                select_templates=True,
                sort_field="name",
                sort_order="ASC",
            )

    # Sort by name before rendering
    groups = sorted(groups, key=lambda tg: tg.name)  # type: ignore # unable to infer that type doesn't change?

    render_result(
        AggregateResult(
            result=[ShowTemplateGroupResult.from_result(tg, templates) for tg in groups]
        )
    )


@app.command("extend_templategroup", rich_help_panel=HELP_PANEL)
def extend_templategroup(
    ctx: typer.Context,
    src_group: str = typer.Argument(
        help="Group to get templates from.",
        show_default=False,
    ),
    dest_group: str = typer.Argument(
        help="Group(s) to add templates to. Comma-separated. Supports wildcards.",
        show_default=False,
    ),
    dryrun: bool = typer.Option(
        False,
        "--dryrun",
        help="Show groups and templates without copying.",
    ),
) -> None:
    """Add all templates from a group to other groups.

    Interprets the source group as a template group in >= 6.2, otherwise as a host group.

    Does not modify the source group or its templates.
    To remove the templates from the source group, use the [command]move_templates[/] command instead.
    """
    from zabbix_cli.commands.results.templategroup import ExtendTemplateGroupResult

    dest_arg = parse_list_arg(dest_group)

    src: Union[HostGroup, TemplateGroup]
    dest: Union[List[HostGroup], List[TemplateGroup]]
    if app.state.client.version.release > (6, 2, 0):
        src = app.state.client.get_templategroup(src_group, select_templates=True)
        dest = app.state.client.get_templategroups(
            *dest_arg, select_templates=True, search=True
        )
    else:
        src = app.state.client.get_hostgroup(src_group, select_templates=True)
        dest = app.state.client.get_hostgroups(
            *dest_arg, select_templates=True, search=True
        )

    if not src.templates:
        exit_err(f"No templates found in {src_group!r}")
    if not dest:
        exit_err(f"No groups found matching {dest_group!r}")

    if not dryrun:
        app.state.client.add_templates_to_groups(src.templates, dest)
    else:
        info("Would copy the following templates:")
    render_result(ExtendTemplateGroupResult.from_result(src, dest, src.templates))
    if not dryrun:
        success(
            f"Copied {len(src.templates)} templates from {src.name} to {len(dest)} groups."
        )


@app.command("move_templates", rich_help_panel=HELP_PANEL)
def move_templates(
    src_group: str = typer.Argument(
        help="Group to move templates from.",
        show_default=False,
    ),
    dest_group: str = typer.Argument(
        help="Group to move templates to.",
        show_default=False,
    ),
    rollback: bool = typer.Option(
        True,
        "--rollback/--no-rollback",
        help="Rollback changes if templates cannot be removed from source group afterwards.",
    ),
    dryrun: bool = typer.Option(
        False,
        "--dryrun",
        help="Show templates and groups without making changes.",
    ),
) -> None:
    """Move all templates from one group to another."""
    from zabbix_cli.commands.results.templategroup import MoveTemplatesResult

    src: Union[HostGroup, TemplateGroup]
    dest: Union[HostGroup, TemplateGroup]

    if app.state.client.version.release < (6, 2, 0):
        src = app.state.client.get_hostgroup(src_group, select_templates=True)
        dest = app.state.client.get_hostgroup(dest_group, select_templates=True)
    else:
        src = app.state.client.get_templategroup(src_group, select_templates=True)
        dest = app.state.client.get_templategroup(dest_group, select_templates=True)

    if not src.templates:
        exit_err(f"No templates found in template group {src_group!r}.")

    if dryrun:
        info(f"Would copy {len(src.templates)} templates from {src.name!r}:")
    else:
        app.state.client.add_templates_to_groups(
            src.templates,
            # Clunky typing semantics here:
            # We cannot prove that list is homogenous ("list[HostGroup] | list[TemplateGroup]")
            # because inferred type is "list[HostGroup | TemplateGroup]""
            [dest],  # pyright: ignore[reportArgumentType]
        )
        info(f"Added templates to {dest.name!r}.")
        try:
            app.state.client.remove_templates_from_groups(
                src.templates,
                [src],  # pyright: ignore[reportArgumentType] # ditto
            )
        except Exception as e:
            if rollback:
                error(
                    f"Failed to remove hosts from {src.name!r}. Attempting to roll back changes."
                )
                app.state.client.remove_templates_from_groups(
                    src.templates,
                    [dest],  # pyright: ignore[reportArgumentType] # ditto
                )
            raise e
        else:
            info(f"Removed templates from {src.name!r}.")

    render_result(MoveTemplatesResult.from_result(src, dest))
    if not dryrun:
        success(
            f"Moved {len(src.templates)} templates from {src.name!r} to {dest.name!r}."
        )
