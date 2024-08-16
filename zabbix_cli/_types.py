from __future__ import annotations

import sys

if sys.version_info >= (3, 10):
    from types import EllipsisType

    EllipsisType = EllipsisType
else:
    from typing import Any

    EllipsisType = Any
