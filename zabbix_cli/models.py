from __future__ import annotations

from typing import Dict
from typing import Generic
from typing import List
from typing import Optional
from typing import Protocol
from typing import runtime_checkable
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
# Yeah, this all passes type checking and all that, but it's very inelegant
# and way more complicated than it probably has to be.


@runtime_checkable
class TableRenderableProto(Protocol):
    def _table_cols_rows(self) -> ColsRowsType:
        ...

    def as_table(self) -> Table:
        ...


class TableRenderable(BaseModel):
    """Base model that can be rendered as a table."""

    def _table_cols_rows(self) -> ColsRowsType:
        """Returns the columns and row for the table representation of the object."""
        cols = list(self.model_fields)
        row = [str(getattr(self, field_name)) for field_name in cols]
        return cols, [row] if row else []

    def as_table(self) -> Table:
        """Renders a Rich table given the rows and cols generated for the object."""
        # TODO: figure out how to render data field in a structured way :)))
        table = Table()
        cols, rows = self._table_cols_rows()
        for col in cols:
            table.add_column(col, overflow="fold")
        for row in rows:
            table.add_row(*row)
            table.add_section()
        return table

    # We should implement the rich renderable protocol...


class TableRenderableDict(RootModel[Dict[str, str]]):
    """Root model that can be used to render a dict as a table.
    Only includes keys that have a non-empty value."""

    root: Dict[str, str] = {}

    def _table_cols_rows(self) -> ColsRowsType:
        # only returns the keys that have a value
        cols = [k for k, v in self.root.items() if v]
        row = [self.root[k] for k in cols]
        return cols, [row] if row else []

    as_table = TableRenderable.as_table


DataT = TypeVar("DataT", bound=BaseModel)


class Result(TableRenderable, Generic[DataT]):
    message: str = Field(default="")
    errors: List[str] = Field(default_factory=list)
    """Field that signals that the result should be printed as a message, not a table."""
    return_code: ReturnCode = ReturnCode.DONE
    result: Optional[Union[DataT, List[DataT]]] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True, validate_assignment=True, extra="allow"
    )


TableRenderableT = TypeVar("TableRenderableT", bound=TableRenderable)


class AggregateResult(Result[TableRenderableT]):
    """Aggregate result of multiple results."""

    @validator("result")
    def _result_must_be_list(cls, v: object) -> List[DataT]:
        if not isinstance(v, list):
            raise ValueError("result must be a list")
        return v

    def _table_cols_rows(self) -> ColsRowsType:
        cols = []  # type: ColsType
        rows = []  # type: RowsType

        # Kind of unfortunate assertions due to type of result in superclass
        assert self.result is not None
        assert isinstance(self.result, list)

        for result in self.result:
            c, r = result._table_cols_rows()
            if not cols:
                cols = c
            if r:
                rows.append(r[0])
        return cols, rows
