from pathlib import Path
import asyncio
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context
from astrbot.api import logger
import astrbot.api.message_components as Comp

from ..utils.html_renderer import HtmlRenderer
from ..utils.resource import get_template_path, get_assets_path, get_random_background
from ..core.http import HttpClient

class SubscriptionHandler:
    def __init__(self, context: Context, db, bg_dir: Path):
        self.context = context
        self.db = db
        self.renderer = HtmlRenderer(get_template_path())
        self.bg_folder = bg_dir

    def _get_target_id(self, event: AstrMessageEvent):
        """从事件中提取目标ID (统一会话格式: platform:message_type:session_id)"""
        return event.unified_msg_origin

    async def add_subscription(self, event: AstrMessageEvent, uid: str, parser):
        target_id = self._get_target_id(event)
        try:
            user_info = await parser.get_user_info(uid)
            if not user_info: yield event.plain_result(f"❌ 无法获取 UP 主信息: {uid}"); return
            
            from ..database.db_manager import Subscription
            sub = Subscription(uid=uid, username=user_info["username"], sub_type="dynamic",
                               categories=[1, 2, 3, 4, 5, 6], tags=[], target_id=target_id, enabled=True)

            if self.db.add_subscription(sub):
                bg_data = get_random_background(self.bg_folder)
                img_bytes = await self.renderer.render(
                    "sub_add.html.jinja",
                    {"username": user_info["username"], "face": user_info["face"], "uid": uid,
                     "sub_type": "dynamic", "action": "ADDED"},
                    viewport={"width": 400, "height": 400},
                    selector=".card"
                )
                yield event.chain_result([Comp.Plain(f"✅ 已添加动态订阅: {user_info['username']} ({uid})"), Comp.Image.fromBytes(img_bytes)])
            else:
                yield event.plain_result("⚠️ 订阅已存在")
        except Exception as e: logger.error(f"Add sub failed: {e}"); yield event.plain_result(f"❌ 内部错误: {e}")

    async def add_live_subscription(self, event: AstrMessageEvent, uid: str, parser):
        target_id = self._get_target_id(event)
        try:
            user_info = await parser.get_user_info(uid)
            if not user_info: yield event.plain_result(f"❌ 无法获取 UP 主信息: {uid}"); return
            
            from ..database.db_manager import Subscription
            sub = Subscription(uid=uid, username=user_info["username"], sub_type="live", categories=[1, 2, 3], tags=[], target_id=target_id, enabled=True)
            if self.db.add_subscription(sub):
                bg_data = get_random_background(self.bg_folder)
                img_bytes = await self.renderer.render(
                    "sub_add.html.jinja",
                    {"username": user_info["username"], "face": user_info["face"], "uid": uid,
                     "sub_type": "live", "action": "ADDED"},
                    viewport={"width": 400, "height": 400},
                    selector=".card"
                )
                yield event.chain_result([Comp.Plain(f"✅ 已添加直播订阅: {user_info['username']} ({uid})"), Comp.Image.fromBytes(img_bytes)])
            else: yield event.plain_result("⚠️ 订阅已存在")
        except Exception as e: logger.error(f"Add live sub failed: {e}"); yield event.plain_result(f"❌ 内部错误: {e}")

    async def remove_subscription(self, event: AstrMessageEvent, uid: str, sub_type: str, parser):
        target_id = self._get_target_id(event)
        user_info = await parser.get_user_info(uid)
        username, face = (user_info["username"], user_info["face"]) if user_info else (uid, "")

        if self.db.remove_subscription(uid, sub_type, target_id):
            bg_data = get_random_background(self.bg_folder)
            img_bytes = await self.renderer.render(
                "sub_add.html.jinja",
                {"username": username, "face": face, "uid": uid,
                 "sub_type": sub_type, "action": "REMOVED"},
                viewport={"width": 400, "height": 400},
                selector=".card"
            )
            yield event.chain_result([Comp.Plain(f"🗑️ 已取消{sub_type}订阅: {username} ({uid})"), Comp.Image.fromBytes(img_bytes)])
        else: yield event.plain_result(f"❌ {sub_type}订阅不存在: {uid}")

    async def list_subscriptions(self, event: AstrMessageEvent, scheduler):
        target_id = self._get_target_id(event)
        subs = self.db.get_subscriptions(target_id)
        if not subs: yield event.plain_result("📭 当前会话无订阅"); return

        client = await HttpClient.get_client()
        subs_map = {}
        for sub in subs:
            if sub.uid not in subs_map: subs_map[sub.uid] = {"uid": sub.uid, "username": sub.username, "has_dynamic": False, "has_live": False}
            if sub.sub_type == "dynamic": subs_map[sub.uid]["has_dynamic"] = True
            elif sub.sub_type == "live": subs_map[sub.uid]["has_live"] = True

        async def fetch_info(uid):
            face = "http://i0.hdslb.com/bfs/face/member/noface.jpg"
            try:
                res = await client.get("https://api.bilibili.com/x/web-interface/card", params={"mid": uid}, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    if data["code"] == 0: face = data["data"]["card"]["face"]
            except: pass
            return uid, face

        yield event.plain_result("⏳ 正在获取订阅详细信息...")
        info_results = await asyncio.gather(*[fetch_info(uid) for uid in subs_map.keys()])
        face_map = dict(info_results)

        live_status_map = {}
        live_uids = [u for u, s in subs_map.items() if s["has_live"]]
        if live_uids:
            try:
                live_infos = await scheduler.live_platform.batch_get_status(live_uids)
                for i in live_infos: live_status_map[str(i.uid)] = i.live_status == 1
            except: pass

        all_subs = []
        for uid, info in subs_map.items():
            info["face"] = face_map.get(str(uid), ""); info["is_live"] = live_status_map.get(str(uid), False)
            all_subs.append(info)

        bg_data = get_random_background(self.bg_folder)
        try:
            img_bytes = await self.renderer.render("sub_list.html.jinja", {"subs": all_subs, "bg_image_uri": bg_data["uri"], "page_title": "订阅列表"}, viewport={"width": 1000, "height": 800})
            yield event.chain_result([Comp.Image.fromBytes(img_bytes)])
        except Exception as e: logger.error(f"Render list failed: {e}"); yield event.plain_result("❌ 列表渲染失败")
