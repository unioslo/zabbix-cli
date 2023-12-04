from __future__ import annotations

from typing import ClassVar
from typing import List
from typing import Tuple

from packaging.version import Version
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from rich.table import Table
from strenum import StrEnum


class ReturnCode(StrEnum):
    DONE = "Done"
    ERROR = "Error"


ColsRowsType = Tuple[List[str], List[List[str]]]


class Result(BaseModel):
    _version: ClassVar[Version] = Version("6.4.0")  # assume latest released version
    """Zabbix API version the data stems from.
    This is a class variable that can be overridden, which causes all
    subclasses to use the new value when accessed.

    WARNING: Do not access directly from outside this class.
    Prefer the `version` property instead.
    """
    message: str = Field(default="")
    """Field that signals that the result should be printed as a message, not a table."""
    return_code: ReturnCode = ReturnCode.DONE

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)

    @property
    def version(self) -> Tuple[int, ...]:
        """Zabbix API version release tuple."""
        return Result._version.release

    @version.setter
    def version(self, version: Version) -> None:
        Result._version = version

    def _table_cols_rows(self) -> ColsRowsType:
        """Returns the columns and row for the table representation of the object."""
        cols = list(self.model_fields)
        row = [str(getattr(self, field_name)) for field_name in cols]
        return cols, [row]

    def as_table(self) -> Table:
        """Renders a Rich table given the rows and cols generated for the object."""
        # TODO: figure out how to render data field in a structured way :)))
        table = Table()
        cols, rows = self._table_cols_rows()
        for col in cols:
            table.add_column(col)
        for row in rows:
            table.add_row(*row)
            table.add_section()
        return table


class AggregateResult(Result):  # NOTE: make generic?
    """Aggregate result of multiple results."""

    result: List[Result] = []

    def _table_cols_rows(self) -> ColsRowsType:
        cols = []  # type: list[str]
        rows = []  # type: list[list[str]]
        for result in self.result:
            c, r = result._table_cols_rows()
            if not cols:
                cols = c
            if r:
                rows.append(r[0])
        return cols, rows
