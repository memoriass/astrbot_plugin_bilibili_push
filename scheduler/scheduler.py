"""调度器模块"""
import asyncio
from typing import Callable, Awaitable

from ..logger import logger
from ..sub_manager import DBManager, Subscription
from ..core.types import SubUnit, UserSubInfo, Category, Tag, MessageSegment
from ..platform.bilibili.bilibili_dynamic import BilibiliDynamic
from ..platform.bilibili.bilibili_live import BilibiliLive
from ..theme.brief import BriefTheme
from ..theme.ceobe_canteen import CeobeCanteenTheme
from ..theme.renderer import BrowserManager

class BilibiliScheduler:
    def __init__(
        self,
        db: DBManager,
        check_interval: int = 30,
        on_new_post: Callable[[str, str, list[MessageSegment]], Awaitable[None]] | None = None,
        context: "Context" = None,
    ):
        self.db = db
        self.check_interval = check_interval
        self.on_new_post = on_new_post
        self.context = context
        
        self.bili_platform = BilibiliDynamic()
        self.live_platform = BilibiliLive()
        
        self.themes = {
            "brief": BriefTheme(),
            "ceobecanteen": CeobeCanteenTheme()
        }
        
        self.running = False
        self.task: asyncio.Task | None = None
        self.seen_posts: dict[str, set[str]] = {} # uid -> set of post ids
        
    async def start(self):
        if self.running: return
        await BrowserManager.init()
        self.running = True
        self.task = asyncio.create_task(self._run_loop())
        logger.info(f"Bilibili 调度器启动，间隔 {self.check_interval}s")
        
    async def stop(self):
        self.running = False
        if self.task: self.task.cancel()
        await BrowserManager.close()
    
    async def _run_loop(self):
        while self.running:
            try:
                await self._check_all()
            except Exception as e:
                logger.error(f"调度循环错误: {e}", exc_info=True)
            await asyncio.sleep(self.check_interval)
            
    async def _check_all(self):
        subs = self.db.get_subscriptions()
        dyn_subs = [s for s in subs if s.sub_type == 'dynamic']
        live_subs = [s for s in subs if s.sub_type == 'live']
        
        if dyn_subs:
            for sub_unit in self._group_subs(dyn_subs):
                uid = sub_unit.sub_target
                try:
                    # 获取
                    posts = await self.bili_platform.fetch_new_post(sub_unit)
                    
                    # 去重逻辑
                    if uid not in self.seen_posts:
                        # 尝试从 KV 加载
                        if self.context:
                            cached = await self.context.get_kv_data(f"seen_posts_{uid}", [])
                            if cached:
                                self.seen_posts[uid] = set(cached)
                        
                    if uid not in self.seen_posts:
                         # 首次运行或无缓存，初始化缓存，不推送
                         self.seen_posts[uid] = {p.id for p in posts}
                         if self.context:
                             await self.context.put_kv_data(f"seen_posts_{uid}", list(self.seen_posts[uid]))
                         continue
                        
                    new_posts = []
                    for post in posts:
                        if post.id not in self.seen_posts[uid]:
                            new_posts.append(post)
                            self.seen_posts[uid].add(post.id)
                    
                    # 限制缓存大小
                    if len(self.seen_posts[uid]) > 100:
                        # 只保留最新的 100 个
                        self.seen_posts[uid] = {p.id for p in sorted(posts, key=lambda x: x.timestamp, reverse=True)[:100]}

                    if new_posts and self.context:
                         # 更新 KV
                         await self.context.put_kv_data(f"seen_posts_{uid}", list(self.seen_posts[uid]))

                    if new_posts:
                        await self._dispatch_posts(
                            self.bili_platform.platform_name, 
                            new_posts, 
                            sub_unit.user_sub_infos
                        )
                except Exception as e:
                    logger.error(f"动态检查失败 {sub_unit.sub_target}: {e}")

        if live_subs:
             # 直播状态管理
             if not hasattr(self, "live_status_cache"):
                 self.live_status_cache = {}

             for sub_unit in self._group_subs(live_subs):
                 uid = sub_unit.sub_target
                 try:
                     new_status = await self.live_platform.get_status(uid)
                     old_status = self.live_status_cache.get(uid)
                     
                     if old_status:
                         # 对比状态
                         posts = self.live_platform.compare_status(uid, old_status, new_status)
                         if posts:
                             # 有状态变更，需要发送
                             # compare_status 返回的是 RawPost (Info)，需要 parse
                             parsed_posts = []
                             for raw in posts:
                                 parsed_posts.append(await self.live_platform.parse(raw))
                                 
                             await self._dispatch_posts(
                                self.live_platform.platform_name,
                                parsed_posts,
                                sub_unit.user_sub_infos
                             )
                     
                     # 更新缓存
                     self.live_status_cache[uid] = new_status
                     
                 except Exception as e:
                     logger.error(f"直播检查失败 {uid}: {e}")

    def _group_subs(self, subs: list[Subscription]) -> list[SubUnit]:
        grouped = {}
        for sub in subs:
            if sub.uid not in grouped: grouped[sub.uid] = []
            grouped[sub.uid].append(sub)
        sub_units = []
        for uid, sub_list in grouped.items():
            user_sub_infos = []
            for sub in sub_list:
                user_sub_infos.append(UserSubInfo(
                    user_id=sub.target_id,
                    categories=[Category(c) for c in sub.categories],
                    tags=[Tag(t) for t in sub.tags]
                ))
            sub_units.append(SubUnit(sub_target=uid, user_sub_infos=user_sub_infos))
        return sub_units
        
    async def _dispatch_posts(self, platform_name, posts, user_infos):
        for user_info in user_infos:
            target_id = user_info.user_id
            for post in posts:
                # 过滤逻辑 (Category/Tag)
                if self.bili_platform.get_category(post) not in user_info.categories:
                    continue
                # Tag 过滤暂略
                
                try:
                    theme = self.themes["ceobecanteen"]
                    # 检查是否支持
                    if not await theme.is_support_render(post):
                        theme = self.themes["brief"]
                        
                    msgs = await theme.render(post)
                    if self.on_new_post:
                        await self.on_new_post(platform_name, target_id, msgs)
                except Exception as e:
                    logger.error(f"推送失败: {e}")
