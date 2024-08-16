from __future__ import annotations

from typing import List
from typing import Literal
from typing import Set
from typing import Union

from zabbix_cli.models import TableRenderable
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import HostGroup
from zabbix_cli.pyzabbix.types import Template
from zabbix_cli.pyzabbix.types import TemplateGroup


class LinkTemplateToHostResult(TableRenderable):
    host: str
    templates: List[str]
    action: str

    @classmethod
    def from_result(
        cls,
        templates: List[Template],
        host: Host,
        action: str,
    ) -> LinkTemplateToHostResult:
        to_link: Set[str] = set()  # names of templates to link
        for t in templates:
            for h in t.hosts:
                if h.host == host.host:
                    break
            else:
                to_link.add(t.host)
        return cls(
            host=host.host,
            templates=sorted(to_link),
            action=action,
        )


class UnlinkTemplateFromHostResult(TableRenderable):
    host: str
    templates: List[str]
    action: str

    @classmethod
    def from_result(
        cls,
        templates: List[Template],
        host: Host,
        action: str,
    ) -> UnlinkTemplateFromHostResult:
        """Only show templates that are actually unlinked."""
        to_remove: Set[str] = set()
        for t in templates:
            for h in t.hosts:
                if h.host == host.host:
                    to_remove.add(t.host)  # name of template
                    break
        return cls(
            host=host.host,
            templates=list(to_remove),
            action=action,
        )


class LinkTemplateResult(TableRenderable):
    """Result type for (un)linking templates to templates."""

    source: List[str]
    destination: List[str]
    action: str

    @classmethod
    def from_result(
        cls,
        source: List[Template],
        destination: List[Template],
        action: Literal["Link", "Unlink", "Unlink and clear"],
    ) -> LinkTemplateResult:
        return cls(
            source=[t.host for t in source],
            destination=[t.host for t in destination],
            action=action,
        )


class TemplateGroupResult(TableRenderable):
    templates: List[str]
    groups: List[str]

    @classmethod
    def from_result(
        cls,
        templates: List[Template],
        groups: Union[List[TemplateGroup], List[HostGroup]],
    ) -> TemplateGroupResult:
        return cls(
            templates=[t.host for t in templates],
            groups=[h.name for h in groups],
        )


class RemoveTemplateFromGroupResult(TableRenderable):
    group: str
    templates: List[str]

    @classmethod
    def from_result(
        cls,
        templates: List[Template],
        group: Union[TemplateGroup, HostGroup],
    ) -> RemoveTemplateFromGroupResult:
        to_remove: Set[str] = set()
        for template in group.templates:
            for t in templates:
                if t.host == template.host:
                    to_remove.add(t.host)
                    break
        return cls(
            templates=list(to_remove),
            group=group.name,
        )
