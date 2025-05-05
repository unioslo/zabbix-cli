from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import NamedTuple
from typing import Optional

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from zabbix_cli.config.constants import CONFIG_PRIORITY
from zabbix_cli.config.constants import DEFAULT_CONFIG_FILE
from zabbix_cli.exceptions import ConfigError

if TYPE_CHECKING:
    from zabbix_cli.config.model import Config

logger = logging.getLogger(__name__)


def load_config_toml(filename: Path) -> dict[str, Any]:
    """Load a TOML configuration file."""
    import tomli

    try:
        return tomli.loads(filename.read_text())
    except tomli.TOMLDecodeError as e:
        raise ConfigError(f"Error decoding TOML file {filename}: {e}") from e
    except OSError as e:
        raise ConfigError(f"Error reading TOML file {filename}: {e}") from e


def load_config_conf(filename: Path) -> dict[str, Any]:
    """Load a conf configuration file with ConfigParser."""
    import configparser

    config = configparser.ConfigParser()
    try:
        config.read_file(filename.open())
        return {s: dict(config.items(s)) for s in config.sections()}
    except (configparser.Error, OSError) as e:
        raise ConfigError(
            f"Error reading legacy configuration file {filename}: {e}"
        ) from e


def find_config(
    filename: Optional[Path] = None,
    priority: tuple[Path, ...] = CONFIG_PRIORITY,
) -> Optional[Path]:
    """Find all available configuration files.

    :param filename: An optional user supplied file to throw into the mix
    """
    # FIXME: this is a mess.
    #        If we have a file, just try to load it and call it a day?
    filename_prio = list(priority)
    if filename:
        filename_prio.insert(
            0, filename
        )  # TODO: append last when we implement multi-file config merging
    for fp in filename_prio:
        if fp.exists():
            logging.debug("found config %r", fp)
            return fp
    return None


def get_config(filename: Optional[Path] = None, *, init: bool = False) -> Config:
    """Get a configuration object.

    Args:
        filename (Optional[str], optional): An optional user supplied file to throw into the mix. Defaults to None.

    Returns:
        Config: Config object loaded from file
    """
    from zabbix_cli.config.model import Config

    return Config.from_file(filename, init=init)


def get_replacement_fields(field: FieldInfo) -> list[str]:
    replacement: list[str] = []
    # NOTE: I think this is silly over doing `isinstance(field.json_schema_extra, dict)`
    #       but Pyright fails to infer types correctly when doing so, because it
    #       assumes the type is `dict[Unknown, Unknown]` after performing such
    #       isinstance checks. Not great.
    if isinstance(field.json_schema_extra, dict):
        # if field.json_schema_extra and not callable(field.json_schema_extra):
        rep = field.json_schema_extra.get("replacement")
        if isinstance(rep, str):
            replacement.append(rep)
        elif isinstance(rep, list):
            replacement = list({r for r in rep if isinstance(r, str)})
    return replacement


# TODO: can we bake this into get_deprecated_fields_set? Should we?
def check_deprecated_fields(model: BaseModel) -> None:
    """Check for deprecated fields in a model and log a warning."""
    # Sort for reproducibility + readability
    for field_name in sorted(model.model_fields_set):
        f = model.model_fields.get(field_name)
        if not f:
            continue
        if f.deprecated:
            if replacements := get_replacement_fields(f):
                from zabbix_cli.output.console import warning

                r = ", ".join(replacements)
                warning(
                    f"Config option [configopt]{field_name}[/] is deprecated. Replaced by: [configopt]{r}[/]."
                )
            else:
                logger.warning("Config option `%s` is deprecated.", field_name)


def get_deprecated_fields_set(
    model: BaseModel, parent: Optional[str] = None
) -> list[DeprecatedField]:
    """Get a list of deprecated fields set on a model and all its submodels."""
    fields: list[DeprecatedField] = []
    # Sort for reproducibility + readability
    for field_name in sorted(model.model_fields_set):
        field = model.model_fields.get(field_name)
        if not field:
            continue

        # Get field value safely
        try:
            value = getattr(model, field_name)
        except AttributeError:
            logger.error(
                "Field %s.%s exists in model_fields_set but is not accessible",
                model,
                field_name,
            )
            continue

        # Recurse into submodels
        if isinstance(value, BaseModel):
            submodel_fields = get_deprecated_fields_set(value, parent=field_name)
            fields.extend(submodel_fields)
        else:
            # We have a field that is not a submodel
            if not field.deprecated:
                continue
            name = f"{parent}.{field_name}" if parent else field_name
            replacements = get_replacement_fields(field)
            fields.append(DeprecatedField(name, value, replacements))
    return fields


def update_deprecated_fields(model: BaseModel) -> None:
    deprecated_fields = get_deprecated_fields_set(model)
    for field in deprecated_fields:
        if not field.replacement:
            continue
        # Update the model with the new field
        for replacement in field.replacement:
            _set_replacement_field(model, field, replacement)


def _set_replacement_field(
    model: BaseModel, field: DeprecatedField, replacement: str
) -> None:
    try:
        # Decompose the replacement field into its attributes
        attributes = replacement.split(".")
        to_replace = model
        for attr in attributes[:-1]:
            to_replace = getattr(to_replace, attr)
        field_to_update = attributes[-1]

        # Don't update if replacement field is already set
        if (
            isinstance(to_replace, BaseModel)
            and field_to_update in to_replace.model_fields_set
        ):
            logger.debug("Field `%s` is already set, skipping", field.replacement)
            return

        setattr(to_replace, field_to_update, field.value)
    except AttributeError as e:
        logger.error(
            "Failed to update field `%s` with value `%s` from  deprecated field `%s`: %s",
            field.replacement,
            field.value,
            field.field_name,
            e,
        )


class DeprecatedField(NamedTuple):
    """A deprecated field in a model."""

    field_name: str
    value: Any
    replacement: list[str] = []


def init_config(
    config: Optional[Config] = None,
    config_file: Optional[Path] = None,
    *,
    overwrite: bool = False,
    # Compatibility with V2 zabbix-cli-init args
    url: Optional[str] = None,
    username: Optional[str] = None,
) -> Config:
    """Creates required directories and boostraps config with
    options required to connect to the Zabbix API.
    """

    from zabbix_cli.config.model import Config
    from zabbix_cli.dirs import init_directories

    # Create required directories
    init_directories()

    if config_file is None:
        config_file = DEFAULT_CONFIG_FILE
    if config_file.exists() and not overwrite:
        raise ConfigError(
            f"File {config_file} already exists. Use [option]--overwrite[/] to overwrite it."
        )

    if not config:
        config = Config.sample_config()
    config.config_path = config_file

    if url:
        config.api.url = url
    if username:
        config.api.username = username

    return config
