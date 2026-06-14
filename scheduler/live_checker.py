from ..core.compat import model_dump, type_validate_python
from ..database.db_manager import Subscription
from ..utils.logger import logger
from .subscription_group import group_subscriptions


class LiveSubscriptionChecker:
    def __init__(self, db, platform, dispatcher, push_on_startup=False, star=None):
        self.db = db
        self.platform = platform
        self.dispatcher = dispatcher
        self.push_on_startup = push_on_startup
        self.star = star
        self.status_cache: dict[str, object] = {}
        self.cache_loaded = False
        self.is_first_check = True

    async def check(self, subs: list[Subscription]):
        await self._load_status_cache(subs)
        current_is_first = self.is_first_check

        for sub_unit in group_subscriptions(subs):
            uid = sub_unit.sub_target
            try:
                new_status = await self.platform.get_status(uid)
                posts = self._build_posts(uid, new_status, current_is_first)
                if posts:
                    parsed_posts = []
                    for raw in posts:
                        parsed_post = await self.platform.parse(raw)
                        logger.info(f"  已解析直播 Post: {parsed_post.title}")
                        parsed_posts.append(parsed_post)
                    await self.dispatcher.dispatch(
                        self.platform.platform_name,
                        parsed_posts,
                        sub_unit.user_sub_infos,
                    )
                else:
                    logger.debug(
                        f"直播状态无需推送 [UID:{uid}] (LiveStatus:{new_status.live_status})"
                    )

                self.status_cache[uid] = new_status
                if self.star:
                    await self.star.put_kv_data(
                        f"live_status_{uid}", model_dump(new_status)
                    )
            except Exception as exc:
                logger.error(f"直播检查失败 {uid}: {exc}")

        self.is_first_check = False

    async def manual_check(self, target_id: str) -> int:
        subs = self.db.get_enabled_subscriptions(target_id)
        live_subs = [sub for sub in subs if sub.sub_type == "live"]
        logger.info(f"手动检查开始 | Target: {target_id} | LiveSubs: {len(live_subs)}")
        count = 0

        for sub_unit in group_subscriptions(live_subs):
            uid = sub_unit.sub_target
            try:
                new_status = await self.platform.get_status(uid)
                logger.info(
                    f"手动检查 UID: {uid}, 状态: {new_status.live_status}, 标题: {new_status.title}"
                )
                if new_status.live_status != 1:
                    continue
                raw_post = self.platform._gen_current_status(new_status, 1)
                parsed_post = await self.platform.parse(raw_post)
                await self.dispatcher.dispatch(
                    self.platform.platform_name,
                    [parsed_post],
                    sub_unit.user_sub_infos,
                )
                count += 1
            except Exception as exc:
                logger.error(f"手动检查失败 {uid}: {exc}")
        return count

    async def _load_status_cache(self, subs: list[Subscription]):
        if self.cache_loaded:
            return
        if self.star:
            try:
                for sub_unit in group_subscriptions(subs):
                    uid = sub_unit.sub_target
                    raw_data = await self.star.get_kv_data(f"live_status_{uid}", None)
                    if raw_data:
                        try:
                            self.status_cache[uid] = type_validate_python(
                                self.platform.Info, raw_data
                            )
                        except Exception as exc:
                            logger.warning(f"恢复直播状态缓存失败 {uid}: {exc}")
            except Exception as exc:
                logger.warning(f"加载直播状态缓存出错: {exc}")
        self.cache_loaded = True

    def _build_posts(self, uid: str, new_status, current_is_first: bool):
        old_status = self.status_cache.get(uid)
        posts = []

        if old_status:
            posts = self.platform.compare_status(uid, old_status, new_status)
        elif new_status.live_status == 1:
            posts = [self.platform._gen_current_status(new_status, 1)]

        if (
            current_is_first
            and self.push_on_startup
            and new_status.live_status == 1
            and not posts
        ):
            posts = [self.platform._gen_current_status(new_status, 1)]

        if posts:
            logger.info(
                f"直播状态更新 [UID:{uid}] - 准备分发推送消息 (状态: {new_status.live_status})"
            )
        return posts
