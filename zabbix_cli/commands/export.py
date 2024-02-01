from __future__ import annotations

import glob
import time
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any
from typing import Iterator
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Protocol
from typing import TYPE_CHECKING
from typing import Union

import typer
from pydantic import field_serializer
from rich.progress import BarColumn
from rich.progress import Progress
from rich.progress import SpinnerColumn
from rich.progress import TaskProgressColumn
from rich.progress import TextColumn
from rich.progress import TimeElapsedColumn
from strenum import StrEnum

from zabbix_cli._v2_compat import ARGS_POSITIONAL
from zabbix_cli.app import app
from zabbix_cli.config import Config
from zabbix_cli.config import ExportFormat
from zabbix_cli.config import OutputFormat
from zabbix_cli.exceptions import ZabbixCLIError
from zabbix_cli.logs import logger
from zabbix_cli.models import Result
from zabbix_cli.models import ReturnCode
from zabbix_cli.models import TableRenderable
from zabbix_cli.output.console import console
from zabbix_cli.output.console import err_console
from zabbix_cli.output.console import error
from zabbix_cli.output.console import exit_err
from zabbix_cli.output.console import info
from zabbix_cli.output.console import warning
from zabbix_cli.output.formatting.path import path_link
from zabbix_cli.output.render import render_result
from zabbix_cli.pyzabbix.pyzabbix import ZabbixAPI
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import HostGroup
from zabbix_cli.pyzabbix.types import Image
from zabbix_cli.pyzabbix.types import Map
from zabbix_cli.pyzabbix.types import MediaType
from zabbix_cli.pyzabbix.types import Template
from zabbix_cli.pyzabbix.types import TemplateGroup
from zabbix_cli.utils.args import parse_bool_arg
from zabbix_cli.utils.args import parse_list_arg
from zabbix_cli.utils.args import parse_path_arg
from zabbix_cli.utils.utils import convert_seconds_to_duration
from zabbix_cli.utils.utils import open_directory
from zabbix_cli.utils.utils import sanitize_filename


if TYPE_CHECKING:
    from zabbix_cli.models import RowsType  # noqa: F401
    from zabbix_cli.models import ColsRowsType


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
    def __call__(self) -> Iterator[Path]:
        ...


class Exporter(NamedTuple):
    func: ExporterFunc
    type: ExportType


Exportable = Union[
    HostGroup,
    TemplateGroup,
    Host,
    Image,
    Map,
    Template,
    MediaType,
]


