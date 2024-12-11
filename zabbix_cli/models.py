from __future__ import annotations

from collections.abc import MutableSequence
from enum import Enum
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar
from typing import Generic
from typing import Optional
from typing import Union
from typing import cast

import rich.box
from packaging.version import Version
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import JsonValue
from pydantic.fields import ComputedFieldInfo
from pydantic.fields import FieldInfo
from strenum import StrEnum
from typing_extensions import TypeVar

from zabbix_cli.logs import logger
from zabbix_cli.table import get_table
from zabbix_cli.utils.rich import get_safe_renderable

if TYPE_CHECKING:
    from rich.console import RenderableType
    from rich.table import Table


class ReturnCode(StrEnum):
    DONE = "Done"
    ERROR = "Error"


ColsType = list[str]
"""A list of column headers."""

RowContent = MutableSequence["RenderableType"]
"""A list of renderables representing the content of a row."""

RowsType = MutableSequence[RowContent]
"""A list of rows, where each row is a list of strings."""

ColsRowsType = tuple[ColsType, RowsType]
"""A tuple containing a list of columns and a list of rows, where each row is a list of strings."""


class MetaKey(str, Enum):
    """Keys used in the `json_schema_extra` dict of a field to customize
    its rendering.
    """

    JOIN_CHAR = "join_char"
    HEADER = "header"


def fmt_field_name(field_name: str) -> str:
    """Formats a field name for display in a table."""
    return field_name.capitalize().replace("_", " ")


# We wrap the results of commands in a Result object,
# but ONLY if we are rendering it as JSON. This makes the logic in the
# `render` module a bit of a mess, since the function type annotations
# are all over the place.
#
# Yeah, this all passes type checking and all that, but it's very Bad (tm)
# and way more complicated than it probably has to be.


T = TypeVar("T", bound=JsonValue)


