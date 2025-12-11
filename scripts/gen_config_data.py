"""Generates a YAML file containing all the global options for the CLI."""

from __future__ import annotations

import logging
import sys
from enum import Enum
from pathlib import Path
from typing import Any
from typing import Literal
from typing import Optional
from typing import Union
from typing import get_args
from typing import get_origin

import tomli_w
import yaml  # type: ignore
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import Json
from pydantic import RootModel
from pydantic import SecretStr
from pydantic import TypeAdapter
from pydantic import ValidationInfo
from pydantic import computed_field
from pydantic import field_validator
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from typing_extensions import Self
from zabbix_cli.config.model import Config

sys.path.append(Path(__file__).parent.as_posix())
from common import DATA_DIR  # noqa
from common import add_path_placeholders  # noqa


JSONAdapter = TypeAdapter(Json)

TYPE_MAP = {
    SecretStr: "str",
    Path: "str",
    Literal: "str",
}
"""Special types that are represented differently in config file and in the code."""


TYPE_CAN_STR = {str, int, float, bool, list, dict, set, tuple, type(None)}
"""Types that can be represented by calling str() on them"""
# NOTE: Does this apply to all built-ins? Can we just check for builtins?


# HACK: dict retrieval with type hinting
def get_field_info(info: ValidationInfo) -> FieldInfo:
    return info.data["field"]


class ConfigBase(BaseModel):
    """Common fields shared by config tables and options."""

    field: Optional[FieldInfo] = Field(default=None, exclude=True)

    name: str
    description: str = ""
    parents: list[str] = []

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @computed_field()
    def is_model(self) -> bool:
        return hasattr(self, "fields")

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, value: Any) -> str:
        return value or ""

    @field_validator("description", mode="after")
    @classmethod
    def dedent_description(cls, value: str) -> str:
        return "\n".join(line.strip() for line in value.splitlines())


class ConfigOption(ConfigBase):
    type: str
    default: Any = None
    required: bool = False
    examples: Optional[list[Any]] = None

    @computed_field()
    def is_model(self) -> bool:
        return False

    @computed_field()
    @property
    def choices(self) -> Optional[list[Any]]:
        # Handle common choice types
        if not self.field or self.field.annotation is None:
            return None
        origin = get_origin(self.field.annotation)
        if origin is Literal:
            return list(get_args(self.field.annotation))
        elif lenient_issubclass(self.field.annotation, Enum):
            return list(self.field.annotation)
        return None

    @computed_field()
    @property
    def choices_str(self) -> Optional[str]:
        if not self.choices:
            return None
        return ", ".join(str(choice) for choice in self.choices)

    @computed_field()
    @property
    def parents_str(self) -> str:
        return ".".join(self.parents)

    def example_toml_dict(self) -> dict[str, Any]:
        if not self.examples:
            # We have no examples to provide, this is a problem
            raise ValueError(
                f"Cannot render field {self.name!r}. "
                "It has no defaults and no examples. "
                "Provide an example in the field definition under `examples`."
            )
        example = self.examples[0]

        ex: dict[str, Any] = {}
        current = ex
        if self.parents:
            for parent in self.parents:
                current[parent] = {}
                current = current[parent]
        current[self.name] = example
        return ex

    @computed_field()
    @property
    def example(self) -> str:
        """TOML representation of the first example."""
        ex = self.example_toml_dict()
        ex_jsonable = JSONAdapter.dump_python(ex, exclude_none=True, mode="json")
        return tomli_w.dumps(ex_jsonable)

    @classmethod
    def from_field_info(
        cls, name: str, field: FieldInfo, parents: list[str]
    ) -> ConfigOption:
        return cls(
            # WARNING: DO NOT CHANGE THE ORDER OF THE `field` PARAMETER
            # `field` must be validated first in order to have access to
            # the field data in the validation methods
            field=field,
            # Custom param to tell where we are in the model hierarchy
            parents=parents,
            # Rest of the parameters
            name=name,
            type=field.annotation,  # type: ignore # field validator
            description=field.description,  # type: ignore # field validator
            default=field.default,
            required=field.default is PydanticUndefined and not field.default_factory,
            examples=field.examples,
        )

    @field_validator("default", mode="before")
    @classmethod
    def validate_default(cls, value: Any) -> Optional[Any]:
        if value is PydanticUndefined:
            return None
        if isinstance(value, SecretStr):
            return value.get_secret_value()
        if isinstance(value, bool):
            return str(value).lower()
        return value

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, value: Any) -> str:
        if value is None:
            return "Any"

        origin = get_origin(value)
        args = get_args(value)

        def type_to_str(t: type[Any]) -> str:
            if lenient_issubclass(value, str):
                return "str"

            if lenient_issubclass(value, Enum):
                # Get the name of the first enum member type
                # NOTE: Will fail if enum has no members
                return str(list(value)[0])  # pyright: ignore[reportUnknownArgumentType]

            # Types that are represented as strings in config (paths, secrets, etc.)
            if typ := TYPE_MAP.get(t):
                return typ

            # Primitives and built-in generics (str, int, list[str], dict[str, int], etc.)
            if origin in TYPE_CAN_STR:
                return str(value)

            # Fall back on the string representation of the type
            return getattr(value, "__name__", str(value))

        # Handle generics, literals, etc.
        if origin and args:
            # Get the name of the first type in the Literal type
            # NOTE: we expect that Literal is only used with a single type
            if origin is Literal:
                return args[0].__class__.__name__
            # Get first non-None type in Union
            # NOTE: we expect that the config does not have unions of more than 2 types
            elif origin is Union and args:
                # Strip None from the Union
                ar = (type_to_str(a) for a in args if a is not type(None))
                return " | ".join(ar)

        return type_to_str(value)

    @field_validator("examples", mode="before")
    @classmethod
    def validate_examples(
        cls, value: Optional[list[Any]], info: ValidationInfo
    ) -> list[Any]:
        if value:
            return value
        field = get_field_info(info)
        if field.default is not PydanticUndefined:
            return [field.default]
        elif field.default_factory:
            return [field.default_factory()]
        return []


