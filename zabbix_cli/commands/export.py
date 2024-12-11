from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import NamedTuple
from typing import Optional
from typing import Protocol

import typer
from strenum import StrEnum

from zabbix_cli._v2_compat import ARGS_POSITIONAL
from zabbix_cli.app import Example
from zabbix_cli.app import app
from zabbix_cli.config.constants import OutputFormat
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.logs import logger
from zabbix_cli.output.console import console
from zabbix_cli.output.console import err_console
from zabbix_cli.output.console import error
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.console import success
from zabbix_cli.output.console import warning
from zabbix_cli.output.formatting.path import path_link
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.enums import ExportFormat
from zabbix_cli.utils.args import parse_bool_arg
from zabbix_cli.utils.args import parse_list_arg
from zabbix_cli.utils.args import parse_path_arg
from zabbix_cli.utils.fs import open_directory
from zabbix_cli.utils.fs import sanitize_filename
from zabbix_cli.utils.utils import convert_seconds_to_duration

if TYPE_CHECKING:
    from typing_extensions import TypedDict
    from typing_extensions import Unpack

    from zabbix_cli.config.model import Config
    from zabbix_cli.pyzabbix.client import ZabbixAPI
    from zabbix_cli.pyzabbix.types import Host
    from zabbix_cli.pyzabbix.types import HostGroup
    from zabbix_cli.pyzabbix.types import Image
    from zabbix_cli.pyzabbix.types import Map
    from zabbix_cli.pyzabbix.types import MediaType
    from zabbix_cli.pyzabbix.types import Template
    from zabbix_cli.pyzabbix.types import TemplateGroup

    class ExportKwargs(TypedDict, total=False):
        hosts: list[Host]
        host_groups: list[HostGroup]
        images: list[Image]
        maps: list[Map]
        media_types: list[MediaType]
        templates: list[Template]
        template_groups: list[TemplateGroup]


HELP_PANEL = "Import/Export"


class ExportType(StrEnum):
    HOST_GROUPS = "host_groups"  # >=6.2
    TEMPLATE_GROUPS = "template_groups"  # >=6.2
    HOSTS = "hosts"
    IMAGES = "images"
    MAPS = "maps"
    TEMPLATES = "templates"
    MEDIA_TYPES = "mediaTypes"  # >= 6.0 (but should work on 5.0 too)

    @classmethod
    def _missing_(cls, value: Any) -> ExportType:
        if str(value.lower()) == "groups":
            return cls.HOST_GROUPS
        raise ValueError(f"Invalid export type: {value}")

    def human_readable(self) -> str:
        if self.value == "mediaTypes":
            return "media types"
        return self.value.replace("_", " ").lower()


class ExporterFunc(Protocol):
    def __call__(self) -> Iterator[Optional[Path]]: ...


class Exporter(NamedTuple):
    func: ExporterFunc
    type: ExportType


