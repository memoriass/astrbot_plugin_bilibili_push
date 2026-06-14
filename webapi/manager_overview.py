from __future__ import annotations

import asyncio

from ..core.http import HttpClient
from .manager_serializers import (
    NO_FACE,
    serialize_account,
    serialize_pending_task,
    serialize_subscription,
)


class ManagerOverviewService:
    def __init__(self, plugin):
        self.plugin = plugin

    async def build(self) -> dict:
        subscriptions = await self._enrich_subscriptions([
            serialize_subscription(sub)
            for sub in self.plugin.db.get_subscriptions()
        ])
        accounts = [serialize_account(acc) for acc in await HttpClient.get_accounts()]
        pending_tasks = [
            serialize_pending_task(task)
            for task in await self.plugin.pending_store.list_tasks()
        ]
        return {
            "diagnostics": self._diagnostics(subscriptions, accounts, pending_tasks),
            "subscriptions": subscriptions,
            "accounts": accounts,
            "pending_tasks": pending_tasks,
        }

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

    async def _enrich_subscriptions(self, subscriptions: list[dict]) -> list[dict]:
        uids = sorted({sub["uid"] for sub in subscriptions if sub.get("uid")})
        face_map, live_status_map = await asyncio.gather(
            self._fetch_face_map(uids),
            self._fetch_live_status_map(subscriptions),
        )
        for sub in subscriptions:
            uid = sub.get("uid") or ""
            sub["face"] = face_map.get(uid, NO_FACE)
            sub["is_live"] = live_status_map.get(uid, False)
        return subscriptions

    async def _fetch_face_map(self, uids: list[str]) -> dict[str, str]:
        if not uids:
            return {}
        client = await HttpClient.get_client()

        async def fetch_face(uid: str) -> tuple[str, str]:
            face = NO_FACE
            try:
                res = await client.get(
                    "https://api.bilibili.com/x/web-interface/card",
                    params={"mid": uid},
                    timeout=5,
                )
                if res.status_code == 200:
                    data = res.json()
                    if data.get("code") == 0:
                        face = data.get("data", {}).get("card", {}).get("face") or face
            except Exception:
                pass
            return uid, face

        return dict(await asyncio.gather(*[fetch_face(uid) for uid in uids]))

    async def _fetch_live_status_map(self, subscriptions: list[dict]) -> dict[str, bool]:
        live_uids = sorted({
            sub["uid"]
            for sub in subscriptions
            if sub.get("uid") and sub.get("sub_type") == "live"
        })
        if not live_uids:
            return {}
        try:
            live_infos = await self.plugin.scheduler.live_platform.batch_get_status(live_uids)
            return {str(info.uid): info.live_status == 1 for info in live_infos}
        except Exception:
            return {}
