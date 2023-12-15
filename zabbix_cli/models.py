from __future__ import annotations

from typing import cast
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
from pydantic import validator
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


# @runtime_checkable
# class TableRenderableProto(Protocol):
#     def _table_cols_rows(self) -> ColsRowsType:
#         ...

#     def as_table(self) -> Table:
#         ...


TableRenderableProto = Union["TableRenderable", "TableRenderableDict"]


class TableRenderable(BaseModel):
    """Base model that can be rendered as a table."""

    def _table_cols_rows(self) -> ColsRowsType:
        """Returns the columns and row for the table representation of the object."""
        cols = list(self.model_fields)
        row = [str(getattr(self, field_name)) for field_name in cols]
        return cols, [row] if row else []

    def as_table(self) -> Table:
        """Renders a Rich table given the rows and cols generated for the object."""
        cols, rows = self._table_cols_rows()
        return get_table(cols, rows)

    # We should implement the rich renderable protocol...


class TableRenderableDict(RootModel[Dict[str, str]]):
    """Root model that can be used to render a dict as a table.
    Render the table vertically rather than horizontally, with
    keys as the first column and values as the second column.
    Only includes keys that have a non-empty value."""

    root: Dict[str, str] = {}

    def _table_cols_rows(self) -> ColsRowsType:
        # only returns the keys that have a value
        cols = ["Key", "Value"]
        rows = [[k, str(v)] for k, v in self.root.items() if v]
        return cols, rows

    def as_table(self) -> Table:
        """Renders a Rich table given the rows and cols generated for the object."""
        cols, rows = self._table_cols_rows()
        return get_table(cols, rows)


DataT = TypeVar("DataT", bound=BaseModel)


class Result(TableRenderable, Generic[DataT]):
    message: str = Field(default="")
    """Field that signals that the result should be printed as a message, not a table."""
    errors: List[str] = Field(default_factory=list)
    return_code: ReturnCode = ReturnCode.DONE
    result: Optional[Union[DataT, List[DataT]]] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True, validate_assignment=True, extra="allow"
    )


TableRenderableT = TypeVar("TableRenderableT", bound=TableRenderable)


class AggregateResult(Result[TableRenderableT]):
    """Aggregate result of multiple results.

    Used for compatibility with the legacy JSON format."""

    @validator("result")
    def _result_must_be_list(cls, v: object) -> List[DataT]:
        if not isinstance(v, list):
            raise ValueError("AggregateResult result must be a list")
        return v

    def _table_cols_rows(self) -> ColsRowsType:
        cols = []  # type: ColsType
        rows = []  # type: RowsType

        # Mypy doesn't understand validator ensured this is a list
        self.result = cast(List[TableRenderableT], self.result)

        for result in self.result:
            c, r = result._table_cols_rows()
            if not cols:
                cols = c
            if r:
                rows.append(r[0])
        return cols, rows