class ZabbixExporter:
    """Export Zabbix configuration for one or more components."""

    def __init__(
        self,
        client: ZabbixAPI,
        config: Config,
        types: list[ExportType],
        names: list[str],
        directory: Path,
        format: ExportFormat,
        legacy_filenames: bool,
        pretty: bool,
        ignore_errors: bool,
    ) -> None:
        self.client = client
        self.config = config
        self.export_types = types
        self.names = names
        self.directory = directory
        self.format = format
        self.legacy_filenames = legacy_filenames
        self.pretty = pretty
        self.ignore_errors = ignore_errors

        # Ideally, we fetch and write at the same time, so we keep memory usage low,
        # while utilizing I/O and CPU as much as possible.
        # Will need to be rewritten to use threads to achieve this.

        # TODO: test that mapping contains all export types
        self.exporter_map: dict[ExportType, ExporterFunc] = {
            ExportType.HOST_GROUPS: self.export_host_groups,
            ExportType.TEMPLATE_GROUPS: self.export_template_groups,
            ExportType.HOSTS: self.export_hosts,
            ExportType.IMAGES: self.export_images,
            ExportType.MAPS: self.export_maps,
            ExportType.TEMPLATES: self.export_templates,
            ExportType.MEDIA_TYPES: self.export_media_types,
        }

        self.check_export_types()

    def run(self) -> list[Path]:
        """Run exporters."""
        files: list[Path] = []
        with err_console.status("") as status:
            for exporter in self.get_exporters():
                status.update(f"Exporting {exporter.type.human_readable()}...")
                for file in exporter.func():
                    if file:
                        files.append(file)
                success(f"Exported {exporter.type.human_readable()}")
        return files

    def check_export_types(self) -> None:
        """Check export types for compatibility."""
        # If we have no specific exports, export all object types
        for export_type in self.export_types:
            self._check_export_type_compat(export_type)

    def _check_export_type_compat(self, export_type: ExportType) -> None:
        if export_type == ExportType.TEMPLATE_GROUPS:
            if self.client.version.release < (6, 2, 0):
                raise ZabbixCLIError(
                    "Template group exports are not supported in Zabbix versions < 6.2."
                )

    def get_exporters(self) -> list[Exporter]:
        """Get a list of exporters to run."""
        exporters: list[Exporter] = []
        for export_type in self.export_types:
            exporter = self.exporter_map.get(export_type, None)
            if not exporter:  # should never happen - tests should catch this
                raise ZabbixCLIError(
                    f"No exporter available for export type: {export_type}"
                )
            exporters.append(Exporter(exporter, export_type))
        return exporters

    def get_filename(self, name: str, id: str, export_type: ExportType) -> Path:
        """Get path to export file given a ."""
        stem = self.get_filename_stem(name, id)
        directory = self.directory / export_type.value
        return directory / f"{stem}.{self.format.value}"

    def get_filename_stem(self, name: str, id: str) -> str:
        if self.legacy_filenames:
            fn = self._get_legacy_filename_stem(name, id)
        else:
            fn = self._get_filename_stem(name, id)
        if self.config.app.export_timestamps:
            ts = datetime.now().strftime("%Y-%m-%dT%H%M%S%Z")
            fn = f"{fn}_{ts}"
        return sanitize_filename(fn)

    def _get_legacy_filename_stem(self, name: str, id: str) -> str:
        """Format legacy filename."""
        return f"zabbix_export_{name}_{id}"

    def _get_filename_stem(self, name: str, id: str) -> str:
        """Format filename."""
        return f"{name}_{id}"

    # TODO: refactor export methods if we want to add --ignore-errors
    # We have to find a way to generalize the export process while keeping
    # type safety intact.
    # The challenge is that we need to continue if a single export fails,
    # so we can't just wrap the call of the export method in a try/except
    # Each method needs to guard the export call of each object in a try/except
    # and that will be extremely verbose and repetitive.
    def export_host_groups(self) -> Iterator[Optional[Path]]:
        hostgroups = self.client.get_hostgroups(*self.names, search=True)
        for hg in hostgroups:
            filename = self.get_filename(hg.name, hg.groupid, ExportType.HOST_GROUPS)
            yield self.do_run_export(filename, host_groups=[hg])

    def export_template_groups(self) -> Iterator[Optional[Path]]:
        template_groups = self.client.get_templategroups(*self.names, search=True)
        for tg in template_groups:
            filename = self.get_filename(
                tg.name, tg.groupid, ExportType.TEMPLATE_GROUPS
            )
            yield self.do_run_export(filename, template_groups=[tg])

    def export_hosts(self) -> Iterator[Optional[Path]]:
        hosts = self.client.get_hosts(*self.names)
        for host in hosts:
            filename = self.get_filename(host.host, host.hostid, ExportType.HOSTS)
            yield self.do_run_export(filename, hosts=[host])

    def export_images(self) -> Iterator[Optional[Path]]:
        images = self.client.get_images(*self.names, select_image=False)
        for image in images:
            filename = self.get_filename(image.name, image.imageid, ExportType.IMAGES)
            yield self.do_run_export(filename, images=[image])

    def export_maps(self) -> Iterator[Optional[Path]]:
        maps = self.client.get_maps(*self.names)
        for m in maps:
            filename = self.get_filename(m.name, m.sysmapid, ExportType.MAPS)
            yield self.do_run_export(filename, maps=[m])

    def export_media_types(self) -> Iterator[Optional[Path]]:
        media_types = self.client.get_media_types(*self.names)
        for mt in media_types:
            filename = self.get_filename(
                mt.name, mt.mediatypeid, ExportType.MEDIA_TYPES
            )
            yield self.do_run_export(filename, media_types=[mt])

    def export_templates(self) -> Iterator[Optional[Path]]:
        templates = self.client.get_templates(*self.names)
        for template in templates:
            filename = self.get_filename(
                template.host, template.templateid, ExportType.TEMPLATES
            )
            yield self.do_run_export(filename, templates=[template])

    def do_run_export(
        self, filename: Path, **kwargs: Unpack[ExportKwargs]
    ) -> Optional[Path]:
        """Runs the export process."""
        try:
            exported = self.client.export_configuration(
                pretty=self.pretty,
                format=self.format,
                **kwargs,
            )
            return self.write_exported(exported, filename)
        except Exception as e:
            # HACKY: since we do some ugly metaprogramming to generalize the export process,
            # we don't have the actual object on hand to print a useful representation of it.
            # If every object had a __pretty__ or similar, we could use `next(iter(kwargs.values()))`
            # then get the firsty entry of that list and call __pretty__ on it. But as it stands,
            # it's prettier to just print the expected filename than to leak the entire object repr
            msg = f"Failed to export {filename}: {e}"
            if self.ignore_errors:
                error(msg, exc_info=True)
                return None
            else:
                raise ZabbixCLIError(msg) from e

    def write_exported(self, exported: str, filename: Path) -> Path:
        """Writes an exported object to a file. Returns path to file."""
        # TODO: add some logging here to show progress
        # run some callback that updates a progress bar or something
        if not filename.parent.exists():
            try:
                filename.parent.mkdir(parents=True)
            except Exception as e:
                raise ZabbixCLIError(
                    f"Failed to create directory {filename.parent}: {e}. Ensure you have permissions to create directories in the export directory."
                ) from e
        with open(filename, "w", encoding="utf-8") as f:
            f.write(exported)
        return filename


