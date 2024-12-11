from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Optional


class BasePatcher(ABC):
    """Context manager that logs and prints diagnostic info if an exception
    occurs.
    """

    def __init__(self, description: str) -> None:
        self.description = description

    @abstractmethod
    def __package_info__(self) -> str:
        raise NotImplementedError

    def __enter__(self) -> BasePatcher:
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:
        if not exc_type:
            return True
        import sys

        import rich
        from rich.table import Table

        from zabbix_cli.__about__ import __version__

        # Rudimentary, but provides enough info to debug and fix the issue
        console = rich.console.Console(stderr=True)
        console.print_exception()
        console.print()
        table = Table(
            title="Diagnostics",
            show_header=False,
            show_lines=False,
        )
        table.add_row(
            "[b]Package [/]",
            self.__package_info__(),
        )
        table.add_row(
            "[b]zabbix-cli [/]",
            __version__,
        )
        table.add_row(
            "[b]Python [/]",
            sys.version,
        )
        table.add_row(
            "[b]Platform [/]",
            sys.platform,
        )
        console.print(table)
        console.print(f"[bold red]ERROR: Failed to patch {self.description}[/]")
        raise SystemExit(1)


def get_patcher(info: str) -> type[BasePatcher]:
    """Returns a patcher for a given package."""

    class Patcher(BasePatcher):
        def __package_info__(self) -> str:
            return info

    return Patcher
