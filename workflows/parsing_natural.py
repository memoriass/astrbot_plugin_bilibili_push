from __future__ import annotations

import re

from .models import WorkflowRequest


def workflow_from_natural_language(text: str) -> WorkflowRequest | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    if _contains_any(raw, ("账号", "登录")) and _contains_any(raw, ("状态", "情况")):
        return WorkflowRequest("account_status", source="natural")
    if _contains_any(raw, ("诊断", "检查", "测试")) and _contains_any(raw, ("状态", "连接", "插件", "b站", "B站")):
        return WorkflowRequest("check_status", source="natural")
    if _contains_any(raw, ("列表", "有哪些", "查看")) and _contains_any(raw, ("订阅", "UP", "up")):
        return WorkflowRequest("list_subscriptions", source="natural")
    if _contains_any(raw, ("订阅", "添加", "新增")) and _contains_any(raw, ("动态", "直播", "UP", "up", "b站", "B站")):
        sub_type = _subscription_type(raw)
        keyword = extract_up_keyword(raw)
        return WorkflowRequest(
            "add_subscription",
            target=keyword,
            params={"query": keyword, "sub_type": sub_type},
            source="natural",
        )
    if _contains_any(raw, ("搜索", "查找", "找一下", "搜一下")):
        keyword = extract_up_keyword(raw)
        return WorkflowRequest(
            "search_up",
            target=keyword,
            params={"query": keyword},
            source="natural",
        )
    return None


def extract_up_keyword(text: str) -> str:
    value = _strip_wake_prefix(str(text or "").strip())
    value = re.sub(r"https?://\S+", " ", value)
    for token in _NOISE_TOKENS:
        value = re.sub(re.escape(token), " ", value, flags=re.IGNORECASE)
    value = re.sub(r"[,，.。!！?？、;；:：()\[\]{}<>《》【】\"'“”‘’]+", " ", value)
    parts = [part for part in re.split(r"\s+", value) if part]
    if not parts:
        return str(text or "").strip()
    return _best_keyword_part(parts)


def _subscription_type(text: str) -> str:
    has_dynamic = "动态" in text
    has_live = "直播" in text
    if has_dynamic and has_live:
        return "both"
    return "live" if has_live else "dynamic"


def _strip_wake_prefix(text: str) -> str:
    return re.sub(r"^[A-Za-z0-9_\-]{1,24}\s+", "", text, count=1).strip()


def _best_keyword_part(parts: list[str]) -> str:
    for part in reversed(parts):
        if re.search(r"[A-Za-z0-9_\-\u4e00-\u9fff]", part):
            return part
    return parts[-1]


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


_NOISE_TOKENS = (
    "添加",
    "新增",
    "创建",
    "订阅",
    "关注",
    "搜索",
    "查找",
    "找一下",
    "搜一下",
    "帮我",
    "给我",
    "请",
    "一下",
    "一个",
    "bilibili",
    "Bilibili",
    "bili",
    "B站",
    "b站",
    "UP主",
    "up主",
    "UP",
    "up",
    "动态",
    "直播",
    "推送",
    "提醒",
)