class ZabbixExporter:
    """Export Zabbix configuration for one or more components."""

    def __init__(
        self,
        client: ZabbixAPI,
        config: Config,
        objects: List[str],
        names: List[str],
        directory: Path,
        format: ExportFormat,
        legacy_filenames: bool,
        pretty: bool,
    ) -> None:
        self.client = client
        self.config = config
        self.export_types = self.parse_export_types(objects)
        self.names = names
        self.directory = directory
        self.format = format
        self.legacy_filenames = legacy_filenames
        self.pretty = pretty

        # Ideally, we fetch and write at the same time, so we keep memory usage low,
        # while utilizing I/O and CPU as much as possible.
        # Will need to be rewritten to use threads to achieve this.

        # TODO: test that mapping contains all export types
        self.exporter_map = {
            ExportType.HOST_GROUPS: self.export_host_groups,
            ExportType.TEMPLATE_GROUPS: self.export_template_groups,
            ExportType.HOSTS: self.export_hosts,
            ExportType.IMAGES: self.export_images,
            ExportType.MAPS: self.export_maps,
            ExportType.TEMPLATES: self.export_templates,
            ExportType.MEDIA_TYPES: self.export_media_types,
        }  # type: dict[ExportType, ExporterFunc]

        # Curry the export method with the appropriate arguments
        self.do_export = partial(
            self.client.export_configuration, pretty=self.pretty, format=self.format
        )

    def run(self) -> List[Path]:
        """Run exporters."""
        files = []  # type: List[Path]
        for exporter in self.get_exporters():
            with err_console.status(f"Exporting {exporter.type.human_readable()}..."):
                exported = exporter.func()
                files.extend(exported)
        return files

    def parse_export_types(self, objects: List[str]) -> List[ExportType]:
        """Parses list of object export type names.

        In V2, this was called "objects", which isn't very descriptive...
        """
        # If we have no specific exports, export all object types
        if not objects:
            objects = list(ExportType)
        objs = []  # type: List[ExportType]
        for obj in objects:
            try:
                export_type = ExportType(obj)
                self._check_export_type_compat(export_type)
                objs.append(export_type)
            except ZabbixCLIError as e:
                raise e  # should this be exit_err instead?
            except Exception as e:
                raise ZabbixCLIError(f"Invalid export type: {obj}") from e
        # dedupe
        # TODO: test that StrEnum is hashable on all Python versions
        # FIXME: this deduplication makes the order non-deterministic!
        return list(set(objs))

    def _check_export_type_compat(self, export_type: ExportType) -> None:
        if export_type == ExportType.TEMPLATE_GROUPS:
            if self.client.version.release < (6, 2, 0):
                raise ZabbixCLIError(
                    "Template group exports are not supported in Zabbix versions < 6.2."
                )

    def get_exporters(self) -> List[Exporter]:
        """Get a list of exporters to run."""
        exporters = []  # type: List[Exporter]
        for export_type in self.export_types:
            exporter = self.exporter_map.get(export_type, None)
            if not exporter:  # should never happen - tests should catch this
                raise ZabbixCLIError(
                    f"No exporter available for export type: {export_type}"
                )
            exporters.append(Exporter(exporter, export_type))
        return exporters

    def generate_filename(self, obj: Exportable) -> Path:
        """Generate filename for exported object."""
        name = "unknown"
        id_ = "unknown"
        directory = self.directory
        if isinstance(obj, HostGroup):
            name = obj.name
            id_ = obj.groupid
            directory /= ExportType.HOST_GROUPS.value
        elif isinstance(obj, TemplateGroup):
            name = obj.name
            id_ = obj.groupid
            directory /= ExportType.TEMPLATE_GROUPS.value
        elif isinstance(obj, Host):
            name = obj.host
            id_ = obj.hostid
            directory /= ExportType.HOSTS.value
        elif isinstance(obj, Image):
            name = obj.name
            id_ = obj.imageid
            directory /= ExportType.IMAGES.value
        elif isinstance(obj, Map):
            name = obj.name
            id_ = obj.sysmapid
            directory /= ExportType.MAPS.value
        elif isinstance(obj, Template):
            name = obj.host
            id_ = obj.templateid
            directory /= ExportType.TEMPLATES.value
        elif isinstance(obj, MediaType):
            name = obj.name
            id_ = obj.mediatypeid
            directory /= ExportType.MEDIA_TYPES.value
        stem = self.get_filename_stem(name, id_)
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
    def export_host_groups(self) -> Iterator[Path]:
        # FIXME URGRENT WHATVER: check if we should use search=True or False
        hostgroups = self.client.get_hostgroups(*self.names, search=True)
        for hg in hostgroups:
            exported = self.do_export(host_groups=[hg])
            yield self.write_exported(exported, hg)

    def export_template_groups(self) -> Iterator[Path]:
        template_groups = self.client.get_templategroups(*self.names, search=True)
        for tg in template_groups:
            exported = self.do_export(template_groups=[tg])
            yield self.write_exported(exported, tg)

    def export_hosts(self) -> Iterator[Path]:
        hosts = self.client.get_hosts(*self.names)
        for host in hosts:
            exported = self.do_export(hosts=[host])
            yield self.write_exported(exported, host)

    def export_images(self) -> Iterator[Path]:
        images = self.client.get_images(*self.names, select_image=False)
        for image in images:
            exported = self.do_export(images=[image])
            yield self.write_exported(exported, image)

    def export_maps(self) -> Iterator[Path]:
        maps = self.client.get_maps(*self.names)
        for m in maps:
            exported = self.do_export(maps=[m])
            yield self.write_exported(exported, m)

    def export_media_types(self) -> Iterator[Path]:
        media_types = self.client.get_media_types(*self.names)
        for mt in media_types:
            exported = self.do_export(media_types=[mt])
            yield self.write_exported(exported, mt)

    def export_templates(self) -> Iterator[Path]:
        templates = self.client.get_templates(*self.names)
        for template in templates:
            exported = self.do_export(templates=[template])
            yield self.write_exported(exported, template)

    def write_exported(self, exported: str, obj: Exportable) -> Path:
        """Writes an exported object to a file. Returns path to file."""
        # TODO: add some logging here to show progress
        # run some callback that updates a progress bar or something
        filename = self.generate_filename(obj)
        if not filename.parent.exists():
            try:
                filename.parent.mkdir(parents=True)
            except Exception as e:
                raise ZabbixCLIError(
                    f"Failed to create directory {filename.parent}: {e}. Ensure you have permissions to create directories in the export directory."
                ) from e
        with open(filename, "w") as f:
            f.write(exported)
        return filename


