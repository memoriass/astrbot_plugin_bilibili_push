"""Bilibili 推送插件主入口 (Core重构版)"""
import time
import asyncio
from pathlib import Path

import astrbot.api.message_components as Comp
from astrbot.api import AstrBotConfig, logger as astrbot_logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, register

from .core.types import MsgText, MsgImage
from .scheduler import BilibiliScheduler
from .sub_manager import DBManager, Subscription

from astrbot.core.utils.astrbot_path import get_astrbot_data_path

@register(
    "bilibili_push",
    "AstrBot",
    "Bilibili 推送插件 (Native Core) - 原生重构版",
    "2.0.0",
    "https://github.com/AstrBotDevs/AstrBot",
)
class BilibiliPushPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or {}
        
        self.platform_name = self.config.get("platform_name", "auto")
        self.check_interval = self.config.get("check_interval", 30)
        
        # 使用标准插件数据目录: data/plugin_data/astrbot_plugin_bilibili_push
        self.data_dir = get_astrbot_data_path() / "plugin_data" / "astrbot_plugin_bilibili_push"
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = DBManager(self.data_dir)
        self.scheduler = BilibiliScheduler(
            db=self.db,
            check_interval=self.check_interval,
            on_new_post=self.on_new_post,
            context=self.context # Pass context for KV storage
        )
        
    async def initialize(self):
        await self.scheduler.start()
        
    async def terminate(self):
        await self.scheduler.stop()

    async def on_new_post(self, platform_name: str, target_id: str, msgs: list):
        try:
            chain_parts = []
            for msg in msgs:
                if isinstance(msg, MsgText):
                    chain_parts.append(Comp.Plain(msg.text))
                elif isinstance(msg, MsgImage):
                    # msg.data can be str url, path, or bytes
                    data = msg.data
                    if isinstance(data, bytes):
                        temp_dir = Path(self.data_dir) / "temp"
                        temp_dir.mkdir(parents=True, exist_ok=True)
                        temp_file = temp_dir / f"temp_{int(time.time()*1000)}.jpg"
                        with open(temp_file, "wb") as f:
                            f.write(data)
                        chain_parts.append(Comp.Image.fromFileSystem(str(temp_file.absolute())))
                    elif isinstance(data, (str, Path)):
                        s_data = str(data)
                        if s_data.startswith("http"):
                            chain_parts.append(Comp.Image.fromURL(s_data))
                        else:
                            chain_parts.append(Comp.Image.fromFileSystem(s_data))

            group_id = target_id.replace(":", "_") if ":" in target_id else target_id
            origin = f"{self.get_effective_platform_name()}:GroupMessage:{group_id}"
            
            chain = MessageChain(chain_parts)
            await self.context.send_message(origin, chain)
            astrbot_logger.info(f"推送消息成功 -> {origin}")
            
        except Exception as e:
            astrbot_logger.error(f"消息发送失败: {e}", exc_info=True)

    def _get_target_id(self, event: AstrMessageEvent) -> str | None:
        """从事件中提取目标ID (群组ID)"""
        if event.unified_msg_origin:
            parts = event.unified_msg_origin.split(":")
            if len(parts) >= 3: 
                return parts[2]
        if hasattr(event.message_obj, "group_id") and event.message_obj.group_id:
            return str(event.message_obj.group_id)
        return None

    @filter.command("bilibili 添加订阅")
    async def add_subscription(self, event: AstrMessageEvent):
        args = event.message_str.split()
        if len(args) < 3:
            yield event.plain_result("❌ 用法: bilibili 添加订阅 <UID>")
            return
            
        uid = args[2].strip()
        if not uid.isdigit():
            yield event.plain_result("❌ UID 必须是数字")
            return
            
        target_id = self._get_target_id(event)
        if not target_id:
             yield event.plain_result("❌ 无法获取群组 ID，请在群组中使用此命令")
             return

        try:
            platform = self.scheduler.bili_platform
            username = await platform.get_target_name(uid)
            
            if not username:
                yield event.plain_result(f"❌ 无法获取 UP 主信息: {uid}")
                return
                
            sub = Subscription(
                uid=uid, username=username, sub_type="dynamic",
                categories=[], tags=[], target_id=target_id, enabled=True
            )
            
            if self.db.add_subscription(sub):
                yield event.plain_result(f"✅ 已添加动态订阅: {username} ({uid})")
            else:
                yield event.plain_result(f"⚠️ 订阅已存在")
        except Exception as e:
            astrbot_logger.error(f"添加失败: {e}")
            yield event.plain_result(f"❌ 内部错误: {e}")

    @filter.command("bilibili 添加直播")
    async def add_live_subscription(self, event: AstrMessageEvent):
        args = event.message_str.split()
        if len(args) < 3: 
            yield event.plain_result("❌ 用法: bilibili 添加直播 <UID>")
            return
        uid = args[2].strip()
        
        target_id = self._get_target_id(event)
        if not target_id: 
            yield event.plain_result("❌ 无法获取群组 ID")
            return

        try:
            platform = self.scheduler.live_platform
            username = await platform.get_target_name(uid)
            if not username: 
                yield event.plain_result(f"❌ 无法获取直播间信息: {uid}")
                return

            sub = Subscription(
                uid=uid, username=username, sub_type="live",
                categories=[1,2,3], tags=[], target_id=target_id, enabled=True
            )
            if self.db.add_subscription(sub):
                yield event.plain_result(f"✅ 已添加直播订阅: {username}")
            else:
                yield event.plain_result(f"⚠️ 订阅已存在")
        except Exception as e: 
            yield event.plain_result(f"❌ 添加失败: {e}")

    @filter.command("bilibili 删除订阅")
    async def remove_subscription(self, event: AstrMessageEvent):
        args = event.message_str.split()
        if len(args) < 3: 
            yield event.plain_result("❌ 用法: bilibili 删除订阅 <UID> [类型:dynamic/live]")
            return
        uid = args[2].strip()
        sub_type = args[3].strip() if len(args) > 3 else "dynamic"
        
        target_id = self._get_target_id(event)
        if not target_id: return
        
        if self.db.remove_subscription(uid, sub_type, target_id):
            yield event.plain_result(f"✅ 删除成功: {uid} ({sub_type})")
        else:
            yield event.plain_result(f"❌ 订阅不存在")

    @filter.command("bilibili 订阅列表")
    async def list_subscriptions(self, event: AstrMessageEvent):
        target_id = self._get_target_id(event)
        if not target_id: return
        
        subs = self.db.get_subscriptions(target_id)
        if not subs:
            yield event.plain_result("📭 当前群组无订阅")
            return

        msg = f"📋 订阅列表 ({len(subs)})\n"
        for sub in subs:
            type_emoji = "📺" if sub.sub_type == "live" else "📝"
            msg += f"{type_emoji} {sub.username} ({sub.uid})\n"
        yield event.plain_result(msg)

    def get_effective_platform_name(self) -> str:
        if self.platform_name == "auto":
            available = [p.meta().id for p in self.context.platform_manager.platform_insts]
            return available[0] if available else "llonebot"
        return self.platform_name
