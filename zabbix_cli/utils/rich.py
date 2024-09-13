from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rich.errors import MarkupError
from rich.text import Text

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from rich.console import RenderableType


def get_safe_renderable(renderable: RenderableType) -> RenderableType:
    """Ensure that the renderable can be rendered without raising an exception."""
    if isinstance(renderable, str):
        return get_text(renderable)
    return renderable


def get_text(text: str, log: bool = True) -> Text:
    """Interpret text as markup-styled text, or plain text if it fails."""
    try:
        return Text.from_markup(text)
    except MarkupError as e:
        # Log this so that we can more easily debug incorrect rendering
        # In most cases, this will be due to some Zabbix item key that looks
        # like a markup tag, e.g. `system.cpu.load[percpu,avg]`
        # but we need to log it nonetheless for other cases
        # However, we don't want to log when we're removing markup
        # from log records, so we have a `log` parameter to control this.
        if log:
            logger.debug("Markup error when rendering text: '%s': %s", text, e)
        return Text(text)
