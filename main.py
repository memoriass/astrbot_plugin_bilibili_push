import asyncio
import os
import time
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.agent.tool import ToolSet
from astrbot.core.star.filter.command import GreedyStr

from .core.http import HttpClient
from .database.db_manager import DatabaseManager
from .handlers.help_handler import HelpHandler
from .handlers.link_handler import LinkParserHandler
from .handlers.login_handler import LoginHandler
from .handlers.search_handler import SearchHandler
from .handlers.subscription_handler import SubscriptionHandler
from .parser.bilibili_parser import BilibiliParser
from .rendering import HtmlRendererAdapter
from .scheduler import BilibiliScheduler
from .utils.html_renderer import BrowserManager
from .utils.resource import get_template_path


@register(
    "astrbot_plugin_bilibili_push", "Aisidaka", "Bilibili 动态与直播推送", "1.2.0"
)
class BilibiliPush(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config = {}

        # 路径初始化
        self.plugin_dir = Path(__file__).parent
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        self.data_dir = (
            Path(get_astrbot_data_path())
            / "plugin_data"
            / "astrbot_plugin_bilibili_push"
        )
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
        self.enable_ai_tools = config.get("enable_ai_tools", True)
        self.enable_ai_agent_entry = config.get("enable_ai_agent_entry", True)
        self.ai_tool_timeout_sec = int(config.get("ai_tool_timeout_sec", 20))
        self.ai_max_steps = int(config.get("ai_max_steps", 8))

        # 核心组件初始化
        self.db = DatabaseManager(self.data_dir / "data.db")
        self.parser = BilibiliParser()
        self.scheduler = BilibiliScheduler(
            db=self.db,
            check_interval=self.check_interval,
            push_on_startup=self.push_on_startup,
            render_type=self.render_type,
            on_new_post=self._handle_new_post,
            star=self,
        )

        # 渲染器与指令处理器初始化 (解耦)
        self.renderer = HtmlRendererAdapter(get_template_path())
        self.help_handler = HelpHandler(context)
        self.sub_handler = SubscriptionHandler(
            context,
            self.db,
            self.bg_dir,
            renderer=self.renderer,
        )
        self.login_handler = LoginHandler(
            context,
            self.temp_dir,
            self.bg_dir,
            renderer=self.renderer,
        )
        self.search_handler = SearchHandler(
            context,
            self.bg_dir,
            renderer=self.renderer,
        )
        self.link_handler = LinkParserHandler(
            context,
            renderer=self.renderer,
            template_name="parser_bili",
        )

    def _init_resources(self):
        import os
        import shutil

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
        async for ret in self.help_handler.handle_help(event):
            yield ret

    @filter.command("添加b站订阅", alias={"bilibili 添加订阅", "add_bili_sub"})
    async def add_sub(self, event: AstrMessageEvent, uid: str):
        """添加动态订阅"""
        async for ret in self.sub_handler.add_subscription(event, uid, self.parser):
            yield ret

    @filter.command("添加b站直播", alias={"bilibili 添加直播", "add_bili_live"})
    async def add_live(self, event: AstrMessageEvent, uid: str):
        """添加直播订阅"""
        async for ret in self.sub_handler.add_live_subscription(
            event, uid, self.parser
        ):
            yield ret

    @filter.command("取消b站订阅", alias={"删除b站订阅", "del_bili_sub"})
    async def del_sub(self, event: AstrMessageEvent, uid: str):
        """取消动态订阅"""
        async for ret in self.sub_handler.remove_subscription(
            event, uid, "dynamic", self.parser
        ):
            yield ret

    @filter.command("取消b站直播", alias={"删除b站直播", "del_bili_live"})
    async def del_live(self, event: AstrMessageEvent, uid: str):
        """取消直播提醒"""
        async for ret in self.sub_handler.remove_subscription(
            event, uid, "live", self.parser
        ):
            yield ret

    @filter.command("b站订阅列表", alias={"bilibili 订阅列表", "list_bili_sub"})
    async def list_subs(self, event: AstrMessageEvent):
        """列出本会话的所有订阅"""
        async for ret in self.list_subscriptions(event):
            yield ret

    async def list_subscriptions(self, event: AstrMessageEvent):
        # 兼容旧版调用或者直接在这里实现
        async for ret in self.sub_handler.list_subscriptions(event, self.scheduler):
            yield ret

    @filter.command("b站登录", alias={"bilibili 登录", "b站扫码"})
    async def login(self, event: AstrMessageEvent):
        """通过二维码登录 B 站账号"""
        async for ret in self.login_handler.handle_login(event):
            yield ret

    @filter.command("b站登录状态")
    async def status(self, event: AstrMessageEvent):
        """查看当前登录账号池状态"""
        async for ret in self.login_handler.handle_status(event):
            yield ret

    @filter.command("b站搜索", alias={"bilibili 搜索", "search_bili"})
    async def search(self, event: AstrMessageEvent, keyword: str):
        """在 B 站搜索 UP 主并获取 UID"""
        async for ret in self.search_handler.handle_search(event, keyword, self):
            yield ret

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_link(self, event: AstrMessageEvent):
        """自动感应链接并解析"""
        async for ret in self.link_handler.handle_links(
            event, self.parser, self.enable_link_parser
        ):
            yield ret

    @filter.command("b站助手", alias={"bilibili 助手", "bili 助手"})
    async def bilibili_agent(self, event: AstrMessageEvent, query: GreedyStr):
        """显式 Agent 入口（可选）"""
        prompt = query.strip()
        if not self.enable_ai_agent_entry:
            yield event.plain_result("⚠️ AI Agent 入口已关闭")
            return
        if not prompt:
            yield event.plain_result(
                "❌ 请输入问题，例如：b站助手 帮我搜索影视飓风并订阅动态"
            )
            return

        tool_names = [
            "bili_search_up",
            "bili_add_dynamic_sub",
            "bili_add_live_sub",
            "bili_list_subs",
            "bili_remove_sub",
        ]
        tool_mgr = self.context.get_llm_tool_manager()
        selected_tools = ToolSet()
        for name in tool_names:
            tool = tool_mgr.get_func(name)
            if tool:
                selected_tools.add_tool(tool)

        if selected_tools.empty():
            yield event.plain_result("❌ 当前会话没有可用的 B站 AI 工具")
            return

        try:
            provider_id = await self.context.get_current_chat_provider_id(
                umo=event.unified_msg_origin,
            )
            llm_resp = await self.context.tool_loop_agent(
                event=event,
                chat_provider_id=provider_id,
                prompt=prompt,
                tools=selected_tools,
                max_steps=self.ai_max_steps,
                tool_call_timeout=self.ai_tool_timeout_sec,
            )
            yield event.plain_result(llm_resp.completion_text or "已完成")
        except Exception as exc:
            logger.error(f"Bilibili Agent 调用失败: {exc}", exc_info=True)
            yield event.plain_result(f"❌ Agent 调用失败: {exc}")

    @filter.llm_tool(name="bili_search_up")
    async def bili_search_up_tool(self, event: AstrMessageEvent, keyword: str) -> str:
        """搜索 B站 UP 主并返回 UID 列表。

        Args:
            keyword(string): 搜索关键词。
        """
        if not self.enable_ai_tools:
            return "AI 工具已关闭。"
        return await self._ai_search_up(keyword)

    @filter.llm_tool(name="bili_add_dynamic_sub")
    async def bili_add_dynamic_sub_tool(self, event: AstrMessageEvent, uid: str) -> str:
        """添加 B站动态订阅。

        Args:
            uid(string): UP 主 UID。
        """
        if not self.enable_ai_tools:
            return "AI 工具已关闭。"
        return await self._ai_add_subscription(event, uid, "dynamic")

    @filter.llm_tool(name="bili_add_live_sub")
    async def bili_add_live_sub_tool(self, event: AstrMessageEvent, uid: str) -> str:
        """添加 B站直播订阅。

        Args:
            uid(string): UP 主 UID。
        """
        if not self.enable_ai_tools:
            return "AI 工具已关闭。"
        return await self._ai_add_subscription(event, uid, "live")

    @filter.llm_tool(name="bili_list_subs")
    async def bili_list_subs_tool(
        self,
        event: AstrMessageEvent,
        placeholder: str = "",
    ) -> str:
        """列出当前会话的 B站订阅。

        Args:
            placeholder(string): 预留参数，可留空。
        """
        if not self.enable_ai_tools:
            return "AI 工具已关闭。"
        return self._ai_list_subscriptions(event)

    @filter.llm_tool(name="bili_remove_sub")
    async def bili_remove_sub_tool(
        self,
        event: AstrMessageEvent,
        uid: str,
        sub_type: str,
    ) -> str:
        """删除 B站订阅。

        Args:
            uid(string): UP 主 UID。
            sub_type(string): 订阅类型，dynamic 或 live。
        """
        if not self.enable_ai_tools:
            return "AI 工具已关闭。"
        return self._ai_remove_subscription(event, uid, sub_type)

    async def _ai_search_up(self, keyword: str) -> str:
        if not keyword.strip():
            return "搜索关键词不能为空。"
        client = await HttpClient.get_client()
        try:
            response = await client.get(
                "https://api.bilibili.com/x/web-interface/search/type",
                params={"search_type": "bili_user", "keyword": keyword, "page": 1},
                timeout=10,
            )
            if response.status_code != 200:
                return f"搜索失败，HTTP {response.status_code}。"
            data = response.json()
            if data.get("code") != 0:
                return f"搜索失败，code={data.get('code')}。"
            results = data.get("data", {}).get("result", [])
            if not results:
                return f"未找到关键词“{keyword}”对应的 UP 主。"
            lines = [f"搜索结果（关键词：{keyword}）:"]
            for idx, item in enumerate(results[:8], start=1):
                lines.append(
                    f"{idx}. {item.get('uname', '')} | UID={item.get('mid', '')}"
                )
            return "\n".join(lines)
        except Exception as exc:
            logger.error(f"AI 搜索 UP 失败: {exc}", exc_info=True)
            return f"搜索失败：{exc}"

    async def _ai_add_subscription(
        self,
        event: AstrMessageEvent,
        uid: str,
        sub_type: str,
    ) -> str:
        if sub_type not in {"dynamic", "live"}:
            return "sub_type 仅支持 dynamic 或 live。"
        user_info = await self.parser.get_user_info(uid)
        if not user_info:
            return f"无法获取 UID={uid} 的用户信息。"

        target_id = event.unified_msg_origin
        existing = self.db.get_subscriptions(target_id)
        if any(sub.uid == str(uid) and sub.sub_type == sub_type for sub in existing):
            return f"订阅已存在：{user_info['username']} ({uid}) [{sub_type}]"

        from .database.db_manager import Subscription

        categories = [1, 2, 3, 4, 5, 6] if sub_type == "dynamic" else [1, 2, 3]
        sub = Subscription(
            uid=uid,
            username=user_info["username"],
            sub_type=sub_type,
            target_id=target_id,
            categories=categories,
            tags=[],
            enabled=True,
        )
        ok = self.db.add_subscription(sub)
        if not ok:
            return "写入订阅失败，请稍后重试。"
        return f"已添加订阅：{user_info['username']} ({uid}) [{sub_type}]"

    def _ai_remove_subscription(
        self,
        event: AstrMessageEvent,
        uid: str,
        sub_type: str,
    ) -> str:
        if sub_type not in {"dynamic", "live"}:
            return "sub_type 仅支持 dynamic 或 live。"
        target_id = event.unified_msg_origin
        ok = self.db.remove_subscription(uid, sub_type, target_id)
        if not ok:
            return f"未找到订阅：UID={uid}, type={sub_type}"
        return f"已删除订阅：UID={uid}, type={sub_type}"

    def _ai_list_subscriptions(self, event: AstrMessageEvent) -> str:
        target_id = event.unified_msg_origin
        subs = self.db.get_subscriptions(target_id)
        if not subs:
            return "当前会话暂无订阅。"

        grouped: dict[str, set[str]] = {}
        names: dict[str, str] = {}
        for sub in subs:
            grouped.setdefault(sub.uid, set()).add(sub.sub_type)
            names[sub.uid] = sub.username

        lines = ["当前会话订阅列表："]
        for uid in sorted(grouped.keys()):
            sub_types = "/".join(sorted(grouped[uid]))
            lines.append(f"- {names.get(uid, uid)} | UID={uid} | type={sub_types}")
        return "\n".join(lines)

    # --- 工具方法 ---

    async def _cleanup_temp_files(self):
        """定期清理扫描登录用的临时二维码"""
        while True:
            try:
                now = time.time()
                for f in self.temp_dir.iterdir():
                    if f.is_file() and now - f.stat().st_mtime > 3600:
                        os.remove(f)
            except Exception as exc:
                logger.warning(f"临时文件清理失败: {exc}")
            await asyncio.sleep(1800)

    async def _handle_new_post(self, platform: str, target_id: str, msgs: list):
        """处理来自调度器的新动态/直播推送"""
        from astrbot.api import logger
        from astrbot.api.event import MessageChain

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
