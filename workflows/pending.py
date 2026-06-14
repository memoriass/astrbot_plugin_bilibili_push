from __future__ import annotations

import re
import secrets
import time

from .models import CANCEL_REPLIES, CONFIRM_REPLIES, WorkflowRequest
from .runtime import event_message_text, event_origin
from .utils import normalize_reply


TASK_PREFIX = "bili"


def store_pending_task(
    plugin,
    event,
    request: WorkflowRequest,
    *,
    kind: str,
    payload: dict,
) -> str:
    task_id = f"{TASK_PREFIX}{secrets.token_hex(4)}"
    task = {
        "task_id": task_id,
        "kind": kind,
        "origin": event_origin(event),
        "workflow": request.workflow,
        "request": {
            "workflow": request.workflow,
            "target": request.target,
            "params": dict(request.params),
        },
        "created_at": time.time(),
        **payload,
    }
    plugin.create_bili_pending_task(task)
    return task_id


async def run_continue_pending(plugin, event, request: WorkflowRequest) -> str:
    task_ref = _task_ref_from_request_or_text(request, event_message_text(event))
    if not task_ref:
        return "继续任务需要 task_id，例如 `bili1a2b 1`。"

    task_id, matches = plugin.resolve_bili_pending_task_id(
        task_ref,
        origin=event_origin(event),
    )
    if matches:
        return f"任务ID片段 `{task_ref}` 匹配多个任务：{', '.join(matches[:5])}。请多输入几位。"
    if not task_id:
        return f"任务不存在或已过期：{task_ref}"

    task = plugin.get_bili_pending_task(task_id)
    if not task:
        return f"任务不存在或已过期：{task_ref}"

    action = _action_from_request_or_text(request, event_message_text(event), task_ref)
    if task.get("kind") == "up_candidates":
        return await _continue_candidates(plugin, event, request, task_id, task, action)
    if task.get("kind") == "confirm_add_subscription":
        return await _continue_confirm(plugin, event, task_id, task, action)
    return f"未知任务类型：{task.get('kind')}"


async def _continue_candidates(plugin, event, request, task_id: str, task: dict, action: str) -> str:
    if normalize_reply(action) in CANCEL_REPLIES:
        plugin.delete_bili_pending_task(task_id)
        return f"已取消任务：{task_id}"

    candidates = task.get("candidates") or []
    index = _choice_index(action, len(candidates))
    if index is None:
        return f"请回复 1-{len(candidates)} 的序号，或发送 `bili{task_id[-4:]} 取消`。"

    candidate = candidates[index]
    plugin.delete_bili_pending_task(task_id)
    if task.get("mode") != "add_subscription":
        return f"已选择：{candidate.get('username')} | UID={candidate.get('uid')}"

    from .subscription import build_confirm_task

    next_request = WorkflowRequest(
        workflow="add_subscription",
        target=str(candidate.get("uid") or ""),
        params={"sub_type": task.get("sub_type") or "dynamic"},
        source=request.source,
    )
    return build_confirm_task(plugin, event, next_request, candidate)


async def _continue_confirm(plugin, event, task_id: str, task: dict, action: str) -> str:
    normalized = normalize_reply(action)
    if normalized in CANCEL_REPLIES:
        plugin.delete_bili_pending_task(task_id)
        return f"已取消任务：{task_id}"
    if normalized not in CONFIRM_REPLIES:
        return f"请发送 `bili{task_id[-4:]} 确认` 或 `bili{task_id[-4:]} 取消`。"

    candidate = task.get("candidate") or {}
    uid = str(candidate.get("uid") or "")
    sub_type = str(task.get("sub_type") or "dynamic")
    plugin.delete_bili_pending_task(task_id)

    from .subscription import add_subscription_by_uid

    return await add_subscription_by_uid(plugin, event, uid, sub_type)


def extract_task_ref(text: str) -> str:
    match = re.search(
        r"(?<![0-9A-Za-z_\u4e00-\u9fff])bili([0-9a-fA-F]{3,8})(?![0-9A-Za-z_\u4e00-\u9fff])",
        str(text or ""),
    )
    return f"bili{match.group(1).lower()}" if match else ""


def _task_ref_from_request_or_text(request: WorkflowRequest, text: str) -> str:
    for key in ("task_id", "task", "id", "target"):
        value = request.params.get(key) if key != "target" else request.target
        extracted = extract_task_ref(str(value or ""))
        if extracted:
            return extracted
    return extract_task_ref(text)


def _action_from_request_or_text(request: WorkflowRequest, text: str, task_ref: str) -> str:
    for key in ("choice", "selection", "index", "action", "confirm"):
        value = request.params.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    cleaned = str(text or "").replace(task_ref, "", 1).strip()
    return cleaned or str(request.target or "").strip()


def _choice_index(action: str, max_index: int) -> int | None:
    normalized = normalize_reply(action)
    if normalized in CANCEL_REPLIES:
        return None
    match = re.search(r"(?:选|选择|第)?\s*(\d{1,2})\s*(?:个|项)?", str(action or ""))
    if not match:
        return None
    value = int(match.group(1))
    if not 1 <= value <= max_index:
        return None
    return value - 1
