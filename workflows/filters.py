from __future__ import annotations

from astrbot.api import AstrBotConfig
from astrbot.api.event import AstrMessageEvent
from astrbot.core.star.filter.custom_filter import CustomFilter

from .parsing_command import workflow_from_pending_event


class BiliPendingShortcutFilter(CustomFilter):
    def filter(self, event: AstrMessageEvent, cfg: AstrBotConfig) -> bool:
        return workflow_from_pending_event(event) is not None
