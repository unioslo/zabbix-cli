from __future__ import annotations

from typing import Literal
from typing import Union

from zabbix_cli.models import TableRenderable
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import HostGroup
from zabbix_cli.pyzabbix.types import Template
from zabbix_cli.pyzabbix.types import TemplateGroup


class LinkTemplateToHostResult(TableRenderable):
    host: str
    templates: list[str]
    action: str

    @classmethod
    def from_result(
        cls,
        templates: list[Template],
        host: Host,
        action: str,
    ) -> LinkTemplateToHostResult:
        to_link: set[str] = set()  # names of templates to link
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
    templates: list[str]
    action: str

    @classmethod
    def from_result(
        cls,
        templates: list[Template],
        host: Host,
        action: str,
    ) -> UnlinkTemplateFromHostResult:
        """Only show templates that are actually unlinked."""
        to_remove: set[str] = set()
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

    source: list[str]
    destination: list[str]
    action: str

    @classmethod
    def from_result(
        cls,
        source: list[Template],
        destination: list[Template],
        action: Literal["Link", "Unlink", "Unlink and clear"],
    ) -> LinkTemplateResult:
        return cls(
            source=[t.host for t in source],
            destination=[t.host for t in destination],
            action=action,
        )


class TemplateGroupResult(TableRenderable):
    templates: list[str]
    groups: list[str]

    @classmethod
    def from_result(
        cls,
        templates: list[Template],
        groups: Union[list[TemplateGroup], list[HostGroup]],
    ) -> TemplateGroupResult:
        return cls(
            templates=[t.host for t in templates],
            groups=[h.name for h in groups],
        )


class RemoveTemplateFromGroupResult(TableRenderable):
    group: str
    templates: list[str]

    @classmethod
    def from_result(
        cls,
        templates: list[Template],
        group: Union[TemplateGroup, HostGroup],
    ) -> RemoveTemplateFromGroupResult:
        to_remove: set[str] = set()
        for template in group.templates:
            for t in templates:
                if t.host == template.host:
                    to_remove.add(t.host)
                    break
        return cls(
            templates=list(to_remove),
            group=group.name,
        )