class ConfigTable(ConfigBase):
    # NOTE: can we generalize this to always be a list of ConfigOption?
    # Can we get rid of ConfigTable altogether and just compose everything of
    # ConfigOption by adding `fields` to the ConfigOption model?
    # That way we could have a consistent interface regardless of
    # whether we're dealing with a submodel or a field.
    fields: list[Union[ConfigTable, ConfigOption]]

    @classmethod
    def from_field_info(
        cls, name: str, field: FieldInfo, parents: list[str], field_parents: list[str]
    ) -> Self:
        assert field.annotation
        return cls(
            field=field,
            parents=parents,
            name=name,
            description=field.annotation.__doc__,  # type: ignore # validator
            fields=get_config_options(field.annotation, name, field_parents),
        )

    def example_toml_dict(self) -> dict[str, Any]:
        return {}  # HACK: avoid isinstance checking

    @computed_field()
    @property
    def example(self) -> str:
        ex: dict[str, Any] = {}
        # Pretty stupid way to render an example, but it works
        for field in self.fields:
            if field.is_model:
                continue
            example = field.example_toml_dict()
            if not ex:
                ex.update(example)
            else:
                if self.name in ex:
                    ex[self.name].update(example)
                elif self.parents:
                    e = ex
                    for parent in self.parents:
                        if not e.get(parent):
                            e[parent] = {}
                        e = e[parent]
                    e[self.name.rpartition(".")[-1]].update(example)
                    ex.update(e)
                else:
                    ex.update(example)

        ex_jsonable = JSONAdapter.dump_python(ex, exclude_none=True, mode="json")
        return tomli_w.dumps(ex_jsonable)


def lenient_issubclass(cls: type, class_or_tuple: Union[type, tuple[type]]) -> bool:
    try:
        return issubclass(cls, class_or_tuple)
    except TypeError:
        return False


def get_config_options(
    type_: type[BaseModel], current_name: str = "", parents: Optional[list[str]] = None
) -> list[Union[ConfigTable, ConfigOption]]:
    """Recursively extract the configuration options from a Pydantic model."""
    if parents is None:
        parents = []
    options: list[Union[ConfigTable, ConfigOption]] = []
    for field_name, field in type_.model_fields.items():
        if field.exclude:
            continue
        if not field.annotation:
            continue
        if field.default is None:
            continue
        if field.deprecated:
            continue

        if lenient_issubclass(field.annotation, RootModel):
            logging.debug("Skipping %s. It is a root model.", field_name)
            continue

        if current_name:
            name = f"{current_name}.{field_name}"
        else:
            name = field_name

        if lenient_issubclass(field.annotation, BaseModel):
            # We have a nested model
            field_parents = parents.copy()
            field_parents.append(field_name)
            options.append(
                ConfigTable.from_field_info(name, field, parents, field_parents)
            )
        else:
            # We have a field
            options.append(
                ConfigOption.from_field_info(field_name, field, parents=parents)
            )
    return options


def generate_config_info() -> ConfigTable:
    """Generate the configuration options for the CLI."""
    conf = ConfigTable(name="", fields=[])
    conf.fields = get_config_options(Config, conf.name)
    return conf


def main() -> None:
    conf = generate_config_info()
    out = yaml.dump(conf.model_dump(mode="json", exclude_none=True), sort_keys=False)
    out = add_path_placeholders(out)  # type: ignore
    # Replace paths with placeholders
    with open(DATA_DIR / "config_options.yaml", "w") as f:
        f.write(out)


if __name__ == "__main__":
    main()
