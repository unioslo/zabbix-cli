from __future__ import annotations

from pydantic import BaseModel
from rich.table import Table
from strenum import StrEnum


class ReturnCode(StrEnum):
    DONE = "Done"


class ResultType(BaseModel):
    def as_table(self) -> Table:
        table = Table()
        for field_name in self.model_fields_set:
            table.add_column(field_name)
        table.add_row(
            *[getattr(self, field_name) for field_name in self.model_fields_set]
        )
        return table


# Do we need to add some sort of sentinel value as defaults here?
class Result(ResultType):
    return_code: ReturnCode = ReturnCode.DONE
    message: str
