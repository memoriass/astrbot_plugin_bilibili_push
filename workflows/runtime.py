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


def event_reply_texts(event: AstrMessageEvent) -> list[str]:
    messages = getattr(getattr(event, "message_obj", None), "message", None) or []
    texts = []
    for component in messages:
        if component.__class__.__name__ != "Reply":
            continue
        message = getattr(component, "message_str", "") or ""
        if message:
            texts.append(str(message))
    return texts


def message_event_from_tool_arg(event: Any) -> AstrMessageEvent:
    context = getattr(event, "context", None)
    actual_event = getattr(context, "event", None)
    return actual_event or event
