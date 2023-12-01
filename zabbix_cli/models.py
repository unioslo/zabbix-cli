from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from pydantic import Field
from rich.table import Table
from strenum import StrEnum


class ReturnCode(StrEnum):
    DONE = "Done"


ColsRowType = tuple[list[str], list[str]]


class ResultType(BaseModel):
    message: str = ""
    """Field that signals that the result should be printed as a message, not a table."""

    def _table_cols_row(self) -> ColsRowType:
        """Returns the columns and row for the table representation of this object."""
        cols = list(self.model_fields)
        row = [str(getattr(self, field_name)) for field_name in cols]
        return cols, row

    def as_table(self) -> Table:
        # TODO: figure out how to render data field in a structured way :)))
        table = Table()
        cols, row = self._table_cols_row()
        for col in cols:
            table.add_column(col)
        table.add_row(*row)
        return table


class Result(ResultType):
    data: Optional[BaseModel] = Field(None, exclude=True)  # TODO: remove?
    return_code: ReturnCode = ReturnCode.DONE
