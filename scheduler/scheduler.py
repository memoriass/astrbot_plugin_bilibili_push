"""调度器模块"""

import asyncio
from collections.abc import Awaitable, Callable

from ..core.types import Category, MessageSegment, SubUnit, Tag, UserSubInfo
from ..logger import logger
from ..platform.bilibili.bilibili_dynamic import BilibiliDynamic
from ..platform.bilibili.bilibili_live import BilibiliLive
from ..sub_manager import DBManager, Subscription
from ..theme.dynamic_card import DynamicCardTheme
from ..theme.movie_card import MovieCardTheme
from ..theme.renderer import BrowserManager


class BilibiliScheduler:
    def __init__(
        self,
        db: DBManager,
        check_interval: int = 30,
        push_on_startup: bool = False,
        render_type: str = "image",
        image_template: str = "dynamic_card",
        on_new_post: Callable[[str, str, list[MessageSegment]], Awaitable[None]]
        | None = None,
        star: "Star" = None,
    ):
        self.db = db
        self.check_interval = check_interval
        self.push_on_startup = push_on_startup
        self.render_type = render_type
        self.image_template = image_template
        self.on_new_post = on_new_post
        self.star = star

        self.bili_platform = BilibiliDynamic()
        self.live_platform = BilibiliLive()

        self.themes = {
            "dynamic_card": DynamicCardTheme(),
            "movie_card": MovieCardTheme(),
        }

        self.running = False
        self.task: asyncio.Task | None = None
        self.seen_posts: dict[str, set[str]] = {}  # uid -> set of post ids
        self.live_status_cache: dict[str, Any] = {}  # uid -> status info
        self._live_cache_loaded = False

    async def start(self):
        if self.running:
            return
        await BrowserManager.init()
        self.running = True
        self.task = asyncio.create_task(self._run_loop())
        logger.info(f"Bilibili 调度器启动，间隔 {self.check_interval}s")

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
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
                        # 假设整个 cached map 存为一个大的 dict 可能太大，或者按 uid 存
                        # 这里为了简单，先按 uid 存取，或加载所有订阅的
                        # 考虑到 KV 接口，我们可以按 uid_live_status 来存
                        for sub_unit in self._group_subs(live_subs):
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

            for sub_unit in self._group_subs(live_subs):
                uid = sub_unit.sub_target
                try:
                    new_status = await self.live_platform.get_status(uid)
                    old_status = self.live_status_cache.get(uid)

                    should_push = False

                    if old_status:
                        # 有缓存，对比状态
                        posts = self.live_platform.compare_status(
                            uid, old_status, new_status
                        )
                        if posts:
                            should_push = True
                    else:
                        # 无缓存（首次运行）
                        # 此时 old_status 仍为 None，不推送，仅作为基准
                        if self.push_on_startup and new_status.live_status == 1:
                            # 模拟一个关播的旧状态，触发 TURN_ON
                            fake_old = self.live_platform._gen_empty_info(int(uid))
                            posts = self.live_platform.compare_status(
                                uid, fake_old, new_status
                            )
                            if posts:
                                should_push = True

                    if should_push:
                        # 有状态变更，需要发送
                        # compare_status 返回的是 RawPost (Info)，需要 parse
                        parsed_posts = []
                        for raw in posts:
                            parsed_posts.append(await self.live_platform.parse(raw))

                        await self._dispatch_posts(
                            self.live_platform.platform_name,
                            parsed_posts,
                            sub_unit.user_sub_infos,
                        )

                    # 更新缓存 (内存 + KV)
                    self.live_status_cache[uid] = new_status
                    if self.star:
                        # Pydantic 转 dict 存 KV
                        await self.star.put_kv_data(
                            f"live_status_{uid}", new_status.model_dump()
                        )

                except Exception as e:
                    logger.error(f"直播检查失败 {uid}: {e}")

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
                    if (
                        self.bili_platform.get_category(post)
                        not in user_info.categories
                    ):
                        continue

                try:
                    logger.debug(f"准备推送: {post.title} -> {target_id}")
                    theme = self.themes["dynamic_card"]
                    if self.image_template == "movie_card":
                        theme = self.themes["movie_card"]

                    is_supported = await theme.is_support_render(post)
                    logger.debug(
                        f"主题 {type(theme).__name__} 支持渲染: {is_supported}"
                    )

                    if not is_supported:
                        logger.warning("主题不支持渲染该类型的推文，跳过")
                        continue

                    msgs = await theme.render(post)
                    logger.debug(f"渲染完成，消息段数量: {len(msgs)}")

                    if self.on_new_post:
                        await self.on_new_post(platform_name, target_id, msgs)
                except Exception as e:
                    logger.error(f"推送失败: {e}")
