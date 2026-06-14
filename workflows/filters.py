from __future__ import annotations

from typing import Any

from astrbot.api import AstrBotConfig
from astrbot.api.event import AstrMessageEvent
from astrbot.core.star.filter.custom_filter import CustomFilter

from .parsing_command import workflow_from_pending_shortcut


class BiliPendingShortcutFilter(CustomFilter):
    def filter(self, event: AstrMessageEvent, cfg: AstrBotConfig) -> bool:
        text = _message_text(event)
        if not text:
            return False
        return workflow_from_pending_shortcut(text) is not None


def _message_text(event: Any) -> str:
    getter = getattr(event, "get_message_str", None)
    if callable(getter):
        return str(getter() or "")
    return str(getattr(event, "message_str", "") or "")
