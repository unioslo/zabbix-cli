from __future__ import annotations

from collections import deque
from dataclasses import field
from datetime import datetime
from typing import Iterator
from typing import Optional

import click
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import NaiveDatetime


class HistoryEntry(BaseModel):
    ctx: click.Context
    timestamp: NaiveDatetime = field(default_factory=datetime.now)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class History:
    """A log of HTTP responses."""

    instance: Optional[History] = None
    entries: deque[HistoryEntry] = deque()

    def __new__(cls, max_logs: int | None = None) -> History:
        """Return the singleton instance of the log."""
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def add(self, entry: click.Context) -> None:
        """Add a new entry to the log."""
        self.entries.append(HistoryEntry(ctx=entry))

    def resize(self, max_logs: int) -> None:
        """Resize the log to the specified maximum number of entries."""
        self.entries = deque(self.entries, maxlen=max_logs)

    def clear(self) -> None:
        """Clear the log."""
        self.entries.clear()

    def __iter__(self) -> Iterator[HistoryEntry]:
        """Return an iterator over the entries in the log."""
        return iter(self.entries)

    def __getitem__(self, index: int) -> HistoryEntry:
        """Return the entry at the specified index."""
        return self.entries[index]

    def __len__(self) -> int:
        """Return the number of entries in the log."""
        return len(self.entries)
