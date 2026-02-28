"""调度器模块"""

import asyncio
from collections.abc import Awaitable, Callable

from ..core.types import Category, MessageSegment, SubUnit, Tag, UserSubInfo
from ..utils.logger import logger
from ..dynamic.bilibili import BilibiliDynamic
from ..live.bilibili import BilibiliLive
from ..database.db_manager import DatabaseManager, Subscription
from ..utils.renderers.dynamic_card import DynamicCardTheme
from ..utils.renderers.movie_card import MovieCardTheme
from ..utils.html_renderer import BrowserManager


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

        from ..utils.html_renderer import HtmlRenderer
        from ..utils.resource import get_template_path
        renderer = HtmlRenderer(get_template_path())
        self.themes = {
            "dynamic_card": DynamicCardTheme(renderer),
            "movie_card": MovieCardTheme(renderer),
            "dynamic_movie_card": MovieCardTheme(renderer, template_name="dynamic_movie_card.html.jinja"),
        }

        self.running = False
        self.task: asyncio.Task | None = None
        self.seen_posts: dict[str, set[str]] = {}  # uid -> set of post ids
        self.live_status_cache: dict[str, Any] = {}  # uid -> status info
        self._live_cache_loaded = False
        self._is_first_check = True

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
            except Exception as e:
                logger.error(f"调度循环错误: {e}", exc_info=True)
            await asyncio.sleep(self.check_interval)

    async def _check_all(self):
        subs = self.db.get_subscriptions()
        dyn_subs = [s for s in subs if s.sub_type == "dynamic"]
        live_subs = [s for s in subs if s.sub_type == "live"]

        if dyn_subs:
            for sub_unit in self._group_subs(dyn_subs):
                uid = sub_unit.sub_target
                try:
                    # 获取
                    posts = await self.bili_platform.fetch_new_post(sub_unit)

                    # 去重逻辑
                    if uid not in self.seen_posts:
                        # 尝试从 KV 加载
                        if self.star:
                            cached = await self.star.get_kv_data(
                                f"seen_posts_{uid}", []
                            )
                            if cached:
                                self.seen_posts[uid] = set(cached)

                    if uid not in self.seen_posts:
                        # 首次运行或无缓存，初始化缓存，不推送
                        self.seen_posts[uid] = {p.id for p in posts}
                        if self.star:
                            await self.star.put_kv_data(
                                f"seen_posts_{uid}", list(self.seen_posts[uid])
                            )
                        continue

                    new_posts = []
                    for post in posts:
                        if post.id not in self.seen_posts[uid]:
                            new_posts.append(post)
                            self.seen_posts[uid].add(post.id)

                    # 限制缓存大小
                    if len(self.seen_posts[uid]) > 100:
                        # 只保留最新的 100 个
                        self.seen_posts[uid] = {
                            p.id
                            for p in sorted(
                                posts, key=lambda x: x.timestamp, reverse=True
                            )[:100]
                        }

                    if new_posts and self.star:
                        # 更新 KV
                        await self.star.put_kv_data(
                            f"seen_posts_{uid}", list(self.seen_posts[uid])
                        )

                    if new_posts:
                        await self._dispatch_posts(
                            self.bili_platform.platform_name,
                            new_posts,
                            sub_unit.user_sub_infos,
                        )
                except Exception as e:
                    logger.error(f"动态检查失败 {sub_unit.sub_target}: {e}")

        if live_subs:
            # 直播状态管理
            # 尝试从 KV 加载一次直播状态缓存
            if not self._live_cache_loaded:
                if self.star:
                    try:
                        grouped_subs = self._group_subs(live_subs)
                        for sub_unit in grouped_subs:
                            uid = sub_unit.sub_target
                            raw_data = await self.star.get_kv_data(
                                f"live_status_{uid}", None
                            )
                            if raw_data:
                                # 恢复对象
                                from ..core.compat import type_validate_python
                                try:
                                    self.live_status_cache[uid] = type_validate_python(
                                        self.live_platform.Info, raw_data
                                    )
                                except Exception as e:
                                    logger.warning(f"恢复直播状态缓存失败 {uid}: {e}")
                    except Exception as e:
                        logger.warning(f"加载直播状态缓存出错: {e}")
                self._live_cache_loaded = True

            current_is_first = self._is_first_check # 记录本次循环是否为启动首次
            grouped_live_subs = self._group_subs(live_subs)
            for sub_unit in grouped_live_subs:
                uid = sub_unit.sub_target
                try:
                    new_status = await self.live_platform.get_status(uid)
                    old_status = self.live_status_cache.get(uid)

                    should_push = False
                    posts = []

                    if old_status:
                        # 有缓存，对比状态
                        posts = self.live_platform.compare_status(
                            uid, old_status, new_status
                        )
                        if posts:
                            should_push = True
                    else:
                        # 完全没有缓存（新添加，或KV里也没数据）
                        if new_status.live_status == 1:
                            # 既然是新号且正在直播，我们倾向于推送一次“直播中”
                            should_push = True
                            posts = [self.live_platform._gen_current_status(new_status, 1)]
                    
                    # 启动强推逻辑：如果有老缓存且状态没变(should_push=False)，但在启动时需要强推
                    if current_is_first and self.push_on_startup and new_status.live_status == 1:
                        if not should_push:
                            should_push = True
                            posts = [self.live_platform._gen_current_status(new_status, 1)]

                    if should_push:
                        logger.info(f"直播状态更新 [UID:{uid}] - 准备分发推送消息 (状态: {new_status.live_status})")
                        parsed_posts = []
                        for raw in posts:
                            parsed_post = await self.live_platform.parse(raw)
                            logger.info(f"  已解析直播 Post: {parsed_post.title}")
                            parsed_posts.append(parsed_post)

                        await self._dispatch_posts(
                            self.live_platform.platform_name,
                            parsed_posts,
                            sub_unit.user_sub_infos,
                        )
                    else:
                        logger.debug(f"直播状态无需推送 [UID:{uid}] (LiveStatus:{new_status.live_status})")

                    # 更新缓存
                    self.live_status_cache[uid] = new_status
                    if self.star:
                        await self.star.put_kv_data(
                            f"live_status_{uid}", new_status.model_dump()
                        )
                except Exception as e:
                    logger.error(f"直播检查失败 {uid}: {e}")

            self._is_first_check = False

    async def manual_live_check(self, target_id: str) -> int:
        """手动触发直播检测，返回触发推送的数量"""
        subs = self.db.get_subscriptions(target_id)
        live_subs = [s for s in subs if s.sub_type == "live"]
        logger.info(f"手动检查开始 | Target: {target_id} | LiveSubs: {len(live_subs)}")
        count = 0

        if not live_subs:
            return 0

        for sub_unit in self._group_subs(live_subs):
            uid = sub_unit.sub_target
            try:
                new_status = await self.live_platform.get_status(uid)
                logger.info(
                    f"手动检查 UID: {uid}, 状态: {new_status.live_status}, 标题: {new_status.title}"
                )
                # 如果正在直播 (live_status == 1)
                if new_status.live_status == 1:
                    # 模拟 Category 1 (开播提醒)
                    # 使用 _gen_current_status 生成 RawPost
                    raw_post = self.live_platform._gen_current_status(new_status, 1)
                    parsed_post = await self.live_platform.parse(raw_post)

                    await self._dispatch_posts(
                        self.live_platform.platform_name,
                        [parsed_post],
                        sub_unit.user_sub_infos,
                    )
                    count += 1
            except Exception as e:
                logger.error(f"手动检查失败 {uid}: {e}")
        return count

    def _group_subs(self, subs: list[Subscription]) -> list[SubUnit]:
        grouped = {}
        for sub in subs:
            if sub.uid not in grouped:
                grouped[sub.uid] = []
            grouped[sub.uid].append(sub)
        sub_units = []
        for uid, sub_list in grouped.items():
            user_sub_infos = []
            for sub in sub_list:
                user_sub_infos.append(
                    UserSubInfo(
                        user_id=sub.target_id,
                        categories=[Category(c) for c in sub.categories],
                        tags=[Tag(t) for t in sub.tags],
                    )
                )
            sub_units.append(SubUnit(sub_target=uid, user_sub_infos=user_sub_infos))
        return sub_units

    async def _dispatch_posts(self, platform_name, posts, user_infos):
        for user_info in user_infos:
            target_id = user_info.user_id
            for post in posts:
                # 过滤逻辑 (Category/Tag)
                # 直播消息特殊处理：不过滤，因为 Post 对象丢失了 Category 信息，且直播推送由 compare_status 控制
                if post.platform != "bilibili-live":
                    if post.category not in user_info.categories:
                        continue
                else:
                    # 直播过滤逻辑：1.开播 2.标题更新 3.下播
                    if post.category not in user_info.categories:
                        logger.info(f"  [DISCARD] 直播分类不匹配: Post.cat={post.category} not in UserInfo.cats={user_info.categories}")
                        continue

                try:
                    logger.info(f"  正在处理推送给 {target_id} | Platform: {post.platform} | Category: {post.category}")
                    
                    # 严格场景映射
                    if post.platform == "bilibili-live":
                        theme = self.themes["movie_card"]
                    else:
                        theme = self.themes["dynamic_movie_card"]

                    is_supported = await theme.is_support_render(post)
                    if not is_supported:
                        logger.warning(f"  主题 {type(theme).__name__} 不支持渲染该推文，跳过")
                        continue

                    if self.on_new_post:
                        logger.info(f"  使用主题 {type(theme).__name__} 开始渲染并调用推送回调...")
                        msgs = await theme.render(post)
                        await self.on_new_post(platform_name, target_id, msgs)
                        logger.info(f"  回调调用完成")
                    else:
                        logger.warning(f"  未配置推送回调 (on_new_post is None)，消息已丢弃")
                except Exception as e:
                    logger.error(f"推送失败: {e}")
