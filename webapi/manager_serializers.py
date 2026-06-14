from __future__ import annotations

import json

from ..core.http import HttpClient


NO_FACE = "http://i0.hdslb.com/bfs/face/member/noface.jpg"


def serialize_subscription(sub) -> dict:
    return {
        "uid": str(sub.uid),
        "username": sub.username,
        "sub_type": sub.sub_type,
        "target_id": sub.target_id,
        "categories": list(sub.categories or []),
        "tags": list(sub.tags or []),
        "enabled": bool(sub.enabled),
    }


def serialize_account(account: dict) -> dict:
    return {
        "uid": str(account.get("uid") or ""),
        "name": str(account.get("name") or ""),
        "face": str(account.get("face") or ""),
        "valid": bool(account.get("valid", True)),
        "status_code": account.get("status_code"),
    }


def serialize_pending_task(task: dict) -> dict:
    candidate = task.get("candidate") or {}
    return {
        "task_id": str(task.get("task_id") or ""),
        "kind": str(task.get("kind") or ""),
        "origin": str(task.get("origin") or ""),
        "workflow": str(task.get("workflow") or ""),
        "keyword": str(task.get("keyword") or ""),
        "mode": str(task.get("mode") or ""),
        "sub_type": str(task.get("sub_type") or ""),
        "created_at": task.get("created_at"),
        "expires_at": task.get("expires_at"),
        "candidate": {
            "uid": str(candidate.get("uid") or ""),
            "username": str(candidate.get("username") or ""),
        }
        if candidate
        else None,
        "candidate_count": len(task.get("candidates") or []),
    }


async def fetch_user_info(uid: str) -> dict:
    client = await HttpClient.get_client()
    try:
        res = await client.get(
            "https://api.bilibili.com/x/web-interface/card",
            params={"mid": uid},
            timeout=5,
        )
        data = res.json()
        if data.get("code") == 0:
            card = data.get("data", {}).get("card", {})
            return {
                "username": str(card.get("name") or ""),
                "face": str(card.get("face") or ""),
            }
    except Exception:
        pass
    return {}


def parse_categories(value, sub_type: str) -> list[int]:
    parsed = []
    for item in parse_list(value):
        try:
            parsed.append(int(item))
        except (TypeError, ValueError):
            continue
    if parsed:
        return parsed
    return [1, 2, 3, 4, 5, 6] if sub_type == "dynamic" else [1, 2, 3]


def parse_tags(value) -> list[str]:
    return [str(item).strip() for item in parse_list(value) if str(item).strip()]


def parse_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            loaded = json.loads(text)
            if isinstance(loaded, list):
                return loaded
        except json.JSONDecodeError:
            pass
        return [part.strip() for part in text.replace("，", ",").split(",")]
    return [value]


def parse_cookies(payload: dict) -> dict | None:
    value = payload.get("cookies")
    if isinstance(value, dict):
        return {str(key): str(val) for key, val in value.items()}

    text = str(payload.get("cookies_text") or value or "").strip()
    if not text:
        return None
    try:
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            return {str(key): str(val) for key, val in loaded.items()}
    except json.JSONDecodeError:
        pass

    cookies = {}
    for chunk in text.replace("\n", ";").split(";"):
        if "=" not in chunk:
            continue
        key, val = chunk.split("=", 1)
        key = key.strip()
        if key:
            cookies[key] = val.strip()
    return cookies or None


def bool_payload(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "启用", "有效"}
