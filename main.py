import asyncio
import os
import time
from pathlib import Path

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.api import AstrBotConfig

# --- Import from new structure ---
from .core.http import HttpClient
from .parser.bilibili_parser import BilibiliParser
from .scheduler import BilibiliScheduler
from .database.db_manager import DatabaseManager
from .handlers.help_handler import HelpHandler
from .handlers.subscription_handler import SubscriptionHandler
from .handlers.login_handler import LoginHandler
from .handlers.search_handler import SearchHandler
from .handlers.link_handler import LinkParserHandler
from .utils.html_renderer import BrowserManager
from .utils.resource import get_template_path

@register("astrbot_plugin_bilibili_push", "Aisidaka", "Bilibili 动态与直播推送", "1.2.0")
class BilibiliPush(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config = {}
        
        # 路径初始化
        self.plugin_dir = Path(__file__).parent
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path
        self.data_dir = Path(get_astrbot_data_path()) / "plugin_data" / "astrbot_plugin_bilibili_push"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = self.data_dir / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.bg_dir = self.data_dir / "backgrounds"
        self.bg_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化资源与原始数据库
        self._init_resources()
        
        # 获取插件配置
        config = context.get_config() or {}
        self.push_on_startup = config.get("push_on_startup", False)
        self.check_interval = config.get("check_interval", 30)
        self.render_type = config.get("render_type", "image")
        
        self.enable_link_parser = config.get("enable_link_parser", True)
        self.search_cache_expiry_hours = config.get("search_cache_expiry_hours", 24)
        self.platform_name = config.get("platform_name", "auto")

        # 核心组件初始化
        self.db = DatabaseManager(self.data_dir / "data.db")
        self.parser = BilibiliParser()
        self.scheduler = BilibiliScheduler(
            db=self.db, 
            check_interval=self.check_interval,
            push_on_startup=self.push_on_startup,
            render_type=self.render_type,
            on_new_post=self._handle_new_post,
            star=self
        )

        # 指令处理器初始化 (解耦)
        self.help_handler = HelpHandler(context, self.bg_dir)
        self.sub_handler = SubscriptionHandler(context, self.db, self.bg_dir)
        self.login_handler = LoginHandler(context, self.temp_dir, self.bg_dir)
        self.search_handler = SearchHandler(context, self.bg_dir)
        self.link_handler = LinkParserHandler(context, "parser_bili")

    def _init_resources(self):
        import shutil
        import os
        from astrbot.api import logger
        
        # 复制初始背景图片
        default_bg_dir = self.plugin_dir / "utils" / "resources" / "backgrounds"
        if default_bg_dir.exists():
            for root, dirs, files in os.walk(default_bg_dir):
                for file in files:
                    if file.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                        src_file = Path(root) / file
                        rel_path = src_file.relative_to(default_bg_dir)
                        dst_file = self.bg_dir / rel_path
                        
                        dst_file.parent.mkdir(parents=True, exist_ok=True)
                        if not dst_file.exists():
                            try:
                                shutil.copy2(src_file, dst_file)
                                logger.debug(f"已复制初始背景图: {rel_path}")
                            except Exception as e:
                                logger.warning(f"复制初始背景图失败 {file}: {e}")

    async def initialize(self):
        """插件启动入口"""
        await HttpClient.set_star_instance(self)
        await BrowserManager.init()
        asyncio.create_task(self.scheduler.start())
        asyncio.create_task(self._cleanup_temp_files())

    # --- 指令入口 ---

    @filter.command("b站帮助", alias={"bilibili 帮助", "bili_help"})
    async def bilibili_help(self, event: AstrMessageEvent):
        """显示帮助菜单图卡"""
        async for ret in self.help_handler.handle_help(event): yield ret

    @filter.command("添加b站订阅", alias={"bilibili 添加订阅", "add_bili_sub"})
    async def add_sub(self, event: AstrMessageEvent, uid: str):
        """添加动态订阅"""
        async for ret in self.sub_handler.add_subscription(event, uid, self.parser): yield ret

    @filter.command("添加b站直播", alias={"bilibili 添加直播", "add_bili_live"})
    async def add_live(self, event: AstrMessageEvent, uid: str):
        """添加直播订阅"""
        async for ret in self.sub_handler.add_live_subscription(event, uid, self.parser): yield ret

    @filter.command("取消b站订阅", alias={"删除b站订阅", "del_bili_sub"})
    async def del_sub(self, event: AstrMessageEvent, uid: str):
        """取消动态订阅"""
        async for ret in self.sub_handler.remove_subscription(event, uid, "dynamic", self.parser): yield ret

    @filter.command("取消b站直播", alias={"删除b站直播", "del_bili_live"})
    async def del_live(self, event: AstrMessageEvent, uid: str):
        """取消直播提醒"""
        async for ret in self.sub_handler.remove_subscription(event, uid, "live", self.parser): yield ret

    @filter.command("b站订阅列表", alias={"bilibili 订阅列表", "list_bili_sub"})
    async def list_subs(self, event: AstrMessageEvent):
        """列出本会话的所有订阅"""
        async for ret in self.list_subscriptions(event): yield ret

    async def list_subscriptions(self, event: AstrMessageEvent):
        # 兼容旧版调用或者直接在这里实现
        async for ret in self.sub_handler.list_subscriptions(event, self.scheduler): yield ret

    @filter.command("b站登录", alias={"bilibili 登录", "b站扫码"})
    async def login(self, event: AstrMessageEvent):
        """通过二维码登录 B 站账号"""
        async for ret in self.login_handler.handle_login(event): yield ret

    @filter.command("b站登录状态")
    async def status(self, event: AstrMessageEvent):
        """查看当前登录账号池状态"""
        async for ret in self.login_handler.handle_status(event): yield ret

    @filter.command("b站搜索", alias={"bilibili 搜索", "search_bili"})
    async def search(self, event: AstrMessageEvent, keyword: str):
        """在 B 站搜索 UP 主并获取 UID"""
        async for ret in self.search_handler.handle_search(event, keyword, self): yield ret

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_link(self, event: AstrMessageEvent):
        """自动感应链接并解析"""
        async for ret in self.link_handler.handle_links(event, self.parser, self.enable_link_parser): yield ret

    # --- 工具方法 ---

    async def _cleanup_temp_files(self):
        """定期清理扫描登录用的临时二维码"""
        while True:
            try:
                now = time.time()
                for f in self.temp_dir.iterdir():
                    if f.is_file() and now - f.stat().st_mtime > 3600: os.remove(f)
            except: pass
            await asyncio.sleep(1800)

    async def _handle_new_post(self, platform: str, target_id: str, msgs: list):
        """处理来自调度器的新动态/直播推送"""
        from astrbot.api.event import MessageChain
        from astrbot.api import logger
        try:
            logger.info(f"Bilibili 正在执行最终推送: {target_id} | 消息段: {len(msgs)}")
            # 直接通过构造函数初始化，msgs 应为 BaseMessageComponent 列表
            chain = MessageChain(chain=msgs)
            
            # target_id 已经是 platform:type:id 格式
            await self.context.send_message(target_id, chain)
            logger.info(f"Bilibili 推送任务已提交给框架: {target_id}")
        except Exception as e:
            logger.error(f"Bilibili 推送消息失败 ({target_id}): {e}")

    async def terminate(self):
        """插件终止时回收浏览器资源"""
        await self.scheduler.terminate()