def parse_export_types(value: list[str]) -> list[ExportType]:
    # If we have no specific exports, export all object types
    if not value:
        value = list(ExportType)
    elif "#all#" in value:
        warning("#all# is a deprecated value and will be removed in a future version.")
        value = list(ExportType)
    objs: list[ExportType] = []
    for obj in value:
        try:
            export_type = ExportType(obj)
            # self._check_export_type_compat(export_type)
            objs.append(export_type)
        except ZabbixCLIError as e:
            raise e  # should this be exit_err instead?
        except Exception as e:
            raise ZabbixCLIError(f"Invalid export type: {obj}") from e
    # dedupe
    # TODO: test that StrEnum is hashable on all Python versions
    return sorted(set(objs))


def parse_export_types_callback(
    ctx: typer.Context, param: typer.CallbackParam, value: list[str]
) -> list[ExportType]:
    """Parses list of object export type names.

    In V2, this was called "objects", which isn't very descriptive...
    """
    if ctx.resilient_parsing:
        return []  # pragma: no cover
    return parse_export_types(value)


@app.command(
    name="export_configuration",
    rich_help_panel=HELP_PANEL,
    examples=[
        Example(
            "Export everything",
            "export_configuration",
        ),
        Example(
            "Export all host groups",
            "export_configuration --type host_groups",
        ),
        Example(
            "Export all host groups containing 'Linux'",
            "export_configuration --type host_groups --name '*Linux*'",
        ),
        Example(
            "Export all template groups and templates containing 'Linux' or 'Windows'",
            "export_configuration --type template_groups --type templates --name '*Linux*,*Windows*'",
        ),
    ],
)
def export_configuration(
    ctx: typer.Context,
    directory: Optional[Path] = typer.Option(
        None,
        "--directory",
        help="Directory to export configuration to. Overrides directory in config.",
        writable=True,
        file_okay=False,
    ),
    # NOTE: We can't accept comma-separated values AND multiple values when using enums!
    # Typer performs its parsing before callbacks are run, sadly.
    types: list[ExportType] = typer.Option(
        [],
        "--type",
        help="Type(s) of objects to export. Can be specified multiple times. Defaults to all object types.",
        callback=parse_export_types_callback,
    ),
    names: Optional[str] = typer.Option(
        None, "--name", help="Name(s) of objects to export. Comma-separated list."
    ),
    format: Optional[ExportFormat] = typer.Option(
        None,
        "--format",
        help="Format to export to. Overrides export format in config.",
    ),
    # TODO: move/add this option to config
    legacy_filenames: bool = typer.Option(
        False,
        "--legacy-filenames",
        help="DEPRECATED: Use legacy filename scheme for exported objects.",
    ),
    pretty: bool = typer.Option(
        False,
        "--pretty",
        help="Pretty-print output. Not supported for XML.",
    ),
    open_dir: bool = typer.Option(
        False,
        "--open",
        help="Open export directory in file explorer after exporting.",
    ),
    ignore_errors: bool = typer.Option(
        False,
        "--ignore-errors",
        help="Enable best-effort exporting. Print errors but continue exporting.",
    ),
    # TODO: add --ignore-errors option
    # Legacy positional args
    args: Optional[list[str]] = ARGS_POSITIONAL,
) -> None:
    r"""Export Zabbix configuration for one or more components.

    Uses defaults from Zabbix-CLI configuration file if not specified.

    [b]NOTE:[/] [option]--name[/] arguments are globs, not regex patterns.

    [b]Filename scheme is as follows:[/]

        [code]DIRECTORY/OBJECT_TYPE/NAME_ID_\[timestamp].FORMAT[/]

    [b]But it can be changed to the legacy scheme with [option]--legacy-filenames[/option]:[/b]

        [code]DIRECTORY/OBJECT_TYPE/zabbix_export_OBJECT_TYPE_NAME_ID_\[timestamp].FORMAT[/]

    Timestamps are disabled by default, but can be enabled with the [configopt]app.export_timestamps[/]
    configuration option.

    Shows detailed information about exported files in JSON output mode.
    """
    from zabbix_cli.commands.results.export import ExportResult
    from zabbix_cli.models import Result

    if args:
        if not len(args) == 3:
            exit_err("Invalid number of arguments. Use options instead.")
        directory = parse_path_arg(args[0])
        types = parse_export_types(parse_list_arg(args[1]))
        names = args[2]
        # No format arg in V2...

    if legacy_filenames:
        warning(
            "--legacy-filenames is deprecated and will be removed in a future version."
        )

    exportdir = directory or app.state.config.app.export_directory

    # V2 compat: passing in #all# exports all names
    if names == "#all#":
        obj_names = []
    else:
        obj_names = parse_list_arg(names)

    if not format:
        format = app.state.config.app.export_format

    # TODO: guard this in try/except and render useful error if it fails
    exporter = ZabbixExporter(
        client=app.state.client,
        config=app.state.config,
        types=types,
        names=obj_names,
        directory=exportdir,
        format=format,
        legacy_filenames=legacy_filenames,
        pretty=pretty,
        ignore_errors=ignore_errors,
    )
    exported = exporter.run()
    # NOTE: record duration similar to import_configuration?
    render_result(
        Result(
            message=f"Exported {len(exported)} files to {exportdir}",
            result=ExportResult(
                exported=exported, types=types, names=obj_names, format=format
            ),
            table=False,
        )
    )

    if open_dir:
        open_directory(exportdir)


