from __future__ import annotations

from astrbot.api import AstrBotConfig
from astrbot.api.event import AstrMessageEvent
from astrbot.core.star.filter.custom_filter import CustomFilter

from .parsing_pending import workflow_from_pending_event
from .parsing_natural import workflow_from_natural_language
from .runtime import event_message_text


class BiliPendingShortcutFilter(CustomFilter):
    def filter(self, event: AstrMessageEvent, cfg: AstrBotConfig) -> bool:
        return workflow_from_pending_event(event) is not None


class BiliNaturalWorkflowFilter(CustomFilter):
    def filter(self, event: AstrMessageEvent, cfg: AstrBotConfig) -> bool:
        if not getattr(event, "is_wake", False):
            return False
        return workflow_from_natural_language(event_message_text(event)) is not None
