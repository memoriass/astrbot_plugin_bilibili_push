from __future__ import annotations

import astrbot.api.message_components as Comp
from astrbot.api import logger

from .results import WorkflowResult


async def render_workflow_result(event, renderer, result: WorkflowResult):
    if not result.cards:
        return event.plain_result(result.text)

    segments = [Comp.Plain(result.text)]
    failed = False
    for card in result.cards:
        try:
            img_bytes = await renderer.render(
                card.template_name,
                card.templates,
                viewport=card.viewport,
                selector=card.selector,
            )
            segments.append(Comp.Image.fromBytes(img_bytes))
        except Exception as exc:
            failed = True
            logger.error(f"Workflow card render failed: {exc}", exc_info=True)

    if failed and len(segments) == 1:
        return event.plain_result(f"{result.text}\n\n卡片渲染失败，已返回文本结果。")
    if failed:
        segments[0] = Comp.Plain(f"{result.text}\n\n部分卡片渲染失败。")
    return event.chain_result(segments)