class ZabbixImporter:
    def __init__(
        self,
        client: ZabbixAPI,
        config: Config,
        files: list[Path],
        create_missing: bool,
        update_existing: bool,
        delete_missing: bool,
        ignore_errors: bool,
    ) -> None:
        self.client = client
        self.config = config
        self.files = files
        self.ignore_errors = ignore_errors
        self.create_missing = create_missing
        self.update_existing = update_existing
        self.delete_missing = delete_missing

        self.imported: list[Path] = []
        self.failed: list[Path] = []

    def run(self) -> None:
        """Runs the importer."""
        from rich.progress import BarColumn
        from rich.progress import Progress
        from rich.progress import SpinnerColumn
        from rich.progress import TaskProgressColumn
        from rich.progress import TextColumn
        from rich.progress import TimeElapsedColumn

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            transient=True,
            console=err_console,
        )
        with progress:
            task = progress.add_task("Importing files...", total=len(self.files))
            for file in self.files:
                self.import_file(file)
                progress.update(task, advance=1)

    def import_file(self, file: Path) -> None:
        # API method will return true if successful, but does failure return false
        # or does it raise an exception?
        try:
            self.client.import_configuration(file)
        except Exception as e:
            self.failed.append(file)
            msg = f"Failed to import {file}: {e}"
            if self.ignore_errors:
                error(msg, exc_info=True)
            else:
                raise ZabbixCLIError(msg) from e
        else:
            self.imported.append(file)
            logger.info(f"Imported file {file}")