class TableRenderable(BaseModel):
    """Base model that can be rendered as a table."""

    model_config = ConfigDict(populate_by_name=True)

    __title__: Optional[str] = None
    __show_lines__: bool = True
    __box__: rich.box.Box = rich.box.ROUNDED

    zabbix_version: ClassVar[Version] = Version(
        "7.0.0"
    )  # assume latest released version
    """Zabbix API version the data stems from.
    This is a class variable that can be overridden, which causes all
    subclasses to use the new value.

    This class variable is set by `State.login` based on the connected
    Zabbix server API version. Assumes latest released version by default.
    """
    legacy_json_format: ClassVar[bool] = False
    """Use the legacy JSON format when rendered as JSON.

    This class variable is set by `State.login` based on the
    current configuration. Assumes new JSON format by default."""

    empty_ok: bool = Field(default=False, exclude=True)
    """Don't print a message if table is empty when rendered as Table."""

    def _get_extra(self, field: str, key: MetaKey, default: T) -> T:
        f = self.model_fields.get(field, None)
        if not f:
            raise ValueError(f"Field {field!r} does not exist.")
        if not f.json_schema_extra or not isinstance(f.json_schema_extra, dict):
            return default
        # NOTE: this cast isn't super type safe, but we are expected to call this
        # method with the extra key constants defined above.
        #
        # If need be, we can add some sort of model validator that ensures
        # all JSON schema extra keys have the correct type.
        # But that will only happen once we actually encounter such a bug.
        return cast(T, f.json_schema_extra.get(key, default))

    def __all_fields__(self) -> dict[str, Union[FieldInfo, ComputedFieldInfo]]:
        """Returns all fields for the model, including computed fields,
        but excluding excluded fields.
        """
        all_fields: dict[str, Union[FieldInfo, ComputedFieldInfo]] = {
            **self.model_fields,
            **self.model_computed_fields,
        }
        return {n: f for n, f in all_fields.items() if not getattr(f, "exclude", False)}

    def __cols__(self) -> ColsType:
        """Returns the columns for the table representation of the object.

        Only override if you want to customize the column headers without
        overriding the rows. Otherwise, override `__cols_rows__`.

        By default, uses the name of the fields as the column headers,
        with the first letter capitalized.
        This can be overriden with `header` in `json_schema_extra`:

        >>> class User(TableRenderable):
        ...     userid: str = Field(json_schema_extra={"header" : "User ID"})
        ...     username: str = ""
        ...
        >>> User().__cols__()
        ["User ID", "Username"]
        """
        cols: list[str] = []

        for field_name, field in self.__all_fields__().items():
            if (
                field.json_schema_extra
                and isinstance(field.json_schema_extra, dict)
                and field.json_schema_extra.get(MetaKey.HEADER, None)
            ):
                cols.append(str(field.json_schema_extra[MetaKey.HEADER]))
            else:
                cols.append(fmt_field_name(field_name))
        return cols

    def __rows__(self) -> RowsType:
        r"""Returns the rows for the table representation of the object.

        Only override if you want to customize the rows without
        overriding the columns. Otherwise, override `__cols_rows__`.

        Render types in the following way:
            - TableRenderable: render as a table
            - BaseModel: render as JSON string
            - list: render as newline delimited string
        Everything else is rendered as a string.

        Example
        -------
        >>> class User(TableRenderable):
        ...     userid: str
        ...     username: str
        ...     groups: List[str] = []
        ...
        >>> User(userid="1", username="admin", groups=["foo", "bar", "baz"]).__rows__()
        [["1", "admin", "foo\nbar\nbaz"]]
        """  # noqa: D416
        fields: dict[str, Any | str] = {
            field_name: getattr(self, field_name, "")
            for field_name in self.__all_fields__()
        }
        for field_name, value in fields.items():
            if isinstance(value, TableRenderable):
                fields[field_name] = value.as_table()
            elif isinstance(value, BaseModel):
                # Fall back to rendering as JSON string
                logger.warning(
                    "Cannot render %s as a table.",
                    value.__class__.__name__,
                    stack_info=True,  # we want to know how we got here
                )
                fields[field_name] = value.model_dump_json(indent=2)
            elif isinstance(value, list):
                value = cast(list[Any], value)
                # A list either contains TableRenderable objects or stringable objects
                if value and all(isinstance(v, TableRenderable) for v in value):
                    # TableRenderables are wrapped in an AggregateResult to render them
                    # as a single table instead of a table per item.
                    # NOTE: we assume list contains items of the same type
                    # Rendering an aggregate result with mixed types is not supported
                    # and will probably break.
                    value = cast(list[TableRenderable], value)
                    fields[field_name] = AggregateResult(result=value).as_table()
                else:
                    # Other lists are rendered as newline delimited strings.
                    # The delimiter can be modified with the `JOIN_CHAR` meta-key in
                    # the field's `json_schema_extra`.
                    join_char = self._get_extra(field_name, MetaKey.JOIN_CHAR, "\n")
                    fields[field_name] = join_char.join(str(v) for v in value)
            else:
                fields[field_name] = str(value)
        return [list(fields.values())]  # must be a list of lists

    def __cols_rows__(self) -> ColsRowsType:
        """Returns the columns and rows for the table representation of the object.

        Example:
            >>> class User(TableRenderable):
            ...     userid: str = Field(json_schema_extra={"header" : "User ID"})
            ...     username: str = ""
            ...
            >>> User(userid="1", username="admin").__cols_rows__()
            (["UserID", "Username"], [["1", "admin"]])
        """
        return self.__cols__(), self.__rows__()

    def as_table(self) -> Table:
        """Renders a Rich table given the rows and cols generated for the object."""
        cols, rows = self.__cols_rows__()
        for row in rows:
            for i, cell in enumerate(row):
                row[i] = get_safe_renderable(cell)

        return get_table(
            cols=cols,
            rows=rows,
            title=self.__title__,
            show_lines=self.__show_lines__,
            box=self.__box__,
        )

    # We should implement the rich renderable protocol...


DataT = TypeVar("DataT", default=TableRenderable)


class BaseResult(TableRenderable):
    message: str = Field(default="")
    """Field that signals that the result should be printed as a message, not a table."""
    errors: list[str] = Field(default_factory=list)
    return_code: ReturnCode = ReturnCode.DONE
    table: bool = Field(default=True, exclude=True)

    model_config = ConfigDict(
        arbitrary_types_allowed=True, validate_assignment=True, extra="allow"
    )


class Result(BaseResult, Generic[DataT]):
    """A result wrapping a single data object."""

    result: Optional[Union[DataT, list[DataT]]] = None

    # https://docs.pydantic.dev/latest/concepts/serialization/#serialize_as_any-runtime-setting
    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        return super().model_dump(serialize_as_any=True, **kwargs)

    def model_dump_json(self, **kwargs: Any) -> str:
        return super().model_dump_json(serialize_as_any=True, **kwargs)


TableRenderableT = TypeVar("TableRenderableT", bound=TableRenderable)


class AggregateResult(BaseResult, Generic[TableRenderableT]):
    """Resut wrapping multiple table renderables.

    Used for compatibility with the legacy JSON format,
    as well as implementing table rendering for multiple
    results.
    """

    result: list[TableRenderableT] = Field(default_factory=list)

    def __cols_rows__(self) -> ColsRowsType:
        cols: ColsType = []
        rows: RowsType = []

        for result in self.result:
            c, r = result.__cols_rows__()
            if not cols:
                cols = c
            if r:
                rows.append(r[0])  # NOTE: why not add all rows?
        return cols, rows