@app.command(name="export_configuration", rich_help_panel=HELP_PANEL)
def export_configuration(
    ctx: typer.Context,
    directory: Optional[str] = typer.Option(
        None,
        help="Directory to export configuration to. Overrides directory in config.",
    ),
    objects: Optional[str] = typer.Option(
        None, "--object", help="Type(s) of objects to export. Comma-separated list."
    ),
    names: Optional[str] = typer.Option(
        None, "--name", help="Name(s) of objects to export. Comma-separated list."
    ),
    format: Optional[ExportFormat] = typer.Option(
        None,
        "--format",
        "-f",
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
        is_flag=True,
        help="Pretty-print output. Not supported for XML.",
    ),
    open_dir: bool = typer.Option(
        False,
        "--open",
        is_flag=True,
        help="Open export directory in file explorer after exporting.",
    ),
    # TODO: add --ignore-errors option
    # Legacy positional args
    args: Optional[List[str]] = ARGS_POSITIONAL,
) -> None:
    """Export Zabbix configuration for one or more components.

    Uses defaults from Zabbix-CLI configuration file if not specified.

    Filename scheme is as follows:

    [i]<directory>/<object_type>/<name>_<id>.<format>[/]

    But it can be changed to the legacy scheme with --legacy-filenames:

    [i]<directory>/<object_type>/zabbix_export_<object_type>_<name>_<id>_timestamp>.<format>[/]
    """
    if args:
        if not len(args) == 3:
            exit_err("Invalid number of arguments. Use options instead.")
        directory = args[0]
        objects = args[1]
        names = args[2]
        # No format arg in V2...

    if legacy_filenames:
        warning(
            "--legacy-filenames is deprecated and will be removed in a future version."
        )

    if directory:
        exportdir = parse_path_arg(directory)
    else:
        exportdir = app.state.config.app.export_directory

    # V2 compat: passing in #all# exports all objects (default)
    if objects == "#all#":
        objs = []
    else:
        objs = parse_list_arg(objects)

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
        objects=objs,
        names=obj_names,
        directory=exportdir,
        format=format,
        legacy_filenames=legacy_filenames,
        pretty=pretty,
    )
    exported = exporter.run()
    info(f"Exported {len(exported)} files to {path_link(exportdir)}")

    if open_dir:
        open_directory(exportdir)


