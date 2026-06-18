from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WorkflowRequest:
    workflow: str
    target: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    source: str = "tool"


@dataclass(frozen=True, slots=True)
class CompiledWorkflow:
    workflow: str
    title: str
    purpose: str
    user_visible: bool = True


COMPILED_WORKFLOWS: dict[str, CompiledWorkflow] = {
    "ai_dispatch": CompiledWorkflow(
        "ai_dispatch",
        "AI 前置分流",
        "把自然语言或工具参数先分析为受控分支，再转入具体 Bilibili workflow。",
    ),
    "search_up": CompiledWorkflow(
        "search_up",
        "搜索 UP 主",
        "按关键词搜索 UP 主，返回候选和 pending task。",
    ),
    "add_subscription": CompiledWorkflow(
        "add_subscription",
        "添加订阅",
        "按明确 UID 或关键词生成确认任务，用户确认后添加动态或直播订阅。",
    ),
    "remove_subscription": CompiledWorkflow(
        "remove_subscription",
        "删除订阅",
        "定位当前会话订阅并生成确认任务，用户确认后删除。",
    ),
    "list_subscriptions": CompiledWorkflow(
        "list_subscriptions",
        "订阅列表",
        "列出当前会话订阅。",
    ),
    "account_status": CompiledWorkflow(
        "account_status",
        "账号状态",
        "查看 Bilibili 登录账号池状态。",
    ),
    "check_status": CompiledWorkflow(
        "check_status",
        "诊断状态",
        "检查插件关键依赖和账号池状态。",
    ),
    "continue_pending": CompiledWorkflow(
        "continue_pending",
        "继续任务",
        "继续搜索候选选择或确认添加。",
    ),
}


WORKFLOW_ALIASES = {
    "ai": "ai_dispatch",
    "ai_dispatch": "ai_dispatch",
    "dispatch": "ai_dispatch",
    "natural": "ai_dispatch",
    "assistant": "ai_dispatch",
    "助手": "ai_dispatch",
    "分流": "ai_dispatch",
    "路由": "ai_dispatch",
    "search": "search_up",
    "search_user": "search_up",
    "search_up": "search_up",
    "搜索": "search_up",
    "查找": "search_up",
    "add": "add_subscription",
    "subscribe": "add_subscription",
    "add_subscription": "add_subscription",
    "订阅": "add_subscription",
    "添加": "add_subscription",
    "remove": "remove_subscription",
    "delete": "remove_subscription",
    "unsubscribe": "remove_subscription",
    "remove_subscription": "remove_subscription",
    "删除": "remove_subscription",
    "取消": "remove_subscription",
    "list": "list_subscriptions",
    "list_subscriptions": "list_subscriptions",
    "列表": "list_subscriptions",
    "accounts": "account_status",
    "account_status": "account_status",
    "账号": "account_status",
    "status": "check_status",
    "check_status": "check_status",
    "诊断": "check_status",
    "continue": "continue_pending",
    "continue_pending": "continue_pending",
    "cont": "continue_pending",
    "选": "continue_pending",
    "选择": "continue_pending",
    "确认": "continue_pending",
    "取消任务": "continue_pending",
}


CONFIRM_REPLIES = {
    "确认",
    "确定",
    "确认添加",
    "添加",
    "可以",
    "是",
    "是的",
    "好",
    "yes",
    "y",
    "ok",
    "okay",
    "add",
    "confirm",
}


REMOVE_CONFIRM_REPLIES = {
    "确认",
    "确定",
    "确认删除",
    "删除",
    "移除",
    "退订",
    "可以",
    "是",
    "是的",
    "好",
    "yes",
    "y",
    "ok",
    "okay",
    "remove",
    "delete",
    "unsubscribe",
    "confirm",
}


CANCEL_REPLIES = {
    "取消",
    "放弃",
    "不添加",
    "不要",
    "不用",
    "否",
    "no",
    "n",
    "cancel",
    "stop",
}
