from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import Dict
from typing import List
from typing import Union

from pydantic import Field
from pydantic import computed_field
from pydantic import field_serializer

from zabbix_cli.models import TableRenderable
from zabbix_cli.pyzabbix.types import HostGroup
from zabbix_cli.pyzabbix.types import Template
from zabbix_cli.pyzabbix.types import TemplateGroup

if TYPE_CHECKING:
    from zabbix_cli.models import ColsRowsType
    from zabbix_cli.models import RowsType


class ShowTemplateGroupResult(TableRenderable):
    """Result type for templategroup."""

    groupid: str = Field(..., json_schema_extra={"header": "Group ID"})
    name: str
    templates: List[Template] = []
    show_templates: bool = Field(True, exclude=True)

    @classmethod
    def from_result(
        cls, group: Union[HostGroup, TemplateGroup], show_templates: bool
    ) -> ShowTemplateGroupResult:
        return cls(
            groupid=group.groupid,
            name=group.name,
            templates=group.templates,
            show_templates=show_templates,
        )

    @computed_field
    @property
    def template_count(self) -> int:
        return len(self.templates)

    @field_serializer("templates")
    def templates_serializer(self, value: List[Template]) -> List[Dict[str, Any]]:
        if self.show_templates:
            return [t.model_dump(mode="json") for t in value]
        return []

    def __rows__(self) -> RowsType:
        tpls = self.templates if self.show_templates else []
        return [
            [
                self.groupid,
                self.name,
                "\n".join(str(t.host) for t in sorted(tpls, key=lambda t: t.host)),
                str(self.template_count),
            ]
        ]


class ExtendTemplateGroupResult(TableRenderable):
    source: str
    destination: List[str]
    templates: List[str]

    @classmethod
    def from_result(
        cls,
        src_group: Union[HostGroup, TemplateGroup],
        dest_group: Union[List[HostGroup], List[TemplateGroup]],
        templates: List[Template],
    ) -> ExtendTemplateGroupResult:
        return cls(
            source=src_group.name,
            destination=[grp.name for grp in dest_group],
            templates=[t.host for t in templates],
        )


class MoveTemplatesResult(TableRenderable):
    """Result type for `move_templates` command."""

    source: str
    destination: str
    templates: List[str]

    @classmethod
    def from_result(
        cls,
        source: Union[HostGroup, TemplateGroup],
        destination: Union[HostGroup, TemplateGroup],
    ) -> MoveTemplatesResult:
        return cls(
            source=source.name,
            destination=destination.name,
            templates=[template.host for template in source.templates],
        )

    def __cols_rows__(self) -> ColsRowsType:
        """Only print the template names in the table.

        Source and destination are apparent from the surrounding context.
        """
        cols = ["Templates"]
        rows: RowsType = [["\n".join(self.templates)]]
        return cols, rows
