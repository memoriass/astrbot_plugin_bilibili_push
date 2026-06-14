"""调度器模块"""

import asyncio
from collections.abc import Awaitable, Callable

from ..core.types import MessageSegment
from ..database.db_manager import DatabaseManager, Subscription
from ..dynamic.bilibili import BilibiliDynamic
from ..live.bilibili import BilibiliLive
from ..utils.html_renderer import BrowserManager, HtmlRenderer
from ..utils.logger import logger
from ..utils.renderers.dynamic_card import DynamicCardTheme
from ..utils.renderers.movie_card import MovieCardTheme
from ..utils.resource import get_template_path
from .dispatcher import PostDispatcher
from .dynamic_checker import DynamicSubscriptionChecker
from .live_checker import LiveSubscriptionChecker
from .subscription_group import group_subscriptions


class BilibiliScheduler:
    def __init__(
        self,
        db: DatabaseManager,
        check_interval: int = 30,
        push_on_startup: bool = False,
        render_type: str = "image",
        on_new_post: Callable[[str, str, list[MessageSegment]], Awaitable[None]]
        | None = None,
        star: "Star" = None,
    ):
        self.db = db
        self.check_interval = check_interval
        self.push_on_startup = push_on_startup
        self.render_type = render_type
        self.on_new_post = on_new_post
        self.star = star

        self.bili_platform = BilibiliDynamic()
        self.live_platform = BilibiliLive()
        self.themes = self._build_themes()
        self.dispatcher = PostDispatcher(self.themes, self.on_new_post)
        self.dynamic_checker = DynamicSubscriptionChecker(
            self.bili_platform,
            self.dispatcher,
            star=self.star,
        )
        self.live_checker = LiveSubscriptionChecker(
            db=self.db,
            platform=self.live_platform,
            dispatcher=self.dispatcher,
            push_on_startup=self.push_on_startup,
            star=self.star,
        )

        self.running = False
        self.task: asyncio.Task | None = None

    def _build_themes(self):
        renderer = HtmlRenderer(get_template_path())
        return {
            "dynamic_card": DynamicCardTheme(renderer),
            "movie_card": MovieCardTheme(renderer),
            "dynamic_movie_card": MovieCardTheme(
                renderer, template_name="dynamic_movie_card.html.jinja"
            ),
        }

    async def start(self):
        if self.running:
            return
        await BrowserManager.init()
        self.running = True
        self.task = asyncio.create_task(self._run_loop())
        logger.info(f"Bilibili 调度器启动，间隔 {self.check_interval}s")

    async def terminate(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        await BrowserManager.close()
        logger.info("Bilibili 调度器已终止")

    async def _run_loop(self):
        while self.running:
            try:
                await self._check_all()
            except Exception as exc:
                logger.error(f"调度循环错误: {exc}", exc_info=True)
            await asyncio.sleep(self.check_interval)

    async def _check_all(self):
        subs = self.db.get_enabled_subscriptions()
        dyn_subs = [sub for sub in subs if sub.sub_type == "dynamic"]
        live_subs = [sub for sub in subs if sub.sub_type == "live"]

        if dyn_subs:
            await self.dynamic_checker.check(dyn_subs)
        if live_subs:
            await self.live_checker.check(live_subs)

    async def manual_live_check(self, target_id: str) -> int:
        return await self.live_checker.manual_check(target_id)

    def _group_subs(self, subs: list[Subscription]):
        return group_subscriptions(subs)

    async def _dispatch_posts(self, platform_name, posts, user_infos):
        await self.dispatcher.dispatch(platform_name, posts, user_infos)
