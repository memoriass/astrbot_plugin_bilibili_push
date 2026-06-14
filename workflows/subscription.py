from __future__ import annotations

from ..database.db_manager import Subscription
from .formatting import format_candidates
from .models import WorkflowRequest
from .pending import store_pending_task
from .runtime import event_origin
from .search import search_up_candidates
from .utils import first_text, is_uid, normalize_sub_type


async def run_add_subscription(plugin, event, request: WorkflowRequest) -> str:
    payload = {"target": request.target, **request.params}
    target = first_text(payload, "uid", "target", "mid")
    sub_type = normalize_sub_type(first_text(payload, "sub_type", "type") or "dynamic")
    if is_uid(target):
        return await add_subscription_by_uid(plugin, event, target, sub_type)

    keyword = first_text(payload, "keyword", "query", "name") or target
    if not keyword:
        return "请提供 UP 主 UID 或搜索关键词。"

    candidates, error = await search_up_candidates(keyword)
    if error:
        return error
    if not candidates:
        return f"未找到关键词“{keyword}”对应的 UP 主。"

    task_id = store_pending_task(
        plugin,
        event,
        request,
        kind="up_candidates",
        payload={
            "keyword": keyword,
            "candidates": candidates,
            "mode": "add_subscription",
            "sub_type": sub_type,
        },
    )
    return (
        format_candidates(candidates, title=f"请选择要订阅的 UP（{keyword}）")
        + f"\n\n任务ID: {task_id}\n"
        + f"发送 `bili{task_id[-4:]} <序号>` 选择候选；选择后还需要确认才会写入订阅。"
    )


async def add_subscription_by_uid(plugin, event, uid: str, sub_type: str) -> str:
    if sub_type not in {"dynamic", "live", "both"}:
        return "sub_type 仅支持 dynamic、live 或 both。"

    user_info = await plugin.parser.get_user_info(uid)
    if not user_info:
        return f"无法获取 UID={uid} 的用户信息。"

    types = ["dynamic", "live"] if sub_type == "both" else [sub_type]
    target_id = event_origin(event)
    existing = plugin.db.get_subscriptions(target_id)
    messages = []
    for one_type in types:
        if any(sub.uid == str(uid) and sub.sub_type == one_type for sub in existing):
            messages.append(f"订阅已存在：{user_info['username']} ({uid}) [{one_type}]")
            continue
        sub = Subscription(
            uid=uid,
            username=user_info["username"],
            sub_type=one_type,
            target_id=target_id,
            categories=_default_categories(one_type),
            tags=[],
            enabled=True,
        )
        if plugin.db.add_subscription(sub):
            messages.append(f"已添加订阅：{user_info['username']} ({uid}) [{one_type}]")
        else:
            messages.append(f"写入订阅失败或已存在：{user_info['username']} ({uid}) [{one_type}]")
    return "\n".join(messages)


def run_remove_subscription(plugin, event, request: WorkflowRequest) -> str:
    payload = {"target": request.target, **request.params}
    uid = first_text(payload, "uid", "target", "mid")
    sub_type = normalize_sub_type(first_text(payload, "sub_type", "type") or "dynamic")
    if not is_uid(uid):
        return "删除订阅需要明确 UID。"
    if sub_type == "both":
        results = [
            _remove_one(plugin, event, uid, "dynamic"),
            _remove_one(plugin, event, uid, "live"),
        ]
        return "\n".join(results)
    return _remove_one(plugin, event, uid, sub_type)


def build_confirm_task(plugin, event, request: WorkflowRequest, candidate: dict) -> str:
    sub_type = normalize_sub_type(str(request.params.get("sub_type") or "dynamic"))
    task_id = store_pending_task(
        plugin,
        event,
        request,
        kind="confirm_add_subscription",
        payload={"candidate": candidate, "sub_type": sub_type},
    )
    return (
        f"已选择：{candidate.get('username')} | UID={candidate.get('uid')} | type={sub_type}\n"
        f"任务ID: {task_id}\n"
        f"发送 `bili{task_id[-4:]} 确认` 写入订阅，或发送 `bili{task_id[-4:]} 取消` 放弃。"
    )


def _remove_one(plugin, event, uid: str, sub_type: str) -> str:
    ok = plugin.db.remove_subscription(uid, sub_type, event_origin(event))
    if not ok:
        return f"未找到订阅：UID={uid}, type={sub_type}"
    return f"已删除订阅：UID={uid}, type={sub_type}"


def _default_categories(sub_type: str) -> list[int]:
    return [1, 2, 3, 4, 5, 6] if sub_type == "dynamic" else [1, 2, 3]
