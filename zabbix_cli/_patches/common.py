from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Optional, Type


class BasePatcher(ABC):
    """Context manager that logs and prints diagnostic info if an exception
    occurs."""

    def __init__(self, description: str) -> None:
        self.description = description

    @abstractmethod
    def __package_info__(self) -> str:
        raise NotImplementedError

    def __enter__(self) -> BasePatcher:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:
        if not exc_type:
            return True
        import rich
        import sys

        # Rudimentary, but provides enough info to debug and fix the issue
        console = rich.console.Console(stderr=True)
        console.print_exception()
        console.print(f"[bold red]Failed to patch [i]{self.description}[/][/]")
        console.print(self.__package_info__())
        console.print(f"Python version: {sys.version}")

        return True


def get_patcher(info: str) -> Type[BasePatcher]:
    """Returns a patcher instance."""

    class Patcher(BasePatcher):
        def __package_info__(self) -> str:
            return info

    return Patcher