class ZabbixImporter:
    def __init__(
        self,
        client: ZabbixAPI,
        config: Config,
        files: List[Path],
        create_missing: bool,
        update_existing: bool,
        ignore_errors: bool,
    ) -> None:
        self.client = client
        self.config = config
        self.files = files
        self.ignore_errors = ignore_errors
        self.create_missing = create_missing
        self.update_existing = update_existing

        self.imported = []  # type: List[Path]
        self.failed = []  # type: List[Path]

    def run(self) -> None:
        """Runs the importer."""
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
            self.client.import_configuration(file, create_missing=self.create_missing)
        except Exception as e:
            self.failed.append(file)
            msg = f"Failed to import {file}"
            if self.ignore_errors:
                error(msg, exc_info=True)
            else:
                raise ZabbixCLIError(msg) from e
        else:
            self.imported.append(file)
            logger.info(f"Imported file {file}")


class ZabbixImportResult(TableRenderable):
    """Result type for `import_configuration` command."""

    success: bool = True
    dryrun: bool = False
    imported: List[Path] = []
    failed: List[Path] = []
    duration: Optional[float] = None
    """Duration it took to import files in seconds. Is None if import failed."""

    @field_serializer("imported", "failed", when_used="json")
    def _serialize_files(self, files: List[Path]) -> List[str]:
        """Serializes files as list of normalized, absolute paths with symlinks resolved."""
        return [str(f.resolve()) for f in files]

    def __cols_rows__(self) -> ColsRowsType:
        cols = ["Imported", "Failed"]  # type: List[str]
        rows = [
            [
                "\n".join(path_link(f) for f in self.imported),
                "\n".join(path_link(f) for f in self.failed),
            ]
        ]  # type: RowsType
        return cols, rows


def filter_valid_imports(files: List[Path]) -> List[Path]:
    """Filter list of files to only those that are valid for import."""
    importables = [i.casefold() for i in ExportFormat.get_importables()]
    valid = []  # type: List[Path]
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
    dry_run: bool = typer.Option(False, "--dry-run", is_flag=True),
    create_missing: bool = typer.Option(
        True, "--create-missing/--no-create-missing", help="Create missing objects."
    ),
    update_existing: bool = typer.Option(
        True, "--update-existing/--no-update-existing", help="Update existing objects."
    ),
    ignore_errors: bool = typer.Option(
        False,
        "--ignore-errors",
        is_flag=True,
        help="Enable best-effort importing. Print errors but continue importing.",
    ),
    # Legacy positional args
    args: Optional[List[str]] = ARGS_POSITIONAL,
) -> None:
    """Import Zabbix configuration from file, directory or glob pattern.

    Imports all files in all subdirectories if a directory is specified.
    Uses default export directory if no argument is specified.

    Determines format to import based on file extensions.
    """
    if args:
        if not len(args) == 2:
            exit_err("Invalid number of arguments. Use options instead.")
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
        if app.state.config.app.output_format == OutputFormat.TABLE:
            to_print = [path_link(f) for f in files]
            console.print("\n".join(to_print), highlight=False, no_wrap=True)
            info(msg)
        else:
            render_result(
                Result(
                    message=msg,
                    result=ZabbixImportResult(
                        success=True, dryrun=True, imported=files
                    ),
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
    )

    try:
        start_time = time.monotonic()
        importer.run()
    except Exception as e:
        res = Result(
            message=f"{e}. See log for further details.",
            return_code=ReturnCode.ERROR,
            result=ZabbixImportResult(
                success=False,
                dryrun=False,
                imported=importer.imported,
                failed=importer.failed,
            ),
        )
    else:
        duration = time.monotonic() - start_time
        msg = f"Imported {len(importer.imported)} files in {convert_seconds_to_duration(int(duration))}"
        if importer.failed:
            msg += f", failed to import {len(importer.failed)} files"
        res = Result(
            message=msg,
            result=ZabbixImportResult(
                success=len(importer.failed) == 0,
                imported=importer.imported,
                failed=importer.failed,
                duration=duration,
            ),
        )

    render_result(res)