def filter_valid_imports(files: list[Path]) -> list[Path]:
    """Filter list of files to include only valid imports."""
    importables = [i.casefold() for i in ExportFormat.get_importables()]
    valid: list[Path] = []
    for f in files:
        if not f.exists():
            continue
        if f.is_dir():
            continue
        if f.suffix.strip(".").casefold() not in importables:
            continue
        valid.append(f)
    return valid


@app.command(name="import_configuration", rich_help_panel=HELP_PANEL)
def import_configuration(
    ctx: typer.Context,
    to_import: Optional[str] = typer.Argument(
        None,
        help="Path to file or directory to import configuration from. Accepts glob pattern. Uses default export directory if not specified.",
    ),
    dry_run: bool = typer.Option(False, "--dryrun", help="Preview files to import."),
    create_missing: bool = typer.Option(
        True, "--create-missing/--no-create-missing", help="Create missing objects."
    ),
    update_existing: bool = typer.Option(
        True, "--update-existing/--no-update-existing", help="Update existing objects."
    ),
    delete_missing: bool = typer.Option(
        False, "--delete-missing/--no-delete-missing", help="Delete missing objects."
    ),
    ignore_errors: bool = typer.Option(
        False,
        "--ignore-errors",
        help="Enable best-effort importing. Print errors from failed imports but continue importing.",
    ),
    # Legacy positional args
    args: Optional[list[str]] = ARGS_POSITIONAL,
) -> None:
    """Import Zabbix configuration from file, directory or glob pattern.

    Imports all files in all subdirectories if a directory is specified.
    Uses default export directory if no argument is specified.

    Determines format to import based on file extensions.
    """
    import glob

    from zabbix_cli.commands.results.export import ImportResult
    from zabbix_cli.models import Result
    from zabbix_cli.models import ReturnCode

    if args:
        if not len(args) == 2:
            exit_err("Invalid number of positional arguments. Use options instead.")
        to_import = args[0]
        dry_run = parse_bool_arg(args[1])

    # Use default export directory if no path is specified
    if not to_import:
        to_import = str(app.state.config.app.export_directory)

    # Determine if we are dealing with a directory, file or glob
    import_path = Path(to_import)
    if import_path.exists():
        if import_path.is_dir():
            files = list(import_path.glob("**/*"))
        else:
            files = [import_path]
    else:
        # Arg doesn't exist, must be glob pattern
        # If user passes in empty string, that's on them!
        files = [Path(p) for p in glob.glob(to_import)]

    files = filter_valid_imports(files)

    # HACK: in order to print a list of files without messing with line wrapping
    # and other formatting headaches, we just print using the console here
    # TODO: print properly with just render_result instead of this hack
    if dry_run:
        msg = f"Found {len(files)} files to import"
        if app.state.config.app.output.format == OutputFormat.TABLE:
            to_print = [path_link(f) for f in files]
            console.print("\n".join(to_print), highlight=False, no_wrap=True)
            info(msg)
        else:
            render_result(
                Result(
                    message=msg,
                    result=ImportResult(success=True, dryrun=True, imported=files),
                )
            )
        return

    if not files:
        exit_err(f"No files found to import matching: {to_import}")

    info(f"Found {len(files)} files to import")

    importer = ZabbixImporter(
        client=app.state.client,
        config=app.state.config,
        files=files,
        create_missing=create_missing,
        update_existing=update_existing,
        ignore_errors=ignore_errors,
        delete_missing=delete_missing,
    )

    try:
        start_time = time.monotonic()
        importer.run()
    except Exception as e:
        res = Result(
            message=f"{e}. See log for further details. Use [cyan]--ignore-errors[/] to ignore failed files.",
            return_code=ReturnCode.ERROR,
            result=ImportResult(
                success=False,
                dryrun=False,
                imported=importer.imported,
                failed=importer.failed,
            ),
            table=False,  # only render this in JSON mode
        )
    else:
        duration = time.monotonic() - start_time
        msg = f"Imported {len(importer.imported)} files in {convert_seconds_to_duration(int(duration))}"
        if importer.failed:
            msg += f", failed to import {len(importer.failed)} files"
        res = Result(
            message=msg,
            result=ImportResult(
                success=len(importer.failed) == 0,
                imported=importer.imported,
                failed=importer.failed,
                duration=duration,
            ),
            table=False,  # only render this in JSON mode
        )

    render_result(res)
