from __future__ import annotations

from typing import Any

from astrbot.api.event import AstrMessageEvent


def event_origin(event: AstrMessageEvent) -> str:
    return str(
        getattr(event, "unified_msg_origin", "")
        or getattr(event, "session_id", "")
        or "",
    )


def event_message_text(event: AstrMessageEvent) -> str:
    getter = getattr(event, "get_message_str", None)
    if callable(getter):
        return str(getter() or "")
    return str(getattr(event, "message_str", "") or "")


def message_event_from_tool_arg(event: Any) -> AstrMessageEvent:
    context = getattr(event, "context", None)
    actual_event = getattr(context, "event", None)
    return actual_event or event
