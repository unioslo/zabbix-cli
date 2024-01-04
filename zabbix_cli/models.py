from __future__ import annotations

from typing import Dict
from typing import Generic
from typing import List
from typing import Optional
from typing import Tuple
from typing import TypeVar
from typing import Union

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import RootModel
from pydantic.fields import ComputedFieldInfo
from pydantic.fields import FieldInfo
from rich.table import Table
from strenum import StrEnum

from zabbix_cli.table import get_table


class ReturnCode(StrEnum):
    DONE = "Done"
    ERROR = "Error"


ColsType = List[str]
"""A list of column headers."""

RowsType = List[List[str]]
"""A list of rows, where each row is a list of strings."""

ColsRowsType = Tuple[List[str], List[List[str]]]
"""A tuple containing a list of columns and a list of rows, where each row is a list of strings."""


def fmt_field_name(field_name: str) -> str:
    """Formats a field name for display in a table."""
    return field_name.capitalize().replace("_", " ")


# FIXME: this suddenly became a HUGE mess with the introduction of
# the RootModel type (TableRenderableDict), which necessitated implementing
# the table rendering protocol to declare that both it and TableRenderable
# can be rendered as a table. However, for a lot of methods just annotating
# with TableRenderableProto is not enough, because we often need to access
# pydantic methods and attributes that are not part of the protocol.
#
# Furthermore, we also wrap the results of commands in a Result object,
# but ONLY if we are rendering it as JSON. This makes the logic in the
# `render` module a bit of a mess, since the function type annotations
# are all over the place.
#
# Yeah, this all passes type checking and all that, but it's very Bad (tm)
# and way more complicated than it probably has to be.


class TableRenderable(BaseModel):
    """Base model that can be rendered as a table."""

    model_config = ConfigDict(populate_by_name=True)

    __title__: Optional[str] = None

    def __all_fields__(self) -> Dict[str, Union[FieldInfo, ComputedFieldInfo]]:
        """Returns all fields for the model, including computed fields,
        but excluding fields that have `exclude=True` set."""
        all_fields = {
            **self.model_fields,
            **self.model_computed_fields,
        }  # type: Dict[str, Union[FieldInfo, ComputedFieldInfo]]
        return {n: f for n, f in all_fields.items() if not getattr(f, "exclude", False)}

    def __cols__(self) -> ColsType:
        """Returns the columns for the table representation of the object.

        Only override if you want to customize the column headers without
        overriding the rows. Otherwise, override `__cols_rows__`.

        By default, uses the name of the fields as the column headers,
        with the first letter capitalized. This can be overriden with `header` in `json_schema_extra`:

        >>> class User(TableRenderable):
        ...     userid: str = Field(json_schema_extra={"header" : "UserID"})
        ...     username: str = ""
        ...
        >>> User().__cols__()
        ["UserID", "Username"]
        """
        cols = []

        for field_name, field in self.__all_fields__().items():
            if getattr(field, "exclude", False):  # computed fields can't be excluded
                continue
            if (
                field.json_schema_extra
                and isinstance(field.json_schema_extra, dict)
                and field.json_schema_extra.get("header", None)
            ):
                cols.append(str(field.json_schema_extra["header"]))
            else:
                cols.append(fmt_field_name(field_name))
        return cols

    def __rows__(self) -> RowsType:
        """Returns the rows for the table representation of the object.

        Only override if you want to customize the rows without
        overriding the columns. Otherwise, override `__cols_rows__`.

        Render types in the following way:
            - TableRenderable: render as a table
            - TableRenderableDict: render as a table
            - BaseModel: render as JSON string
            - list: render as newline delimited string
        Everything else is rendered as a string.

        Example:

        >>> class User(TableRenderable):
        ...     userid: str = Field(json_schema_extra={"header" : "UserID"})
        ...     username: str = ""
        ...
        >>> User(userid="1", username="admin").__rows__()
        [["1", "admin"]]
        """
        row = [getattr(self, field_name, "") for field_name in self.__all_fields__()]
        for i, value in enumerate(row):
            if isinstance(value, (TableRenderable, TableRenderableDict)):
                row[i] = value.as_table()
            elif isinstance(value, BaseModel):
                row[i] = value.model_dump_json(indent=2)
            elif isinstance(value, list):
                row[i] = "\n".join(str(v) for v in value)
            else:
                row[i] = str(value)
        return [row]

    def __cols_rows__(self) -> ColsRowsType:
        """Returns the columns and row for the table representation of the object.

        Example:

        >>> class User(TableRenderable):
        ...     userid: str = Field(json_schema_extra={"header" : "UserID"})
        ...     username: str = ""
        ...
        >>> User(userid="1", username="admin").__cols_rows__()
        (["UserID", "Username"], [["1", "admin"]])
        """
        return self.__cols__(), self.__rows__()

    def as_table(self) -> Table:
        """Renders a Rich table given the rows and cols generated for the object."""
        cols, rows = self.__cols_rows__()
        return get_table(cols=cols, rows=rows, title=self.__title__)

    # We should implement the rich renderable protocol...


class TableRenderableDict(RootModel[Dict[str, str]]):
    """Root model that can be used to render a dict as a table.
    Render the table vertically rather than horizontally, with
    keys as the first column and values as the second column.
    Only includes keys that have a non-empty value."""

    root: Dict[str, str] = {}

    def __cols_rows__(self) -> ColsRowsType:
        # only returns the keys that have a value
        cols = ["Key", "Value"]
        rows = [[k, str(v)] for k, v in self.root.items() if v]
        return cols, rows

    def as_table(self) -> Table:
        """Renders a Rich table given the rows and cols generated for the object."""
        cols, rows = self.__cols_rows__()
        return get_table(cols, rows)


DataT = TypeVar("DataT")


class ResultBase(TableRenderable):
    message: str = Field(default="")
    """Field that signals that the result should be printed as a message, not a table."""
    errors: List[str] = Field(default_factory=list)
    return_code: ReturnCode = ReturnCode.DONE

    model_config = ConfigDict(
        arbitrary_types_allowed=True, validate_assignment=True, extra="allow"
    )


class Result(ResultBase, Generic[DataT]):
    result: Optional[Union[DataT, List[DataT]]] = None


TableRenderableT = TypeVar("TableRenderableT", bound=TableRenderable)
TableRenderableProto = Union["TableRenderable", "TableRenderableDict"]


class AggregateResult(ResultBase, Generic[TableRenderableT]):
    """Aggregate result of multiple results.

    Used for compatibility with the legacy JSON format,
    as well as implementing table rendering for multiple
    results."""

    result: List[TableRenderableT] = Field(default_factory=list)

    def __cols_rows__(self) -> ColsRowsType:
        cols = []  # type: ColsType
        rows = []  # type: RowsType

        for result in self.result:
            c, r = result.__cols_rows__()
            if not cols:
                cols = c
            if r:
                rows.append(r[0])
        return cols, rows
