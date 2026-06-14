from __future__ import annotations

from ..core.http import HttpClient


PLUGIN_NAME = "astrbot_plugin_bilibili_push"


def register_bilibili_web_apis(context, plugin):
    api = BilibiliManagerApi(plugin)
    context.register_web_api(
        f"/{PLUGIN_NAME}/overview",
        api.overview,
        ["GET"],
        "Bilibili manager overview",
    )
    context.register_web_api(
        f"/{PLUGIN_NAME}/subscriptions/delete",
        api.delete_subscription,
        ["POST"],
        "Delete Bilibili subscription",
    )
    context.register_web_api(
        f"/{PLUGIN_NAME}/subscriptions/enabled",
        api.set_subscription_enabled,
        ["POST"],
        "Enable or disable Bilibili subscription",
    )
    context.register_web_api(
        f"/{PLUGIN_NAME}/pending/clear",
        api.clear_pending,
        ["POST"],
        "Clear Bilibili workflow pending tasks",
    )
    return api


class BilibiliManagerApi:
    def __init__(self, plugin):
        self.plugin = plugin

    async def overview(self):
        subscriptions = [
            _serialize_subscription(sub)
            for sub in self.plugin.db.get_subscriptions()
        ]
        accounts = [_serialize_account(acc) for acc in await HttpClient.get_accounts()]
        pending_tasks = [
            _serialize_pending_task(task)
            for task in await self.plugin.pending_store.list_tasks()
        ]
        return _ok(
            {
                "diagnostics": self._diagnostics(
                    subscriptions,
                    accounts,
                    pending_tasks,
                ),
                "subscriptions": subscriptions,
                "accounts": accounts,
                "pending_tasks": pending_tasks,
            }
        )

    async def delete_subscription(self):
        payload = await _request_json()
        uid = str(payload.get("uid") or "").strip()
        sub_type = str(payload.get("sub_type") or "").strip()
        target_id = str(payload.get("target_id") or "").strip()
        if not uid or sub_type not in {"dynamic", "live"} or not target_id:
            return _error("uid、sub_type、target_id 参数不完整。")

        removed = self.plugin.db.remove_subscription(uid, sub_type, target_id)
        if not removed:
            return _error("未找到匹配订阅。")
        return _ok({"removed": True})

    async def set_subscription_enabled(self):
        payload = await _request_json()
        uid = str(payload.get("uid") or "").strip()
        sub_type = str(payload.get("sub_type") or "").strip()
        target_id = str(payload.get("target_id") or "").strip()
        enabled = bool(payload.get("enabled"))
        if not uid or sub_type not in {"dynamic", "live"} or not target_id:
            return _error("uid、sub_type、target_id 参数不完整。")

        updated = self.plugin.db.set_subscription_enabled(
            uid,
            sub_type,
            target_id,
            enabled,
        )
        if not updated:
            return _error("未找到匹配订阅。")
        return _ok({"updated": True, "enabled": enabled})

    async def clear_pending(self):
        count = await self.plugin.pending_store.clear()
        return _ok({"cleared": count})

    def _diagnostics(
        self,
        subscriptions: list[dict],
        accounts: list[dict],
        pending_tasks: list[dict],
    ) -> dict:
        targets = {sub["target_id"] for sub in subscriptions}
        dynamic_count = sum(1 for sub in subscriptions if sub["sub_type"] == "dynamic")
        live_count = sum(1 for sub in subscriptions if sub["sub_type"] == "live")
        enabled_count = sum(1 for sub in subscriptions if sub["enabled"])
        valid_accounts = sum(1 for acc in accounts if acc.get("valid", True))
        return {
            "check_interval": self.plugin.check_interval,
            "render_type": self.plugin.render_type,
            "enable_link_parser": self.plugin.enable_link_parser,
            "enable_ai_tools": self.plugin.enable_ai_tools,
            "enable_ai_agent_entry": self.plugin.enable_ai_agent_entry,
            "subscriptions": len(subscriptions),
            "enabled_subscriptions": enabled_count,
            "dynamic_subscriptions": dynamic_count,
            "live_subscriptions": live_count,
            "targets": len(targets),
            "accounts": len(accounts),
            "valid_accounts": valid_accounts,
            "pending_tasks": len(pending_tasks),
        }


def _serialize_subscription(sub) -> dict:
    return {
        "uid": str(sub.uid),
        "username": sub.username,
        "sub_type": sub.sub_type,
        "target_id": sub.target_id,
        "categories": list(sub.categories or []),
        "tags": list(sub.tags or []),
        "enabled": bool(sub.enabled),
    }


def _serialize_account(account: dict) -> dict:
    return {
        "uid": str(account.get("uid") or ""),
        "name": str(account.get("name") or ""),
        "face": str(account.get("face") or ""),
        "valid": bool(account.get("valid", True)),
        "status_code": account.get("status_code"),
    }


def _serialize_pending_task(task: dict) -> dict:
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


async def _request_json() -> dict:
    from quart import request

    data = await request.get_json()
    return data if isinstance(data, dict) else {}


def _ok(data: dict | None = None) -> dict:
    return {"status": "ok", "data": data or {}}


def _error(message: str) -> dict:
    return {"status": "error", "message": message}
