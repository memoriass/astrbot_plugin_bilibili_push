import asyncio

from ..core.compat import model_dump, type_validate_python
from ..database.db_manager import Subscription
from ..utils.logger import logger
from .subscription_group import group_subscriptions


class LiveSubscriptionChecker:
    def __init__(
        self,
        db,
        platform,
        dispatcher,
        push_on_startup=False,
        star=None,
        request_delay_sec: float = 0.8,
        batch_size: int = 50,
    ):
        self.db = db
        self.platform = platform
        self.dispatcher = dispatcher
        self.push_on_startup = push_on_startup
        self.star = star
        self.request_delay_sec = max(0.0, float(request_delay_sec))
        self.batch_size = max(1, int(batch_size))
        self.status_cache: dict[str, object] = {}
        self.cache_loaded = False
        self.is_first_check = True

    async def check(self, subs: list[Subscription]):
        await self._load_status_cache(subs)
        current_is_first = self.is_first_check
        sub_units = group_subscriptions(subs)
        batches = list(self._chunks(sub_units))

        for index, batch in enumerate(batches):
            try:
                statuses = await self.platform.batch_get_status([
                    sub_unit.sub_target for sub_unit in batch
                ])
                for sub_unit, new_status in zip(batch, statuses):
                    await self._handle_status(sub_unit, new_status, current_is_first)
            except Exception as exc:
                logger.error(f"直播批量检查失败: {exc}")
            if index < len(batches) - 1:
                await self._pause_between_requests()

        self.is_first_check = False

    async def manual_check(self, target_id: str) -> int:
        subs = self.db.get_enabled_subscriptions(target_id)
        live_subs = [sub for sub in subs if sub.sub_type == "live"]
        logger.info(f"手动检查开始 | Target: {target_id} | LiveSubs: {len(live_subs)}")
        return await self._manual_check_subs(live_subs)

    async def manual_check_all(self) -> tuple[int, int]:
        live_subs = [
            sub
            for sub in self.db.get_enabled_subscriptions()
            if sub.sub_type == "live"
        ]
        targets = {sub.target_id for sub in live_subs}
        pushed = await self._manual_check_subs(live_subs)
        return len(targets), pushed

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

    async def _handle_status(self, sub_unit, new_status, current_is_first: bool):
        uid = sub_unit.sub_target
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
            await self.star.put_kv_data(f"live_status_{uid}", model_dump(new_status))

    async def _manual_check_subs(self, live_subs: list[Subscription]) -> int:
        count = 0
        sub_units = group_subscriptions(live_subs)
        batches = list(self._chunks(sub_units))
        for index, batch in enumerate(batches):
            try:
                statuses = await self.platform.batch_get_status([
                    sub_unit.sub_target for sub_unit in batch
                ])
                for sub_unit, new_status in zip(batch, statuses):
                    uid = sub_unit.sub_target
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
                logger.error(f"手动直播批量检查失败: {exc}")
            if index < len(batches) - 1:
                await self._pause_between_requests()
        return count

    def _chunks(self, items):
        for index in range(0, len(items), self.batch_size):
            yield items[index:index + self.batch_size]

    async def _pause_between_requests(self):
        if self.request_delay_sec > 0:
            await asyncio.sleep(self.request_delay_sec)
